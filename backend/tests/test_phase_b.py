"""
izQMS Phase B + Deviation Module backend tests.
Covers: attachments, exports (CSV/XLSX/audit), form-schemas, risk-score,
reports/trend, reports/aging, password-reset consume, deviation 9-part flow,
deviation extensions/department-comments/sign/pdf.
"""
import io
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
QA = ("qa.head@izqms.com", "QaHead@2026")


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email} failed: {r.text}"
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['access_token']}"})
    s.token = data["access_token"]
    s.user = data["user"]
    return s


def _esign(pw, reason, **extra):
    body = {"esign_password": pw, "esign_reason": reason}
    if extra:
        body["extra"] = extra
    return body


@pytest.fixture(scope="session")
def admin_s():
    return _login(*ADMIN)


@pytest.fixture(scope="session")
def qa_s():
    return _login(*QA)


def _create_record(admin_s, type_="DEVIATION", title=None):
    payload = {
        "type": type_,
        "title": title or f"TEST_PhB {type_} {uuid.uuid4().hex[:6]}",
        "description": "PhB test record",
        "severity": "Low",
        "priority": "Low",
    }
    r = admin_s.post(f"{API}/records", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------- Attachments -------------------
class TestAttachments:
    def test_upload_list_download_delete(self, admin_s):
        rec = _create_record(admin_s)
        rid = rec["id"]

        files = {"file": ("test.txt", b"hello izqms phase B", "text/plain")}
        up = admin_s.post(f"{API}/records/{rid}/attachments", files=files)
        assert up.status_code == 200, up.text
        att = up.json()
        assert "id" in att
        aid = att["id"]

        ls = admin_s.get(f"{API}/records/{rid}/attachments")
        assert ls.status_code == 200
        items = ls.json()
        assert any(a["id"] == aid for a in items)

        dn = admin_s.get(f"{API}/attachments/{aid}/download")
        assert dn.status_code == 200
        assert b"hello izqms phase B" in dn.content

        de = admin_s.delete(f"{API}/attachments/{aid}",
                            json={"reason": "test cleanup"})
        assert de.status_code in (200, 204), de.text

        # audit trail - actions logged under entity_type=RECORD
        au = admin_s.get(f"{API}/audit", params={"limit": 200})
        actions = [a["action"] for a in au.json()]
        assert "ATTACHMENT_UPLOAD" in actions
        assert "ATTACHMENT_DOWNLOAD" in actions
        assert "ATTACHMENT_DELETE" in actions


# ------------------- Exports -------------------
class TestExports:
    def test_records_csv(self, admin_s):
        r = admin_s.get(f"{API}/exports/records.csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "").lower() or len(r.content) > 0
        assert b"record_number" in r.content or b"," in r.content

    def test_records_xlsx(self, admin_s):
        r = admin_s.get(f"{API}/exports/records.xlsx")
        assert r.status_code == 200
        # XLSX starts with PK (zip)
        assert r.content[:2] == b"PK", f"Expected XLSX zip header, got {r.content[:10]}"

    def test_audit_csv(self, admin_s):
        r = admin_s.get(f"{API}/exports/audit.csv")
        assert r.status_code == 200
        assert len(r.content) > 0

    def test_export_audits_emitted(self, admin_s):
        admin_s.get(f"{API}/exports/records.csv")
        admin_s.get(f"{API}/exports/records.xlsx")
        admin_s.get(f"{API}/exports/audit.csv")
        au = admin_s.get(f"{API}/audit", params={"limit": 200})
        actions = [a["action"] for a in au.json()]
        # At least one of the export audits should fire
        assert any(x in actions for x in
                   ("EXPORT_RECORDS_CSV", "EXPORT_RECORDS_XLSX", "EXPORT_AUDIT_CSV"))


# ------------------- Form Builder -------------------
class TestFormSchemas:
    def test_list_and_update(self, admin_s):
        r = admin_s.get(f"{API}/form-schemas")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

        new_fields = [
            {"key": "root_cause", "label": "Root Cause", "type": "text", "required": True},
            {"key": "severity_band", "label": "Severity", "type": "select",
             "options": ["Low", "Medium", "High"]},
        ]
        up = admin_s.put(f"{API}/form-schemas/DEVIATION",
                        json={"module": "DEVIATION", "fields": new_fields,
                              "reason": "PhB test schema"})
        assert up.status_code == 200, up.text
        # GET back
        g = admin_s.get(f"{API}/form-schemas/DEVIATION")
        assert g.status_code == 200
        body = g.json()
        keys = [f["key"] for f in body.get("fields", [])]
        assert "root_cause" in keys

        au = admin_s.get(f"{API}/audit", params={"action": "FORM_SCHEMA_UPDATE", "limit": 5})
        assert au.status_code == 200
        assert len(au.json()) >= 1


# ------------------- Risk Score -------------------
class TestRiskScore:
    def test_compute_rpn(self, admin_s):
        rec = _create_record(admin_s)
        rid = rec["id"]
        r = admin_s.post(f"{API}/records/{rid}/risk-score",
                        json={"severity": 5, "occurrence": 4, "detection": 3})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("rpn") == 60
        assert "band" in d

    def test_invalid_range_returns_400_or_422(self, admin_s):
        rec = _create_record(admin_s)
        rid = rec["id"]
        r = admin_s.post(f"{API}/records/{rid}/risk-score",
                        json={"severity": 9, "occurrence": 1, "detection": 1})
        assert r.status_code in (400, 422)


# ------------------- Reports charts -------------------
class TestReports:
    def test_trend(self, admin_s):
        r = admin_s.get(f"{API}/reports/trend", params={"months": 6})
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("buckets", "by_type", "closed_per_month"):
            assert k in d, f"missing key {k}"

    def test_aging(self, admin_s):
        r = admin_s.get(f"{API}/reports/aging")
        assert r.status_code == 200
        d = r.json()
        for k in ("bands", "by_type"):
            assert k in d


# ------------------- Reset password CONSUME -------------------
class TestPasswordResetConsume:
    def test_forgot_then_reset_via_token(self, admin_s):
        # Create user with known pw
        suffix = uuid.uuid4().hex[:8]
        body = {
            "name": f"TEST PR {suffix}",
            "email": f"pr_{suffix}@izqms.com",
            "employee_id": f"EMP-PR{suffix[:5]}",
            "username": f"pr_{suffix}",
            "department": "QA", "location": "HQ", "roles": ["initiator"],
            "password": "PRStart@2026",
            "requires_approval": False,
            "esign_password": ADMIN[1],
            "esign_reason": "pr test",
        }
        cr = admin_s.post(f"{API}/users", json=body)
        assert cr.status_code == 200, cr.text
        user_id = cr.json()["user"]["id"]
        email = cr.json()["user"]["email"]
        # forgot
        fr = requests.post(f"{API}/auth/forgot-password", json={"email": email})
        assert fr.status_code == 200
        # Retrieve token from db via direct mongo
        import pymongo
        cli = pymongo.MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = cli[os.environ.get("DB_NAME", "izqms_database")]
        tok = db.password_reset_tokens.find_one({"user_id": user_id}, sort=[("created_at", -1)])
        if not tok:
            pytest.skip("password_reset_tokens not stored — cannot test consume")
        token = tok.get("token")
        assert token, f"token field missing in record: {tok}"
        rr = requests.post(f"{API}/auth/reset-password",
                          json={"token": token, "new_password": "NewPR@2026!"})
        assert rr.status_code == 200, f"reset-password failed: {rr.status_code} {rr.text}"
        # login with new pw
        ln = requests.post(f"{API}/auth/login",
                          json={"email": email, "password": "NewPR@2026!"})
        assert ln.status_code == 200


# ------------------- Deviation 9-Part flow -------------------
class TestDeviationFlow:
    @pytest.fixture(scope="class")
    def dev(self, admin_s):
        r = admin_s.post(f"{API}/records", json={
            "type": "DEVIATION",
            "title": "TEST_PhB DEV 9-Part",
            "description": "PhB deviation flow",
            "severity": "Low", "priority": "Low",
        })
        assert r.status_code == 200, r.text
        rec = r.json()
        assert rec["record_number"].startswith("DEV-")
        return rec

    def test_part1_to_open(self, admin_s, dev):
        rid = dev["id"]
        up = admin_s.put(f"{API}/deviations/{rid}/parts",
                        json={"part": "part1", "data": {"title_of_deviation": "Temp excursion",
                                                          "reported_by": "admin"}})
        assert up.status_code == 200, up.text
        # sign part1
        sg = admin_s.post(f"{API}/deviations/{rid}/sign",
                         json={"block": "part1_reviewed_by",
                               "password": ADMIN[1], "reason": "Part1 review"})
        assert sg.status_code == 200, sg.text
        g = admin_s.get(f"{API}/records/{rid}")
        assert g.json()["status"] == "OPEN"

    def test_part6_to_in_review(self, admin_s, dev):
        rid = dev["id"]
        admin_s.put(f"{API}/deviations/{rid}/parts",
                   json={"part": "part6", "data": {"capa_required": True,
                                                     "capa_description": "Calibrate"}})
        sg = admin_s.post(f"{API}/deviations/{rid}/sign",
                         json={"block": "part6_reviewed_by",
                               "password": ADMIN[1], "reason": "Part6 review"})
        assert sg.status_code == 200, sg.text
        g = admin_s.get(f"{API}/records/{rid}")
        assert g.json()["status"] == "IN_REVIEW"

    def test_extension_and_dept_comment(self, admin_s, dev):
        rid = dev["id"]
        ex = admin_s.post(f"{API}/deviations/{rid}/extensions",
                        json={"revised_target_date": "2030-12-31",
                              "justification": "Need more data for investigation",
                              "reason": "extension request"})
        assert ex.status_code == 200, ex.text

        dc = admin_s.post(f"{API}/deviations/{rid}/department-comments",
                        json={"department": "Engineering",
                              "comments": "Equipment under repair",
                              "reason": "dept input"})
        assert dc.status_code == 200, dc.text

    def test_part9_to_approved_then_closed(self, admin_s, dev):
        rid = dev["id"]
        admin_s.put(f"{API}/deviations/{rid}/parts",
                   json={"part": "part9", "data": {"qa_remarks": "Approved",
                                                     "closure_remarks": "Closed"}})
        # QA Review
        sg = admin_s.post(f"{API}/deviations/{rid}/sign",
                         json={"block": "part9_qa_reviewed_by",
                               "password": ADMIN[1], "reason": "QA review"})
        assert sg.status_code == 200, sg.text
        g = admin_s.get(f"{API}/records/{rid}")
        assert g.json()["status"] == "APPROVED", f"got {g.json()['status']}"

        # QA Head Closure
        sg2 = admin_s.post(f"{API}/deviations/{rid}/sign",
                          json={"block": "part9_qa_head_closure",
                                "password": ADMIN[1], "reason": "QA head closure"})
        assert sg2.status_code == 200, sg2.text
        g2 = admin_s.get(f"{API}/records/{rid}")
        assert g2.json()["status"] == "CLOSED", f"got {g2.json()['status']}"

    def test_sign_wrong_password_401(self, admin_s):
        rec = _create_record(admin_s, type_="DEVIATION")
        rid = rec["id"]
        admin_s.put(f"{API}/deviations/{rid}/parts",
                   json={"part": "part1", "data": {"title_of_deviation": "x"}})
        r = admin_s.post(f"{API}/deviations/{rid}/sign",
                        json={"block": "part1_reviewed_by",
                              "password": "WRONG", "reason": "should fail"})
        assert r.status_code == 401

    def test_pdf_export(self, admin_s, dev):
        rid = dev["id"]
        r = admin_s.get(f"{API}/deviations/{rid}/pdf")
        assert r.status_code == 200, r.text[:200]
        assert r.content[:4] == b"%PDF", f"not a PDF: {r.content[:20]}"
        assert len(r.content) > 2048

    def test_audit_entries_for_dev_module(self, admin_s):
        au = admin_s.get(f"{API}/audit", params={"limit": 500})
        actions = {a["action"] for a in au.json()}
        for needed in ("DEVIATION_EDIT", "DEVIATION_SIGN",
                       "DEVIATION_EXTENSION_REQUEST",
                       "DEVIATION_DEPT_COMMENT",
                       "DEVIATION_PDF_EXPORT"):
            assert needed in actions, f"missing audit action: {needed}; have {sorted(actions)[:20]}"
