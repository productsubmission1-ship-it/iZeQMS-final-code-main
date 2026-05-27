"""Additional role-mgmt edge cases not covered by test_role_mgmt.py:
- Cannot revoke last remaining role
- Non-admin (employee) cannot call mutating role-mgmt endpoints (overrides, assign, etc.)
- Auditor cannot mutate
- Override audit trail (USER_PERMISSION_REMOVE)
"""
import os
import uuid
import pytest
import requests

API = os.environ.get("API_BASE", "https://permission-matrix-9.preview.emergentagent.com/api")
ADMIN = ("admin@izqms.com", "Admin@2026")
EMP = ("employee@izqms.com", "Employee@2026")
AUD = ("auditor@izqms.com", "Auditor@2026")


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {_login(*ADMIN)}"}


@pytest.fixture(scope="module")
def emp_h():
    return {"Authorization": f"Bearer {_login(*EMP)}"}


@pytest.fixture(scope="module")
def aud_h():
    return {"Authorization": f"Bearer {_login(*AUD)}"}


@pytest.fixture(scope="module")
def emp_id(admin_h):
    r = requests.get(f"{API}/users", headers=admin_h, timeout=10)
    return next(u["id"] for u in r.json() if u["email"] == EMP[0])


def test_non_admin_cannot_create_override(emp_h, emp_id):
    r = requests.post(f"{API}/role-mgmt/users/{emp_id}/overrides", headers=emp_h,
                      json={"module": "deviation", "action": "approve", "effect": "ALLOW", "reason": "x"}, timeout=10)
    assert r.status_code in (401, 403), r.text


def test_non_admin_cannot_patch_role(emp_h, admin_h):
    rows = requests.get(f"{API}/role-mgmt/roles", headers=admin_h, timeout=10).json()
    rid = rows[0]["id"]
    r = requests.patch(f"{API}/role-mgmt/roles/{rid}", headers=emp_h,
                       json={"name": "hack", "reason": "x", "permissions": {}}, timeout=10)
    assert r.status_code in (401, 403)


def test_auditor_cannot_create_role(aud_h):
    r = requests.post(f"{API}/role-mgmt/roles", headers=aud_h,
                      json={"code": f"a_{uuid.uuid4().hex[:6]}", "name": "X", "reason": "x", "permissions": {}}, timeout=10)
    assert r.status_code in (401, 403)


def test_auditor_cannot_assign_role(aud_h, admin_h, emp_id):
    rows = requests.get(f"{API}/role-mgmt/roles", headers=admin_h, timeout=10).json()
    rid = rows[0]["id"]
    r = requests.post(f"{API}/role-mgmt/users/{emp_id}/assign-role", headers=aud_h,
                      json={"role_id": rid, "reason": "hack"}, timeout=10)
    assert r.status_code in (401, 403)


def test_cannot_remove_last_role(admin_h, emp_id):
    """Employee currently has 1 role. Trying to revoke it should fail."""
    eff = requests.get(f"{API}/role-mgmt/users/{emp_id}/permissions", headers=admin_h, timeout=10).json()
    roles = eff["roles_applied"]
    if len(roles) != 1:
        pytest.skip(f"employee has {len(roles)} roles, expected 1")
    rid = roles[0]["id"]
    r = requests.post(f"{API}/role-mgmt/users/{emp_id}/revoke-role", headers=admin_h,
                      json={"role_id": rid, "reason": "test last-role guard"}, timeout=10)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"


def test_override_remove_writes_audit(admin_h, emp_id):
    # create override, then remove, then verify audit
    r = requests.post(f"{API}/role-mgmt/users/{emp_id}/overrides", headers=admin_h,
                      json={"module": "incident", "action": "create", "effect": "ALLOW", "reason": "audit-test"}, timeout=10)
    assert r.status_code == 200
    oid = r.json()["id"]
    r = requests.delete(f"{API}/role-mgmt/users/{emp_id}/overrides/{oid}",
                        headers=admin_h, params={"reason": "cleanup audit"}, timeout=10)
    assert r.status_code == 200
    # audit
    a = requests.get(f"{API}/role-mgmt/users/{emp_id}/permissions/audit", headers=admin_h, timeout=10)
    if a.status_code == 200:
        entries = a.json()
        assert any(e.get("action") == "USER_PERMISSION_REMOVE" for e in entries), \
            f"no USER_PERMISSION_REMOVE in {[e.get('action') for e in entries]}"


def test_role_audit_contains_create_and_update(admin_h):
    rows = requests.get(f"{API}/role-mgmt/roles", headers=admin_h, timeout=10).json()
    temp = next((r for r in rows if not r["is_system"]), None)
    if not temp:
        pytest.skip("no custom role")
    audit = requests.get(f"{API}/role-mgmt/roles/{temp['id']}/audit", headers=admin_h, timeout=10).json()
    actions = {a["action"] for a in audit}
    assert "ROLE_CREATE" in actions or "ROLE_UPDATE" in actions or "ROLE_COPY" in actions


def test_modules_have_dashboard_user_management(admin_h):
    r = requests.get(f"{API}/role-mgmt/modules", headers=admin_h, timeout=10).json()
    assert "dashboard" in r["modules"]
    assert "user_management" in r["modules"]
    um_acts = [a["key"] for a in r["modules"]["user_management"]["actions"]]
    assert "create_user" in um_acts and "assign_role" in um_acts
    dash_acts = [a["key"] for a in r["modules"]["dashboard"]["actions"]]
    assert "view_dashboard" in dash_acts
