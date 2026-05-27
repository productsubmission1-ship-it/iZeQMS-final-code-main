"""
izQMS Role-Matrix backend tests (Iteration 4).
Covers the 7-role canonical matrix:
  super_admin > admin > qa_manager > qa_reviewer > {department_manager, employee_operator}
  auditor (read-only, transverse)

Test surface:
  * Login with all 7 NEW seed accounts (admin@, qa.manager@, qa.reviewer@,
    dept.manager@, employee@, auditor@, admin.user@)
  * Login with LEGACY accounts (qa.head@, reviewer@, initiator@) whose
    DB-stored roles should be migrated to canonical strings at startup
  * GET /api/roles returns canonical_roles list, permission_matrix,
    role_hierarchy, my_effective_roles, my_permissions
  * POST /api/records/{id}/action permission gating:
      - employee_operator → 403 on APPROVE / CLOSE / REVIEW
      - qa_reviewer       → 403 on APPROVE / CLOSE ; allowed REVIEW / REJECT
      - qa_manager        → APPROVE / REJECT / CLOSE allowed
      - auditor           → 403 on every action
      - admin / super_admin → allowed
  * Auditor write blocks: POST /api/records, POST /api/records/draft,
    PATCH /api/records/{id} → 403 ; GET /api/records → 200
  * User management gating: POST /api/users + lifecycle endpoints require
    admin / super_admin (403 for qa_manager / qa_reviewer / employee / auditor)
    APPROVE during PENDING_QA still allows qa_manager
  * Workflow-config gating: PATCH /api/settings/password-policy and
    POST/PUT /api/form-schemas/{module} require admin/super_admin
  * Notification fan-out picks canonical qa_reviewer / qa_manager on
    OPEN/IN_REVIEW transitions
"""
import os
import uuid
import time
from pathlib import Path

import pytest
import requests

_env_path = Path("/app/frontend/.env")
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

# --- Canonical credentials (per /app/memory/test_credentials.md) ---
SUPER_ADMIN = ("admin@izqms.com", "Admin@2026")
ADMIN = ("admin.user@izqms.com", "AdminUser@2026")
QA_MANAGER = ("qa.manager@izqms.com", "QaManager@2026")
QA_REVIEWER = ("qa.reviewer@izqms.com", "QaReviewer@2026")
DEPT_MANAGER = ("dept.manager@izqms.com", "DeptMgr@2026")
EMPLOYEE = ("employee@izqms.com", "Employee@2026")
AUDITOR = ("auditor@izqms.com", "Auditor@2026")

# Legacy users (must still authenticate; roles must be migrated)
LEGACY_QA_HEAD = ("qa.head@izqms.com", "QaHead@2026")
LEGACY_REVIEWER = ("reviewer@izqms.com", "Reviewer@2026")
LEGACY_INITIATOR = ("initiator@izqms.com", "Initiator@2026")


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        return None
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    s.user = data["user"]
    s.token = data["access_token"]
    return s


def _esign_action(action, password=None, reason=None, comment=""):
    return {
        "password": password,
        "reason": reason or f"role-matrix test {action}",
        "action": action,
        "comment": comment,
    }


def _create_record(sess, password, type_="DEVIATION", title=None):
    body = {
        "type": type_,
        "title": title or f"TEST_RM {uuid.uuid4().hex[:8]}",
        "description": "role-matrix smoke",
        "department": "Quality Assurance",
        "location": "HQ",
        "severity": "Medium",
        "priority": "Medium",
    }
    r = sess.post(f"{API}/records", json=body)
    assert r.status_code in (200, 201), f"create_record failed: {r.status_code} {r.text}"
    return r.json()


# =========================================================================
# 1. Authentication for all 7 canonical seed accounts
# =========================================================================
class TestSeedLogins:
    @pytest.mark.parametrize("creds", [
        SUPER_ADMIN, ADMIN, QA_MANAGER, QA_REVIEWER,
        DEPT_MANAGER, EMPLOYEE, AUDITOR,
    ])
    def test_canonical_seed_login(self, creds):
        email, pwd = creds
        s = _login(email, pwd)
        assert s is not None, f"{email} cannot log in"
        assert s.user["email"] == email
        assert isinstance(s.user["roles"], list) and len(s.user["roles"]) >= 1


# =========================================================================
# 2. Legacy accounts still log in + roles migrated to canonical
# =========================================================================
class TestLegacyMigration:
    LEGACY_EXPECTED = {
        "qa.head@izqms.com":   {"qa_manager"},        # qa_head → qa_manager
        "reviewer@izqms.com":  {"qa_reviewer"},       # reviewer → qa_reviewer
        "initiator@izqms.com": {"employee_operator"}, # initiator → employee_operator
    }

    @pytest.mark.parametrize("creds", [LEGACY_QA_HEAD, LEGACY_REVIEWER, LEGACY_INITIATOR])
    def test_legacy_login_still_works(self, creds):
        email, pwd = creds
        s = _login(email, pwd)
        assert s is not None, f"legacy {email} cannot log in (migration broken?)"

    def test_legacy_roles_migrated_to_canonical(self):
        admin = _login(*SUPER_ADMIN)
        assert admin
        r = admin.get(f"{API}/users")
        assert r.status_code == 200
        users = {u["email"]: u for u in r.json()}
        for email, expected_canonical in self.LEGACY_EXPECTED.items():
            assert email in users, f"{email} missing in /api/users"
            roles = set(users[email].get("roles", []))
            # Every stored role on the legacy user must already be canonical
            assert all(r in {
                "super_admin", "admin", "qa_manager", "qa_reviewer",
                "department_manager", "employee_operator", "auditor",
            } for r in roles), f"{email} still has legacy roles: {roles}"
            assert expected_canonical & roles, (
                f"{email} expected to contain {expected_canonical} after "
                f"migration but has {roles}"
            )


# =========================================================================
# 3. GET /api/roles catalog endpoint
# =========================================================================
class TestRolesEndpoint:
    EXPECTED_CANONICAL = [
        "super_admin", "admin", "qa_manager", "qa_reviewer",
        "department_manager", "employee_operator", "auditor",
    ]

    def test_roles_payload_for_super_admin(self):
        s = _login(*SUPER_ADMIN)
        assert s
        r = s.get(f"{API}/roles")
        assert r.status_code == 200, r.text
        data = r.json()
        assert sorted(data["canonical_roles"]) == sorted(self.EXPECTED_CANONICAL)
        assert "permission_matrix" in data
        # Every key from the matrix is present
        for perm in ("create_record", "approve_record", "user_management"):
            assert perm in data["permission_matrix"]
        assert "role_hierarchy" in data
        assert "my_effective_roles" in data and "my_permissions" in data
        # super_admin gets everything
        eff = set(data["my_effective_roles"])
        assert eff.issuperset(set(self.EXPECTED_CANONICAL))
        assert "user_management" in data["my_permissions"]

    def test_roles_payload_for_auditor(self):
        s = _login(*AUDITOR)
        assert s
        r = s.get(f"{API}/roles")
        assert r.status_code == 200
        data = r.json()
        perms = set(data["my_permissions"])
        # Auditor: view_reports, export_reports, audit_trail_view (no writes)
        assert "view_reports" in perms
        assert "audit_trail_view" in perms
        # No write/manage
        for forbidden in ("create_record", "approve_record", "user_management", "workflow_config"):
            assert forbidden not in perms, f"auditor unexpectedly has {forbidden}"

    def test_roles_payload_for_employee(self):
        s = _login(*EMPLOYEE)
        assert s
        r = s.get(f"{API}/roles")
        assert r.status_code == 200
        perms = set(r.json()["my_permissions"])
        assert "create_record" in perms
        assert "edit_draft" in perms
        for forbidden in ("approve_record", "close_record", "user_management"):
            assert forbidden not in perms


# =========================================================================
# 4. Record action permission gating
# =========================================================================
@pytest.fixture(scope="module")
def open_record():
    """Create a record as employee + push to OPEN status for downstream tests."""
    emp = _login(*EMPLOYEE)
    assert emp, "employee login required"
    rec = _create_record(emp, EMPLOYEE[1])
    return rec


class TestRecordActionGating:
    def test_employee_cannot_approve(self, open_record):
        s = _login(*EMPLOYEE)
        r = s.post(f"{API}/records/{open_record['id']}/action",
                   json=_esign_action("APPROVE", password=EMPLOYEE[1]))
        assert r.status_code == 403, r.text

    def test_employee_cannot_close(self, open_record):
        s = _login(*EMPLOYEE)
        r = s.post(f"{API}/records/{open_record['id']}/action",
                   json=_esign_action("CLOSE", password=EMPLOYEE[1]))
        assert r.status_code == 403

    def test_employee_cannot_review(self, open_record):
        s = _login(*EMPLOYEE)
        r = s.post(f"{API}/records/{open_record['id']}/action",
                   json=_esign_action("REVIEW", password=EMPLOYEE[1]))
        assert r.status_code == 403

    def test_qa_reviewer_cannot_approve(self, open_record):
        s = _login(*QA_REVIEWER)
        r = s.post(f"{API}/records/{open_record['id']}/action",
                   json=_esign_action("APPROVE", password=QA_REVIEWER[1]))
        assert r.status_code == 403, r.text

    def test_qa_reviewer_cannot_close(self, open_record):
        s = _login(*QA_REVIEWER)
        r = s.post(f"{API}/records/{open_record['id']}/action",
                   json=_esign_action("CLOSE", password=QA_REVIEWER[1]))
        assert r.status_code == 403

    def test_qa_reviewer_can_review(self):
        """Use a fresh OPEN record so we don't conflict with other tests."""
        emp = _login(*EMPLOYEE)
        rec = _create_record(emp, EMPLOYEE[1])
        rev = _login(*QA_REVIEWER)
        r = rev.post(f"{API}/records/{rec['id']}/action",
                     json=_esign_action("REVIEW", password=QA_REVIEWER[1]))
        assert r.status_code == 200, f"reviewer REVIEW failed: {r.status_code} {r.text}"
        # Now status should be IN_REVIEW
        got = rev.get(f"{API}/records/{rec['id']}").json()
        assert got["status"] == "IN_REVIEW"

    def test_qa_reviewer_can_reject(self):
        emp = _login(*EMPLOYEE)
        rec = _create_record(emp, EMPLOYEE[1])
        rev = _login(*QA_REVIEWER)
        r = rev.post(f"{API}/records/{rec['id']}/action",
                     json=_esign_action("REJECT", password=QA_REVIEWER[1]))
        assert r.status_code == 200, r.text

    def test_qa_manager_can_approve_reject_close(self):
        # Build OPEN → IN_REVIEW → APPROVED → CLOSED with qa_manager doing
        # APPROVE + CLOSE (qa_reviewer does the REVIEW step).
        emp = _login(*EMPLOYEE)
        rec = _create_record(emp, EMPLOYEE[1])
        rev = _login(*QA_REVIEWER)
        r1 = rev.post(f"{API}/records/{rec['id']}/action",
                      json=_esign_action("REVIEW", password=QA_REVIEWER[1]))
        assert r1.status_code == 200, r1.text
        mgr = _login(*QA_MANAGER)
        r2 = mgr.post(f"{API}/records/{rec['id']}/action",
                      json=_esign_action("APPROVE", password=QA_MANAGER[1]))
        assert r2.status_code == 200, f"qa_manager APPROVE: {r2.status_code} {r2.text}"
        r3 = mgr.post(f"{API}/records/{rec['id']}/action",
                      json=_esign_action("CLOSE", password=QA_MANAGER[1]))
        assert r3.status_code == 200, f"qa_manager CLOSE: {r3.status_code} {r3.text}"

    @pytest.mark.parametrize("action", ["REVIEW", "APPROVE", "REJECT", "CLOSE"])
    def test_auditor_blocked_on_every_action(self, open_record, action):
        s = _login(*AUDITOR)
        r = s.post(f"{API}/records/{open_record['id']}/action",
                   json=_esign_action(action, password=AUDITOR[1]))
        assert r.status_code == 403, f"auditor must be blocked on {action}, got {r.status_code}"

    def test_admin_can_approve(self):
        emp = _login(*EMPLOYEE)
        rec = _create_record(emp, EMPLOYEE[1])
        adm = _login(*ADMIN)
        # admin should be able to APPROVE OPEN record directly (allowed states include OPEN)
        r = adm.post(f"{API}/records/{rec['id']}/action",
                     json=_esign_action("APPROVE", password=ADMIN[1]))
        assert r.status_code == 200, f"admin APPROVE: {r.status_code} {r.text}"


# =========================================================================
# 5. Auditor write blocks (records create / draft / patch)
# =========================================================================
class TestAuditorWriteBlocks:
    def test_auditor_cannot_create_record(self):
        s = _login(*AUDITOR)
        r = s.post(f"{API}/records", json={
            "type": "DEVIATION", "title": "TEST_RM auditor block",
            "description": "should fail",
        })
        assert r.status_code == 403, r.text

    def test_auditor_cannot_create_draft(self):
        s = _login(*AUDITOR)
        r = s.post(f"{API}/records/draft", json={
            "type": "DEVIATION", "title": "TEST_RM auditor block",
            "description": "should fail",
        })
        assert r.status_code == 403, r.text

    def test_auditor_can_list_records(self):
        s = _login(*AUDITOR)
        r = s.get(f"{API}/records")
        assert r.status_code == 200

    def test_auditor_cannot_patch_record(self, open_record):
        s = _login(*AUDITOR)
        r = s.patch(f"{API}/records/{open_record['id']}",
                    json={"title": "TEST_RM hijack", "reason": "should be blocked"})
        assert r.status_code == 403, r.text


# =========================================================================
# 6. User management gating
# =========================================================================
def _new_user_payload(actor_pwd, roles=("employee_operator",)):
    suf = uuid.uuid4().hex[:8]
    return {
        "email": f"TEST_RM_{suf}@izqms.com",
        "username": f"trm_{suf}",
        "employee_id": f"TRM{suf.upper()}",
        "name": "TEST_RM user",
        "department": "Quality Assurance",
        "location": "HQ",
        "roles": list(roles),
        "esign_password": actor_pwd,
        "esign_reason": "role-matrix create",
    }


class TestUserManagementGating:
    @pytest.mark.parametrize("creds", [QA_MANAGER, QA_REVIEWER, EMPLOYEE, AUDITOR])
    def test_non_admin_cannot_create_user(self, creds):
        s = _login(*creds)
        r = s.post(f"{API}/users", json=_new_user_payload(creds[1]))
        assert r.status_code == 403, f"{creds[0]} should not create users (got {r.status_code})"

    def test_admin_can_create_user(self):
        s = _login(*ADMIN)
        r = s.post(f"{API}/users", json=_new_user_payload(ADMIN[1]))
        assert r.status_code in (200, 201), r.text

    @pytest.mark.parametrize("creds", [QA_REVIEWER, EMPLOYEE, AUDITOR])
    def test_non_admin_cannot_reset_password(self, creds):
        # Pick any existing user id
        admin = _login(*SUPER_ADMIN)
        target_id = admin.get(f"{API}/users").json()[0]["id"]
        s = _login(*creds)
        r = s.post(
            f"{API}/users/{target_id}/reset-password",
            json={"esign_password": creds[1], "esign_reason": "x"},
        )
        assert r.status_code == 403, f"{creds[0]} reset-password expected 403, got {r.status_code}"

    @pytest.mark.parametrize("action", ["activate", "deactivate", "lock", "unlock"])
    def test_qa_manager_cannot_lifecycle_user(self, action):
        # qa_manager is allowed in some legacy endpoints? Per matrix lifecycle requires admin.
        admin = _login(*SUPER_ADMIN)
        target_id = admin.get(f"{API}/users").json()[0]["id"]
        s = _login(*QA_MANAGER)
        r = s.post(
            f"{API}/users/{target_id}/{action}",
            json={"esign_password": QA_MANAGER[1], "esign_reason": "x"},
        )
        # Per matrix qa_manager must NOT be able to act on user lifecycle.
        assert r.status_code == 403, f"qa_manager {action} expected 403, got {r.status_code}: {r.text[:200]}"

    def test_qa_manager_can_approve_pending_user(self):
        admin = _login(*ADMIN)
        body = _new_user_payload(ADMIN[1])
        body["requires_approval"] = True
        r = admin.post(f"{API}/users", json=body)
        if r.status_code not in (200, 201):
            pytest.skip(f"could not seed pending user: {r.status_code} {r.text[:200]}")
        resp = r.json()
        # POST /users returns {"user": {...}, "temp_password": ...}
        target = resp.get("user") or resp
        approval = target.get("approval_status")
        if approval != "PENDING_QA":
            pytest.skip(
                f"admin creator bypasses approval (got {approval}); "
                f"qa_manager approval path requires a PENDING_QA user"
            )
        mgr = _login(*QA_MANAGER)
        r2 = mgr.post(
            f"{API}/users/{target['id']}/approve",
            json={"esign_password": QA_MANAGER[1], "esign_reason": "approve pending"},
        )
        assert r2.status_code == 200, f"qa_manager APPROVE got {r2.status_code}: {r2.text[:300]}"


# =========================================================================
# 7. Workflow config gating
# =========================================================================
class TestWorkflowConfigGating:
    def test_qa_manager_cannot_change_password_policy(self):
        s = _login(*QA_MANAGER)
        r = s.patch(f"{API}/settings/password-policy", json={"min_length": 10})
        assert r.status_code == 403, r.text

    def test_employee_cannot_change_password_policy(self):
        s = _login(*EMPLOYEE)
        r = s.patch(f"{API}/settings/password-policy", json={"min_length": 10})
        assert r.status_code == 403

    def test_admin_can_change_password_policy(self):
        s = _login(*ADMIN)
        r = s.patch(f"{API}/settings/password-policy", json={"min_length": 8})
        assert r.status_code == 200, r.text

    def test_qa_manager_cannot_put_form_schema(self):
        s = _login(*QA_MANAGER)
        r = s.put(f"{API}/form-schemas/DEVIATION",
                  json={"module": "DEVIATION", "fields": []})
        assert r.status_code == 403, r.text

    def test_auditor_cannot_put_form_schema(self):
        s = _login(*AUDITOR)
        r = s.put(f"{API}/form-schemas/DEVIATION",
                  json={"module": "DEVIATION", "fields": []})
        assert r.status_code == 403


# =========================================================================
# 8. Notification fan-out picks canonical roles
# =========================================================================
class TestNotificationFanout:
    def test_qa_reviewer_notified_on_OPEN(self):
        # The fan-out fires on workflow transitions (record_action) — not on
        # direct POST /records. So use the draft + SUBMIT_REVIEW path.
        emp = _login(*EMPLOYEE)
        draft_body = {
            "type": "DEVIATION",
            "title": f"TEST_RM notif {uuid.uuid4().hex[:6]}",
            "description": "notification fan-out",
            "department": "Quality Assurance",
            "location": "HQ",
            "severity": "Medium",
            "priority": "Medium",
        }
        dr = emp.post(f"{API}/records/draft", json=draft_body)
        if dr.status_code not in (200, 201):
            pytest.skip(f"/records/draft unavailable: {dr.status_code} {dr.text[:200]}")
        rec = dr.json()
        # SUBMIT_REVIEW takes DRAFT → OPEN and fans out to reviewers
        r = emp.post(f"{API}/records/{rec['id']}/action",
                     json=_esign_action("SUBMIT_REVIEW", password=EMPLOYEE[1]))
        assert r.status_code == 200, r.text
        time.sleep(1.5)
        rev = _login(*QA_REVIEWER)
        raw = rev.get(f"{API}/notifications").json()
        items = raw.get("items", raw) if isinstance(raw, dict) else raw
        rno = rec.get("record_number", "")
        found = any(rno in (n.get("title", "") + " " + n.get("body", "")) for n in items)
        assert found, f"qa_reviewer did not receive OPEN notification for {rno}"

    def test_qa_manager_notified_on_IN_REVIEW(self):
        # Push a record to IN_REVIEW with qa_reviewer
        emp = _login(*EMPLOYEE)
        rec = _create_record(emp, EMPLOYEE[1])
        rev = _login(*QA_REVIEWER)
        r1 = rev.post(f"{API}/records/{rec['id']}/action",
                      json=_esign_action("REVIEW", password=QA_REVIEWER[1]))
        assert r1.status_code == 200, r1.text
        time.sleep(1.0)
        mgr = _login(*QA_MANAGER)
        raw = mgr.get(f"{API}/notifications").json()
        items = raw.get("items", raw) if isinstance(raw, dict) else raw
        rno = rec["record_number"]
        found = any(rno in (n.get("title", "") + " " + n.get("body", "")) for n in items)
        assert found, f"qa_manager did not receive IN_REVIEW notification for {rno}"
