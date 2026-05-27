"""
Comprehensive test suite for the dynamic Role Management module.
Covers:
- Module catalog
- Role CRUD (create / read / update / copy / activate / deactivate)
- System role guardrails
- User-specific overrides (additional / restricted / temporary)
- Effective permission computation
- Role audit trail
- Role assignment & revocation
"""
import os
import sys
import time
import uuid

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Allow PUBLIC URL via env, default to internal port 8001
API = os.environ.get("API_BASE", "http://localhost:8001/api")

ADMIN_EMAIL = "admin@izqms.com"
ADMIN_PASSWORD = "Admin@2026"
EMPLOYEE_EMAIL = "employee@izqms.com"


def _login(email=ADMIN_EMAIL, pw=ADMIN_PASSWORD):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login()}"}


@pytest.fixture(scope="module")
def employee_id(admin_headers):
    r = requests.get(f"{API}/users", headers=admin_headers, timeout=10)
    r.raise_for_status()
    for u in r.json():
        if u["email"] == EMPLOYEE_EMAIL:
            return u["id"]
    pytest.skip("Employee user not seeded")


def test_module_catalog(admin_headers):
    r = requests.get(f"{API}/role-mgmt/modules", headers=admin_headers, timeout=10)
    r.raise_for_status()
    data = r.json()
    assert "deviation" in data["modules"]
    assert "capa" in data["modules"]
    assert "user_management" in data["modules"]
    assert "role_management" in data["modules"]
    # Spot check action keys
    dev_actions = [a["key"] for a in data["modules"]["deviation"]["actions"]]
    assert "create" in dev_actions
    assert "approve" in dev_actions
    assert "export_pdf" in dev_actions


def test_seed_roles_present(admin_headers):
    r = requests.get(f"{API}/role-mgmt/roles", headers=admin_headers, timeout=10)
    r.raise_for_status()
    codes = {row["code"] for row in r.json()}
    assert {"super_admin", "admin", "qa_manager", "qa_reviewer",
            "department_manager", "employee_operator", "auditor"}.issubset(codes)


def test_super_admin_has_all_permissions(admin_headers):
    rows = requests.get(f"{API}/role-mgmt/roles", headers=admin_headers, timeout=10).json()
    sa = next(r for r in rows if r["code"] == "super_admin")
    for m, acts in sa["permissions"].items():
        for a, v in acts.items():
            assert v is True, f"super_admin should have {m}.{a}=True"


def test_create_custom_role(admin_headers):
    code = f"qa_temp_{uuid.uuid4().hex[:6]}"
    body = {
        "code": code,
        "name": "Test QA Temp Role",
        "description": "Created by test suite",
        "department_access": ["Quality Assurance"],
        "module_access": ["deviation", "capa"],
        "workflow_access": False,
        "approval_access": False,
        "review_access": True,
        "electronic_signature_access": True,
        "report_access": False,
        "audit_trail_access": False,
        "permissions": {
            "deviation": {"create": True, "edit": True, "review": True},
            "capa": {"create": True, "review": True},
        },
        "reason": "Pytest fixture",
    }
    r = requests.post(f"{API}/role-mgmt/roles", headers=admin_headers, json=body, timeout=10)
    assert r.status_code == 200, r.text
    role = r.json()
    assert role["code"] == code
    assert role["is_system"] is False
    assert role["permissions"]["deviation"]["create"] is True
    assert role["permissions"]["deviation"]["approve"] is False  # not granted
    # Duplicate code should fail
    r2 = requests.post(f"{API}/role-mgmt/roles", headers=admin_headers, json=body, timeout=10)
    assert r2.status_code == 400


def test_update_role(admin_headers):
    # Find the temp role
    rows = requests.get(f"{API}/role-mgmt/roles", headers=admin_headers, timeout=10).json()
    temp = next((r for r in rows if r["code"].startswith("qa_temp_")), None)
    if not temp:
        pytest.skip("No temp role to update")
    body = {
        "name": "Updated Temp Role",
        "permissions": {
            **temp["permissions"],
            "deviation": {**temp["permissions"]["deviation"], "approve": True},
        },
        "reason": "Adding approve right",
    }
    r = requests.patch(f"{API}/role-mgmt/roles/{temp['id']}", headers=admin_headers, json=body, timeout=10)
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["name"] == "Updated Temp Role"
    assert updated["permissions"]["deviation"]["approve"] is True
    # Audit trail
    audit = requests.get(f"{API}/role-mgmt/roles/{temp['id']}/audit", headers=admin_headers, timeout=10).json()
    assert any(a["action"] == "ROLE_UPDATE" for a in audit)


def test_copy_role(admin_headers):
    rows = requests.get(f"{API}/role-mgmt/roles", headers=admin_headers, timeout=10).json()
    src = next(r for r in rows if r["code"] == "qa_reviewer")
    new_code = f"qa_rev_copy_{uuid.uuid4().hex[:6]}"
    r = requests.post(
        f"{API}/role-mgmt/roles/{src['id']}/copy",
        headers=admin_headers,
        json={"new_code": new_code, "new_name": "QA Reviewer Copy", "reason": "Pilot"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    copy = r.json()
    assert copy["code"] == new_code
    assert copy["is_system"] is False
    assert copy["copied_from"] == src["id"]
    # Permissions should match source
    assert copy["permissions"] == src["permissions"]


def test_deactivate_activate_role(admin_headers):
    rows = requests.get(f"{API}/role-mgmt/roles", headers=admin_headers, timeout=10).json()
    custom = next((r for r in rows if not r["is_system"]), None)
    if not custom:
        pytest.skip("No custom role")
    r = requests.post(f"{API}/role-mgmt/roles/{custom['id']}/activate",
                      headers=admin_headers, json={"active": False, "reason": "Test deactivate"}, timeout=10)
    assert r.status_code == 200
    assert r.json()["active"] is False
    r = requests.post(f"{API}/role-mgmt/roles/{custom['id']}/activate",
                      headers=admin_headers, json={"active": True, "reason": "Test reactivate"}, timeout=10)
    assert r.status_code == 200
    assert r.json()["active"] is True


def test_system_roles_cannot_be_deactivated(admin_headers):
    rows = requests.get(f"{API}/role-mgmt/roles", headers=admin_headers, timeout=10).json()
    sa = next(r for r in rows if r["code"] == "super_admin")
    r = requests.post(f"{API}/role-mgmt/roles/{sa['id']}/activate",
                      headers=admin_headers, json={"active": False, "reason": "should fail"}, timeout=10)
    assert r.status_code == 400


def test_user_effective_permissions(admin_headers, employee_id):
    r = requests.get(f"{API}/role-mgmt/users/{employee_id}/permissions", headers=admin_headers, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["email"] == EMPLOYEE_EMAIL
    # Employee has employee_operator role → deviation.create should be true, approve false
    assert data["permissions"]["deviation"]["create"] is True
    assert data["permissions"]["deviation"]["approve"] is False


def test_add_additional_override(admin_headers, employee_id):
    # Grant employee deviation.approve as ADDITIONAL
    r = requests.post(
        f"{API}/role-mgmt/users/{employee_id}/overrides",
        headers=admin_headers,
        json={
            "module": "deviation", "action": "approve",
            "effect": "ALLOW",
            "reason": "Test additional access",
        }, timeout=10,
    )
    assert r.status_code == 200, r.text
    ov = r.json()
    assert ov["kind"] == "ADDITIONAL"
    assert ov["effect"] == "ALLOW"

    # Effective should now include approve
    eff = requests.get(f"{API}/role-mgmt/users/{employee_id}/permissions",
                       headers=admin_headers, timeout=10).json()
    assert eff["permissions"]["deviation"]["approve"] is True
    assert "approve" in eff["additional"]["deviation"]


def test_add_restricted_override(admin_headers, employee_id):
    # Restrict deviation.create
    r = requests.post(
        f"{API}/role-mgmt/users/{employee_id}/overrides",
        headers=admin_headers,
        json={
            "module": "deviation", "action": "create",
            "effect": "DENY",
            "reason": "Test restricted access",
        }, timeout=10,
    )
    assert r.status_code == 200
    eff = requests.get(f"{API}/role-mgmt/users/{employee_id}/permissions",
                       headers=admin_headers, timeout=10).json()
    # Effective deviation.create should be False (deny wins)
    assert eff["permissions"]["deviation"]["create"] is False
    assert "create" in eff["restricted"]["deviation"]


def test_temporary_override(admin_headers, employee_id):
    from datetime import datetime, timezone, timedelta
    expires = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()
    r = requests.post(
        f"{API}/role-mgmt/users/{employee_id}/overrides",
        headers=admin_headers,
        json={
            "module": "capa", "action": "approve",
            "effect": "ALLOW",
            "expires_at": expires,
            "reason": "Temp approval during audit",
        }, timeout=10,
    )
    assert r.status_code == 200
    ov = r.json()
    assert ov["kind"] == "TEMPORARY"
    # Should grant immediately
    eff = requests.get(f"{API}/role-mgmt/users/{employee_id}/permissions",
                       headers=admin_headers, timeout=10).json()
    assert eff["permissions"]["capa"]["approve"] is True
    # Wait for expiry
    time.sleep(3)
    eff2 = requests.get(f"{API}/role-mgmt/users/{employee_id}/permissions",
                        headers=admin_headers, timeout=10).json()
    assert eff2["permissions"]["capa"]["approve"] is False


def test_remove_override(admin_headers, employee_id):
    overrides = requests.get(f"{API}/role-mgmt/users/{employee_id}/overrides",
                             headers=admin_headers, timeout=10).json()
    # Delete ALL overrides created by this test module so the suite is fully re-runnable.
    for target in overrides:
        r = requests.delete(
            f"{API}/role-mgmt/users/{employee_id}/overrides/{target['id']}",
            headers=admin_headers, params={"reason": "Test cleanup"}, timeout=10,
        )
        assert r.status_code == 200
    # Confirm overrides list is now empty
    leftover = requests.get(f"{API}/role-mgmt/users/{employee_id}/overrides",
                            headers=admin_headers, timeout=10).json()
    assert leftover == []


def test_assign_and_revoke_dynamic_role(admin_headers, employee_id):
    # Find a custom role
    rows = requests.get(f"{API}/role-mgmt/roles", headers=admin_headers, timeout=10).json()
    custom = next((r for r in rows if not r["is_system"] and r["active"]), None)
    if not custom:
        pytest.skip("No custom role available")
    # Assign
    r = requests.post(
        f"{API}/role-mgmt/users/{employee_id}/assign-role",
        headers=admin_headers,
        json={"role_id": custom["id"], "reason": "Pilot"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    # Effective permissions should now include perms from that role
    eff = requests.get(f"{API}/role-mgmt/users/{employee_id}/permissions",
                       headers=admin_headers, timeout=10).json()
    role_ids = [r["id"] for r in eff["roles_applied"]]
    assert custom["id"] in role_ids
    # Revoke
    r = requests.post(
        f"{API}/role-mgmt/users/{employee_id}/revoke-role",
        headers=admin_headers,
        json={"role_id": custom["id"], "reason": "End pilot"},
        timeout=10,
    )
    assert r.status_code == 200


def test_invalid_override_module_action(admin_headers, employee_id):
    r = requests.post(
        f"{API}/role-mgmt/users/{employee_id}/overrides",
        headers=admin_headers,
        json={"module": "doesnotexist", "action": "foo",
              "effect": "ALLOW", "reason": "bad"},
        timeout=10,
    )
    assert r.status_code == 400


def test_non_admin_cannot_create_role():
    # Employee account
    tok = _login(EMPLOYEE_EMAIL, "Employee@2026")
    h = {"Authorization": f"Bearer {tok}"}
    r = requests.post(f"{API}/role-mgmt/roles", headers=h,
                      json={"code": "test_x", "name": "X", "reason": "x", "permissions": {}}, timeout=10)
    assert r.status_code in (401, 403)
