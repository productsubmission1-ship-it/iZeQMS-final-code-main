"""Iteration 6 regression tests:
1. Legacy QMS DEVIATION workflow (admin) — create, REVIEW, APPROVE, CLOSE
2. QA Manager can REVIEW + APPROVE (canonical role still works)
3. RESTRICTED DENY override on qa_manager blocks APPROVE (403)
4. Removing override restores APPROVE (200)
5. Audit export JSON format
6. Plant PATCH with audit reason
"""
import os
import time
import uuid
import pytest
import requests

API = os.environ.get("API_BASE", "https://permission-matrix-9.preview.emergentagent.com/api")
ADMIN = ("admin@izqms.com", "Admin@2026")
QAM = ("qa.manager@izqms.com", "QaManager@2026")


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {_login(*ADMIN)}"}


@pytest.fixture(scope="module")
def qam_h():
    return {"Authorization": f"Bearer {_login(*QAM)}"}


@pytest.fixture(scope="module")
def qam_id(admin_h):
    r = requests.get(f"{API}/users", headers=admin_h, timeout=10)
    r.raise_for_status()
    return next(u["id"] for u in r.json() if u["email"] == QAM[0])


def _create_dev(headers):
    payload = {
        "type": "DEVIATION",
        "title": f"TEST_dev_{uuid.uuid4().hex[:6]}",
        "description": "regression test record",
        "severity": "Low",
        "priority": "Low",
    }
    r = requests.post(f"{API}/records", headers=headers, json=payload, timeout=15)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _action(headers, rid, action, password, extra=None):
    body = {"action": action, "password": password, "reason": "regression test", "comment": "ok"}
    if extra:
        body.update(extra)
    return requests.post(f"{API}/records/{rid}/action", headers=headers, json=body, timeout=15)


# -------- Legacy DEVIATION lifecycle (admin) --------
def test_legacy_dev_full_lifecycle_admin(admin_h):
    rec = _create_dev(admin_h)
    rid = rec["id"]
    r = _action(admin_h, rid, "REVIEW", ADMIN[1])
    assert r.status_code == 200, r.text
    r = _action(admin_h, rid, "APPROVE", ADMIN[1])
    assert r.status_code == 200, r.text
    r = _action(admin_h, rid, "CLOSE", ADMIN[1])
    assert r.status_code == 200, r.text


# -------- QA Manager canonical role --------
def test_qa_manager_review_approve(admin_h, qam_h):
    rec = _create_dev(admin_h)
    rid = rec["id"]
    r = _action(qam_h, rid, "REVIEW", QAM[1])
    assert r.status_code == 200, r.text
    r = _action(qam_h, rid, "APPROVE", QAM[1])
    assert r.status_code == 200, r.text


# -------- RESTRICTED override blocks APPROVE --------
def test_restricted_override_blocks_then_unblocks(admin_h, qam_h, qam_id):
    # baseline: APPROVE works
    rec = _create_dev(admin_h)
    rid = rec["id"]
    assert _action(qam_h, rid, "REVIEW", QAM[1]).status_code == 200

    # add DENY override on qa_manager
    o = requests.post(
        f"{API}/role-mgmt/users/{qam_id}/overrides",
        headers=admin_h,
        json={"module": "deviation", "action": "approve", "effect": "DENY", "reason": "iter6 test"},
        timeout=10,
    )
    assert o.status_code == 200, o.text
    oid = o.json()["id"]
    try:
        # APPROVE should now fail
        r = _action(qam_h, rid, "APPROVE", QAM[1])
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}: {r.text}"
    finally:
        # remove override
        d = requests.delete(
            f"{API}/role-mgmt/users/{qam_id}/overrides/{oid}",
            headers=admin_h, params={"reason": "iter6 cleanup"}, timeout=10,
        )
        assert d.status_code == 200, d.text

    # after removal — wait a hair for cache then re-test (a fresh record to avoid stale state)
    time.sleep(0.5)
    rec2 = _create_dev(admin_h)
    rid2 = rec2["id"]
    assert _action(qam_h, rid2, "REVIEW", QAM[1]).status_code == 200
    r2 = _action(qam_h, rid2, "APPROVE", QAM[1])
    assert r2.status_code == 200, r2.text


# -------- Audit JSON export --------
def test_audit_export_json(admin_h):
    r = requests.get(f"{API}/role-mgmt/audit/export?format=json", headers=admin_h, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0


# -------- Plant PATCH --------
def test_plant_patch(admin_h):
    code = f"P-{uuid.uuid4().hex[:5].upper()}"
    r = requests.post(f"{API}/module-framework/plants", headers=admin_h,
                      json={"code": code, "name": "PatchPlant", "location": "X"}, timeout=10)
    assert r.status_code == 200
    pid = r.json()["id"]
    r = requests.patch(f"{API}/module-framework/plants/{pid}", headers=admin_h,
                       json={"location": "Y", "reason": "iter6 patch test"}, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["location"] == "Y"


# -------- Auto-retire prior PUBLISHED on next publish --------
def test_publish_auto_retires_prev(admin_h):
    plants = requests.get(f"{API}/module-framework/plants", headers=admin_h, timeout=10).json()
    pid = next(p["id"] for p in plants if p["code"] == "PLANT-1")
    code = f"auto_{uuid.uuid4().hex[:6]}"
    # v1
    t1 = requests.post(f"{API}/module-framework/templates", headers=admin_h,
                      json={"code": code, "name": "v1", "plant_id": pid}, timeout=10).json()
    requests.post(f"{API}/module-framework/templates/{t1['id']}/publish",
                  headers=admin_h, json={"reason": "v1 pub"}, timeout=10).raise_for_status()
    # v2
    t2 = requests.post(f"{API}/module-framework/templates", headers=admin_h,
                      json={"code": code, "name": "v2", "plant_id": pid}, timeout=10).json()
    assert t2["version"] == 2
    requests.post(f"{API}/module-framework/templates/{t2['id']}/publish",
                  headers=admin_h, json={"reason": "v2 pub"}, timeout=10).raise_for_status()
    # v1 should now be RETIRED
    r = requests.get(f"{API}/module-framework/templates/{t1['id']}", headers=admin_h, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "RETIRED"


def test_dynamic_record_audit_isolated(admin_h):
    plants = requests.get(f"{API}/module-framework/plants", headers=admin_h, timeout=10).json()
    pid = next(p["id"] for p in plants if p["code"] == "PLANT-1")
    code = f"aud_{uuid.uuid4().hex[:6]}"
    tpl = requests.post(f"{API}/module-framework/templates", headers=admin_h,
                       json={"code": code, "name": "auditcheck", "plant_id": pid}, timeout=10).json()
    requests.post(f"{API}/module-framework/templates/{tpl['id']}/publish",
                  headers=admin_h, json={"reason": "publish for audit test"}, timeout=10).raise_for_status()
    rec = requests.post(f"{API}/module-framework/records", headers=admin_h,
                       json={"template_id": tpl["id"], "plant_id": pid, "title": "audit r",
                             "reason": "init"}, timeout=10).json()
    requests.post(f"{API}/module-framework/records/{rec['id']}/transition", headers=admin_h,
                  json={"to_stage": "REVIEW", "password": ADMIN[1], "reason": "go to review"}, timeout=10).raise_for_status()
    a = requests.get(f"{API}/module-framework/records/{rec['id']}/audit", headers=admin_h, timeout=10)
    assert a.status_code == 200, a.text
    entries = a.json()
    assert len(entries) >= 1
    # All entries pertain to this record (entity_id check if present)
    for e in entries:
        if "entity_id" in e:
            assert e["entity_id"] == rec["id"]
    actions = [e.get("action", "") for e in entries]
    assert any("DYN_TRANSITION" in a for a in actions), f"no DYN_TRANSITION in {actions}"
