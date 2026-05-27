"""Iteration 7 — Module Framework legacy-module integration tests.

Validates:
1. Active-template endpoint returns latest PUBLISHED GLOBAL template per category
2. Role catalog exposes module_framework with 4 actions
3. Default role permission-matrix presets are correct for module_framework
4. Records auto-bind to active framework template
5. framework_form_data persistence on create + patch
6. The 5 seeded compliant templates exist with proper attributes
"""
import os
import uuid
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://permission-matrix-9.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@izqms.com"
ADMIN_PASSWORD = "Admin@2026"

CATEGORIES = ["DEVIATION", "CAPA", "CHANGE_CONTROL", "INCIDENT", "EVENT"]
EXPECTED_CODES = {
    "DEVIATION": "qa005f02_deviation",
    "CAPA": "qa005f06_capa",
    "CHANGE_CONTROL": "qa004f02_change_control",
    "INCIDENT": "qa005f04_incident",
    "EVENT": "qa005f08_event_log",
}

# ----------------------------- helpers -----------------------------

def _login(email=ADMIN_EMAIL, pw=ADMIN_PASSWORD):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    r.raise_for_status()
    return r.json()["access_token"]


_admin_token = None
def admin_headers():
    global _admin_token
    if _admin_token is None:
        _admin_token = _login()
    return {"Authorization": f"Bearer {_admin_token}"}


# ===================== 1. Active-template endpoint =====================

def test_active_template_for_each_category():
    h = admin_headers()
    for cat in CATEGORIES:
        r = requests.get(f"{API}/module-framework/active-template", params={"category": cat}, headers=h, timeout=15)
        assert r.status_code == 200, f"{cat}: {r.status_code} {r.text}"
        payload = r.json()
        assert payload["category"] == cat
        tpl = payload["template"]
        assert tpl is not None, f"No active template for {cat}"
        assert tpl["status"] == "PUBLISHED", f"{cat} status={tpl.get('status')}"
        assert tpl["plant_id"] == "GLOBAL", f"{cat} plant_id={tpl.get('plant_id')}"
        sections = tpl.get("sections") or []
        if cat == "EVENT":
            assert len(sections) >= 3, f"{cat} sections={len(sections)}"
        else:
            assert len(sections) >= 9, f"{cat} sections={len(sections)}"
        assert tpl["code"] == EXPECTED_CODES[cat], f"{cat} code={tpl.get('code')}"


def test_active_template_missing_category_400():
    h = admin_headers()
    r = requests.get(f"{API}/module-framework/active-template", params={"category": ""}, headers=h, timeout=10)
    assert r.status_code in (400, 422)


# ===================== 2. Role catalog =====================

def test_role_modules_has_module_framework_with_4_actions():
    h = admin_headers()
    r = requests.get(f"{API}/role-mgmt/modules", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    modules = body.get("modules", body)  # endpoint returns {"modules": {...}}
    assert "module_framework" in modules, f"keys={list(modules.keys())[:20]}"
    mf = modules["module_framework"]
    action_keys = {a["key"] for a in mf["actions"]}
    expected = {"view_module_framework", "manage_module_templates", "publish_module_templates", "retire_module_templates"}
    assert action_keys == expected, f"got={action_keys}"


# ===================== 3. Role defaults =====================

def _perm(role_obj):
    return role_obj.get("permissions") or {}


def test_role_defaults_module_framework_matrix():
    h = admin_headers()
    r = requests.get(f"{API}/role-mgmt/roles", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    roles = r.json()
    by_code = {x["code"]: x for x in roles}
    must_be_full = ["admin", "super_admin", "qa_manager"]
    for code in must_be_full:
        assert code in by_code, f"missing role {code}"
        p = _perm(by_code[code]).get("module_framework", {})
        for k in ["view_module_framework", "manage_module_templates", "publish_module_templates", "retire_module_templates"]:
            assert p.get(k) is True, f"{code}.{k} expected True got {p.get(k)}"

    # qa_reviewer: only view
    p = _perm(by_code["qa_reviewer"]).get("module_framework", {})
    assert p.get("view_module_framework") is True
    for k in ["manage_module_templates", "publish_module_templates", "retire_module_templates"]:
        assert p.get(k) in (False, None), f"qa_reviewer.{k}={p.get(k)}"

    # employee/dept manager/auditor: all False
    for code in ["employee_operator", "department_manager", "auditor"]:
        if code not in by_code:
            continue
        p = _perm(by_code[code]).get("module_framework", {})
        for k in ["view_module_framework", "manage_module_templates", "publish_module_templates", "retire_module_templates"]:
            assert p.get(k) in (False, None), f"{code}.{k}={p.get(k)}"


# ===================== 4. Records auto-bind =====================

def test_create_capa_record_auto_binds_template():
    h = admin_headers()
    body = {
        "type": "CAPA",
        "title": f"TEST_iter7 CAPA auto-bind {uuid.uuid4().hex[:6]}",
        "description": "iter7 auto-bind check",
        "department": "Quality Assurance",
        "severity": "MEDIUM",
        "priority": "MEDIUM",
    }
    r = requests.post(f"{API}/records", json=body, headers=h, timeout=15)
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec.get("framework_template_id"), f"framework_template_id missing: {rec}"
    assert rec.get("framework_template_version") == 1, f"version={rec.get('framework_template_version')}"
    # framework_form_data should be {}
    assert rec.get("framework_form_data") == {}


def test_create_capa_with_framework_form_data():
    h = admin_headers()
    body = {
        "type": "CAPA",
        "title": f"TEST_iter7 CAPA formdata {uuid.uuid4().hex[:6]}",
        "description": "iter7 form data persist",
        "framework_form_data": {"classification": "Major"},
    }
    r = requests.post(f"{API}/records", json=body, headers=h, timeout=15)
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec.get("framework_form_data") == {"classification": "Major"}
    # GET verifies persistence
    rid = rec["id"]
    g = requests.get(f"{API}/records/{rid}", headers=h, timeout=10)
    assert g.status_code == 200
    assert g.json().get("framework_form_data") == {"classification": "Major"}


def test_patch_framework_form_data():
    h = admin_headers()
    create = requests.post(f"{API}/records", json={
        "type": "CAPA",
        "title": f"TEST_iter7 CAPA patch {uuid.uuid4().hex[:6]}",
        "description": "iter7 patch",
    }, headers=h, timeout=15)
    assert create.status_code == 200, create.text
    rid = create.json()["id"]
    patch = requests.patch(f"{API}/records/{rid}", json={
        "framework_form_data": {"x": 1, "classification": "Critical"},
        "reason": "iter7 patch test",
    }, headers=h, timeout=15)
    assert patch.status_code == 200, patch.text
    g = requests.get(f"{API}/records/{rid}", headers=h, timeout=10)
    assert g.status_code == 200
    fd = g.json().get("framework_form_data") or {}
    assert fd.get("x") == 1
    assert fd.get("classification") == "Critical"


# ===================== 5. Seeded templates inventory =====================

def test_five_compliant_templates_seeded_published_global():
    """Use admin /module-framework/templates list to verify the 5 PDF-aligned templates."""
    h = admin_headers()
    r = requests.get(f"{API}/module-framework/templates", headers=h, timeout=15)
    assert r.status_code == 200, r.text
    rows = r.json()
    by_code = {row["code"]: row for row in rows}
    for cat, code in EXPECTED_CODES.items():
        assert code in by_code, f"missing seeded template {code} ({cat}). Codes={list(by_code.keys())[:30]}"
        t = by_code[code]
        assert t["status"] == "PUBLISHED", f"{code} status={t['status']}"
        assert t["plant_id"] == "GLOBAL", f"{code} plant_id={t['plant_id']}"
        assert t["version"] == 1, f"{code} version={t['version']}"
        assert t["category"] == cat, f"{code} category={t['category']}"
