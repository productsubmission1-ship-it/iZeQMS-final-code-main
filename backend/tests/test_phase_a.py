"""
izQMS Phase A backend tests — User Management overhaul + 21 CFR Part 11.
Covers:
  * POST /api/users (admin/qa_head only, e-sig, temp password)
  * Duplicate email/username
  * GET /api/users expanded payload
  * User actions: activate, deactivate, lock, unlock, reset-password,
    extend-expiry, approve, reject — all e-sig guarded, RBAC enforced
  * Reset-password forces must_change_password + token_revoked_at
  * /auth/change-password — current pw, reuse rejection, policy, clears flag
  * /auth/forgot-password — always 200
  * /settings/password-policy GET/PATCH (admin only)
  * /sessions list + revoke (admin only)
  * /notifications list, read, read-all
  * Login on locked/deactivated/non-ACTIVE user → 403
  * Failed login increments failed_login_count + LOGIN_FAILED audit
  * Successful login resets failed_login_count, sets last_login
  * /records/draft creates DRAFT with auto record_number
  * /users/{id}/audit returns entity_id/user_id matched entries
"""
import os
import time
import uuid
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

ADMIN = ("admin@izqms.com", "Admin@izQMS2026")
QA_HEAD = ("qa.head@izqms.com", "QaHead@2026")
REVIEWER = ("reviewer@izqms.com", "Reviewer@2026")
INITIATOR = ("initiator@izqms.com", "Initiator@2026")


# ---------------- Helpers ----------------
def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    s.token = data["access_token"]
    s.user = data["user"]
    return s


def _esign(password, reason, **extra):
    body = {"esign_password": password, "esign_reason": reason}
    if extra:
        body["extra"] = extra
    return body


def _rand_suffix():
    return uuid.uuid4().hex[:8]


# ---------------- Session fixtures ----------------
@pytest.fixture(scope="session")
def admin_s():
    return _login(*ADMIN)


@pytest.fixture(scope="session")
def qa_head_s():
    return _login(*QA_HEAD)


@pytest.fixture(scope="session")
def initiator_s():
    return _login(*INITIATOR)


# ---------------- Helper to provision a fresh user ----------------
def _create_user(admin_s, **overrides):
    suffix = _rand_suffix()
    body = {
        "name": overrides.get("name", f"TEST User {suffix}"),
        "email": overrides.get("email", f"test_{suffix}@izqms.com"),
        "employee_id": overrides.get("employee_id", f"EMP-T{suffix[:5]}"),
        "username": overrides.get("username", f"test_{suffix}"),
        "department": overrides.get("department", "QA"),
        "location": overrides.get("location", "HQ"),
        "roles": overrides.get("roles", ["initiator"]),
        "user_type": overrides.get("user_type", "Employee"),
        "access_level": overrides.get("access_level", "Full"),
        "requires_approval": overrides.get("requires_approval", False),
        "esign_password": ADMIN[1],
        "esign_reason": overrides.get("esign_reason", "Test provisioning"),
    }
    if "password" in overrides:
        body["password"] = overrides["password"]
    if "expiry_date" in overrides:
        body["expiry_date"] = overrides["expiry_date"]
    r = admin_s.post(f"{API}/users", json=body)
    return r


# =====================================================================
# User creation
# =====================================================================
class TestUserCreate:
    def test_admin_creates_user_with_temp_password(self, admin_s):
        r = _create_user(admin_s)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "user" in data and "temp_password" in data
        assert data["temp_password"] and len(data["temp_password"]) >= 8
        u = data["user"]
        # Expanded fields
        for k in ("id", "employee_id", "username", "email", "user_type",
                  "access_level", "last_login", "failed_login_count",
                  "approval_status", "locked", "must_change_password"):
            assert k in u, f"missing field {k} in user response"
        assert u["approval_status"] == "ACTIVE"  # admin bypasses approval
        assert u["must_change_password"] is True
        assert u["failed_login_count"] == 0

    def test_admin_creates_user_with_given_password_no_temp(self, admin_s):
        r = _create_user(admin_s, password="StrongPass@2026")
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("temp_password") is None

    def test_duplicate_email_returns_400(self, admin_s):
        r1 = _create_user(admin_s)
        assert r1.status_code == 200
        email = r1.json()["user"]["email"]
        # same email different username
        suffix = _rand_suffix()
        r2 = _create_user(admin_s, email=email, username=f"u_{suffix}",
                          employee_id=f"EMP-{suffix}")
        assert r2.status_code == 400
        assert "Email" in r2.text or "email" in r2.text

    def test_duplicate_username_returns_400(self, admin_s):
        r1 = _create_user(admin_s)
        assert r1.status_code == 200
        username = r1.json()["user"]["username"]
        suffix = _rand_suffix()
        r2 = _create_user(admin_s, username=username,
                          email=f"u_{suffix}@izqms.com",
                          employee_id=f"EMP-{suffix}")
        assert r2.status_code == 400

    def test_initiator_cannot_create_user(self, initiator_s):
        r = _create_user(initiator_s)
        assert r.status_code == 403

    def test_wrong_esign_password_returns_401(self, admin_s):
        suffix = _rand_suffix()
        body = {
            "name": f"TEST {suffix}", "email": f"t_{suffix}@izqms.com",
            "employee_id": f"EMP-{suffix}", "username": f"u_{suffix}",
            "department": "QA", "location": "HQ", "roles": ["initiator"],
            "esign_password": "wrong-password",
            "esign_reason": "Trying with wrong pw",
        }
        r = admin_s.post(f"{API}/users", json=body)
        assert r.status_code == 401


# =====================================================================
# GET /api/users payload
# =====================================================================
class TestUserList:
    def test_get_users_expanded_fields(self, admin_s):
        r = admin_s.get(f"{API}/users")
        assert r.status_code == 200
        users = r.json()
        assert isinstance(users, list) and len(users) > 0
        sample = users[0]
        for k in ("id", "email", "employee_id", "username", "user_type",
                  "access_level", "last_login", "failed_login_count",
                  "approval_status", "locked"):
            assert k in sample, f"missing {k} in list users"


# =====================================================================
# User actions (activate/deactivate/lock/unlock/reset/extend/approve/reject)
# =====================================================================
class TestUserActions:
    @pytest.fixture
    def target_user(self, admin_s):
        r = _create_user(admin_s)
        assert r.status_code == 200
        return r.json()["user"]

    def test_initiator_cannot_call_actions(self, initiator_s, target_user):
        uid = target_user["id"]
        body = _esign(INITIATOR[1], "Trying without permission")
        for ep in ("activate", "deactivate", "lock", "unlock",
                   "approve", "reject", "reset-password"):
            r = initiator_s.post(f"{API}/users/{uid}/{ep}", json=body)
            assert r.status_code == 403, f"{ep} should be 403 for initiator, got {r.status_code}"

    def test_wrong_esign_returns_401_and_audits_esign_failed(self, admin_s, target_user):
        uid = target_user["id"]
        body = _esign("bad-password", "wrong pw test")
        r = admin_s.post(f"{API}/users/{uid}/deactivate", json=body)
        assert r.status_code == 401
        # Check audit
        r2 = admin_s.get(f"{API}/users/{uid}/audit")
        assert r2.status_code == 200
        actions = [a.get("action") for a in r2.json()]
        assert "ESIGN_FAILED" in actions

    def test_deactivate_then_activate(self, admin_s, target_user):
        uid = target_user["id"]
        body = _esign(ADMIN[1], "Deactivate test")
        r = admin_s.post(f"{API}/users/{uid}/deactivate", json=body)
        assert r.status_code == 200
        assert r.json()["active"] is False
        # Activate
        r2 = admin_s.post(f"{API}/users/{uid}/activate",
                          json=_esign(ADMIN[1], "Reactivate"))
        assert r2.status_code == 200
        assert r2.json()["active"] is True

    def test_lock_then_unlock(self, admin_s, target_user):
        uid = target_user["id"]
        r = admin_s.post(f"{API}/users/{uid}/lock",
                         json=_esign(ADMIN[1], "Lock test"))
        assert r.status_code == 200
        assert r.json()["locked"] is True
        r2 = admin_s.post(f"{API}/users/{uid}/unlock",
                          json=_esign(ADMIN[1], "Unlock test"))
        assert r2.status_code == 200
        assert r2.json()["locked"] is False
        assert r2.json().get("failed_login_count", 0) == 0

    def test_extend_expiry(self, admin_s, target_user):
        uid = target_user["id"]
        new_date = "2030-12-31T00:00:00"
        body = _esign(ADMIN[1], "Extend expiry", expiry_date=new_date)
        r = admin_s.post(f"{API}/users/{uid}/extend-expiry", json=body)
        assert r.status_code == 200
        assert r.json()["expiry_date"] == new_date

    def test_extend_expiry_missing_date_returns_400(self, admin_s, target_user):
        uid = target_user["id"]
        body = _esign(ADMIN[1], "Extend expiry no date")
        r = admin_s.post(f"{API}/users/{uid}/extend-expiry", json=body)
        assert r.status_code == 400

    def test_reject_user(self, admin_s):
        # Create a user that requires approval (qa_head creates → PENDING_QA)
        qa = _login(*QA_HEAD)
        suffix = _rand_suffix()
        body = {
            "name": f"TEST Approve {suffix}",
            "email": f"appr_{suffix}@izqms.com",
            "employee_id": f"EMP-A{suffix[:5]}",
            "username": f"appr_{suffix}",
            "department": "QA", "location": "HQ", "roles": ["initiator"],
            "requires_approval": True,
            "esign_password": QA_HEAD[1],
            "esign_reason": "create pending user",
        }
        r = qa.post(f"{API}/users", json=body)
        assert r.status_code == 200, r.text
        uid = r.json()["user"]["id"]
        # admin rejects
        rj = admin_s.post(f"{API}/users/{uid}/reject",
                          json=_esign(ADMIN[1], "Reject this user"))
        assert rj.status_code == 200
        assert rj.json()["approval_status"] == "REJECTED"
        assert rj.json()["active"] is False


# =====================================================================
# Reset password forces re-login flow
# =====================================================================
class TestResetPasswordFlow:
    def test_reset_returns_temp_and_forces_must_change(self, admin_s):
        # Create target with known password and log it in
        r = _create_user(admin_s, password="OldPass@2026")
        assert r.status_code == 200
        u = r.json()["user"]
        email = u["email"]
        uid = u["id"]

        # First login (must change pw is True from creation), so do change pw to clear
        sess = _login(email, "OldPass@2026")
        cp = sess.post(f"{API}/auth/change-password", json={
            "current_password": "OldPass@2026",
            "new_password": "FreshPass@2026!",
        })
        assert cp.status_code == 200
        # Re-login with new password to get a stable token (must_change_password=False)
        sess = _login(email, "FreshPass@2026!")
        old_token = sess.token

        # Admin resets
        rr = admin_s.post(f"{API}/users/{uid}/reset-password",
                          json=_esign(ADMIN[1], "Admin reset"))
        assert rr.status_code == 200
        temp = rr.json()["temp_password"]
        assert temp and len(temp) >= 8

        # Confirm flag on user
        gu = admin_s.get(f"{API}/users/{uid}")
        assert gu.status_code == 200
        assert gu.json()["must_change_password"] is True

        # Old token must be revoked
        time.sleep(1.5)  # allow iso second-precision to tick past iat
        old_sess = requests.Session()
        old_sess.headers.update({"Authorization": f"Bearer {old_token}"})
        me = old_sess.get(f"{API}/auth/me")
        assert me.status_code == 401, f"old token should be revoked, got {me.status_code}"

        # Login with temp password works
        new_sess = _login(email, temp)
        assert new_sess.user["must_change_password"] is True


# =====================================================================
# change-password
# =====================================================================
class TestChangePassword:
    def test_change_password_flow(self, admin_s):
        r = _create_user(admin_s, password="InitPass@2026")
        email = r.json()["user"]["email"]
        sess = _login(email, "InitPass@2026")

        # Wrong current
        b = sess.post(f"{API}/auth/change-password", json={
            "current_password": "wrong", "new_password": "NewPass@2026!",
        })
        assert b.status_code == 401

        # Too short (policy default 8)
        b = sess.post(f"{API}/auth/change-password", json={
            "current_password": "InitPass@2026", "new_password": "short",
        })
        assert b.status_code == 400

        # OK
        ok = sess.post(f"{API}/auth/change-password", json={
            "current_password": "InitPass@2026",
            "new_password": "NewPass@2026!",
        })
        assert ok.status_code == 200

        # Reuse the prior password → 400
        sess = _login(email, "NewPass@2026!")
        reuse = sess.post(f"{API}/auth/change-password", json={
            "current_password": "NewPass@2026!",
            "new_password": "InitPass@2026",
        })
        assert reuse.status_code == 400


# =====================================================================
# forgot-password (no enumeration)
# =====================================================================
class TestForgotPassword:
    def test_existing_email_returns_200(self):
        r = requests.post(f"{API}/auth/forgot-password",
                          json={"email": ADMIN[0]})
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_nonexisting_email_also_returns_200(self):
        r = requests.post(f"{API}/auth/forgot-password",
                          json={"email": "nobody-xyz@nowhere.io"})
        assert r.status_code == 200


# =====================================================================
# Password policy
# =====================================================================
class TestPasswordPolicy:
    def test_get_policy(self, admin_s):
        r = admin_s.get(f"{API}/settings/password-policy")
        assert r.status_code == 200
        assert isinstance(r.json(), dict)

    def test_patch_policy_admin_only(self, admin_s, initiator_s):
        # Init not allowed
        r0 = initiator_s.patch(f"{API}/settings/password-policy",
                               json={"min_length": 8})
        assert r0.status_code == 403

        # Admin OK
        r = admin_s.patch(f"{API}/settings/password-policy",
                         json={"min_length": 10, "require_upper": True})
        assert r.status_code == 200
        assert r.json().get("min_length") == 10
        # Restore
        admin_s.patch(f"{API}/settings/password-policy",
                      json={"min_length": 8})


# =====================================================================
# Sessions
# =====================================================================
class TestSessions:
    def test_list_sessions_admin_only(self, admin_s, initiator_s):
        r1 = initiator_s.get(f"{API}/sessions")
        assert r1.status_code == 403
        r2 = admin_s.get(f"{API}/sessions")
        assert r2.status_code == 200
        assert isinstance(r2.json(), list)

    def test_revoke_session_invalidates_token(self, admin_s):
        # Create user with known pw, login as that user
        r = _create_user(admin_s, password="RevokePass@2026")
        u = r.json()["user"]
        email = u["email"]
        uid = u["id"]
        # change pw so must_change_password=False
        s0 = _login(email, "RevokePass@2026")
        s0.post(f"{API}/auth/change-password", json={
            "current_password": "RevokePass@2026",
            "new_password": "RevokePass@2026X",
        })
        s = _login(email, "RevokePass@2026X")
        token = s.token

        # Revoke
        rv = admin_s.post(f"{API}/sessions/{uid}/revoke",
                          json=_esign(ADMIN[1], "Forced logout"))
        assert rv.status_code == 200
        time.sleep(1.5)
        # Old token should fail
        sess = requests.Session()
        sess.headers.update({"Authorization": f"Bearer {token}"})
        me = sess.get(f"{API}/auth/me")
        assert me.status_code == 401


# =====================================================================
# Notifications
# =====================================================================
class TestNotifications:
    def test_list_and_mark_read(self, admin_s):
        # Provision a user → admin gets no notification, target user gets account-* on actions
        r = _create_user(admin_s)
        uid = r.json()["user"]["id"]
        email = r.json()["user"]["email"]

        # Trigger a deactivate to create a notification for target user
        admin_s.post(f"{API}/users/{uid}/deactivate",
                     json=_esign(ADMIN[1], "notification gen"))

        # change-password so target user can login (need active)
        admin_s.post(f"{API}/users/{uid}/activate",
                     json=_esign(ADMIN[1], "reactivate"))
        # Reset & change pw
        rp = admin_s.post(f"{API}/users/{uid}/reset-password",
                          json=_esign(ADMIN[1], "set pw"))
        temp = rp.json()["temp_password"]
        sess = _login(email, temp)
        sess.post(f"{API}/auth/change-password", json={
            "current_password": temp, "new_password": "Strong@2026Pass",
        })
        sess = _login(email, "Strong@2026Pass")

        ln = sess.get(f"{API}/notifications")
        assert ln.status_code == 200
        body = ln.json()
        assert "items" in body and "unread" in body
        assert isinstance(body["items"], list)
        # Find first unread item if any
        unread_items = [i for i in body["items"] if not i.get("read")]
        if unread_items:
            nid = unread_items[0]["id"]
            mk = sess.post(f"{API}/notifications/{nid}/read")
            assert mk.status_code == 200

        # mark-all-read
        all_r = sess.post(f"{API}/notifications/read-all")
        assert all_r.status_code == 200
        after = sess.get(f"{API}/notifications").json()
        assert after["unread"] == 0


# =====================================================================
# Login gates
# =====================================================================
class TestLoginGates:
    def test_login_locked_user_returns_403(self, admin_s):
        r = _create_user(admin_s, password="LockTest@2026")
        u = r.json()["user"]
        admin_s.post(f"{API}/users/{u['id']}/lock",
                     json=_esign(ADMIN[1], "lock"))
        r2 = requests.post(f"{API}/auth/login",
                           json={"email": u["email"], "password": "LockTest@2026"})
        assert r2.status_code == 403
        assert "locked" in r2.text.lower()

    def test_login_deactivated_user_returns_403(self, admin_s):
        r = _create_user(admin_s, password="DeactTest@2026")
        u = r.json()["user"]
        admin_s.post(f"{API}/users/{u['id']}/deactivate",
                     json=_esign(ADMIN[1], "deactivate"))
        r2 = requests.post(f"{API}/auth/login",
                           json={"email": u["email"], "password": "DeactTest@2026"})
        assert r2.status_code == 403
        assert "deactivat" in r2.text.lower()

    def test_login_pending_approval_returns_403(self):
        qa = _login(*QA_HEAD)
        suffix = _rand_suffix()
        body = {
            "name": f"TEST Pending {suffix}",
            "email": f"pend_{suffix}@izqms.com",
            "employee_id": f"EMP-P{suffix[:5]}",
            "username": f"pend_{suffix}",
            "department": "QA", "location": "HQ", "roles": ["initiator"],
            "password": "Pending@2026!",
            "requires_approval": True,
            "esign_password": QA_HEAD[1],
            "esign_reason": "pending approval user",
        }
        rc = qa.post(f"{API}/users", json=body)
        assert rc.status_code == 200, rc.text
        u = rc.json()["user"]
        assert u["approval_status"] != "ACTIVE"
        r2 = requests.post(f"{API}/auth/login",
                           json={"email": u["email"], "password": "Pending@2026!"})
        assert r2.status_code == 403

    def test_failed_login_increments_counter_and_audits(self, admin_s):
        r = _create_user(admin_s, password="CountPass@2026")
        u = r.json()["user"]
        # Wrong pw 2 times
        for _ in range(2):
            requests.post(f"{API}/auth/login",
                          json={"email": u["email"], "password": "wrong"})
        gu = admin_s.get(f"{API}/users/{u['id']}")
        assert gu.status_code == 200
        assert gu.json().get("failed_login_count", 0) >= 2

        # Audit has LOGIN_FAILED
        au = admin_s.get(f"{API}/users/{u['id']}/audit")
        assert au.status_code == 200
        actions = [a.get("action") for a in au.json()]
        assert "LOGIN_FAILED" in actions

    def test_successful_login_resets_counter_and_sets_last_login(self, admin_s):
        r = _create_user(admin_s, password="GoodPass@2026")
        u = r.json()["user"]
        requests.post(f"{API}/auth/login",
                      json={"email": u["email"], "password": "wrong"})
        ok = requests.post(f"{API}/auth/login",
                          json={"email": u["email"], "password": "GoodPass@2026"})
        assert ok.status_code == 200
        gu = admin_s.get(f"{API}/users/{u['id']}")
        body = gu.json()
        assert body["failed_login_count"] == 0
        assert body["last_login"] is not None


# =====================================================================
# Drafts
# =====================================================================
class TestDraft:
    def test_create_draft(self, initiator_s):
        body = {
            "type": "CAPA",
            "title": "TEST Draft CAPA",
            "description": "draft body",
            "department": "QA", "location": "HQ",
            "severity": "MINOR", "priority": "LOW",
        }
        r = initiator_s.post(f"{API}/records/draft", json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "DRAFT"
        assert d["workflow_stage"] == "DRAFT"
        assert d["record_number"] and "-" in d["record_number"]
        assert d["initiator_id"] == initiator_s.user["id"]


# =====================================================================
# User audit
# =====================================================================
class TestUserAudit:
    def test_user_audit_returns_entries_sorted_desc(self, admin_s):
        r = _create_user(admin_s)
        uid = r.json()["user"]["id"]
        admin_s.post(f"{API}/users/{uid}/deactivate",
                     json=_esign(ADMIN[1], "audit test 1"))
        admin_s.post(f"{API}/users/{uid}/activate",
                     json=_esign(ADMIN[1], "audit test 2"))
        au = admin_s.get(f"{API}/users/{uid}/audit")
        assert au.status_code == 200
        rows = au.json()
        assert isinstance(rows, list) and len(rows) >= 3
        # sorted desc by timestamp
        ts = [r.get("timestamp") for r in rows if r.get("timestamp")]
        assert ts == sorted(ts, reverse=True)
        # at least one row has entity_id == uid
        assert any(r.get("entity_id") == uid for r in rows)
