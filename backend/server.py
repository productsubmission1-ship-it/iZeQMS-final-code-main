from dotenv import load_dotenv
from pathlib import Path
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any, Dict
from contextlib import asynccontextmanager

import bcrypt
import jwt
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, ConfigDict
import uuid

# ---------------- DB ----------------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MIN = 60
REFRESH_TOKEN_DAYS = 7
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# ============================================================================
# USER ROLE MATRIX  (sourced from Recommended_User_Role_Matrix_izQMS.docx)
# ----------------------------------------------------------------------------
# Canonical hierarchy (top → bottom):
#   super_admin > admin > qa_manager > qa_reviewer > department_manager
#                                                  > employee_operator
#   auditor (read-only, transverse)
# ----------------------------------------------------------------------------
# Permission matrix (Yes / Limited / View / No):
#   create_record      : Employee, Reviewer, QA Manager, Admin, Super Admin = Yes
#   edit_draft         : Employee, Reviewer, QA Manager, Admin, Super Admin = Yes
#   review_record      : Reviewer, QA Manager, Admin, Super Admin           = Yes
#   approve_record     : QA Manager, Admin, Super Admin                     = Yes
#   reject_record      : Reviewer, QA Manager, Admin, Super Admin           = Yes
#   close_record       : QA Manager, Admin, Super Admin                     = Yes
#   view_reports       : Employee=Limited, Reviewer/QAM/Admin/SA            = Yes
#   export_reports     : Reviewer=Limited, QAM/Admin/SA                     = Yes
#   user_management    : Admin, Super Admin                                 = Yes
#   role_management    : Admin=Limited, Super Admin                         = Yes
#   workflow_config    : Admin=Limited, Super Admin                         = Yes
#   audit_trail_access : Reviewer/QAM=View, Admin/SA=Full, Auditor=View
#   department_manager : create records, review department records, assign tasks
#   auditor            : view audit trail / records / reports + export (read-only)
# ============================================================================

# Canonical role identifiers (these are the only role strings the system
# stores going forward; legacy strings are auto-expanded for back-compat).
ROLE_SUPER_ADMIN = "super_admin"
ROLE_ADMIN = "admin"
ROLE_QA_MANAGER = "qa_manager"
ROLE_QA_REVIEWER = "qa_reviewer"
ROLE_DEPARTMENT_MANAGER = "department_manager"
ROLE_EMPLOYEE = "employee_operator"
ROLE_AUDITOR = "auditor"

CANONICAL_ROLES = [
    ROLE_SUPER_ADMIN,
    ROLE_ADMIN,
    ROLE_QA_MANAGER,
    ROLE_QA_REVIEWER,
    ROLE_DEPARTMENT_MANAGER,
    ROLE_EMPLOYEE,
    ROLE_AUDITOR,
]

# Legacy role strings that may exist in older user docs / audit history.
# These are mapped to the canonical equivalents on read.
LEGACY_TO_CANONICAL = {
    "initiator": ROLE_EMPLOYEE,
    "reviewer": ROLE_QA_REVIEWER,
    "approver": ROLE_QA_MANAGER,
    "qa_head": ROLE_QA_MANAGER,
    # "admin" stays "admin"; "super_admin" introduced fresh
}

# When checking a role on a user, every canonical role expands to the set of
# privileges below (subset of canonical names).  super_admin implies all;
# admin implies qa_manager + qa_reviewer + employee + department_manager;
# qa_manager implies qa_reviewer + employee; etc.
ROLE_EXPANSION = {
    ROLE_SUPER_ADMIN: {
        ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_QA_MANAGER, ROLE_QA_REVIEWER,
        ROLE_DEPARTMENT_MANAGER, ROLE_EMPLOYEE, ROLE_AUDITOR,
    },
    ROLE_ADMIN: {
        ROLE_ADMIN, ROLE_QA_MANAGER, ROLE_QA_REVIEWER,
        ROLE_DEPARTMENT_MANAGER, ROLE_EMPLOYEE,
    },
    ROLE_QA_MANAGER: {ROLE_QA_MANAGER, ROLE_QA_REVIEWER, ROLE_EMPLOYEE},
    ROLE_QA_REVIEWER: {ROLE_QA_REVIEWER, ROLE_EMPLOYEE},
    ROLE_DEPARTMENT_MANAGER: {ROLE_DEPARTMENT_MANAGER, ROLE_EMPLOYEE, ROLE_QA_REVIEWER},
    ROLE_EMPLOYEE: {ROLE_EMPLOYEE},
    ROLE_AUDITOR: {ROLE_AUDITOR},
}

# Permission → canonical roles that grant it. Used by has_permission().
PERMISSION_MATRIX: Dict[str, set] = {
    "create_record":    {ROLE_EMPLOYEE, ROLE_DEPARTMENT_MANAGER, ROLE_QA_REVIEWER, ROLE_QA_MANAGER, ROLE_ADMIN, ROLE_SUPER_ADMIN},
    "edit_draft":       {ROLE_EMPLOYEE, ROLE_DEPARTMENT_MANAGER, ROLE_QA_REVIEWER, ROLE_QA_MANAGER, ROLE_ADMIN, ROLE_SUPER_ADMIN},
    "view_all_records": {ROLE_DEPARTMENT_MANAGER, ROLE_QA_REVIEWER, ROLE_QA_MANAGER, ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_AUDITOR},
    "review_record":    {ROLE_QA_REVIEWER, ROLE_DEPARTMENT_MANAGER, ROLE_QA_MANAGER, ROLE_ADMIN, ROLE_SUPER_ADMIN},
    "approve_record":   {ROLE_QA_MANAGER, ROLE_ADMIN, ROLE_SUPER_ADMIN},
    "reject_record":    {ROLE_QA_REVIEWER, ROLE_QA_MANAGER, ROLE_ADMIN, ROLE_SUPER_ADMIN},
    "close_record":     {ROLE_QA_MANAGER, ROLE_ADMIN, ROLE_SUPER_ADMIN},
    "view_reports":     {ROLE_EMPLOYEE, ROLE_DEPARTMENT_MANAGER, ROLE_QA_REVIEWER, ROLE_QA_MANAGER, ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_AUDITOR},
    "export_reports":   {ROLE_QA_REVIEWER, ROLE_QA_MANAGER, ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_AUDITOR},
    "user_management":  {ROLE_ADMIN, ROLE_SUPER_ADMIN},
    "role_management":  {ROLE_ADMIN, ROLE_SUPER_ADMIN},   # admin limited; super_admin full
    "workflow_config":  {ROLE_ADMIN, ROLE_SUPER_ADMIN},   # admin limited; super_admin full
    "audit_trail_view": {ROLE_QA_REVIEWER, ROLE_QA_MANAGER, ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_AUDITOR},
    "audit_trail_full": {ROLE_ADMIN, ROLE_SUPER_ADMIN},
    "assign_tasks":     {ROLE_DEPARTMENT_MANAGER, ROLE_QA_MANAGER, ROLE_ADMIN, ROLE_SUPER_ADMIN},
}


def expand_roles(role_list) -> set:
    """Expand a user's stored roles into the full canonical privilege set.

    Accepts both modern canonical role strings and legacy ones (initiator,
    reviewer, approver, qa_head) - legacy values are silently mapped first.
    Returns a set containing the canonical names a user has *effective*
    access to via the role hierarchy.
    """
    effective: set = set()
    for r in (role_list or []):
        canonical = LEGACY_TO_CANONICAL.get(r, r)
        effective |= ROLE_EXPANSION.get(canonical, {canonical})
    return effective


def has_any_role(user: dict, *roles: str) -> bool:
    """True if user has at least one of the given roles (after expansion).
    Accepts both canonical (qa_manager, qa_reviewer, employee_operator, ...)
    and legacy (qa_head, reviewer, approver, initiator) role strings on
    either side of the check.  Auditor is read-only and never grants
    action permissions."""
    eff = expand_roles(user.get("roles", []))
    wanted = {LEGACY_TO_CANONICAL.get(r, r) for r in roles}
    return bool(eff & wanted)


def has_permission(user: dict, permission: str) -> bool:
    """True if user has the named permission per the role matrix.
    Auditor explicitly only has view/export reports + view audit trail."""
    eff = expand_roles(user.get("roles", []))
    allowed = PERMISSION_MATRIX.get(permission, set())
    if eff & allowed:
        return True
    # Also consult any precomputed dynamic permissions cached on the user dict
    # (set by `get_current_user` via the dynamic Role Matrix module).
    legacy_to_record_action = {
        "create_record":  "create",
        "edit_draft":     "edit",
        "review_record":  "review",
        "approve_record": "approve",
        "reject_record":  "reject",
        "close_record":   "close",
    }
    record_action = legacy_to_record_action.get(permission)
    dyn = user.get("_dynamic_perms") or {}
    if record_action:
        # Any QMS-record module granting that action satisfies the legacy perm
        for mod in ("deviation", "capa", "change_control", "incident", "event"):
            if (dyn.get(mod) or {}).get(record_action):
                return True
    # view_all_records is satisfied if ANY QMS module grants the `view_all` action
    if permission == "view_all_records":
        for mod in ("deviation", "capa", "change_control", "incident", "event"):
            if (dyn.get(mod) or {}).get("view_all"):
                return True
    # role_management / user_management / workflow_config / audit_trail map 1:1
    one_to_one = {
        "role_management":  ("role_management", "manage_permissions"),
        "user_management":  ("user_management", "create_user"),
        "workflow_config":  ("workflow", "configure"),
        "audit_trail_view": ("audit_trail", "view"),
        "audit_trail_full": ("audit_trail", "view_full"),
        "view_reports":     ("reports", "view"),
        "export_reports":   ("reports", "export_pdf"),
    }
    if permission in one_to_one:
        m, a = one_to_one[permission]
        if (dyn.get(m) or {}).get(a):
            return True
    return False


def has_record_action(user: dict, record_type: str, action: str) -> bool:
    """Dynamic-first check: does the user have `action` on the QMS module
    matching `record_type`?  DENY (RESTRICTED) overrides win.  Falls back to the
    legacy static matrix so existing canonical roles keep all their privileges.
    """
    record_type_to_module = {
        "DEVIATION": "deviation", "CAPA": "capa",
        "CHANGE_CONTROL": "change_control", "INCIDENT": "incident", "EVENT": "event",
    }
    module = record_type_to_module.get((record_type or "").upper())
    if not module:
        return False
    dyn = user.get("_dynamic_perms") or {}
    deny = user.get("_dynamic_denies") or {}
    if (deny.get(module) or {}).get(action):
        return False
    if (dyn.get(module) or {}).get(action):
        return True
    # Fall back to legacy
    action_to_legacy = {
        "create": "create_record", "edit": "edit_draft",
        "review": "review_record", "approve": "approve_record",
        "reject": "reject_record", "close": "close_record",
    }
    legacy_perm = action_to_legacy.get(action)
    if legacy_perm:
        eff = expand_roles(user.get("roles", []))
        allowed = PERMISSION_MATRIX.get(legacy_perm, set())
        return bool(eff & allowed)
    return False

logger = logging.getLogger("izqms")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


# ---------------- Helpers ----------------
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]


def create_access_token(user_id: str, email: str) -> str:
    now = now_utc()
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MIN),
        "type": "access",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def generate_temp_password(n: int = 12) -> str:
    import secrets, string
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


def human_diff(old: Any, new: Any) -> str:
    """Render an audit value pair in a human-readable string."""
    if old is None and new is None:
        return ""
    if isinstance(old, dict) and isinstance(new, dict):
        keys = set(old.keys()) | set(new.keys())
        parts = []
        for k in keys:
            ov = old.get(k); nv = new.get(k)
            if ov != nv:
                parts.append(f"{k}: {ov!r} → {nv!r}")
        return "; ".join(parts) if parts else ""
    return f"{old!r} → {new!r}"


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": now_utc() + timedelta(days=REFRESH_TOKEN_DAYS),
        "type": "refresh",
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie("access_token", access, httponly=True, secure=False, samesite="lax", max_age=ACCESS_TOKEN_MIN * 60, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=False, samesite="lax", max_age=REFRESH_TOKEN_DAYS * 86400, path="/")


# ---------------- Models ----------------
class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ESignaturePayload(BaseModel):
    password: str
    reason: str
    action: str
    comment: Optional[str] = None


class RecordIn(BaseModel):
    type: str
    title: str
    description: str
    department: Optional[str] = "Quality Assurance"
    location: Optional[str] = "HQ"
    severity: Optional[str] = "Medium"
    priority: Optional[str] = "Medium"
    due_date: Optional[str] = None
    impact_assessment: Optional[str] = ""
    root_cause: Optional[str] = ""
    proposed_action: Optional[str] = ""
    extra: Optional[Dict[str, Any]] = None
    # Framework binding — when a published Module Framework template drives the
    # form (CAPA / Change Control / Incident / Event), the dynamic field values
    # are captured here. The bound template_id + template_version snapshot
    # ensures records stay anchored to their template version for compliance.
    framework_template_id: Optional[str] = None
    framework_template_version: Optional[int] = None
    framework_form_data: Optional[Dict[str, Any]] = None


class RecordUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    impact_assessment: Optional[str] = None
    root_cause: Optional[str] = None
    proposed_action: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
    framework_form_data: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


class CommentIn(BaseModel):
    body: str


# ---------------- Auth dependency ----------------
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        # Enforce token revocation (Part 11 compliance):
        # reset-password / deactivate / lock / sessions/revoke all set token_revoked_at.
        # A JWT whose iat is <= token_revoked_at must be rejected as 401 Session revoked.
        revoked = user.get("token_revoked_at")
        if revoked:
            try:
                rev_ts = int(datetime.fromisoformat(revoked).timestamp())
            except Exception:
                rev_ts = 0
            if rev_ts >= int(payload.get("iat", 0)):
                raise HTTPException(status_code=401, detail="Session revoked")
        if user.get("locked"):
            raise HTTPException(status_code=401, detail="Session revoked")
        if not user.get("active", True):
            raise HTTPException(status_code=401, detail="Session revoked")
        user.pop("password_hash", None)
        # Attach dynamic Role Matrix permissions to the user so legacy helpers
        # (has_permission / has_record_action) can transparently honour
        # user-specific overrides without bypassing the static matrix.
        try:
            from role_mgmt import get_effective_permissions  # local import (avoid circular)
            eff = await get_effective_permissions(db, user)
            user["_dynamic_perms"] = eff.get("permissions") or {}
            # Build a denial map purely from RESTRICTED (DENY) overrides for
            # easy lookup in has_record_action.
            denies: Dict[str, Dict[str, bool]] = {}
            for mk, ad in (eff.get("restricted") or {}).items():
                for ak in ad.keys():
                    denies.setdefault(mk, {})[ak] = True
            user["_dynamic_denies"] = denies
        except Exception as _e:
            logger.warning(f"Dynamic permission resolve failed (using legacy only): {_e}")
            user["_dynamic_perms"] = {}
            user["_dynamic_denies"] = {}
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_role(*roles: str):
    """Authorize a request if the user holds any of the given roles.

    Accepts canonical role names. Legacy role names are normalized to canonical
    via LEGACY_TO_CANONICAL. The user's stored roles are expanded through
    ROLE_EXPANSION so e.g. super_admin > admin > qa_manager > qa_reviewer >
    employee_operator are honoured.
    """
    async def dep(user: dict = Depends(get_current_user)) -> dict:
        # Normalize requested roles (legacy → canonical)
        wanted = {LEGACY_TO_CANONICAL.get(r, r) for r in roles}
        effective = expand_roles(user.get("roles", []))
        if effective & wanted:
            return user
        raise HTTPException(status_code=403, detail="Insufficient role privileges")
    return dep


def require_permission(permission: str):
    """Authorize a request if the user has the named permission per the matrix."""
    async def dep(user: dict = Depends(get_current_user)) -> dict:
        if has_permission(user, permission):
            return user
        raise HTTPException(status_code=403, detail=f"Permission denied: {permission}")
    return dep


# ---------------- Audit trail ----------------
async def log_audit(*, actor: dict, action: str, entity_type: str, entity_id: str,
                    old_value: Any = None, new_value: Any = None,
                    reason: str = "", extra: Optional[Dict[str, Any]] = None) -> None:
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": iso(now_utc()),
        "timezone": "UTC",
        "user_id": actor.get("id"),
        "user_email": actor.get("email"),
        "user_name": actor.get("name"),
        "user_roles": actor.get("roles", []),
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "old_value": old_value,
        "new_value": new_value,
        "reason": reason,
        "extra": extra or {},
    }
    await db.audit_trail.insert_one(entry)


# ---------------- Brute force ----------------
async def is_locked(identifier: str) -> bool:
    doc = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0})
    if not doc:
        return False
    if doc.get("locked_until"):
        try:
            until = datetime.fromisoformat(doc["locked_until"])
            if until > now_utc():
                return True
        except Exception:
            return False
    return False


async def record_failed_login(identifier: str) -> None:
    doc = await db.login_attempts.find_one({"identifier": identifier}, {"_id": 0}) or {"identifier": identifier, "count": 0}
    doc["count"] = doc.get("count", 0) + 1
    if doc["count"] >= MAX_FAILED_ATTEMPTS:
        doc["locked_until"] = iso(now_utc() + timedelta(minutes=LOCKOUT_MINUTES))
        doc["count"] = 0
    await db.login_attempts.update_one({"identifier": identifier}, {"$set": doc}, upsert=True)


async def clear_failed_logins(identifier: str) -> None:
    await db.login_attempts.delete_one({"identifier": identifier})


# ---------------- Record numbering ----------------
TYPE_PREFIX = {
    "CHANGE_CONTROL": "CC",
    "DEVIATION": "DEV",
    "CAPA": "CAPA",
    "INCIDENT": "INC",
    "EVENT": "EVT",
}


async def generate_record_number(rtype: str) -> str:
    prefix = TYPE_PREFIX.get(rtype)
    if not prefix:
        raise HTTPException(status_code=400, detail="Invalid record type")
    year = now_utc().year
    key = f"{prefix}-{year}"
    counter = await db.counters.find_one_and_update(
        {"key": key},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    seq = counter["seq"] if counter and "seq" in counter else 1
    return f"{prefix}-{year}-{seq:04d}"


# ---------------- Lifespan / seed ----------------
async def seed_users():
    admin_email = os.environ["ADMIN_EMAIL"]
    admin_password = os.environ["ADMIN_PASSWORD"]
    seed_list = [
        {"email": admin_email, "password": admin_password, "name": "System Administrator", "department": "IT", "location": "HQ", "roles": [ROLE_SUPER_ADMIN]},
        {"email": "qa.manager@izqms.com", "password": "QaManager@2026", "name": "Dr. Priya Sharma", "department": "Quality Assurance", "location": "Plant-1", "roles": [ROLE_QA_MANAGER]},
        {"email": "qa.reviewer@izqms.com", "password": "QaReviewer@2026", "name": "Raj Kumar", "department": "Quality Assurance", "location": "Plant-1", "roles": [ROLE_QA_REVIEWER]},
        {"email": "dept.manager@izqms.com", "password": "DeptMgr@2026", "name": "Sneha Patel", "department": "Production", "location": "Plant-1", "roles": [ROLE_DEPARTMENT_MANAGER]},
        {"email": "employee@izqms.com", "password": "Employee@2026", "name": "Anita Desai", "department": "Production", "location": "Plant-2", "roles": [ROLE_EMPLOYEE]},
        {"email": "auditor@izqms.com", "password": "Auditor@2026", "name": "Ravi Mehta", "department": "Compliance", "location": "HQ", "roles": [ROLE_AUDITOR]},
        {"email": "admin.user@izqms.com", "password": "AdminUser@2026", "name": "Operational Admin", "department": "IT", "location": "HQ", "roles": [ROLE_ADMIN]},
    ]
    for idx, u in enumerate(seed_list, start=1):
        existing = await db.users.find_one({"email": u["email"].lower()})
        # Preserve existing operational fields if user already exists
        preserved = {
            "last_login": existing.get("last_login") if existing else None,
            "failed_login_count": existing.get("failed_login_count", 0) if existing else 0,
            "must_change_password": existing.get("must_change_password", False) if existing else False,
            "token_revoked_at": existing.get("token_revoked_at") if existing else None,
            "locked": existing.get("locked", False) if existing else False,
        }
        doc = {
            "id": existing["id"] if existing else str(uuid.uuid4()),
            "employee_id": (existing.get("employee_id") if existing else None) or f"EMP-{1000+idx}",
            "username": (existing.get("username") if existing else None) or u["email"].split("@")[0],
            "email": u["email"].lower(),
            "name": u["name"],
            "department": u["department"],
            "location": u["location"],
            "roles": u["roles"],
            "user_type": existing.get("user_type", "Employee") if existing else "Employee",
            "access_level": existing.get("access_level", "Full") if existing else "Full",
            "manager_id": existing.get("manager_id") if existing else None,
            "expiry_date": existing.get("expiry_date") if existing else None,
            "notes": existing.get("notes", "") if existing else "",
            "active": True,
            "approval_status": "ACTIVE",
            "password_hash": hash_password(u["password"]),
            "password_changed_at": existing.get("password_changed_at") if existing else iso(now_utc()),
            "password_history": existing.get("password_history", []) if existing else [],
            "created_at": existing.get("created_at") if existing else iso(now_utc()),
            "created_by": "SYSTEM",
            **preserved,
        }
        await db.users.update_one({"email": u["email"].lower()}, {"$set": doc}, upsert=True)

    # Default password policy
    await db.settings.update_one(
        {"key": "password_policy"},
        {"$setOnInsert": {
            "key": "password_policy",
            "min_length": 8,
            "require_upper": True,
            "require_lower": True,
            "require_digit": True,
            "require_special": False,
            "expiry_days": 90,
            "max_failed_attempts": 5,
            "lockout_minutes": 15,
            "session_timeout_minutes": 60,
            "history_size": 5,
        }},
        upsert=True,
    )


async def seed_sample_records():
    count = await db.qms_records.count_documents({})
    if count > 0:
        return
    admin = await db.users.find_one({"email": os.environ["ADMIN_EMAIL"].lower()}, {"_id": 0})
    initiator = await db.users.find_one({"email": "employee@izqms.com"}, {"_id": 0})
    if not admin or not initiator:
        return
    samples = [
        {"type": "DEVIATION", "title": "Temperature excursion in cold storage Room CS-02", "description": "Cold storage temperature exceeded 8C for 47 minutes during maintenance window.", "severity": "High", "priority": "High", "due_offset": 7},
        {"type": "CAPA", "title": "Recurring label misprint on Batch B-2026-114", "description": "Three batches consecutively had misaligned labels - requires root cause and corrective plan.", "severity": "Medium", "priority": "High", "due_offset": -2},
        {"type": "CHANGE_CONTROL", "title": "Replace HVAC filter vendor for Cleanroom CR-03", "description": "Vendor change for HEPA filters in cleanroom CR-03. Qualification required.", "severity": "Medium", "priority": "Medium", "due_offset": 30},
        {"type": "INCIDENT", "title": "Compressed air pressure drop in packaging line", "description": "Pressure dropped below 5 bar for 22 minutes on packaging line PL-3.", "severity": "Medium", "priority": "Medium", "due_offset": 14},
        {"type": "EVENT", "title": "Annual mock recall exercise", "description": "Planned mock recall event to verify traceability and recall SOP effectiveness.", "severity": "Low", "priority": "Low", "due_offset": 21},
    ]
    for s in samples:
        rno = await generate_record_number(s["type"])
        doc = {
            "id": str(uuid.uuid4()),
            "record_number": rno,
            "type": s["type"],
            "title": s["title"],
            "description": s["description"],
            "department": "Quality Assurance",
            "location": "Plant-1",
            "severity": s["severity"],
            "priority": s["priority"],
            "status": "OPEN",
            "workflow_stage": "REVIEW",
            "due_date": iso(now_utc() + timedelta(days=s["due_offset"])),
            "impact_assessment": "",
            "root_cause": "",
            "proposed_action": "",
            "initiator_id": initiator["id"],
            "initiator_name": initiator["name"],
            "reviewer_id": None,
            "approver_id": None,
            "created_at": iso(now_utc()),
            "updated_at": iso(now_utc()),
            "closed_at": None,
            "extra": {},
        }
        await db.qms_records.insert_one(doc)
        await log_audit(actor=initiator, action="CREATE", entity_type="RECORD", entity_id=doc["id"],
                        new_value={"record_number": rno, "title": doc["title"], "status": "OPEN"},
                        reason="Seed sample data")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.qms_records.create_index("record_number", unique=True)
    await db.qms_records.create_index("type")
    await db.qms_records.create_index("status")
    await db.audit_trail.create_index("entity_id")
    await db.audit_trail.create_index("timestamp")
    await db.counters.create_index("key", unique=True)
    await db.login_attempts.create_index("identifier")
    # Dynamic role-management indexes
    await db.roles.create_index("code", unique=True)
    await db.roles.create_index("id", unique=True)
    await db.user_permission_overrides.create_index("user_id")
    await db.user_permission_overrides.create_index("id", unique=True)
    # Plant/Site framework indexes
    await db.plants.create_index("code", unique=True)
    await db.plants.create_index("id", unique=True)
    await db.module_templates.create_index([("code", 1), ("plant_id", 1), ("version", -1)])
    await db.module_templates.create_index("id", unique=True)
    await db.dynamic_records.create_index("template_id")
    await db.dynamic_records.create_index("plant_id")
    await db.dynamic_records.create_index("record_number", unique=True)
    await migrate_user_roles_to_canonical()
    await seed_users()
    await seed_sample_records()
    # Seed default dynamic roles (idempotent)
    from role_mgmt import seed_default_roles
    await seed_default_roles(db)
    # Seed default plants (idempotent)
    from module_framework import seed_default_plants
    await seed_default_plants(db)
    # Seed ready-made compliant module templates (idempotent, DRAFT, GLOBAL)
    from seed_compliant_templates import seed_compliant_module_templates
    await seed_compliant_module_templates(db)
    yield
    client.close()


async def migrate_user_roles_to_canonical() -> None:
    """One-time normalization: convert legacy role strings stored on users
    (initiator/reviewer/approver/qa_head) into the canonical role names
    from the User Role Matrix. Preserves existing privileges via the
    LEGACY_TO_CANONICAL map. Idempotent."""
    cursor = db.users.find({}, {"_id": 0, "id": 1, "email": 1, "roles": 1})
    async for u in cursor:
        old = u.get("roles", []) or []
        new = []
        for r in old:
            mapped = LEGACY_TO_CANONICAL.get(r, r)
            if mapped not in new:
                new.append(mapped)
        if new != old:
            await db.users.update_one({"id": u["id"]}, {"$set": {"roles": new}})
            logger.info(f"[role-migrate] {u.get('email')} {old} → {new}")


# ---------------- FastAPI app ----------------
app = FastAPI(title="izQMS API", lifespan=lifespan)
api = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def serialize_user(u: dict) -> dict:
    return {
        "id": u["id"],
        "employee_id": u.get("employee_id"),
        "username": u.get("username"),
        "email": u["email"],
        "name": u["name"],
        "department": u.get("department", ""),
        "location": u.get("location", ""),
        "roles": u.get("roles", []),
        "user_type": u.get("user_type", "Employee"),
        "access_level": u.get("access_level", "Full"),
        "manager_id": u.get("manager_id"),
        "expiry_date": u.get("expiry_date"),
        "notes": u.get("notes", ""),
        "active": u.get("active", True),
        "locked": u.get("locked", False),
        "approval_status": u.get("approval_status", "ACTIVE"),
        "must_change_password": u.get("must_change_password", False),
        "password_changed_at": u.get("password_changed_at"),
        "last_login": u.get("last_login"),
        "failed_login_count": u.get("failed_login_count", 0),
        "created_at": u.get("created_at"),
        "created_by": u.get("created_by"),
    }


# ---------------- Auth endpoints ----------------
@api.post("/auth/login")
async def login(payload: LoginIn, request: Request, response: Response):
    email = payload.email.lower()
    # Identifier is email-only so brute-force tracking works behind load balancers/ingress
    # where request.client.host may rotate across proxy pods.
    identifier = email
    if await is_locked(identifier):
        raise HTTPException(status_code=429, detail="Account temporarily locked. Try again later.")
    user = await db.users.find_one({"email": email})
    if not user:
        await record_failed_login(identifier)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.get("locked", False):
        raise HTTPException(status_code=403, detail="Account locked by administrator. Contact admin.")
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="Account deactivated")
    if user.get("approval_status", "ACTIVE") != "ACTIVE":
        raise HTTPException(status_code=403, detail=f"Account pending approval ({user.get('approval_status')})")
    if user.get("expiry_date"):
        try:
            if datetime.fromisoformat(user["expiry_date"]) < now_utc():
                raise HTTPException(status_code=403, detail="Account expired")
        except HTTPException:
            raise
        except Exception:
            pass
    if not verify_password(payload.password, user["password_hash"]):
        await db.users.update_one({"id": user["id"]}, {"$inc": {"failed_login_count": 1}})
        await record_failed_login(identifier)
        await log_audit(actor=user, action="LOGIN_FAILED", entity_type="USER", entity_id=user["id"], reason="Wrong password")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    await clear_failed_logins(identifier)
    await db.users.update_one({"id": user["id"]}, {"$set": {"failed_login_count": 0, "last_login": iso(now_utc())}})
    access = create_access_token(user["id"], user["email"])
    refresh = create_refresh_token(user["id"])
    set_auth_cookies(response, access, refresh)
    await log_audit(actor=user, action="LOGIN", entity_type="USER", entity_id=user["id"], reason="User login")
    user["last_login"] = iso(now_utc())
    return {"user": serialize_user(user), "access_token": access, "must_change_password": user.get("must_change_password", False)}


@api.post("/auth/logout")
async def logout(response: Response, user: dict = Depends(get_current_user)):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    await log_audit(actor=user, action="LOGOUT", entity_type="USER", entity_id=user["id"], reason="User logout")
    return {"ok": True}


@api.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return serialize_user(user)


# ---------------- E-Signature helper ----------------
async def verify_esignature(user: dict, password: str, reason: str, action: str, entity_type: str, entity_id: str) -> None:
    full = await db.users.find_one({"id": user["id"]})
    if not full or not verify_password(password, full["password_hash"]):
        await log_audit(actor=user, action="ESIGN_FAILED", entity_type=entity_type, entity_id=entity_id, reason=reason, extra={"attempted_action": action})
        raise HTTPException(status_code=401, detail="E-signature failed: invalid password")
    if not reason or len(reason.strip()) < 3:
        raise HTTPException(status_code=400, detail="Reason for action is required (min 3 chars)")


# ---------------- Users mgmt ----------------
@api.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    return users


@api.patch("/users/{user_id}")
async def update_user(user_id: str, payload: Dict[str, Any], actor: dict = Depends(require_role("admin"))):
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    allowed = {k: v for k, v in payload.items() if k in {"roles", "active", "department", "location", "name"}}
    if not allowed:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    old = {k: target.get(k) for k in allowed.keys()}
    await db.users.update_one({"id": user_id}, {"$set": allowed})
    await log_audit(actor=actor, action="UPDATE_USER", entity_type="USER", entity_id=user_id, old_value=old, new_value=allowed, reason=payload.get("reason", "User profile update"))
    updated = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    return updated


# ---------------- QMS Records ----------------
@api.post("/records")
async def create_record(payload: RecordIn, user: dict = Depends(get_current_user)):
    if not has_permission(user, "create_record"):
        raise HTTPException(status_code=403, detail="Your role does not permit creating records (Auditor is read-only)")
    rno = await generate_record_number(payload.type)

    # Framework binding: bind record to the latest PUBLISHED GLOBAL template for
    # the record's type (legacy modules CAPA / Change Control / Incident / Event
    # render the framework-defined form). Deviation keeps its hard-coded form
    # but the binding is still recorded so audits show the active template at
    # creation time.  Snapshot ensures ALCOA++ version stability.
    fw_id = payload.framework_template_id
    fw_ver = payload.framework_template_version
    if not fw_id:
        active_tpl = await db.module_templates.find_one(
            {"category": payload.type, "plant_id": "GLOBAL", "status": "PUBLISHED"},
            {"id": 1, "version": 1, "_id": 0},
            sort=[("version", -1)],
        )
        if active_tpl:
            fw_id = active_tpl.get("id")
            fw_ver = active_tpl.get("version")

    doc = {
        "id": str(uuid.uuid4()),
        "record_number": rno,
        "type": payload.type,
        "title": payload.title,
        "description": payload.description,
        "department": payload.department,
        "location": payload.location,
        "severity": payload.severity,
        "priority": payload.priority,
        "status": "OPEN",
        "workflow_stage": "REVIEW",
        "due_date": payload.due_date or iso(now_utc() + timedelta(days=14)),
        "impact_assessment": payload.impact_assessment or "",
        "root_cause": payload.root_cause or "",
        "proposed_action": payload.proposed_action or "",
        "initiator_id": user["id"],
        "initiator_name": user["name"],
        "reviewer_id": None,
        "approver_id": None,
        "created_at": iso(now_utc()),
        "updated_at": iso(now_utc()),
        "closed_at": None,
        "extra": payload.extra or {},
        "framework_template_id": fw_id,
        "framework_template_version": fw_ver,
        "framework_form_data": payload.framework_form_data or {},
    }
    await db.qms_records.insert_one(doc)
    await log_audit(actor=user, action="CREATE", entity_type="RECORD", entity_id=doc["id"],
                    new_value={"record_number": rno, "title": doc["title"], "type": doc["type"],
                               "framework_template_id": fw_id, "framework_template_version": fw_ver},
                    reason="Record created")
    doc.pop("_id", None)
    return doc


@api.get("/records")
async def list_records(
    type: Optional[str] = None,
    status: Optional[str] = None,
    department: Optional[str] = None,
    q: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 200,
    user: dict = Depends(get_current_user),
):
    query: Dict[str, Any] = {}
    if type:
        query["type"] = type
    if status:
        query["status"] = status
    if department:
        query["department"] = department
    if q:
        query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"record_number": {"$regex": q, "$options": "i"}},
        ]
    if from_date or to_date:
        rng: Dict[str, str] = {}
        if from_date:
            rng["$gte"] = from_date
        if to_date:
            rng["$lte"] = to_date
        query["created_at"] = rng
    # Visibility scoping: if the user lacks view_all_records, only return rows
    # they themselves initiated. Department/Plant managers, QA Reviewer, QA Manager,
    # Admin, Super Admin and Auditor have view_all_records by default — Employee
    # does not, and any custom role missing `view_all` on every QMS module is
    # likewise restricted (URS izQMS §5.3).
    if not has_permission(user, "view_all_records"):
        query["$or"] = (query.get("$or") or []) + [
            {"initiator_id": user.get("id")},
            {"created_by_id": user.get("id")},
            {"created_by": user.get("email")},
            {"initiator_email": user.get("email")},
        ]
    rows = await db.qms_records.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return rows


def _record_is_visible(rec: dict, user: dict) -> bool:
    if has_permission(user, "view_all_records"):
        return True
    return (
        rec.get("initiator_id") == user.get("id")
        or rec.get("created_by_id") == user.get("id")
        or rec.get("created_by") == user.get("email")
        or rec.get("initiator_email") == user.get("email")
    )


@api.get("/records/{record_id}")
async def get_record(record_id: str, user: dict = Depends(get_current_user)):
    rec = await db.qms_records.find_one({"id": record_id}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    if not _record_is_visible(rec, user):
        raise HTTPException(status_code=403, detail="You do not have permission to view this record. Ask an admin to grant 'View all records' on this module.")
    return rec


@api.patch("/records/{record_id}")
async def update_record(record_id: str, payload: RecordUpdate, user: dict = Depends(get_current_user)):
    if not has_permission(user, "edit_draft"):
        raise HTTPException(status_code=403, detail="Your role does not permit editing records (Auditor is read-only)")
    rec = await db.qms_records.find_one({"id": record_id})
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    if rec["status"] in {"CLOSED", "APPROVED"}:
        raise HTTPException(status_code=400, detail="Cannot edit closed/approved records")
    update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if k != "reason"}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    old = {k: rec.get(k) for k in update_data.keys()}
    update_data["updated_at"] = iso(now_utc())
    await db.qms_records.update_one({"id": record_id}, {"$set": update_data})
    await log_audit(actor=user, action="UPDATE", entity_type="RECORD", entity_id=record_id,
                    old_value=old, new_value=update_data, reason=payload.reason or "Record edit")
    return await db.qms_records.find_one({"id": record_id}, {"_id": 0})


@api.post("/records/{record_id}/action")
async def record_action(record_id: str, payload: ESignaturePayload, user: dict = Depends(get_current_user)):
    rec = await db.qms_records.find_one({"id": record_id})
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    await verify_esignature(user, payload.password, payload.reason, payload.action, "RECORD", record_id)

    action = payload.action.upper()
    old_status = rec["status"]
    new_status = old_status
    new_stage = rec.get("workflow_stage")
    updates: Dict[str, Any] = {}

    if action == "SUBMIT_REVIEW":
        if old_status != "DRAFT":
            raise HTTPException(status_code=400, detail="Only DRAFT records can be submitted")
        new_status = "OPEN"
        new_stage = "REVIEW"
    elif action == "REVIEW":
        if not has_record_action(user, rec.get("type"), "review"):
            raise HTTPException(status_code=403, detail="Reviewer role required")
        if old_status != "OPEN":
            raise HTTPException(status_code=400, detail="Record must be OPEN to review")
        new_status = "IN_REVIEW"
        new_stage = "APPROVAL"
        updates["reviewer_id"] = user["id"]
    elif action == "APPROVE":
        if not has_record_action(user, rec.get("type"), "approve"):
            raise HTTPException(status_code=403, detail="Approver role required (QA Manager, Admin, or Super Admin)")
        if old_status not in {"IN_REVIEW", "OPEN"}:
            raise HTTPException(status_code=400, detail="Record must be IN_REVIEW to approve")
        new_status = "APPROVED"
        new_stage = "CLOSURE"
        updates["approver_id"] = user["id"]
    elif action == "REJECT":
        if not has_record_action(user, rec.get("type"), "reject"):
            raise HTTPException(status_code=403, detail="Reviewer/QA Manager/Admin role required to reject")
        if old_status in {"CLOSED"}:
            raise HTTPException(status_code=400, detail="Cannot reject closed record")
        new_status = "REJECTED"
        new_stage = "REINITIATE"
    elif action == "CLOSE":
        if not has_record_action(user, rec.get("type"), "close"):
            raise HTTPException(status_code=403, detail="Close requires QA Manager, Admin, or Super Admin")
        if old_status != "APPROVED":
            raise HTTPException(status_code=400, detail="Only APPROVED records can be closed")
        new_status = "CLOSED"
        new_stage = "CLOSED"
        updates["closed_at"] = iso(now_utc())
    elif action == "REOPEN":
        if old_status != "REJECTED":
            raise HTTPException(status_code=400, detail="Only REJECTED records can be reopened")
        new_status = "OPEN"
        new_stage = "REVIEW"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported action {action}")

    updates.update({"status": new_status, "workflow_stage": new_stage, "updated_at": iso(now_utc())})
    await db.qms_records.update_one({"id": record_id}, {"$set": updates})

    event = {
        "id": str(uuid.uuid4()),
        "record_id": record_id,
        "action": action,
        "actor_id": user["id"],
        "actor_name": user["name"],
        "actor_roles": user.get("roles", []),
        "from_status": old_status,
        "to_status": new_status,
        "reason": payload.reason,
        "comment": payload.comment or "",
        "timestamp": iso(now_utc()),
    }
    await db.workflow_events.insert_one(event)
    event.pop("_id", None)

    await log_audit(
        actor=user,
        action=f"WORKFLOW_{action}",
        entity_type="RECORD",
        entity_id=record_id,
        old_value={"status": old_status},
        new_value={"status": new_status},
        reason=payload.reason,
        extra={"esignature": True, "comment": payload.comment},
    )

    # Notifications to next-in-line
    try:
        targets: List[dict] = []
        # Use canonical role names; legacy names are normalized in DB by the
        # migration step but we still match both to be safe during transition.
        if new_status == "OPEN":
            targets = await db.users.find({"roles": {"$in": [ROLE_QA_REVIEWER, ROLE_QA_MANAGER, ROLE_ADMIN, ROLE_SUPER_ADMIN, "reviewer", "qa_head"]}, "active": True}, {"_id": 0, "id": 1, "email": 1, "name": 1}).to_list(50)
        elif new_status == "IN_REVIEW":
            targets = await db.users.find({"roles": {"$in": [ROLE_QA_MANAGER, ROLE_ADMIN, ROLE_SUPER_ADMIN, "approver", "qa_head"]}, "active": True}, {"_id": 0, "id": 1, "email": 1, "name": 1}).to_list(50)
        elif new_status in {"APPROVED", "REJECTED"}:
            if rec.get("initiator_id"):
                init = await db.users.find_one({"id": rec["initiator_id"]}, {"_id": 0, "id": 1, "email": 1, "name": 1})
                if init:
                    targets = [init]
        for t in targets:
            if not t.get("id"):
                continue
            await create_notification(t["id"], f"{action}: {rec.get('record_number')}",
                                      f"{rec.get('title')} → {new_status}",
                                      link=f"/record/{record_id}", kind="workflow")
            # Fire-and-forget email
            if t.get("email"):
                html = _email_shell(
                    f"{action}: {rec.get('record_number')}",
                    f"<p><b>{rec.get('record_number')}</b> · {rec.get('title')}</p>"
                    f"<p>Status changed from <b>{old_status}</b> to <b>{new_status}</b> by {user.get('name')}.</p>"
                    f"<p>Reason: <i>{payload.reason}</i></p>",
                    (APP_BASE_URL + f"/record/{record_id}") if APP_BASE_URL else None,
                    "Open record",
                )
                asyncio.create_task(send_email(t["email"], f"[izQMS] {action} · {rec.get('record_number')}", html, kind="workflow"))
    except Exception as _e:
        logger.warning(f"Notification dispatch failed: {_e}")

    rec = await db.qms_records.find_one({"id": record_id}, {"_id": 0})
    return {"record": rec, "event": event}


@api.get("/records/{record_id}/workflow")
async def get_workflow(record_id: str, user: dict = Depends(get_current_user)):
    events = await db.workflow_events.find({"record_id": record_id}, {"_id": 0}).sort("timestamp", 1).to_list(500)
    return events


@api.get("/records/{record_id}/audit")
async def get_record_audit(record_id: str, user: dict = Depends(get_current_user)):
    entries = await db.audit_trail.find({"entity_id": record_id}, {"_id": 0}).sort("timestamp", -1).to_list(1000)
    return entries


@api.post("/records/{record_id}/comments")
async def add_comment(record_id: str, payload: CommentIn, user: dict = Depends(get_current_user)):
    rec = await db.qms_records.find_one({"id": record_id})
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    c = {
        "id": str(uuid.uuid4()),
        "record_id": record_id,
        "body": payload.body,
        "user_id": user["id"],
        "user_name": user["name"],
        "timestamp": iso(now_utc()),
    }
    await db.comments.insert_one(c)
    c.pop("_id", None)
    await log_audit(actor=user, action="COMMENT", entity_type="RECORD", entity_id=record_id, new_value={"body": payload.body}, reason="Comment added")
    return c


@api.get("/records/{record_id}/comments")
async def list_comments(record_id: str, user: dict = Depends(get_current_user)):
    rows = await db.comments.find({"record_id": record_id}, {"_id": 0}).sort("timestamp", 1).to_list(500)
    return rows


# ---------------- Dashboard ----------------
@api.get("/dashboard/summary")
async def dashboard_summary(user: dict = Depends(get_current_user)):
    pipeline = [{"$group": {"_id": {"type": "$type", "status": "$status"}, "count": {"$sum": 1}}}]
    raw = await db.qms_records.aggregate(pipeline).to_list(1000)
    by_type: Dict[str, Dict[str, int]] = {}
    totals: Dict[str, int] = {"DRAFT": 0, "OPEN": 0, "IN_REVIEW": 0, "APPROVED": 0, "REJECTED": 0, "CLOSED": 0}
    for r in raw:
        t = r["_id"]["type"]
        s = r["_id"]["status"]
        by_type.setdefault(t, {})[s] = r["count"]
        totals[s] = totals.get(s, 0) + r["count"]

    now_iso = iso(now_utc())
    overdue_count = await db.qms_records.count_documents({"due_date": {"$lt": now_iso}, "status": {"$nin": ["CLOSED", "APPROVED", "REJECTED"]}})
    pending_for_me = await db.qms_records.count_documents({"status": {"$in": ["OPEN", "IN_REVIEW"]}})
    recent = await db.qms_records.find({}, {"_id": 0}).sort("updated_at", -1).limit(8).to_list(8)
    return {"by_type": by_type, "totals": totals, "overdue_count": overdue_count, "pending_for_me": pending_for_me, "recent": recent}


@api.get("/dashboard/my-tasks")
async def my_tasks(user: dict = Depends(get_current_user)):
    statuses: List[str] = []
    if has_permission(user, "review_record"):
        statuses.append("OPEN")
    if has_permission(user, "approve_record"):
        statuses.append("IN_REVIEW")
    if not statuses:
        return []
    rows = await db.qms_records.find({"status": {"$in": statuses}}, {"_id": 0}).sort("due_date", 1).to_list(50)
    return rows


# ---------------- Audit trail global ----------------
@api.get("/audit")
async def list_audit(
    entity_type: Optional[str] = None,
    user_email: Optional[str] = None,
    action: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 200,
    user: dict = Depends(get_current_user),
):
    query: Dict[str, Any] = {}
    if entity_type:
        query["entity_type"] = entity_type
    if user_email:
        query["user_email"] = user_email
    if action:
        query["action"] = action
    if from_date or to_date:
        rng: Dict[str, str] = {}
        if from_date:
            rng["$gte"] = from_date
        if to_date:
            rng["$lte"] = to_date
        query["timestamp"] = rng
    rows = await db.audit_trail.find(query, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return rows


# ---------------- Health ----------------
@api.get("/")
async def root():
    return {"app": "izQMS", "status": "online"}


@api.get("/roles")
async def list_roles(user: dict = Depends(get_current_user)):
    """Catalog of the canonical role hierarchy + permission matrix
    (sourced from the User Role Matrix document). Used by the UI to
    populate role pickers and gate features."""
    eff = sorted(list(expand_roles(user.get("roles", []))))
    role_perms = {role: sorted([p for p, rs in PERMISSION_MATRIX.items() if role in rs])
                  for role in CANONICAL_ROLES}
    return {
        "canonical_roles": CANONICAL_ROLES,
        "legacy_to_canonical": LEGACY_TO_CANONICAL,
        "permission_matrix": {k: sorted(list(v)) for k, v in PERMISSION_MATRIX.items()},
        "role_permissions": role_perms,
        "role_hierarchy": {k: sorted(list(v)) for k, v in ROLE_EXPANSION.items()},
        "my_effective_roles": eff,
        "my_permissions": sorted([p for p in PERMISSION_MATRIX if has_permission(user, p)]),
    }


# =====================================================================
# Phase A additions: users CRUD, password reset, settings, notifications
# =====================================================================

class UserCreateIn(BaseModel):
    name: str
    email: EmailStr
    employee_id: str
    username: str
    department: str
    location: str
    roles: List[str]
    user_type: Optional[str] = "Employee"
    access_level: Optional[str] = "Full"
    manager_id: Optional[str] = None
    expiry_date: Optional[str] = None
    notes: Optional[str] = ""
    password: Optional[str] = None
    requires_approval: Optional[bool] = True
    esign_password: str
    esign_reason: str


class UserActionIn(BaseModel):
    esign_password: str
    esign_reason: str
    extra: Optional[Dict[str, Any]] = None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class PolicyUpdateIn(BaseModel):
    min_length: Optional[int] = None
    require_upper: Optional[bool] = None
    require_lower: Optional[bool] = None
    require_digit: Optional[bool] = None
    require_special: Optional[bool] = None
    expiry_days: Optional[int] = None
    max_failed_attempts: Optional[int] = None
    lockout_minutes: Optional[int] = None
    session_timeout_minutes: Optional[int] = None
    history_size: Optional[int] = None
    reason: Optional[str] = None


async def get_password_policy() -> dict:
    p = await db.settings.find_one({"key": "password_policy"}, {"_id": 0}) or {}
    return p


def validate_password(pw: str, policy: dict) -> Optional[str]:
    if len(pw) < policy.get("min_length", 8):
        return f"Password must be at least {policy.get('min_length', 8)} characters"
    if policy.get("require_upper") and not any(c.isupper() for c in pw):
        return "Password must contain an uppercase letter"
    if policy.get("require_lower") and not any(c.islower() for c in pw):
        return "Password must contain a lowercase letter"
    if policy.get("require_digit") and not any(c.isdigit() for c in pw):
        return "Password must contain a digit"
    if policy.get("require_special") and not any(not c.isalnum() for c in pw):
        return "Password must contain a special character"
    return None


async def create_notification(user_id: str, title: str, body: str, link: Optional[str] = None, kind: str = "info") -> None:
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "title": title,
        "body": body,
        "link": link,
        "kind": kind,
        "read": False,
        "timestamp": iso(now_utc()),
    })


# -------- User CRUD --------
@api.post("/users")
async def create_user(payload: UserCreateIn, actor: dict = Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN))):
    # E-sign verify
    await verify_esignature(actor, payload.esign_password, payload.esign_reason, "CREATE_USER", "USER", "new")

    if await db.users.find_one({"email": payload.email.lower()}):
        raise HTTPException(status_code=400, detail="Email already exists")
    if await db.users.find_one({"username": payload.username}):
        raise HTTPException(status_code=400, detail="Username already exists")

    policy = await get_password_policy()
    raw_pw = payload.password or generate_temp_password(12)
    err = validate_password(raw_pw, policy)
    if payload.password and err:
        raise HTTPException(status_code=400, detail=err)

    # Approval flow: per matrix, admins create users directly. If a non-admin
    # somehow holds this endpoint they would be routed through PENDING_QA →
    # PENDING_ADMIN. (Endpoint is gated to ADMIN / SUPER_ADMIN only.)
    actor_eff = expand_roles(actor.get("roles", []))
    if payload.requires_approval and not (actor_eff & {ROLE_ADMIN, ROLE_SUPER_ADMIN}):
        approval_status = "PENDING_QA"
        active = False
    else:
        approval_status = "ACTIVE"
        active = True

    # Normalize incoming roles to canonical form (reject auditor combined w/ writer roles? — allow per matrix)
    normalized_roles = []
    for r in (payload.roles or []):
        canonical = LEGACY_TO_CANONICAL.get(r, r)
        if canonical not in CANONICAL_ROLES:
            raise HTTPException(status_code=400, detail=f"Unknown role: {r}. Allowed: {CANONICAL_ROLES}")
        if canonical not in normalized_roles:
            normalized_roles.append(canonical)
    if not normalized_roles:
        raise HTTPException(status_code=400, detail="At least one role is required")

    new_id = str(uuid.uuid4())
    doc = {
        "id": new_id,
        "employee_id": payload.employee_id,
        "username": payload.username,
        "email": payload.email.lower(),
        "name": payload.name,
        "department": payload.department,
        "location": payload.location,
        "roles": normalized_roles,
        "user_type": payload.user_type,
        "access_level": payload.access_level,
        "manager_id": payload.manager_id,
        "expiry_date": payload.expiry_date,
        "notes": payload.notes or "",
        "active": active,
        "locked": False,
        "approval_status": approval_status,
        "password_hash": hash_password(raw_pw),
        "password_changed_at": iso(now_utc()),
        "password_history": [],
        "must_change_password": payload.password is None,
        "failed_login_count": 0,
        "last_login": None,
        "token_revoked_at": None,
        "created_at": iso(now_utc()),
        "created_by": actor["email"],
    }
    await db.users.insert_one(doc)
    await log_audit(actor=actor, action="USER_CREATE", entity_type="USER", entity_id=new_id,
                    new_value={"email": doc["email"], "roles": doc["roles"], "approval_status": approval_status},
                    reason=payload.esign_reason, extra={"esignature": True, "temp_password_generated": payload.password is None})

    # Notify approvers if pending
    if approval_status != "ACTIVE":
        approvers = await db.users.find({"roles": {"$in": [ROLE_QA_MANAGER, ROLE_ADMIN, ROLE_SUPER_ADMIN, "qa_head", "admin"]}, "active": True}, {"_id": 0, "id": 1}).to_list(50)
        for a in approvers:
            await create_notification(a["id"], "User pending review", f"New user {doc['name']} ({doc['email']}) needs QA review", link=f"/users/{new_id}", kind="approval")

    return {"user": serialize_user(doc), "temp_password": raw_pw if payload.password is None else None}


@api.get("/users/{user_id}")
async def get_user(user_id: str, actor: dict = Depends(get_current_user)):
    u = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "password_history": 0})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return u


@api.get("/users/{user_id}/audit")
async def get_user_audit(user_id: str, actor: dict = Depends(get_current_user)):
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    rows = await db.audit_trail.find({"$or": [{"entity_id": user_id, "entity_type": "USER"}, {"user_id": user_id}]}, {"_id": 0}).sort("timestamp", -1).to_list(500)
    return rows


def _user_action_helper(action: str):
    async def handler(user_id: str, payload: UserActionIn, actor: dict = Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_QA_MANAGER))):
        target = await db.users.find_one({"id": user_id})
        if not target:
            raise HTTPException(status_code=404, detail="User not found")
        # Per User Role Matrix: only Admin / Super Admin can manage user state.
        # QA Manager is allowed only for the APPROVE step of the two-stage user-approval workflow.
        actor_eff = expand_roles(actor.get("roles", []))
        is_admin_tier = bool(actor_eff & {ROLE_ADMIN, ROLE_SUPER_ADMIN})
        if action != "APPROVE" and not is_admin_tier:
            raise HTTPException(status_code=403, detail="User management is restricted to Admin / Super Admin per role matrix")
        await verify_esignature(actor, payload.esign_password, payload.esign_reason, action, "USER", user_id)
        updates: Dict[str, Any] = {}
        old_snapshot: Dict[str, Any] = {}

        if action == "ACTIVATE":
            old_snapshot = {"active": target.get("active")}
            updates = {"active": True}
        elif action == "DEACTIVATE":
            old_snapshot = {"active": target.get("active")}
            updates = {"active": False, "token_revoked_at": iso(now_utc())}
        elif action == "LOCK":
            old_snapshot = {"locked": target.get("locked", False)}
            updates = {"locked": True, "token_revoked_at": iso(now_utc())}
        elif action == "UNLOCK":
            old_snapshot = {"locked": target.get("locked", False)}
            updates = {"locked": False, "failed_login_count": 0}
            await db.login_attempts.delete_one({"identifier": target["email"]})
        elif action == "APPROVE":
            actor_eff = expand_roles(actor.get("roles", []))
            cur = target.get("approval_status")
            # Two-step approval per matrix: QA Manager reviews first; Admin/Super Admin grants final ACTIVE.
            if cur == "PENDING_QA" and (ROLE_QA_MANAGER in actor_eff or ROLE_ADMIN in actor_eff or ROLE_SUPER_ADMIN in actor_eff):
                updates = {"approval_status": "PENDING_ADMIN"}
            elif cur == "PENDING_ADMIN" and (ROLE_ADMIN in actor_eff or ROLE_SUPER_ADMIN in actor_eff):
                updates = {"approval_status": "ACTIVE", "active": True}
            elif cur == "ACTIVE":
                raise HTTPException(status_code=400, detail="User already active")
            else:
                raise HTTPException(status_code=400, detail=f"Cannot approve user in state {cur}")
            old_snapshot = {"approval_status": cur}
        elif action == "REJECT":
            old_snapshot = {"approval_status": target.get("approval_status")}
            updates = {"approval_status": "REJECTED", "active": False}
        elif action == "EXTEND_EXPIRY":
            new_expiry = (payload.extra or {}).get("expiry_date")
            if not new_expiry:
                raise HTTPException(status_code=400, detail="expiry_date is required in extra")
            old_snapshot = {"expiry_date": target.get("expiry_date")}
            updates = {"expiry_date": new_expiry}
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action {action}")

        await db.users.update_one({"id": user_id}, {"$set": updates})
        await log_audit(actor=actor, action=f"USER_{action}", entity_type="USER", entity_id=user_id,
                        old_value=old_snapshot, new_value=updates, reason=payload.esign_reason,
                        extra={"esignature": True})
        await create_notification(user_id, f"Account {action.lower().replace('_',' ')}",
                                  f"Your account was {action.lower().replace('_',' ')} by {actor['name']}. Reason: {payload.esign_reason}",
                                  kind="account")
        updated = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "password_history": 0})
        return updated
    handler.__name__ = f"user_{action.lower()}"
    return handler


api.add_api_route("/users/{user_id}/activate", _user_action_helper("ACTIVATE"), methods=["POST"])
api.add_api_route("/users/{user_id}/deactivate", _user_action_helper("DEACTIVATE"), methods=["POST"])
api.add_api_route("/users/{user_id}/lock", _user_action_helper("LOCK"), methods=["POST"])
api.add_api_route("/users/{user_id}/unlock", _user_action_helper("UNLOCK"), methods=["POST"])
api.add_api_route("/users/{user_id}/approve", _user_action_helper("APPROVE"), methods=["POST"])
api.add_api_route("/users/{user_id}/reject", _user_action_helper("REJECT"), methods=["POST"])
api.add_api_route("/users/{user_id}/extend-expiry", _user_action_helper("EXTEND_EXPIRY"), methods=["POST"])


@api.post("/users/{user_id}/reset-password")
async def admin_reset_password(user_id: str, payload: UserActionIn, actor: dict = Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN))):
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await verify_esignature(actor, payload.esign_password, payload.esign_reason, "RESET_PASSWORD", "USER", user_id)
    temp = generate_temp_password(12) + "A1!"
    await db.users.update_one({"id": user_id}, {"$set": {
        "password_hash": hash_password(temp),
        "must_change_password": True,
        "failed_login_count": 0,
        "token_revoked_at": iso(now_utc()),
        "password_changed_at": iso(now_utc()),
    }})
    await db.login_attempts.delete_one({"identifier": target["email"]})
    await log_audit(actor=actor, action="USER_RESET_PASSWORD", entity_type="USER", entity_id=user_id,
                    reason=payload.esign_reason, extra={"esignature": True})
    await create_notification(user_id, "Password reset by admin",
                              f"Your password was reset by {actor['name']}. You must set a new password on next login.",
                              kind="security")
    return {"temp_password": temp, "user_id": user_id}


@api.post("/auth/change-password")
async def change_password(payload: ChangePasswordIn, user: dict = Depends(get_current_user)):
    full = await db.users.find_one({"id": user["id"]})
    if not verify_password(payload.current_password, full["password_hash"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    policy = await get_password_policy()
    err = validate_password(payload.new_password, policy)
    if err:
        raise HTTPException(status_code=400, detail=err)
    # Reject reuse from history
    for old in full.get("password_history", []):
        if verify_password(payload.new_password, old):
            raise HTTPException(status_code=400, detail="New password must differ from your last passwords")
    history = ([full["password_hash"]] + full.get("password_history", []))[: max(1, policy.get("history_size", 5))]
    await db.users.update_one({"id": user["id"]}, {"$set": {
        "password_hash": hash_password(payload.new_password),
        "must_change_password": False,
        "password_changed_at": iso(now_utc()),
        "password_history": history,
    }})
    await log_audit(actor=user, action="PASSWORD_CHANGED", entity_type="USER", entity_id=user["id"], reason="User changed password")
    return {"ok": True}


@api.post("/auth/forgot-password")
async def forgot_password(payload: ForgotPasswordIn):
    email = payload.email.lower()
    user = await db.users.find_one({"email": email})
    # Always 200 to prevent enumeration
    if user:
        import secrets as _s
        token = _s.token_urlsafe(32)
        await db.password_reset_tokens.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "token": token,
            "expires_at": iso(now_utc() + timedelta(hours=1)),
            "used": False,
            "created_at": iso(now_utc()),
        })
        logger.info(f"PASSWORD RESET LINK for {email}: /reset-password?token={token}")
        await log_audit(actor=user, action="PASSWORD_RESET_REQUESTED", entity_type="USER", entity_id=user["id"], reason="User requested password reset")
    return {"ok": True}


# -------- Password policy --------
@api.get("/settings/password-policy")
async def policy_get(user: dict = Depends(get_current_user)):
    return await get_password_policy()


@api.patch("/settings/password-policy")
async def policy_set(payload: PolicyUpdateIn, actor: dict = Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN))):
    updates = payload.model_dump(exclude_unset=True)
    reason = updates.pop("reason", None) or "Password policy updated"
    if not updates:
        raise HTTPException(status_code=400, detail="No fields")
    old = await get_password_policy()
    await db.settings.update_one({"key": "password_policy"}, {"$set": updates})
    await log_audit(actor=actor, action="POLICY_UPDATE", entity_type="SETTINGS", entity_id="password_policy",
                    old_value={k: old.get(k) for k in updates.keys()}, new_value=updates,
                    reason=reason)
    return await get_password_policy()


# -------- Sessions (admin) --------
@api.get("/sessions")
async def list_sessions(actor: dict = Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN))):
    users = await db.users.find({"active": True, "last_login": {"$ne": None}}, {"_id": 0, "password_hash": 0, "password_history": 0}).to_list(500)
    policy = await get_password_policy()
    timeout = policy.get("session_timeout_minutes", 60)
    cutoff = now_utc() - timedelta(minutes=timeout)
    out = []
    for u in users:
        if not u.get("last_login"):
            continue
        try:
            last_login_dt = datetime.fromisoformat(u["last_login"])
        except Exception:
            continue
        if last_login_dt <= cutoff:
            continue
        # Skip users whose token has been revoked AFTER last login (i.e., not a fresh re-login)
        revoked = u.get("token_revoked_at")
        if revoked:
            try:
                rev_dt = datetime.fromisoformat(revoked)
                if rev_dt >= last_login_dt:
                    continue
            except Exception:
                pass
        out.append(u)
    return out


@api.post("/sessions/{user_id}/revoke")
async def revoke_session(user_id: str, payload: UserActionIn, actor: dict = Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN))):
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await verify_esignature(actor, payload.esign_password, payload.esign_reason, "REVOKE_SESSION", "USER", user_id)
    await db.users.update_one({"id": user_id}, {"$set": {"token_revoked_at": iso(now_utc())}})
    await log_audit(actor=actor, action="SESSION_REVOKED", entity_type="USER", entity_id=user_id, reason=payload.esign_reason, extra={"esignature": True})
    return {"ok": True}


# -------- Notifications --------
@api.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    rows = await db.notifications.find({"user_id": user["id"]}, {"_id": 0}).sort("timestamp", -1).limit(50).to_list(50)
    unread = await db.notifications.count_documents({"user_id": user["id"], "read": False})
    return {"items": rows, "unread": unread}


@api.post("/notifications/{nid}/read")
async def mark_read(nid: str, user: dict = Depends(get_current_user)):
    await db.notifications.update_one({"id": nid, "user_id": user["id"]}, {"$set": {"read": True}})
    return {"ok": True}


@api.post("/notifications/read-all")
async def mark_all_read(user: dict = Depends(get_current_user)):
    await db.notifications.update_many({"user_id": user["id"], "read": False}, {"$set": {"read": True}})
    return {"ok": True}


# -------- Draft / status enhancements --------
class DraftRecordIn(RecordIn):
    save_as_draft: Optional[bool] = False


@api.post("/records/draft")
async def create_draft(payload: DraftRecordIn, user: dict = Depends(get_current_user)):
    if not has_permission(user, "create_record"):
        raise HTTPException(status_code=403, detail="Your role does not permit creating records (Auditor is read-only)")
    rno = await generate_record_number(payload.type)
    doc = {
        "id": str(uuid.uuid4()),
        "record_number": rno,
        "type": payload.type,
        "title": payload.title or "(Untitled draft)",
        "description": payload.description or "",
        "department": payload.department, "location": payload.location,
        "severity": payload.severity, "priority": payload.priority,
        "status": "DRAFT", "workflow_stage": "DRAFT",
        "due_date": payload.due_date or iso(now_utc() + timedelta(days=14)),
        "impact_assessment": payload.impact_assessment or "",
        "root_cause": payload.root_cause or "",
        "proposed_action": payload.proposed_action or "",
        "initiator_id": user["id"], "initiator_name": user["name"],
        "reviewer_id": None, "approver_id": None,
        "created_at": iso(now_utc()), "updated_at": iso(now_utc()),
        "closed_at": None, "extra": payload.extra or {},
        "framework_template_id": payload.framework_template_id,
        "framework_template_version": payload.framework_template_version,
        "framework_form_data": payload.framework_form_data or {},
    }
    await db.qms_records.insert_one(doc)
    await log_audit(actor=user, action="CREATE_DRAFT", entity_type="RECORD", entity_id=doc["id"],
                    new_value={"record_number": rno}, reason="Draft saved")
    doc.pop("_id", None)
    return doc


# Allow editing of DRAFT records (note: this is a separate route from existing PATCH)
# Existing PATCH blocks CLOSED/APPROVED; DRAFT is editable by default.


# =====================================================================
# Phase B — Email engine, Attachments, Password reset consume,
# Form Builder, Risk Scoring, Exports, Charts
# =====================================================================

import asyncio
import csv
import io
import shutil
from collections import defaultdict

try:
    import resend  # type: ignore
except Exception:
    resend = None  # SDK absent → degrade gracefully

try:
    from openpyxl import Workbook  # type: ignore
except Exception:
    Workbook = None  # type: ignore

from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "/app/backend/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "25")) * 1024 * 1024
APP_BASE_URL = os.environ.get("APP_BASE_URL", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
if resend and RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY


# -------- Email service (Resend; gracefully no-ops without a key) --------
async def send_email(to_email: str, subject: str, html: str, kind: str = "transactional") -> bool:
    """Send transactional email via Resend. Logs and stores a delivery record."""
    delivery = {
        "id": str(uuid.uuid4()),
        "to": to_email,
        "subject": subject,
        "kind": kind,
        "timestamp": iso(now_utc()),
        "status": "queued",
        "error": None,
        "provider_id": None,
    }
    try:
        if resend and RESEND_API_KEY:
            params = {"from": SENDER_EMAIL, "to": [to_email], "subject": subject, "html": html}
            email = await asyncio.to_thread(resend.Emails.send, params)
            delivery["status"] = "sent"
            delivery["provider_id"] = (email or {}).get("id") if isinstance(email, dict) else None
        else:
            delivery["status"] = "logged"
            logger.info(f"[email/{kind}] (no Resend key) to={to_email} subject={subject!r}")
        await db.email_log.insert_one(delivery)
        return delivery["status"] in {"sent", "logged"}
    except Exception as e:
        delivery["status"] = "failed"
        delivery["error"] = str(e)[:500]
        await db.email_log.insert_one(delivery)
        logger.error(f"Email send failed to {to_email}: {e}")
        return False


def _email_shell(title: str, body_html: str, cta_url: Optional[str] = None, cta_label: Optional[str] = None) -> str:
    cta = ""
    if cta_url and cta_label:
        cta = (
            f'<tr><td align="left" style="padding:24px 32px 8px 32px;">'
            f'<a href="{cta_url}" style="background:#0f172a;color:#ffffff;text-decoration:none;'
            f'padding:12px 20px;font-family:Inter,Helvetica,Arial,sans-serif;font-size:13px;'
            f'border-radius:2px;display:inline-block;font-weight:600;letter-spacing:0.02em;">'
            f'{cta_label}</a></td></tr>'
        )
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f8fafc;padding:24px 0;">'
        '<tr><td align="center">'
        '<table width="560" cellpadding="0" cellspacing="0" border="0" '
        'style="background:#ffffff;border:1px solid #e2e8f0;border-radius:4px;">'
        '<tr><td style="padding:20px 32px;border-bottom:1px solid #e2e8f0;">'
        '<table cellpadding="0" cellspacing="0"><tr>'
        '<td style="background:#0f172a;color:#fff;font-family:monospace;font-weight:700;'
        'padding:8px 10px;border-radius:2px;font-size:13px;letter-spacing:-0.04em;">iz</td>'
        '<td style="padding-left:10px;font-family:Inter,Helvetica,Arial,sans-serif;'
        'font-weight:700;color:#0f172a;font-size:15px;">izQMS</td>'
        '</tr></table></td></tr>'
        f'<tr><td style="padding:24px 32px 8px 32px;font-family:Inter,Helvetica,Arial,sans-serif;'
        f'color:#0f172a;font-size:17px;font-weight:600;">{title}</td></tr>'
        f'<tr><td style="padding:8px 32px 16px 32px;font-family:Inter,Helvetica,Arial,sans-serif;'
        f'color:#334155;font-size:14px;line-height:1.55;">{body_html}</td></tr>'
        f'{cta}'
        '<tr><td style="padding:24px 32px;border-top:1px solid #e2e8f0;'
        'font-family:Inter,Helvetica,Arial,sans-serif;color:#94a3b8;font-size:11px;">'
        '21 CFR Part 11 · EU Annex 11 · This is an automated message from the izQMS audit trail.'
        '</td></tr></table></td></tr></table>'
    )


async def notify_user_event(user_id: str, *, subject: str, title: str, body_html: str,
                            link_path: Optional[str] = None, cta_label: Optional[str] = None,
                            kind: str = "info") -> None:
    """Create an in-app notification AND send an email to the target user."""
    u = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not u:
        return
    await create_notification(user_id, title, body_html_to_plain(body_html), link=link_path, kind=kind)
    if not u.get("email"):
        return
    cta_url = (APP_BASE_URL + link_path) if (APP_BASE_URL and link_path) else None
    html = _email_shell(title, body_html, cta_url, cta_label)
    asyncio.create_task(send_email(u["email"], subject, html, kind=kind))


def body_html_to_plain(html: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


# -------- Password reset CONSUME (link from forgot-password) --------
class ResetPasswordIn(BaseModel):
    token: str
    new_password: str


@api.post("/auth/reset-password")
async def reset_password(payload: ResetPasswordIn):
    rec = await db.password_reset_tokens.find_one({"token": payload.token}, {"_id": 0})
    if not rec or rec.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or already-used token")
    try:
        if datetime.fromisoformat(rec["expires_at"]) < now_utc():
            raise HTTPException(status_code=400, detail="Token expired")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Token expired")
    user = await db.users.find_one({"id": rec["user_id"]})
    if not user:
        raise HTTPException(status_code=400, detail="Invalid token")
    policy = await get_password_policy()
    err = validate_password(payload.new_password, policy)
    if err:
        raise HTTPException(status_code=400, detail=err)
    history = ([user["password_hash"]] + user.get("password_history", []))[: max(1, policy.get("history_size", 5))]
    await db.users.update_one({"id": user["id"]}, {"$set": {
        "password_hash": hash_password(payload.new_password),
        "must_change_password": False,
        "password_changed_at": iso(now_utc()),
        "token_revoked_at": iso(now_utc()),  # invalidate any existing JWTs
        "password_history": history,
        "failed_login_count": 0,
    }})
    await db.password_reset_tokens.update_one({"token": payload.token}, {"$set": {"used": True, "used_at": iso(now_utc())}})
    await db.login_attempts.delete_one({"identifier": user["email"]})
    await log_audit(actor=user, action="PASSWORD_RESET_COMPLETED", entity_type="USER", entity_id=user["id"],
                    reason="User completed password reset via emailed token")
    return {"ok": True}


# -------- Attachments --------
class AttachmentDeleteIn(BaseModel):
    reason: str


def _serialize_attachment(a: dict) -> dict:
    return {k: v for k, v in a.items() if k not in {"_id", "stored_path"}}


@api.post("/records/{record_id}/attachments")
async def upload_attachment(
    record_id: str,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
):
    rec = await db.qms_records.find_one({"id": record_id})
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    if rec["status"] in {"CLOSED"}:
        raise HTTPException(status_code=400, detail="Cannot attach files to a closed record")
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_BYTES // 1024 // 1024} MB)")
    att_id = str(uuid.uuid4())
    safe_name = (file.filename or "file").replace("/", "_").replace("\\", "_")[:240]
    target_dir = UPLOAD_DIR / record_id
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_path = target_dir / f"{att_id}__{safe_name}"
    with open(stored_path, "wb") as fp:
        fp.write(data)
    doc = {
        "id": att_id,
        "record_id": record_id,
        "filename": safe_name,
        "content_type": file.content_type or "application/octet-stream",
        "size_bytes": len(data),
        "uploaded_by": user["id"],
        "uploaded_by_name": user["name"],
        "uploaded_at": iso(now_utc()),
        "description": description or "",
        "deleted": False,
        "stored_path": str(stored_path),
    }
    await db.attachments.insert_one(doc)
    await log_audit(actor=user, action="ATTACHMENT_UPLOAD", entity_type="RECORD", entity_id=record_id,
                    new_value={"filename": safe_name, "size_bytes": len(data), "attachment_id": att_id},
                    reason="File attached")
    return _serialize_attachment(doc)


@api.get("/records/{record_id}/attachments")
async def list_attachments(record_id: str, user: dict = Depends(get_current_user)):
    rows = await db.attachments.find({"record_id": record_id, "deleted": False}, {"_id": 0, "stored_path": 0}).sort("uploaded_at", -1).to_list(200)
    return rows


@api.get("/attachments/{att_id}/download")
async def download_attachment(att_id: str, user: dict = Depends(get_current_user)):
    att = await db.attachments.find_one({"id": att_id, "deleted": False})
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    p = Path(att["stored_path"])
    if not p.exists():
        raise HTTPException(status_code=410, detail="File missing on disk")
    await log_audit(actor=user, action="ATTACHMENT_DOWNLOAD", entity_type="RECORD", entity_id=att["record_id"],
                    new_value={"filename": att["filename"], "attachment_id": att_id}, reason="File downloaded")
    return FileResponse(str(p), media_type=att.get("content_type") or "application/octet-stream", filename=att["filename"])


@api.delete("/attachments/{att_id}")
async def delete_attachment(att_id: str, payload: AttachmentDeleteIn, user: dict = Depends(get_current_user)):
    att = await db.attachments.find_one({"id": att_id, "deleted": False})
    if not att:
        raise HTTPException(status_code=404, detail="Attachment not found")
    if att["uploaded_by"] != user["id"] and not has_any_role(user, ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_QA_MANAGER):
        raise HTTPException(status_code=403, detail="Only uploader or admin/QA Manager can remove an attachment")
    if not payload.reason or len(payload.reason.strip()) < 3:
        raise HTTPException(status_code=400, detail="Reason for deletion is required (min 3 chars)")
    await db.attachments.update_one({"id": att_id}, {"$set": {
        "deleted": True, "deleted_by": user["id"], "deleted_by_name": user["name"],
        "deleted_at": iso(now_utc()), "delete_reason": payload.reason.strip(),
    }})
    await log_audit(actor=user, action="ATTACHMENT_DELETE", entity_type="RECORD", entity_id=att["record_id"],
                    old_value={"filename": att["filename"], "attachment_id": att_id}, reason=payload.reason.strip())
    return {"ok": True}


# -------- Dynamic Form Builder --------
class FormFieldIn(BaseModel):
    key: str
    label: str
    type: str = "text"   # text | textarea | number | select | date | checkbox
    required: bool = False
    options: Optional[List[str]] = None  # for select
    placeholder: Optional[str] = None
    section: Optional[str] = "Additional Details"


class FormSchemaIn(BaseModel):
    module: str         # CHANGE_CONTROL | DEVIATION | CAPA | INCIDENT | EVENT
    fields: List[FormFieldIn]
    reason: Optional[str] = None


@api.get("/form-schemas")
async def list_form_schemas(user: dict = Depends(get_current_user)):
    rows = await db.form_schemas.find({}, {"_id": 0}).to_list(50)
    return rows


@api.get("/form-schemas/{module}")
async def get_form_schema(module: str, user: dict = Depends(get_current_user)):
    s = await db.form_schemas.find_one({"module": module}, {"_id": 0})
    if not s:
        return {"module": module, "fields": []}
    return s


@api.put("/form-schemas/{module}")
async def upsert_form_schema(module: str, payload: FormSchemaIn, actor: dict = Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN))):
    if module != payload.module:
        raise HTTPException(status_code=400, detail="Module mismatch")
    if module not in TYPE_PREFIX:
        raise HTTPException(status_code=400, detail="Unknown module")
    fields_data = [f.model_dump() for f in payload.fields]
    seen = set()
    for f in fields_data:
        if not f.get("key") or not f.get("label"):
            raise HTTPException(status_code=400, detail="Each field needs key + label")
        if f["key"] in seen:
            raise HTTPException(status_code=400, detail=f"Duplicate field key: {f['key']}")
        seen.add(f["key"])
    old = await db.form_schemas.find_one({"module": module}, {"_id": 0}) or {}
    doc = {"module": module, "fields": fields_data, "updated_at": iso(now_utc()), "updated_by": actor["email"]}
    await db.form_schemas.update_one({"module": module}, {"$set": doc}, upsert=True)
    await log_audit(actor=actor, action="FORM_SCHEMA_UPDATE", entity_type="FORM_SCHEMA", entity_id=module,
                    old_value={"fields": old.get("fields", [])}, new_value={"fields": fields_data},
                    reason=payload.reason or "Form schema updated")
    return doc


# -------- Risk Priority Scoring --------
class RiskScoreIn(BaseModel):
    severity: int   # 1-5
    occurrence: int  # 1-5
    detection: int   # 1-5
    reason: Optional[str] = None


def _risk_band(rpn: int) -> str:
    if rpn >= 60:
        return "CRITICAL"
    if rpn >= 30:
        return "HIGH"
    if rpn >= 12:
        return "MEDIUM"
    return "LOW"


@api.post("/records/{record_id}/risk-score")
async def set_risk_score(record_id: str, payload: RiskScoreIn, user: dict = Depends(get_current_user)):
    rec = await db.qms_records.find_one({"id": record_id})
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    for k, v in {"severity": payload.severity, "occurrence": payload.occurrence, "detection": payload.detection}.items():
        if not (1 <= v <= 5):
            raise HTTPException(status_code=400, detail=f"{k} must be 1-5")
    rpn = payload.severity * payload.occurrence * payload.detection
    band = _risk_band(rpn)
    risk = {
        "severity": payload.severity,
        "occurrence": payload.occurrence,
        "detection": payload.detection,
        "rpn": rpn,
        "band": band,
        "scored_by": user["id"],
        "scored_by_name": user["name"],
        "scored_at": iso(now_utc()),
    }
    old = rec.get("risk")
    await db.qms_records.update_one({"id": record_id}, {"$set": {"risk": risk, "updated_at": iso(now_utc())}})
    await log_audit(actor=user, action="RISK_SCORE", entity_type="RECORD", entity_id=record_id,
                    old_value=old or {}, new_value=risk, reason=payload.reason or "Risk Priority Number set")
    return risk


# -------- Reports / Charts data --------
@api.get("/reports/trend")
async def report_trend(months: int = 6, user: dict = Depends(get_current_user)):
    """Return per-month counts grouped by module type for the last N months."""
    months = max(1, min(months, 24))
    today = now_utc()
    buckets: List[str] = []
    # First day of current month minus (months-1)
    cur_year = today.year
    cur_month = today.month
    for offset in range(months - 1, -1, -1):
        y = cur_year
        m = cur_month - offset
        while m <= 0:
            m += 12
            y -= 1
        buckets.append(f"{y:04d}-{m:02d}")
    earliest = buckets[0] + "-01T00:00:00+00:00"
    rows = await db.qms_records.find(
        {"created_at": {"$gte": earliest}},
        {"_id": 0, "type": 1, "created_at": 1, "status": 1}
    ).to_list(10000)
    grid: Dict[str, Dict[str, int]] = {b: {k: 0 for k in TYPE_PREFIX} for b in buckets}
    closed_grid: Dict[str, int] = {b: 0 for b in buckets}
    for r in rows:
        ca = r.get("created_at", "")[:7]
        if ca in grid:
            grid[ca][r["type"]] = grid[ca].get(r["type"], 0) + 1
            if r.get("status") in {"CLOSED", "APPROVED"}:
                closed_grid[ca] += 1
    return {
        "buckets": buckets,
        "by_type": grid,
        "closed_per_month": closed_grid,
    }


@api.get("/reports/aging")
async def report_aging(user: dict = Depends(get_current_user)):
    """Age buckets of currently OPEN/IN_REVIEW records by type."""
    rows = await db.qms_records.find(
        {"status": {"$in": ["OPEN", "IN_REVIEW", "DRAFT"]}},
        {"_id": 0, "type": 1, "created_at": 1, "due_date": 1}
    ).to_list(5000)
    bands = ["0-7", "8-14", "15-30", "31-60", "60+"]
    out = {t: {b: 0 for b in bands} for t in TYPE_PREFIX}
    now = now_utc()
    for r in rows:
        try:
            age_days = (now - datetime.fromisoformat(r["created_at"])).days
        except Exception:
            continue
        if age_days <= 7:
            band = "0-7"
        elif age_days <= 14:
            band = "8-14"
        elif age_days <= 30:
            band = "15-30"
        elif age_days <= 60:
            band = "31-60"
        else:
            band = "60+"
        out[r["type"]][band] = out[r["type"]].get(band, 0) + 1
    return {"bands": bands, "by_type": out}


# -------- Exports --------
def _record_export_columns() -> List[str]:
    return ["record_number", "type", "title", "status", "workflow_stage", "severity", "priority",
            "department", "location", "initiator_name", "created_at", "updated_at", "due_date", "closed_at"]


async def _query_records_for_export(type: Optional[str], status: Optional[str],
                                     from_date: Optional[str], to_date: Optional[str]) -> List[dict]:
    query: Dict[str, Any] = {}
    if type:
        query["type"] = type
    if status:
        query["status"] = status
    if from_date or to_date:
        rng: Dict[str, str] = {}
        if from_date:
            rng["$gte"] = from_date
        if to_date:
            rng["$lte"] = to_date
        query["created_at"] = rng
    return await db.qms_records.find(query, {"_id": 0}).sort("created_at", -1).to_list(20000)


@api.get("/exports/records.csv")
async def export_records_csv(
    type: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    rows = await _query_records_for_export(type, status, from_date, to_date)
    cols = _record_export_columns()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({c: r.get(c, "") for c in cols})
    buf.seek(0)
    await log_audit(actor=user, action="EXPORT_RECORDS_CSV", entity_type="REPORT", entity_id="records",
                    new_value={"rows": len(rows), "filters": {"type": type, "status": status,
                                                              "from_date": from_date, "to_date": to_date}},
                    reason="CSV export")
    return StreamingResponse(iter([buf.read()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="izqms-records-{now_utc().strftime("%Y%m%d")}.csv"'})


@api.get("/exports/records.xlsx")
async def export_records_xlsx(
    type: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    if Workbook is None:
        raise HTTPException(status_code=500, detail="openpyxl not installed")
    rows = await _query_records_for_export(type, status, from_date, to_date)
    cols = _record_export_columns()
    wb = Workbook()
    ws = wb.active
    ws.title = "Records"
    ws.append(cols)
    for r in rows:
        ws.append([str(r.get(c, "")) if r.get(c) is not None else "" for c in cols])
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    await log_audit(actor=user, action="EXPORT_RECORDS_XLSX", entity_type="REPORT", entity_id="records",
                    new_value={"rows": len(rows)}, reason="Excel export")
    return StreamingResponse(out, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="izqms-records-{now_utc().strftime("%Y%m%d")}.xlsx"'})


@api.get("/exports/audit.csv")
async def export_audit_csv(
    entity_type: Optional[str] = None,
    user_email: Optional[str] = None,
    action: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    user: dict = Depends(get_current_user),
):
    query: Dict[str, Any] = {}
    if entity_type:
        query["entity_type"] = entity_type
    if user_email:
        query["user_email"] = user_email
    if action:
        query["action"] = action
    if from_date or to_date:
        rng: Dict[str, str] = {}
        if from_date:
            rng["$gte"] = from_date
        if to_date:
            rng["$lte"] = to_date
        query["timestamp"] = rng
    rows = await db.audit_trail.find(query, {"_id": 0}).sort("timestamp", -1).to_list(50000)
    cols = ["timestamp", "user_email", "user_name", "action", "entity_type", "entity_id", "reason", "old_value", "new_value"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "timestamp": r.get("timestamp", ""),
            "user_email": r.get("user_email", ""),
            "user_name": r.get("user_name", ""),
            "action": r.get("action", ""),
            "entity_type": r.get("entity_type", ""),
            "entity_id": r.get("entity_id", ""),
            "reason": r.get("reason", ""),
            "old_value": str(r.get("old_value", "")),
            "new_value": str(r.get("new_value", "")),
        })
    buf.seek(0)
    await log_audit(actor=user, action="EXPORT_AUDIT_CSV", entity_type="REPORT", entity_id="audit",
                    new_value={"rows": len(rows)}, reason="Audit CSV export")
    return StreamingResponse(iter([buf.read()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="izqms-audit-{now_utc().strftime("%Y%m%d")}.csv"'})


# -------- Email triggers hooked into existing flows --------
# After record_action mutates, send an email to next-in-line / initiator.
# We can't override the existing route cleanly; expose a separate notify hook used by the frontend on key events,
# but for robustness wire it via a post-write fanout that runs whenever notifications are created with kind="workflow".

# Instead, augment notify_user_event API: a generic admin-test endpoint for diagnostics.
@api.post("/admin/email-test")
async def admin_email_test(payload: Dict[str, Any], actor: dict = Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN))):
    to_email = payload.get("to") or actor["email"]
    subject = payload.get("subject") or "izQMS email test"
    body = payload.get("body") or "<p>This is a test email from izQMS.</p>"
    html = _email_shell("izQMS email test", body)
    ok = await send_email(to_email, subject, html, kind="diagnostic")
    return {"ok": ok}


@api.get("/admin/email-log")
async def admin_email_log(limit: int = 50, actor: dict = Depends(require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN))):
    rows = await db.email_log.find({}, {"_id": 0}).sort("timestamp", -1).limit(min(limit, 500)).to_list(min(limit, 500))
    return rows


# =====================================================================
# Deviation Module (9-Part controlled template per the SOP / form layout)
# =====================================================================
from deviation_pdf import build_deviation_pdf  # noqa: E402

DEVIATION_PARTS = ["part1", "part2", "part3", "part4", "part5", "part6", "part7", "part8", "part9"]

DEVIATION_BLOCKS: Dict[str, Dict[str, str]] = {
    # block_key -> {meaning, required_role}
    "assigned_by_qa":          {"meaning": "Deviation number assigned by QA",       "role": "qa_head"},
    "part1_initiated_by":      {"meaning": "Initiated By — Part 1",                  "role": "initiator"},
    "part1_reviewed_by":       {"meaning": "Reviewed By — Part 1 (HOD/Designee)",    "role": "reviewer"},
    "part3_recorded_by":       {"meaning": "Recorded By — Part 3",                   "role": "initiator"},
    "part3_reviewed_by":       {"meaning": "Reviewed By — Part 3 (HOD/Designee)",    "role": "reviewer"},
    "part6_recorded_by":       {"meaning": "Recorded By — Part 6 (CAPA)",            "role": "initiator"},
    "part6_reviewed_by":       {"meaning": "Reviewed By — Part 6 (HOD/Designee)",    "role": "reviewer"},
    "part9_qa_reviewed_by":    {"meaning": "QA Reviewed — Part 9",                    "role": "qa_head"},
    "part9_qa_head_closure":   {"meaning": "QA Head/Designee — Final Closure",       "role": "qa_head"},
}
# Per-extension block roles (part7_requested_N / part7_hod_N / part7_qa_N) and
# per-dept block (part8_dept_N) are evaluated dynamically.


class DeviationSavePartIn(BaseModel):
    part: str               # "part1" .. "part9"
    data: Dict[str, Any]
    reason: Optional[str] = None


class DeviationExtensionIn(BaseModel):
    revised_target_date: str
    justification: str
    reason: Optional[str] = None


class DeviationDeptCommentIn(BaseModel):
    department: str
    comments: str
    reason: Optional[str] = None


class DeviationSignIn(BaseModel):
    block: str
    password: str           # e-signature: re-enter password
    comment: Optional[str] = None
    reason: Optional[str] = None


def _has_role(user: dict, *roles: str) -> bool:
    """Deviation-module role check. Accepts both legacy (initiator/reviewer/
    approver/qa_head) and canonical role names. Uses ROLE_EXPANSION so
    super_admin > admin > qa_manager > qa_reviewer > employee."""
    return has_any_role(user, *roles)


async def _get_deviation(record_id: str) -> dict:
    rec = await db.qms_records.find_one({"id": record_id})
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    if rec.get("type") != "DEVIATION":
        raise HTTPException(status_code=400, detail="Record is not a Deviation")
    return rec


async def _check_block_role(block: str, user: dict, rec: dict) -> None:
    # Static blocks
    spec = DEVIATION_BLOCKS.get(block)
    if spec:
        if not _has_role(user, spec["role"]):
            raise HTTPException(status_code=403, detail=f"Role {spec['role']} required for {block}")
        return
    # Dynamic blocks
    if block.startswith("part7_"):
        # part7_requested_N -> any user; part7_hod_N -> reviewer/qa_head; part7_qa_N -> qa_head
        if block.startswith("part7_requested_"):
            return
        if block.startswith("part7_hod_") and _has_role(user, "reviewer", "qa_head"):
            return
        if block.startswith("part7_qa_") and _has_role(user, "qa_head"):
            return
        raise HTTPException(status_code=403, detail=f"Insufficient role for {block}")
    if block.startswith("part8_dept_"):
        # Any user from "other department" can comment — restricting to authenticated user is enough
        return
    raise HTTPException(status_code=400, detail=f"Unknown signature block: {block}")


@api.get("/deviations/{record_id}")
async def get_deviation(record_id: str, user: dict = Depends(get_current_user)):
    rec = await _get_deviation(record_id)
    sigs = await db.deviation_signatures.find({"record_id": record_id}, {"_id": 0}).sort("timestamp", 1).to_list(500)
    rec["signatures"] = sigs
    return {k: v for k, v in rec.items() if k != "_id"}


@api.put("/deviations/{record_id}/parts")
async def save_part(record_id: str, payload: DeviationSavePartIn, user: dict = Depends(get_current_user)):
    if payload.part not in DEVIATION_PARTS:
        raise HTTPException(status_code=400, detail="Invalid part key")
    rec = await _get_deviation(record_id)
    if rec.get("status") in {"CLOSED"}:
        raise HTTPException(status_code=400, detail="Record is closed; no edits allowed")
    # Once a part is signed-off, prevent edits unless admin/qa overrides.
    signed_blocks = await db.deviation_signatures.find({"record_id": record_id}, {"_id": 0, "block": 1}).to_list(200)
    signed_set = {s["block"] for s in signed_blocks}
    locks_for_part = {
        "part1": {"part1_initiated_by", "part1_reviewed_by"},
        "part3": {"part3_recorded_by", "part3_reviewed_by"},
        "part6": {"part6_recorded_by", "part6_reviewed_by"},
        "part9": {"part9_qa_reviewed_by", "part9_qa_head_closure"},
    }
    locks = locks_for_part.get(payload.part, set())
    if locks & signed_set and not _has_role(user, "admin"):
        raise HTTPException(status_code=400, detail=f"{payload.part} is locked by an e-signature; cannot edit")
    cur = rec.get("deviation_data") or {}
    old_part = cur.get(payload.part, {})
    cur[payload.part] = payload.data
    await db.qms_records.update_one({"id": record_id}, {"$set": {"deviation_data": cur, "updated_at": iso(now_utc())}})
    await log_audit(actor=user, action="DEVIATION_EDIT", entity_type="RECORD", entity_id=record_id,
                    old_value={payload.part: old_part}, new_value={payload.part: payload.data},
                    reason=payload.reason or f"Updated {payload.part}")
    return {"ok": True}


@api.post("/deviations/{record_id}/extensions")
async def add_extension(record_id: str, payload: DeviationExtensionIn, user: dict = Depends(get_current_user)):
    rec = await _get_deviation(record_id)
    if rec.get("status") in {"CLOSED"}:
        raise HTTPException(status_code=400, detail="Record is closed")
    d = rec.get("deviation_data") or {}
    p7 = d.get("part7") or {"extensions": []}
    if not isinstance(p7, dict):
        p7 = {"extensions": p7 if isinstance(p7, list) else []}
    p7.setdefault("extensions", []).append({
        "id": str(uuid.uuid4()),
        "revised_target_date": payload.revised_target_date,
        "justification": payload.justification,
        "requested_by": user["id"],
        "requested_by_name": user["name"],
        "requested_at": iso(now_utc()),
    })
    d["part7"] = p7
    await db.qms_records.update_one({"id": record_id}, {"$set": {"deviation_data": d, "updated_at": iso(now_utc())}})
    await log_audit(actor=user, action="DEVIATION_EXTENSION_REQUEST", entity_type="RECORD", entity_id=record_id,
                    new_value={"revised_target_date": payload.revised_target_date, "justification": payload.justification},
                    reason=payload.reason or "Closure extension requested")
    return p7


@api.post("/deviations/{record_id}/department-comments")
async def add_dept_comment(record_id: str, payload: DeviationDeptCommentIn, user: dict = Depends(get_current_user)):
    rec = await _get_deviation(record_id)
    if rec.get("status") in {"CLOSED"}:
        raise HTTPException(status_code=400, detail="Record is closed")
    d = rec.get("deviation_data") or {}
    p8 = d.get("part8") or []
    p8.append({
        "id": str(uuid.uuid4()),
        "department": payload.department,
        "comments": payload.comments,
        "by_user_id": user["id"],
        "by_user_name": user["name"],
        "at": iso(now_utc()),
    })
    d["part8"] = p8
    await db.qms_records.update_one({"id": record_id}, {"$set": {"deviation_data": d, "updated_at": iso(now_utc())}})
    await log_audit(actor=user, action="DEVIATION_DEPT_COMMENT", entity_type="RECORD", entity_id=record_id,
                    new_value={"department": payload.department, "comments": payload.comments},
                    reason=payload.reason or "Other-department comment recorded")
    return p8


@api.post("/deviations/{record_id}/sign")
async def sign_block(record_id: str, payload: DeviationSignIn, user: dict = Depends(get_current_user)):
    rec = await _get_deviation(record_id)
    if rec.get("status") in {"CLOSED"}:
        raise HTTPException(status_code=400, detail="Record is closed")
    # Verify e-signature password
    db_user = await db.users.find_one({"id": user["id"]})
    if not db_user or not verify_password(payload.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="E-signature failed: invalid password")
    await _check_block_role(payload.block, user, rec)
    # Prevent duplicate signatures on the same block
    existing = await db.deviation_signatures.find_one({"record_id": record_id, "block": payload.block})
    if existing:
        raise HTTPException(status_code=400, detail="Block already signed")
    meaning = DEVIATION_BLOCKS.get(payload.block, {}).get("meaning") or payload.block
    sig = {
        "id": str(uuid.uuid4()),
        "record_id": record_id,
        "block": payload.block,
        "user_id": user["id"],
        "user_email": user["email"],
        "user_name": user["name"],
        "meaning": meaning,
        "comment": payload.comment or "",
        "timestamp": iso(now_utc()),
    }
    await db.deviation_signatures.insert_one(sig)
    sig.pop("_id", None)
    # Auto-status progression
    new_status = rec.get("status")
    if payload.block == "part1_reviewed_by" and rec.get("status") == "DRAFT":
        new_status = "OPEN"
    elif payload.block == "part6_reviewed_by" and rec.get("status") in {"OPEN", "DRAFT"}:
        new_status = "IN_REVIEW"
    elif payload.block == "part9_qa_reviewed_by" and rec.get("status") == "IN_REVIEW":
        new_status = "APPROVED"
    elif payload.block == "part9_qa_head_closure":
        new_status = "CLOSED"
    updates: Dict[str, Any] = {"updated_at": iso(now_utc())}
    if new_status != rec.get("status"):
        updates["status"] = new_status
        if new_status == "CLOSED":
            updates["closed_at"] = iso(now_utc())
    await db.qms_records.update_one({"id": record_id}, {"$set": updates})
    await log_audit(actor=user, action="DEVIATION_SIGN", entity_type="RECORD", entity_id=record_id,
                    new_value={"block": payload.block, "meaning": meaning, "status": new_status},
                    reason=payload.reason or f"E-signature: {meaning}")
    return {"ok": True, "signature": sig, "status": new_status}


@api.get("/deviations/{record_id}/pdf")
async def deviation_pdf(record_id: str, user: dict = Depends(get_current_user)):
    rec = await _get_deviation(record_id)
    sigs = await db.deviation_signatures.find({"record_id": record_id}, {"_id": 0}).sort("timestamp", 1).to_list(500)
    audit = await db.audit_trail.find({"entity_id": record_id}, {"_id": 0}).sort("timestamp", -1).to_list(60)
    pdf_bytes = build_deviation_pdf(rec, sigs, list(reversed(audit)))
    await log_audit(actor=user, action="DEVIATION_PDF_EXPORT", entity_type="RECORD", entity_id=record_id,
                    new_value={"size_bytes": len(pdf_bytes)}, reason="Deviation PDF downloaded")
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{rec.get("record_number","deviation")}.pdf"'},
    )


# =====================================================================
# Generic PDF exports (Audit trail + any Module-Framework dynamic record)
# Every download is logged in the audit trail (URS izQMS §4.0).
# =====================================================================
from generic_pdf import build_dynamic_record_pdf, build_audit_trail_pdf, build_legacy_record_pdf, build_reports_pdf  # noqa: E402


@api.get("/audit/pdf")
async def audit_trail_pdf(
    entity_type: Optional[str] = None,
    user_email: Optional[str] = None,
    action: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 2000,
    user: dict = Depends(get_current_user),
):
    # Same filter logic as /audit
    query: Dict[str, Any] = {}
    if entity_type:
        query["entity_type"] = entity_type
    if user_email:
        query["user_email"] = user_email
    if action:
        query["action"] = action
    if from_date or to_date:
        rng: Dict[str, str] = {}
        if from_date:
            rng["$gte"] = from_date
        if to_date:
            rng["$lte"] = to_date
        query["timestamp"] = rng
    rows = await db.audit_trail.find(query, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    pdf_bytes = build_audit_trail_pdf(
        rows=rows,
        filters={"entity_type": entity_type, "action": action, "user_email": user_email,
                 "from_date": from_date, "to_date": to_date},
        printed_by={"name": user.get("name"), "email": user.get("email")},
    )
    await log_audit(actor=user, action="AUDIT_PDF_EXPORT", entity_type="AUDIT_TRAIL", entity_id="GLOBAL",
                    new_value={"rows": len(rows), "size_bytes": len(pdf_bytes), "filters": query},
                    reason="Audit Trail PDF downloaded")
    fname = f"audit-trail-{datetime.utcnow().strftime('%Y%m%d-%H%M')}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@api.get("/module-framework/records/{record_id}/pdf")
async def dynamic_record_pdf(record_id: str, user: dict = Depends(get_current_user)):
    rec = await db.dynamic_records.find_one({"id": record_id}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "Dynamic record not found")
    tpl = await db.module_templates.find_one({"id": rec["template_id"]}, {"_id": 0})
    if not tpl:
        raise HTTPException(400, "Bound template no longer exists")
    audit = await db.audit_trail.find(
        {"entity_type": "DYNAMIC_RECORD", "entity_id": record_id}, {"_id": 0},
    ).sort("timestamp", -1).to_list(500)
    pdf_bytes = build_dynamic_record_pdf(
        record=rec, template=tpl, audit_trail=audit,
        printed_by={"name": user.get("name"), "email": user.get("email")},
    )
    await log_audit(actor=user, action="DYN_RECORD_PDF_EXPORT", entity_type="DYNAMIC_RECORD",
                    entity_id=record_id, new_value={"size_bytes": len(pdf_bytes),
                                                    "template_code": tpl.get("code"),
                                                    "template_version": tpl.get("version")},
                    reason="Dynamic record PDF downloaded")
    fname = f"{rec.get('record_number','record')}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@api.get("/records/{record_id}/pdf")
async def legacy_record_pdf(record_id: str, user: dict = Depends(get_current_user)):
    """Generic PDF export for any legacy QMS record (Change Control / CAPA /
    Incident / Event). For DEVIATION records we delegate to the dedicated
    9-Part renderer (build_deviation_pdf). Every download is logged in the
    global audit trail per URS izQMS §4.0 / 21 CFR Part 11."""
    rec = await db.qms_records.find_one({"id": record_id}, {"_id": 0})
    if not rec:
        raise HTTPException(404, "Record not found")
    audit = await db.audit_trail.find({"entity_id": record_id}, {"_id": 0}).sort("timestamp", -1).to_list(200)
    if rec.get("type") == "DEVIATION":
        sigs = await db.deviation_signatures.find({"record_id": record_id}, {"_id": 0}).sort("timestamp", 1).to_list(500)
        pdf_bytes = build_deviation_pdf(rec, sigs, list(reversed(audit)))
        action = "DEVIATION_PDF_EXPORT"
    else:
        workflow = await db.workflow_events.find({"record_id": record_id}, {"_id": 0}).sort("timestamp", 1).to_list(500) if hasattr(db, "workflow_events") else []
        # Fall back to /records/{id}/workflow shape (matches existing endpoint)
        try:
            workflow_rows = await db.workflow_events.find({"record_id": record_id}, {"_id": 0}).sort("timestamp", 1).to_list(500)
        except Exception:
            workflow_rows = []
        # Pull comments
        try:
            cmts = await db.comments.find({"record_id": record_id}, {"_id": 0}).sort("timestamp", 1).to_list(200)
        except Exception:
            cmts = []
        # Pull bound template (when there is one)
        tpl = None
        tpl_id = rec.get("framework_template_id")
        if tpl_id:
            tpl = await db.module_templates.find_one({"id": tpl_id}, {"_id": 0})
        if not tpl and rec.get("type"):
            tpl = await db.module_templates.find_one(
                {"category": rec["type"], "plant_id": "GLOBAL", "status": "PUBLISHED"},
                {"_id": 0}, sort=[("version", -1)],
            )
        pdf_bytes = build_legacy_record_pdf(
            record=rec, template=tpl,
            workflow=workflow_rows, audit_trail=audit, comments=cmts,
            printed_by={"name": user.get("name"), "email": user.get("email")},
        )
        action = "RECORD_PDF_EXPORT"
    await log_audit(actor=user, action=action, entity_type="RECORD", entity_id=record_id,
                    new_value={"size_bytes": len(pdf_bytes), "type": rec.get("type")},
                    reason=f"{rec.get('type','')} PDF downloaded")
    fname = f"{rec.get('record_number','record')}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ============================================================================
# Generic Section-Save / Section-Sign for non-DEVIATION QMS records
# (Change Control / CAPA / Incident / Event).
# Mirrors the Deviation flow: each PUBLISHED template section can be saved
# independently, then signed by the role mapped on that section. Once signed,
# fields in that section become read-only and signature is immutable.
# Stored in `record_signatures` collection.
# ============================================================================
class SectionSaveIn(BaseModel):
    section_key: str
    data: Dict[str, Any] = {}
    reason: Optional[str] = None


class SectionSignIn(BaseModel):
    section_key: str
    signer_role: str            # e.g. "initiator", "reviewer", "approver", "qa_head", or a free label like "Recorded By"
    password: str               # e-signature re-auth
    reason: Optional[str] = None
    comment: Optional[str] = None


async def _get_record_or_404(record_id: str) -> dict:
    rec = await db.qms_records.find_one({"id": record_id})
    if not rec:
        raise HTTPException(404, "Record not found")
    return rec


@api.get("/records/{record_id}/signatures")
async def list_record_signatures(record_id: str, user: dict = Depends(get_current_user)):
    rec = await _get_record_or_404(record_id)
    if not _record_is_visible(rec, user):
        raise HTTPException(403, "You do not have permission to view this record")
    coll = db.deviation_signatures if rec.get("type") == "DEVIATION" else db.record_signatures
    sigs = await coll.find({"record_id": record_id}, {"_id": 0}).sort("timestamp", 1).to_list(500)
    return sigs


@api.post("/records/{record_id}/section-save")
async def section_save(record_id: str, payload: SectionSaveIn, user: dict = Depends(get_current_user)):
    """Save a single template-section's worth of fields into the record's
    framework_form_data.  Works for any non-DEVIATION QMS record bound to a
    published Module Framework template."""
    rec = await _get_record_or_404(record_id)
    if not _record_is_visible(rec, user):
        raise HTTPException(403, "You do not have permission to edit this record")
    if rec.get("status") in {"CLOSED"}:
        raise HTTPException(400, "Record is closed; no edits allowed")
    if not has_permission(user, "edit_draft"):
        raise HTTPException(403, "Your role does not permit editing records")
    existing_sig = await db.record_signatures.find_one(
        {"record_id": record_id, "section_key": payload.section_key},
    )
    if existing_sig:
        raise HTTPException(400, f"Section '{payload.section_key}' is already signed and cannot be edited")
    old_section = (rec.get("framework_form_data") or {}).get(payload.section_key) or {}
    new_form = dict(rec.get("framework_form_data") or {})
    new_form[payload.section_key] = payload.data
    await db.qms_records.update_one(
        {"id": record_id},
        {"$set": {"framework_form_data": new_form, "updated_at": iso(now_utc())}},
    )
    await log_audit(actor=user, action="SECTION_SAVE", entity_type="RECORD", entity_id=record_id,
                    old_value={payload.section_key: old_section},
                    new_value={payload.section_key: payload.data},
                    reason=payload.reason or f"Saved section {payload.section_key}")
    return {"ok": True, "section_key": payload.section_key}


@api.post("/records/{record_id}/section-sign")
async def section_sign(record_id: str, payload: SectionSignIn, user: dict = Depends(get_current_user)):
    """Apply an e-signature to a template section. Verifies the user's password,
    writes an immutable record_signatures entry, and audits the action.
    """
    rec = await _get_record_or_404(record_id)
    if not _record_is_visible(rec, user):
        raise HTTPException(403, "You do not have permission to sign this record")
    if rec.get("status") in {"CLOSED"}:
        raise HTTPException(400, "Record is closed; no signatures can be added")
    if not payload.reason or len(payload.reason) < 3:
        raise HTTPException(400, "Reason is required (>=3 chars)")
    full = await db.users.find_one({"id": user["id"]})
    if not full or not verify_password(payload.password, full["password_hash"]):
        await log_audit(actor=user, action="SECTION_SIGN_FAIL", entity_type="RECORD",
                        entity_id=record_id, reason="Invalid e-signature password",
                        new_value={"section_key": payload.section_key})
        raise HTTPException(401, "Invalid e-signature password")
    dup = await db.record_signatures.find_one(
        {"record_id": record_id, "section_key": payload.section_key},
    )
    if dup:
        raise HTTPException(400, f"Section '{payload.section_key}' is already signed")
    sig_doc = {
        "id": str(uuid.uuid4()),
        "record_id": record_id,
        "record_number": rec.get("record_number"),
        "record_type": rec.get("type"),
        "section_key": payload.section_key,
        "signer_role": payload.signer_role,
        "signer_id": user["id"],
        "signer_name": user.get("name"),
        "signer_email": user.get("email"),
        "comment": payload.comment or "",
        "reason": payload.reason,
        "timestamp": iso(now_utc()),
    }
    await db.record_signatures.insert_one(sig_doc)
    sig_doc.pop("_id", None)
    await log_audit(actor=user, action="SECTION_SIGN", entity_type="RECORD", entity_id=record_id,
                    new_value={k: v for k, v in sig_doc.items() if k != "id"},
                    reason=payload.reason)
    return sig_doc



@api.get("/reports/pdf")
async def reports_pdf(
    type: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    include_workflows: bool = True,
    limit: int = 2000,
    user: dict = Depends(get_current_user),
):
    """Comprehensive QMS report PDF: filtered records table, by-module x status
    summary, and an optional per-record workflow appendix. Includes the
    compliant footer with 'Printed by ...  Page X of Y'."""
    query: Dict[str, Any] = {}
    if type and type != "ALL":
        query["type"] = type
    if status and status != "ALL":
        query["status"] = status
    if from_date or to_date:
        rng: Dict[str, str] = {}
        if from_date:
            rng["$gte"] = from_date
        if to_date:
            rng["$lte"] = to_date
        query["created_at"] = rng
    rows = await db.qms_records.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    workflows_by_id: Dict[str, List[Dict[str, Any]]] = {}
    if include_workflows and rows:
        ids = [r["id"] for r in rows]
        try:
            wf_rows = await db.workflow_events.find({"record_id": {"$in": ids}}, {"_id": 0}).sort("timestamp", 1).to_list(10000)
        except Exception:
            wf_rows = []
        for w in wf_rows:
            workflows_by_id.setdefault(w.get("record_id"), []).append(w)
    pdf_bytes = build_reports_pdf(
        rows=rows,
        filters={"type": type, "status": status, "from_date": from_date, "to_date": to_date},
        include_workflows=include_workflows,
        workflows_by_id=workflows_by_id,
        printed_by={"name": user.get("name"), "email": user.get("email")},
    )
    await log_audit(actor=user, action="REPORTS_PDF_EXPORT", entity_type="REPORT", entity_id="GLOBAL",
                    new_value={"rows": len(rows), "size_bytes": len(pdf_bytes), "filters": query,
                               "include_workflows": include_workflows},
                    reason="QMS Reports PDF downloaded")
    fname = f"izqms-report-{datetime.utcnow().strftime('%Y%m%d-%H%M')}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@api.post("/module-framework/records/{record_id}/migrate-version")
async def migrate_dynamic_record_to_latest(record_id: str, user: dict = Depends(get_current_user)):
    """Rebinds a dynamic record to the latest PUBLISHED version of its template
    (same code, same plant_id). Used after the admin publishes an updated
    framework to roll forward live records.
    """
    rec = await db.dynamic_records.find_one({"id": record_id})
    if not rec:
        raise HTTPException(404, "Record not found")
    current_tpl = await db.module_templates.find_one({"id": rec["template_id"]})
    if not current_tpl:
        raise HTTPException(400, "Bound template no longer exists")
    latest = await db.module_templates.find_one(
        {"code": current_tpl["code"], "plant_id": current_tpl.get("plant_id"), "status": "PUBLISHED"},
        sort=[("version", -1)],
    )
    if not latest:
        raise HTTPException(400, "No PUBLISHED version available for this template")
    if latest["id"] == current_tpl["id"]:
        return {"ok": True, "noop": True, "version": latest["version"], "record_id": record_id}
    old_v, new_v = current_tpl["version"], latest["version"]
    await db.dynamic_records.update_one(
        {"id": record_id},
        {"$set": {
            "template_id": latest["id"],
            "template_code": latest["code"],
            "template_version": latest["version"],
            "template_name": latest["name"],
            "updated_at": iso(now_utc()),
        }},
    )
    await log_audit(
        actor=user, action="DYN_RECORD_MIGRATE_VERSION", entity_type="DYNAMIC_RECORD",
        entity_id=record_id,
        old_value={"template_id": current_tpl["id"], "template_version": old_v},
        new_value={"template_id": latest["id"], "template_version": new_v},
        reason=f"Migrated record from v{old_v} to v{new_v}",
    )
    return {"ok": True, "from_version": old_v, "to_version": new_v, "record_id": record_id}


# =====================================================================
# Dynamic Role Management module wiring (must be before include_router)
# =====================================================================
from role_mgmt import register_role_mgmt_routes  # noqa: E402

register_role_mgmt_routes(
    api,
    db=db,
    get_current_user=get_current_user,
    require_role=require_role,
    log_audit=log_audit,
    verify_esignature=verify_esignature,
    ROLE_ADMIN=ROLE_ADMIN,
    ROLE_SUPER_ADMIN=ROLE_SUPER_ADMIN,
)

# =====================================================================
# Plant/Site-Based Dynamic Module Framework wiring (isolated subsystem)
# =====================================================================
from module_framework import register_module_framework_routes  # noqa: E402

register_module_framework_routes(
    api,
    db=db,
    get_current_user=get_current_user,
    require_role=require_role,
    log_audit=log_audit,
    verify_esignature=verify_esignature,
    ROLE_ADMIN=ROLE_ADMIN,
    ROLE_SUPER_ADMIN=ROLE_SUPER_ADMIN,
)

app.include_router(api)


