"""Tests for the Plant/Site-Based Dynamic Module Framework."""
import os
import sys
import uuid

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

API = os.environ.get("API_BASE", "http://localhost:8001/api")
ADMIN_EMAIL = "admin@izqms.com"
ADMIN_PASSWORD = "Admin@2026"
EMPLOYEE_EMAIL = "employee@izqms.com"
EMPLOYEE_PASSWORD = "Employee@2026"


def _login(email=ADMIN_EMAIL, pw=ADMIN_PASSWORD):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login()}"}


@pytest.fixture(scope="module")
def employee_headers():
    return {"Authorization": f"Bearer {_login(EMPLOYEE_EMAIL, EMPLOYEE_PASSWORD)}"}


@pytest.fixture(scope="module")
def plant_id(admin_headers):
    r = requests.get(f"{API}/module-framework/plants", headers=admin_headers, timeout=10)
    r.raise_for_status()
    plants = r.json()
    assert plants, "Plants must be seeded"
    # Use PLANT-1
    return next(p["id"] for p in plants if p["code"] == "PLANT-1")


# --------------------------- Plants ---------------------------
def test_seed_plants_present(admin_headers):
    r = requests.get(f"{API}/module-framework/plants", headers=admin_headers, timeout=10)
    r.raise_for_status()
    codes = {p["code"] for p in r.json()}
    assert {"HQ", "PLANT-1", "PLANT-2"}.issubset(codes)


def test_create_plant(admin_headers):
    code = f"P-{uuid.uuid4().hex[:5].upper()}"
    r = requests.post(f"{API}/module-framework/plants", headers=admin_headers,
                      json={"code": code, "name": f"Plant {code}",
                            "location": "Test", "gmp_zone": "Grade A", "time_zone": "UTC"}, timeout=10)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["code"] == code
    # duplicate
    r2 = requests.post(f"{API}/module-framework/plants", headers=admin_headers,
                       json={"code": code, "name": "Dup"}, timeout=10)
    assert r2.status_code == 400


# --------------------------- Templates ---------------------------
def test_template_lifecycle(admin_headers, plant_id):
    code = f"life_{uuid.uuid4().hex[:6]}"
    # create draft
    r = requests.post(f"{API}/module-framework/templates", headers=admin_headers,
                      json={"code": code, "name": "Lifecycle test", "category": "CUSTOM",
                            "plant_id": plant_id}, timeout=10)
    assert r.status_code == 200, r.text
    tpl = r.json()
    assert tpl["status"] == "DRAFT"
    assert tpl["version"] == 1
    # update draft
    r = requests.patch(f"{API}/module-framework/templates/{tpl['id']}", headers=admin_headers,
                       json={"name": "Lifecycle test v2", "reason": "Renamed"}, timeout=10)
    assert r.status_code == 200
    # publish
    r = requests.post(f"{API}/module-framework/templates/{tpl['id']}/publish",
                      headers=admin_headers, json={"reason": "Validated"}, timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "PUBLISHED"
    # cannot edit a published one
    r = requests.patch(f"{API}/module-framework/templates/{tpl['id']}", headers=admin_headers,
                       json={"name": "Should fail", "reason": "x"}, timeout=10)
    assert r.status_code == 400
    # cannot re-publish a published one
    r = requests.post(f"{API}/module-framework/templates/{tpl['id']}/publish",
                      headers=admin_headers, json={"reason": "Retry"}, timeout=10)
    assert r.status_code == 400
    # versioning: create a new draft with same code+plant → version 2
    r = requests.post(f"{API}/module-framework/templates", headers=admin_headers,
                      json={"code": code, "name": "Lifecycle test", "category": "CUSTOM",
                            "plant_id": plant_id}, timeout=10)
    assert r.status_code == 200
    assert r.json()["version"] == 2
    # retire v1
    r = requests.post(f"{API}/module-framework/templates/{tpl['id']}/retire",
                      headers=admin_headers, json={"reason": "Superseded by v2"}, timeout=10)
    assert r.status_code == 200
    assert r.json()["status"] == "RETIRED"


def test_template_copy(admin_headers, plant_id):
    code = f"src_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/module-framework/templates", headers=admin_headers,
                      json={"code": code, "name": "Source", "plant_id": plant_id}, timeout=10)
    assert r.status_code == 200
    src = r.json()
    new_code = f"copy_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/module-framework/templates/{src['id']}/copy",
                      headers=admin_headers,
                      json={"new_code": new_code, "new_name": "Copy", "target_plant_id": "GLOBAL", "reason": "Pilot"}, timeout=10)
    assert r.status_code == 200, r.text
    cp = r.json()
    assert cp["code"] == new_code
    assert cp["plant_id"] == "GLOBAL"
    assert cp["status"] == "DRAFT"


# --------------------------- Dynamic Records ---------------------------
@pytest.fixture(scope="module")
def published_template(admin_headers, plant_id):
    code = f"rec_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/module-framework/templates", headers=admin_headers,
                      json={"code": code, "name": "Record test", "category": "DEVIATION",
                            "plant_id": plant_id}, timeout=10)
    r.raise_for_status()
    tpl = r.json()
    requests.post(f"{API}/module-framework/templates/{tpl['id']}/publish",
                  headers=admin_headers, json={"reason": "Test"}, timeout=10).raise_for_status()
    return tpl


def test_create_dynamic_record(admin_headers, plant_id, published_template):
    r = requests.post(f"{API}/module-framework/records", headers=admin_headers,
                      json={"template_id": published_template["id"], "plant_id": plant_id,
                            "title": "Test record A", "form_data": {"description": "Test"},
                            "reason": "Pytest"}, timeout=10)
    assert r.status_code == 200, r.text
    rec = r.json()
    assert rec["template_version"] == published_template["version"]
    assert rec["current_stage"] == "INITIATION"
    assert rec["record_number"].startswith(published_template["code"].upper())


def test_workflow_transition(admin_headers, plant_id, published_template):
    r = requests.post(f"{API}/module-framework/records", headers=admin_headers,
                      json={"template_id": published_template["id"], "plant_id": plant_id,
                            "title": "Transition test", "reason": "Test"}, timeout=10)
    rec = r.json()
    # Invalid transition
    r = requests.post(f"{API}/module-framework/records/{rec['id']}/transition",
                      headers=admin_headers,
                      json={"to_stage": "CLOSED", "password": ADMIN_PASSWORD, "reason": "Direct close"}, timeout=10)
    assert r.status_code == 400   # cannot jump straight to CLOSED
    # Valid: INITIATION → REVIEW
    r = requests.post(f"{API}/module-framework/records/{rec['id']}/transition",
                      headers=admin_headers,
                      json={"to_stage": "REVIEW", "password": ADMIN_PASSWORD, "reason": "Submitting"}, timeout=10)
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["current_stage"] == "REVIEW"
    assert len(after["history"]) >= 2


def test_bad_password_blocks_transition(admin_headers, plant_id, published_template):
    r = requests.post(f"{API}/module-framework/records", headers=admin_headers,
                      json={"template_id": published_template["id"], "plant_id": plant_id,
                            "title": "Bad pw test", "reason": "Test"}, timeout=10)
    rec = r.json()
    r = requests.post(f"{API}/module-framework/records/{rec['id']}/transition",
                      headers=admin_headers,
                      json={"to_stage": "REVIEW", "password": "WrongPassword!", "reason": "Submitting"}, timeout=10)
    assert r.status_code in (400, 401, 403)


def test_employee_cannot_create_template(employee_headers, plant_id):
    r = requests.post(f"{API}/module-framework/templates", headers=employee_headers,
                      json={"code": "unauth", "name": "Bad", "plant_id": plant_id}, timeout=10)
    assert r.status_code in (401, 403)


def test_audit_export_csv(admin_headers):
    r = requests.get(f"{API}/role-mgmt/audit/export?format=csv",
                     headers=admin_headers, timeout=10)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")
    body = r.text
    assert "Timestamp,User Email" in body
    # At least some role audit rows from earlier tests
    assert "ROLE" in body or "USER_PERMISSION" in body
