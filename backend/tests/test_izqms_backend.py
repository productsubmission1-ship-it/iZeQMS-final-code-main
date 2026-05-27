"""
izQMS backend integration tests.
Covers: auth (JWT + cookies + brute force), records CRUD, workflow with e-signature,
audit trail, dashboard, users mgmt, role enforcement, record numbering.
"""
import os
import time
import uuid
import pytest
import requests
from pathlib import Path

# Load /app/frontend/.env for REACT_APP_BACKEND_URL
_env_path = Path("/app/frontend/.env")
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@izqms.com"
ADMIN_PASSWORD = "Admin@izQMS2026"
REVIEWER_EMAIL = "reviewer@izqms.com"
REVIEWER_PASSWORD = "Reviewer@2026"
QA_HEAD_EMAIL = "qa.head@izqms.com"
QA_HEAD_PASSWORD = "QaHead@2026"
INITIATOR_EMAIL = "initiator@izqms.com"
INITIATOR_PASSWORD = "Initiator@2026"


# ---------------- Fixtures ----------------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    s.token = data["access_token"]
    s.user = data["user"]
    return s


@pytest.fixture(scope="session")
def reviewer_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": REVIEWER_EMAIL, "password": REVIEWER_PASSWORD})
    assert r.status_code == 200, f"Reviewer login failed: {r.text}"
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    s.token = data["access_token"]
    s.user = data["user"]
    return s


@pytest.fixture(scope="session")
def qa_head_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": QA_HEAD_EMAIL, "password": QA_HEAD_PASSWORD})
    assert r.status_code == 200
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    s.token = data["access_token"]
    s.user = data["user"]
    return s


@pytest.fixture(scope="session")
def initiator_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": INITIATOR_EMAIL, "password": INITIATOR_PASSWORD})
    assert r.status_code == 200
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    s.token = data["access_token"]
    s.user = data["user"]
    return s


# ---------------- Health ----------------
class TestHealth:
    def test_root(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        assert r.json().get("status") == "online"


# ---------------- Auth ----------------
class TestAuth:
    def test_login_success_returns_user_and_token_and_sets_cookies(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data and isinstance(data["access_token"], str) and len(data["access_token"]) > 20
        assert data["user"]["email"] == ADMIN_EMAIL
        assert "password_hash" not in data["user"]
        assert "admin" in data["user"]["roles"]
        # Cookies
        cookies = {c.name: c for c in s.cookies}
        assert "access_token" in cookies
        assert "refresh_token" in cookies

    def test_login_wrong_password_401(self):
        # Use a unique IP-equivalent email pattern? IP is constant per session; use a unique email so we don't lock real account
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "WrongPassword!123"})
        assert r.status_code == 401
        assert "Invalid" in r.json().get("detail", "")

    def test_auth_me_via_cookie(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        # Use cookies only (no bearer)
        r2 = s.get(f"{API}/auth/me")
        assert r2.status_code == 200
        assert r2.json()["email"] == ADMIN_EMAIL

    def test_auth_me_via_bearer(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        token = r.json()["access_token"]
        r2 = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert r2.status_code == 200
        assert r2.json()["email"] == ADMIN_EMAIL

    def test_logout_clears_cookies(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200
        # After logout, cookies should be cleared - check Set-Cookie
        set_cookie_header = r.headers.get("set-cookie", "").lower()
        assert "access_token" in set_cookie_header  # delete_cookie emits it
        # New request without cookies/token should be 401
        s2 = requests.Session()
        r2 = s2.get(f"{API}/auth/me")
        assert r2.status_code == 401

    def test_unauthenticated_rejected(self):
        for ep in ["/auth/me", "/records", "/dashboard/summary", "/dashboard/my-tasks", "/users", "/audit"]:
            r = requests.get(f"{API}{ep}")
            assert r.status_code == 401, f"{ep} should require auth, got {r.status_code}"

    def test_brute_force_lockout(self):
        # Use unique email so we don't lock real users for the IP. Identifier is ip:email.
        bogus_email = f"bruteforce_{uuid.uuid4().hex[:8]}@example.com"
        statuses = []
        for _ in range(6):
            r = requests.post(f"{API}/auth/login", json={"email": bogus_email, "password": "wrong"})
            statuses.append(r.status_code)
        # First 5 should be 401, 6th attempt should be 429 (locked)
        assert statuses.count(401) >= 4, f"Expected 401s, got {statuses}"
        assert 429 in statuses, f"Expected lockout 429 after 5 attempts, got {statuses}"


# ---------------- Dashboard ----------------
class TestDashboard:
    def test_summary(self, admin_session):
        r = admin_session.get(f"{API}/dashboard/summary")
        assert r.status_code == 200
        data = r.json()
        for key in ("by_type", "totals", "overdue_count", "recent"):
            assert key in data
        assert isinstance(data["overdue_count"], int)
        assert isinstance(data["recent"], list)

    def test_my_tasks_admin(self, admin_session):
        r = admin_session.get(f"{API}/dashboard/my-tasks")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_my_tasks_initiator_returns_empty(self, initiator_session):
        # Initiator has no reviewer/approver/qa_head/admin roles -> empty
        r = initiator_session.get(f"{API}/dashboard/my-tasks")
        assert r.status_code == 200
        assert r.json() == []


# ---------------- Records ----------------
class TestRecords:
    def test_list_with_filters(self, admin_session):
        r = admin_session.get(f"{API}/records", params={"type": "DEVIATION", "q": "temperature"})
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        for row in rows:
            assert row["type"] == "DEVIATION"

    def test_create_record_and_persistence(self, admin_session):
        payload = {
            "type": "DEVIATION",
            "title": "TEST_ Deviation for create",
            "description": "Created by automated test",
            "severity": "Low",
            "priority": "Low",
        }
        r = admin_session.post(f"{API}/records", json=payload)
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec["title"] == payload["title"]
        assert rec["type"] == "DEVIATION"
        assert rec["status"] == "OPEN"
        # Record number format PREFIX-YYYY-XXXX
        import re
        assert re.match(r"^DEV-\d{4}-\d{4}$", rec["record_number"]), f"Bad record_number {rec['record_number']}"
        # GET verifies persistence
        g = admin_session.get(f"{API}/records/{rec['id']}")
        assert g.status_code == 200
        assert g.json()["record_number"] == rec["record_number"]
        # Audit entry exists
        a = admin_session.get(f"{API}/records/{rec['id']}/audit")
        assert a.status_code == 200
        actions = [e["action"] for e in a.json()]
        assert "CREATE" in actions

    def test_record_numbering_sequential(self, admin_session):
        nums = []
        for i in range(3):
            r = admin_session.post(f"{API}/records", json={
                "type": "DEVIATION",
                "title": f"TEST_ seq {i}",
                "description": "seq test",
            })
            assert r.status_code == 200
            nums.append(r.json()["record_number"])
        # Extract sequence
        seqs = [int(n.split("-")[-1]) for n in nums]
        assert seqs[1] == seqs[0] + 1
        assert seqs[2] == seqs[1] + 1
        # Year is 2026
        for n in nums:
            assert "-2026-" in n

    def test_patch_record_audits_old_new(self, admin_session):
        c = admin_session.post(f"{API}/records", json={
            "type": "CAPA", "title": "TEST_ patch source", "description": "before"
        })
        rid = c.json()["id"]
        r = admin_session.patch(f"{API}/records/{rid}", json={"title": "TEST_ patch updated", "reason": "fix typo"})
        assert r.status_code == 200
        assert r.json()["title"] == "TEST_ patch updated"
        a = admin_session.get(f"{API}/records/{rid}/audit")
        update_entries = [e for e in a.json() if e["action"] == "UPDATE"]
        assert len(update_entries) >= 1
        ue = update_entries[0]
        assert ue["old_value"].get("title") == "TEST_ patch source"
        assert ue["new_value"].get("title") == "TEST_ patch updated"

    def test_get_nonexistent_record_404(self, admin_session):
        r = admin_session.get(f"{API}/records/nonexistent-id-{uuid.uuid4()}")
        assert r.status_code == 404


# ---------------- Workflow / E-signature ----------------
class TestWorkflow:
    @pytest.fixture
    def fresh_record(self, admin_session):
        r = admin_session.post(f"{API}/records", json={
            "type": "INCIDENT", "title": f"TEST_ wf {uuid.uuid4().hex[:6]}", "description": "wf"
        })
        assert r.status_code == 200
        return r.json()

    def test_esign_invalid_password_returns_401_and_audits(self, admin_session, fresh_record):
        rid = fresh_record["id"]
        r = admin_session.post(f"{API}/records/{rid}/action", json={
            "password": "WRONG",
            "reason": "trying to review",
            "action": "REVIEW",
        })
        assert r.status_code == 401
        a = admin_session.get(f"{API}/records/{rid}/audit")
        actions = [e["action"] for e in a.json()]
        assert "ESIGN_FAILED" in actions

    def test_full_workflow_open_review_approve_close(self, admin_session, fresh_record):
        rid = fresh_record["id"]
        # REVIEW (OPEN -> IN_REVIEW)
        r1 = admin_session.post(f"{API}/records/{rid}/action", json={
            "password": ADMIN_PASSWORD, "reason": "Initial review", "action": "REVIEW"
        })
        assert r1.status_code == 200, r1.text
        assert r1.json()["record"]["status"] == "IN_REVIEW"
        # APPROVE
        r2 = admin_session.post(f"{API}/records/{rid}/action", json={
            "password": ADMIN_PASSWORD, "reason": "Approving", "action": "APPROVE"
        })
        assert r2.status_code == 200
        assert r2.json()["record"]["status"] == "APPROVED"
        # CLOSE
        r3 = admin_session.post(f"{API}/records/{rid}/action", json={
            "password": ADMIN_PASSWORD, "reason": "Closing", "action": "CLOSE"
        })
        assert r3.status_code == 200
        assert r3.json()["record"]["status"] == "CLOSED"
        # Workflow events
        wf = admin_session.get(f"{API}/records/{rid}/workflow")
        assert wf.status_code == 200
        events = wf.json()
        actions = [e["action"] for e in events]
        assert actions == ["REVIEW", "APPROVE", "CLOSE"]
        # Audit
        a = admin_session.get(f"{API}/records/{rid}/audit")
        audit_actions = [e["action"] for e in a.json()]
        for needed in ("WORKFLOW_REVIEW", "WORKFLOW_APPROVE", "WORKFLOW_CLOSE"):
            assert needed in audit_actions

    def test_reject_then_reopen(self, admin_session, fresh_record):
        rid = fresh_record["id"]
        admin_session.post(f"{API}/records/{rid}/action", json={
            "password": ADMIN_PASSWORD, "reason": "to review", "action": "REVIEW"
        })
        r = admin_session.post(f"{API}/records/{rid}/action", json={
            "password": ADMIN_PASSWORD, "reason": "not enough info", "action": "REJECT"
        })
        assert r.status_code == 200
        assert r.json()["record"]["status"] == "REJECTED"
        r2 = admin_session.post(f"{API}/records/{rid}/action", json={
            "password": ADMIN_PASSWORD, "reason": "more info added", "action": "REOPEN"
        })
        assert r2.status_code == 200
        assert r2.json()["record"]["status"] == "OPEN"

    def test_reviewer_only_user_cannot_approve(self, admin_session, reviewer_session):
        # Create record via admin
        c = admin_session.post(f"{API}/records", json={
            "type": "EVENT", "title": "TEST_ reviewer approve test", "description": "x"
        })
        rid = c.json()["id"]
        # Reviewer (no approver role) tries to APPROVE directly => 403
        r = reviewer_session.post(f"{API}/records/{rid}/action", json={
            "password": REVIEWER_PASSWORD, "reason": "trying to approve", "action": "APPROVE"
        })
        assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


# ---------------- Comments ----------------
class TestComments:
    def test_add_and_list_comments(self, admin_session):
        c = admin_session.post(f"{API}/records", json={
            "type": "EVENT", "title": "TEST_ comments", "description": "x"
        })
        rid = c.json()["id"]
        ac = admin_session.post(f"{API}/records/{rid}/comments", json={"body": "First comment"})
        assert ac.status_code == 200
        assert ac.json()["body"] == "First comment"
        lc = admin_session.get(f"{API}/records/{rid}/comments")
        assert lc.status_code == 200
        bodies = [c["body"] for c in lc.json()]
        assert "First comment" in bodies


# ---------------- Users mgmt ----------------
class TestUsers:
    def test_list_users_no_password_hash(self, admin_session):
        r = admin_session.get(f"{API}/users")
        assert r.status_code == 200
        users = r.json()
        assert len(users) >= 4
        for u in users:
            assert "password_hash" not in u

    def test_patch_user_as_admin_audits(self, admin_session):
        users = admin_session.get(f"{API}/users").json()
        target = next(u for u in users if u["email"] == REVIEWER_EMAIL)
        original_dept = target.get("department")
        new_dept = f"TestDept-{uuid.uuid4().hex[:4]}"
        r = admin_session.patch(f"{API}/users/{target['id']}", json={"department": new_dept, "reason": "test update"})
        assert r.status_code == 200
        assert r.json()["department"] == new_dept
        # Restore
        admin_session.patch(f"{API}/users/{target['id']}", json={"department": original_dept, "reason": "restore"})

    def test_patch_user_as_non_admin_403(self, reviewer_session):
        # Get a user id
        users = reviewer_session.get(f"{API}/users").json()
        tid = users[0]["id"]
        r = reviewer_session.patch(f"{API}/users/{tid}", json={"department": "X"})
        assert r.status_code == 403


# ---------------- Audit global ----------------
class TestAuditGlobal:
    def test_audit_filters(self, admin_session):
        r = admin_session.get(f"{API}/audit", params={"entity_type": "RECORD", "action": "CREATE", "limit": 50})
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        for row in rows:
            assert row["entity_type"] == "RECORD"
            assert row["action"] == "CREATE"

    def test_audit_filter_by_email(self, admin_session):
        r = admin_session.get(f"{API}/audit", params={"user_email": ADMIN_EMAIL, "limit": 20})
        assert r.status_code == 200
        for row in r.json():
            assert row["user_email"] == ADMIN_EMAIL
