"""
izQMS — Dynamic Role Management Module
---------------------------------------
Implements the dedicated Role Matrix system requested by the problem statement:

- CRUD for roles (create / edit / activate-deactivate / copy / list)
- Module-wise + Action-wise Yes/No permission matrix per role
- User-specific permission overrides (Additional / Restricted / Temporary)
- Effective permission calculation (roles ∪ additional overrides − restricted overrides,
  respecting temporary expiry)
- Full audit-trail recording of every permission change (who / when / old / new / reason)

The legacy hard-coded permission helpers in server.py (`has_permission`,
`PERMISSION_MATRIX`, etc.) remain untouched for backward compatibility with the
existing QMS workflow endpoints.  This module operates **on top** of them so
new dynamic permissions can be added without code changes.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field


# ============================================================================
# Module catalog — single source of truth for Yes/No matrix UI.
# Every module + action that the dynamic Role Matrix can grant/deny lives here.
# Adding a new entry here is the only code change required to expose a new
# permission to the Role Management UI.
# ============================================================================
MODULE_CATALOG: Dict[str, Dict[str, Any]] = {
    "deviation": {
        "label": "Deviation",
        "group": "QMS Records",
        "actions": [
            {"key": "view_own", "label": "View own records"},
            {"key": "view_all", "label": "View all records"},
            {"key": "create", "label": "Create"},
            {"key": "edit", "label": "Edit"},
            {"key": "review", "label": "Review"},
            {"key": "approve", "label": "Approve"},
            {"key": "reject", "label": "Reject"},
            {"key": "close", "label": "Close"},
            {"key": "reopen", "label": "Reopen"},
            {"key": "export_pdf", "label": "Export PDF"},
        ],
    },
    "capa": {
        "label": "CAPA",
        "group": "QMS Records",
        "actions": [
            {"key": "view_own", "label": "View own records"},
            {"key": "view_all", "label": "View all records"},
            {"key": "create", "label": "Create"},
            {"key": "edit", "label": "Edit"},
            {"key": "review", "label": "Review"},
            {"key": "approve", "label": "Approve"},
            {"key": "close", "label": "Close"},
            {"key": "export_pdf", "label": "Export PDF"},
        ],
    },
    "change_control": {
        "label": "Change Control",
        "group": "QMS Records",
        "actions": [
            {"key": "view_own", "label": "View own records"},
            {"key": "view_all", "label": "View all records"},
            {"key": "create", "label": "Create"},
            {"key": "edit", "label": "Edit"},
            {"key": "review", "label": "Review"},
            {"key": "approve", "label": "Approve"},
            {"key": "reject", "label": "Reject"},
            {"key": "close", "label": "Close"},
            {"key": "reopen", "label": "Reopen"},
            {"key": "export_pdf", "label": "Export PDF"},
        ],
    },
    "incident": {
        "label": "Incident",
        "group": "QMS Records",
        "actions": [
            {"key": "view_own", "label": "View own records"},
            {"key": "view_all", "label": "View all records"},
            {"key": "create", "label": "Create"},
            {"key": "edit", "label": "Edit"},
            {"key": "review", "label": "Review"},
            {"key": "approve", "label": "Approve"},
            {"key": "close", "label": "Close"},
            {"key": "export_pdf", "label": "Export PDF"},
        ],
    },
    "event": {
        "label": "Event",
        "group": "QMS Records",
        "actions": [
            {"key": "view_own", "label": "View own records"},
            {"key": "view_all", "label": "View all records"},
            {"key": "create", "label": "Create"},
            {"key": "edit", "label": "Edit"},
            {"key": "review", "label": "Review"},
            {"key": "approve", "label": "Approve"},
            {"key": "close", "label": "Close"},
            {"key": "export_pdf", "label": "Export PDF"},
        ],
    },
    "dashboard": {
        "label": "Dashboard",
        "group": "Insights",
        "actions": [
            {"key": "view_dashboard", "label": "View Dashboard"},
            {"key": "view_kpi", "label": "View KPI"},
            {"key": "export_dashboard", "label": "Export Dashboard"},
        ],
    },
    "reports": {
        "label": "Reports",
        "group": "Insights",
        "actions": [
            {"key": "view", "label": "View"},
            {"key": "export_pdf", "label": "Export PDF"},
            {"key": "export_excel", "label": "Export Excel"},
        ],
    },
    "audit_trail": {
        "label": "Audit Trail",
        "group": "Compliance",
        "actions": [
            {"key": "view", "label": "View"},
            {"key": "export", "label": "Export"},
            {"key": "view_full", "label": "View Full Trail"},
        ],
    },
    "esignature": {
        "label": "Electronic Signature",
        "group": "Compliance",
        "actions": [
            {"key": "sign", "label": "Sign Records"},
            {"key": "verify", "label": "Verify Signatures"},
        ],
    },
    "user_management": {
        "label": "User Management",
        "group": "Administration",
        "actions": [
            {"key": "create_user", "label": "Create User"},
            {"key": "edit_user", "label": "Edit User"},
            {"key": "reset_password", "label": "Reset Password"},
            {"key": "assign_role", "label": "Assign Role"},
            {"key": "activate", "label": "Activate"},
            {"key": "deactivate", "label": "Deactivate"},
            {"key": "lock", "label": "Lock"},
            {"key": "unlock", "label": "Unlock"},
            {"key": "approve", "label": "Approve"},
        ],
    },
    "role_management": {
        "label": "Role Management",
        "group": "Administration",
        "actions": [
            {"key": "create_role", "label": "Create Role"},
            {"key": "edit_role", "label": "Edit Role"},
            {"key": "copy_role", "label": "Copy Role"},
            {"key": "activate_role", "label": "Activate/Deactivate Role"},
            {"key": "manage_permissions", "label": "Manage Role Permissions"},
            {"key": "manage_user_overrides", "label": "Manage User Permissions"},
            {"key": "view_audit", "label": "View Role Audit"},
        ],
    },
    "workflow": {
        "label": "Workflow",
        "group": "Administration",
        "actions": [
            {"key": "view", "label": "View Workflow"},
            {"key": "configure", "label": "Configure Workflow"},
        ],
    },
    "module_framework": {
        "label": "Module Framework",
        "group": "Administration",
        "actions": [
            {"key": "view_module_framework",   "label": "View Module Framework"},
            {"key": "manage_module_templates", "label": "Create / Edit Templates (DRAFT)"},
            {"key": "publish_module_templates","label": "Publish Templates (DRAFT → PUBLISHED)"},
            {"key": "retire_module_templates", "label": "Retire Published Templates"},
        ],
    },
}


def _valid_module_action(module: str, action: str) -> bool:
    m = MODULE_CATALOG.get(module)
    if not m:
        return False
    return any(a["key"] == action for a in m["actions"])


def _all_module_actions() -> List[str]:
    out = []
    for mk, mv in MODULE_CATALOG.items():
        for a in mv["actions"]:
            out.append(f"{mk}.{a['key']}")
    return out


def _empty_permissions(default: bool = False) -> Dict[str, Dict[str, bool]]:
    return {
        mk: {a["key"]: default for a in mv["actions"]}
        for mk, mv in MODULE_CATALOG.items()
    }


# ============================================================================
# Default seed roles
# ============================================================================
# Each entry: (code, name, description, *_access flags, permission preset).
# `permission_preset` is a dict {module: [action_keys_granted]}; everything not
# listed is denied.  These mirror the canonical role matrix already in server.py
# so the dynamic system is back-compat with the existing canonical role names.
# ============================================================================
SEED_ROLES: List[Dict[str, Any]] = [
    {
        "code": "super_admin",
        "name": "Super Administrator",
        "description": "Full unrestricted system access. All modules, all actions, including role and workflow configuration.",
        "is_system": True,
        "department_access": ["ALL"],
        "module_access": list(MODULE_CATALOG.keys()),
        "workflow_access": True,
        "approval_access": True,
        "review_access": True,
        "electronic_signature_access": True,
        "report_access": True,
        "audit_trail_access": True,
        "permission_preset": "ALL",  # special marker
    },
    {
        "code": "admin",
        "name": "Administrator",
        "description": "Administrative access: user management, role assignment (limited), workflow monitoring, full audit trail.",
        "is_system": True,
        "department_access": ["ALL"],
        "module_access": list(MODULE_CATALOG.keys()),
        "workflow_access": True,
        "approval_access": True,
        "review_access": True,
        "electronic_signature_access": True,
        "report_access": True,
        "audit_trail_access": True,
        "permission_preset": "ALL",
    },
    {
        "code": "qa_manager",
        "name": "QA Manager",
        "description": "Reviews and approves QMS records. E-signature approval, record closure, audit trail view.",
        "is_system": True,
        "department_access": ["Quality Assurance", "ALL"],
        "module_access": ["deviation", "capa", "change_control", "incident", "event", "dashboard", "reports", "audit_trail", "esignature"],
        "workflow_access": False,
        "approval_access": True,
        "review_access": True,
        "electronic_signature_access": True,
        "report_access": True,
        "audit_trail_access": True,
        "permission_preset": {
            "deviation": ["view_all", "view_own", "create", "edit", "review", "approve", "reject", "close", "reopen", "export_pdf"],
            "capa": ["view_all", "view_own", "create", "edit", "review", "approve", "close", "export_pdf"],
            "change_control": ["view_all", "view_own", "create", "edit", "review", "approve", "reject", "close", "reopen", "export_pdf"],
            "incident": ["view_all", "view_own", "create", "edit", "review", "approve", "close", "export_pdf"],
            "event": ["view_all", "view_own", "create", "edit", "review", "approve", "close", "export_pdf"],
            "dashboard": ["view_dashboard", "view_kpi", "export_dashboard"],
            "reports": ["view", "export_pdf", "export_excel"],
            "audit_trail": ["view", "export"],
            "esignature": ["sign", "verify"],
            "module_framework": ["view_module_framework", "manage_module_templates", "publish_module_templates", "retire_module_templates"],
        },
    },
    {
        "code": "qa_reviewer",
        "name": "QA Reviewer",
        "description": "Reviews and verifies records, adds comments, rejects or sends for correction. View reports.",
        "is_system": True,
        "department_access": ["Quality Assurance"],
        "module_access": ["deviation", "capa", "change_control", "incident", "event", "dashboard", "reports", "audit_trail", "esignature"],
        "workflow_access": False,
        "approval_access": False,
        "review_access": True,
        "electronic_signature_access": True,
        "report_access": True,
        "audit_trail_access": True,
        "permission_preset": {
            "deviation": ["view_all", "view_own", "create", "edit", "review", "reject", "export_pdf"],
            "capa": ["view_all", "view_own", "create", "edit", "review", "export_pdf"],
            "change_control": ["view_all", "view_own", "create", "edit", "review", "reject", "export_pdf"],
            "incident": ["view_all", "view_own", "create", "edit", "review", "export_pdf"],
            "event": ["view_all", "view_own", "create", "edit", "review", "export_pdf"],
            "dashboard": ["view_dashboard", "view_kpi"],
            "reports": ["view", "export_pdf"],
            "audit_trail": ["view"],
            "esignature": ["sign"],
            "module_framework": ["view_module_framework"],
        },
    },
    {
        "code": "department_manager",
        "name": "Department Manager",
        "description": "Creates records, reviews department records, assigns tasks, department-level reporting.",
        "is_system": True,
        "department_access": [],  # set per-user
        "module_access": ["deviation", "capa", "change_control", "incident", "event", "dashboard", "reports", "esignature"],
        "workflow_access": False,
        "approval_access": False,
        "review_access": True,
        "electronic_signature_access": True,
        "report_access": True,
        "audit_trail_access": False,
        "permission_preset": {
            "deviation": ["view_all", "view_own", "create", "edit", "review", "reject"],
            "capa": ["view_all", "view_own", "create", "edit", "review"],
            "change_control": ["view_all", "view_own", "create", "edit", "review"],
            "incident": ["view_all", "view_own", "create", "edit", "review"],
            "event": ["view_all", "view_own", "create", "edit", "review"],
            "dashboard": ["view_dashboard", "view_kpi"],
            "reports": ["view"],
            "esignature": ["sign"],
        },
    },
    {
        "code": "employee_operator",
        "name": "Employee / Operator",
        "description": "Creates requests, submits forms, edits draft records, adds comments to assigned records.",
        "is_system": True,
        "department_access": [],
        "module_access": ["deviation", "capa", "change_control", "incident", "event", "dashboard", "reports"],
        "workflow_access": False,
        "approval_access": False,
        "review_access": False,
        "electronic_signature_access": True,
        "report_access": True,
        "audit_trail_access": False,
        "permission_preset": {
            "deviation": ["view_own", "create", "edit"],
            "capa": ["view_own", "create", "edit"],
            "change_control": ["view_own", "create", "edit"],
            "incident": ["view_own", "create", "edit"],
            "event": ["view_own", "create", "edit"],
            "dashboard": ["view_dashboard"],
            "reports": ["view"],
            "esignature": ["sign"],
        },
    },
    {
        "code": "auditor",
        "name": "Auditor (Read-only)",
        "description": "Read-only inspector access: view audit trail, records, reports; export reports only.",
        "is_system": True,
        "department_access": ["ALL"],
        "module_access": ["deviation", "capa", "change_control", "incident", "event", "dashboard", "reports", "audit_trail"],
        "workflow_access": False,
        "approval_access": False,
        "review_access": False,
        "electronic_signature_access": False,
        "report_access": True,
        "audit_trail_access": True,
        "permission_preset": {
            "deviation": ["view_all"], "capa": ["view_all"], "change_control": ["view_all"], "incident": ["view_all"], "event": ["view_all"],
            "dashboard": ["view_dashboard", "view_kpi"],
            "reports": ["view", "export_pdf", "export_excel"],
            "audit_trail": ["view", "export", "view_full"],
        },
    },
]


def _resolve_preset(preset) -> Dict[str, Dict[str, bool]]:
    """Convert a permission_preset into the full {module: {action: bool}} matrix."""
    matrix = _empty_permissions(False)
    if preset == "ALL":
        return _empty_permissions(True)
    if isinstance(preset, dict):
        for mk, acts in preset.items():
            if mk not in matrix:
                continue
            for ak in acts:
                if ak in matrix[mk]:
                    matrix[mk][ak] = True
    return matrix


# ============================================================================
# Pydantic models
# ============================================================================
class PermissionMatrix(BaseModel):
    """Module → action → granted bool"""
    # using arbitrary dict — validated by code, not pydantic schema
    pass


class RoleCreateIn(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=80)
    description: str = ""
    department_access: List[str] = []
    module_access: List[str] = []
    workflow_access: bool = False
    approval_access: bool = False
    review_access: bool = False
    electronic_signature_access: bool = False
    report_access: bool = False
    audit_trail_access: bool = False
    permissions: Dict[str, Dict[str, bool]] = {}
    reason: str = "Role created"


class RoleUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    department_access: Optional[List[str]] = None
    module_access: Optional[List[str]] = None
    workflow_access: Optional[bool] = None
    approval_access: Optional[bool] = None
    review_access: Optional[bool] = None
    electronic_signature_access: Optional[bool] = None
    report_access: Optional[bool] = None
    audit_trail_access: Optional[bool] = None
    permissions: Optional[Dict[str, Dict[str, bool]]] = None
    reason: str = "Role updated"


class RoleCopyIn(BaseModel):
    new_code: str = Field(..., min_length=2, max_length=50)
    new_name: str = Field(..., min_length=2, max_length=80)
    reason: str = "Role copied"


class RoleActivateIn(BaseModel):
    active: bool
    reason: str = "Role status changed"


class OverrideCreateIn(BaseModel):
    module: str
    action: str
    effect: str  # "ALLOW" or "DENY"
    expires_at: Optional[str] = None  # ISO; if present → TEMPORARY
    reason: str = Field(..., min_length=3)


class OverrideDeleteIn(BaseModel):
    reason: str = Field(..., min_length=3)


# ============================================================================
# Helpers
# ============================================================================
def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sanitize_permissions(p: Dict[str, Dict[str, bool]]) -> Dict[str, Dict[str, bool]]:
    """Preserve stored permission detail, even for legacy or removed module/action keys.

    We keep the canonical matrix shape for known keys while retaining any unknown
    module/action pairs already present on the role so updates do not silently wipe
    historical permission detail.
    """
    out = _empty_permissions(False)
    if not isinstance(p, dict):
        return out
    for mk, acts in p.items():
        if not isinstance(acts, dict):
            continue
        if mk not in out:
            out[mk] = {}
        for ak, val in acts.items():
            out[mk][ak] = bool(val)
    return out


def _serialize_role(r: dict) -> dict:
    return {
        "id": r["id"],
        "code": r.get("code"),
        "name": r.get("name"),
        "description": r.get("description", ""),
        "active": r.get("active", True),
        "is_system": r.get("is_system", False),
        "department_access": r.get("department_access", []),
        "module_access": r.get("module_access", []),
        "workflow_access": bool(r.get("workflow_access")),
        "approval_access": bool(r.get("approval_access")),
        "review_access": bool(r.get("review_access")),
        "electronic_signature_access": bool(r.get("electronic_signature_access")),
        "report_access": bool(r.get("report_access")),
        "audit_trail_access": bool(r.get("audit_trail_access")),
        "permissions": r.get("permissions", _empty_permissions(False)),
        "copied_from": r.get("copied_from"),
        "created_at": r.get("created_at"),
        "created_by": r.get("created_by"),
        "updated_at": r.get("updated_at"),
        "updated_by": r.get("updated_by"),
    }


def _serialize_override(o: dict) -> dict:
    expires_at = o.get("expires_at")
    is_temp = bool(expires_at)
    kind = "RESTRICTED" if o.get("effect") == "DENY" else ("TEMPORARY" if is_temp else "ADDITIONAL")
    expired = False
    if expires_at:
        try:
            expired = datetime.fromisoformat(expires_at) <= _now()
        except Exception:
            expired = False
    return {
        "id": o["id"],
        "user_id": o["user_id"],
        "module": o["module"],
        "action": o["action"],
        "effect": o["effect"],
        "kind": kind,
        "expires_at": expires_at,
        "expired": expired,
        "reason": o.get("reason", ""),
        "created_at": o.get("created_at"),
        "created_by": o.get("created_by"),
        "created_by_name": o.get("created_by_name"),
    }


# ============================================================================
# Seed
# ============================================================================
async def seed_default_roles(db) -> None:
    for r in SEED_ROLES:
        existing = await db.roles.find_one({"code": r["code"]})
        permissions = _resolve_preset(r["permission_preset"])
        if existing:
            # Refresh module catalog keys but preserve manual overrides for non-system roles.
            # For system roles, keep permissions in sync with the seed (so adding a new
            # module catalog entry auto-propagates).
            if existing.get("is_system"):
                # System roles are authoritative from the seed on every boot.
                # Admins can fork them by creating new (non-system) roles to
                # customise.  This guarantees a newly added module catalog
                # entry is propagated correctly to all built-in roles.
                merged = permissions
                await db.roles.update_one(
                    {"code": r["code"]},
                    {"$set": {
                        "name": r["name"],
                        "description": r["description"],
                        "is_system": True,
                        "department_access": r["department_access"],
                        "module_access": r["module_access"],
                        "workflow_access": r["workflow_access"],
                        "approval_access": r["approval_access"],
                        "review_access": r["review_access"],
                        "electronic_signature_access": r["electronic_signature_access"],
                        "report_access": r["report_access"],
                        "audit_trail_access": r["audit_trail_access"],
                        "permissions": merged,
                    }},
                )
            continue
        doc = {
            "id": str(uuid.uuid4()),
            "code": r["code"],
            "name": r["name"],
            "description": r["description"],
            "active": True,
            "is_system": True,
            "department_access": r["department_access"],
            "module_access": r["module_access"],
            "workflow_access": r["workflow_access"],
            "approval_access": r["approval_access"],
            "review_access": r["review_access"],
            "electronic_signature_access": r["electronic_signature_access"],
            "report_access": r["report_access"],
            "audit_trail_access": r["audit_trail_access"],
            "permissions": permissions,
            "copied_from": None,
            "created_at": _iso(_now()),
            "created_by": "SYSTEM",
            "updated_at": _iso(_now()),
            "updated_by": "SYSTEM",
        }
        await db.roles.insert_one(doc)


# ============================================================================
# Effective-permissions computation
# ============================================================================
async def get_effective_permissions(db, user: dict) -> Dict[str, Any]:
    """Compute effective permissions for a user:
       1. Union of permissions across every ACTIVE role assigned to the user
          (matched by code → user.roles, or by id → user.dynamic_role_ids).
       2. Apply additional/temporary ALLOW overrides → grant.
       3. Apply RESTRICTED DENY overrides → revoke (deny wins).
       Returns: {permissions, role_permissions, user_additional, user_restricted, roles_applied}
    """
    role_codes = set()
    for r in user.get("roles", []) or []:
        role_codes.add(r)
    extra_ids = user.get("dynamic_role_ids") or []

    or_clauses: List[Dict[str, Any]] = []
    if role_codes:
        or_clauses.append({"code": {"$in": list(role_codes)}})
    if extra_ids:
        or_clauses.append({"id": {"$in": list(extra_ids)}})
    role_docs: List[dict] = []
    if or_clauses:
        q: Dict[str, Any] = {"$or": or_clauses} if len(or_clauses) > 1 else or_clauses[0]
        q["active"] = True
        role_docs = await db.roles.find(q, {"_id": 0}).to_list(50)

    # Union of role permissions, preserving legacy keys while still honoring the
    # canonical matrix for known module/action entries.
    role_perms = {}
    for rd in role_docs:
        rp = rd.get("permissions") or {}
        for mk, acts in rp.items():
            if not isinstance(acts, dict):
                continue
            module_perms = role_perms.setdefault(mk, {})
            for ak, val in acts.items():
                if bool(val):
                    module_perms[ak] = True

    # Overrides
    overrides = await db.user_permission_overrides.find({"user_id": user["id"]}, {"_id": 0}).to_list(500)
    now = _now()
    additional: Dict[str, Dict[str, dict]] = {}
    restricted: Dict[str, Dict[str, dict]] = {}
    active_allow: Set[str] = set()
    active_deny: Set[str] = set()
    for o in overrides:
        # Expiry check
        if o.get("expires_at"):
            try:
                if datetime.fromisoformat(o["expires_at"]) <= now:
                    continue  # expired → skip
            except Exception:
                pass
        key = f"{o['module']}.{o['action']}"
        meta = _serialize_override(o)
        if o["effect"] == "ALLOW":
            additional.setdefault(o["module"], {})[o["action"]] = meta
            active_allow.add(key)
        else:
            restricted.setdefault(o["module"], {})[o["action"]] = meta
            active_deny.add(key)

    # Effective
    effective = _empty_permissions(False)
    for mk, acts in role_perms.items():
        if mk not in effective:
            effective[mk] = {}
        for ak, val in acts.items():
            key = f"{mk}.{ak}"
            if val or key in active_allow:
                effective[mk][ak] = True
            if key in active_deny:
                effective[mk][ak] = False

    return {
        "modules": MODULE_CATALOG,
        "permissions": effective,
        "role_permissions": role_perms,
        "additional": additional,
        "restricted": restricted,
        "roles_applied": [
            {"id": r["id"], "code": r.get("code"), "name": r.get("name")} for r in role_docs
        ],
    }


def user_has_module_permission(perms_payload: Dict[str, Any], module: str, action: str) -> bool:
    return bool(((perms_payload.get("permissions") or {}).get(module) or {}).get(action))


# ============================================================================
# Router builder — call from server.py
# ============================================================================
def register_role_mgmt_routes(
    api: APIRouter,
    *,
    db,
    get_current_user,
    require_role,
    log_audit,
    verify_esignature,
    ROLE_ADMIN: str,
    ROLE_SUPER_ADMIN: str,
) -> None:
    """Wire all role-mgmt endpoints onto the existing /api router."""

    admin_dep = require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN)

    # ---- Module catalog ----
    @api.get("/role-mgmt/modules")
    async def get_modules(user: dict = Depends(get_current_user)):
        return {
            "modules": MODULE_CATALOG,
            "module_keys": list(MODULE_CATALOG.keys()),
        }

    # ---- Roles list ----
    @api.get("/role-mgmt/roles")
    async def list_roles(
        active: Optional[bool] = None,
        user: dict = Depends(get_current_user),
    ):
        q: Dict[str, Any] = {}
        if active is not None:
            q["active"] = active
        rows = await db.roles.find(q, {"_id": 0}).sort("code", 1).to_list(500)
        # Also attach user-count per role
        all_users = await db.users.find({}, {"_id": 0, "roles": 1, "dynamic_role_ids": 1}).to_list(2000)
        counts: Dict[str, int] = {}
        for u in all_users:
            for r in (u.get("roles") or []):
                counts[r] = counts.get(r, 0) + 1
            for rid in (u.get("dynamic_role_ids") or []):
                counts[rid] = counts.get(rid, 0) + 1
        out = []
        for r in rows:
            s = _serialize_role(r)
            s["user_count"] = counts.get(r.get("code"), 0) + counts.get(r.get("id"), 0)
            out.append(s)
        return out

    # ---- Role detail ----
    @api.get("/role-mgmt/roles/{role_id}")
    async def get_role(role_id: str, user: dict = Depends(get_current_user)):
        r = await db.roles.find_one({"$or": [{"id": role_id}, {"code": role_id}]}, {"_id": 0})
        if not r:
            raise HTTPException(404, "Role not found")
        return _serialize_role(r)

    # ---- Create role ----
    @api.post("/role-mgmt/roles")
    async def create_role(payload: RoleCreateIn, actor: dict = Depends(admin_dep)):
        code = payload.code.strip().lower().replace(" ", "_")
        if not code.replace("_", "").isalnum():
            raise HTTPException(400, "Role code must be alphanumeric/underscore")
        existing = await db.roles.find_one({"code": code})
        if existing:
            raise HTTPException(400, f"Role code '{code}' already exists")
        permissions = _sanitize_permissions(payload.permissions or {})
        doc = {
            "id": str(uuid.uuid4()),
            "code": code,
            "name": payload.name.strip(),
            "description": payload.description,
            "active": True,
            "is_system": False,
            "department_access": payload.department_access,
            "module_access": payload.module_access,
            "workflow_access": payload.workflow_access,
            "approval_access": payload.approval_access,
            "review_access": payload.review_access,
            "electronic_signature_access": payload.electronic_signature_access,
            "report_access": payload.report_access,
            "audit_trail_access": payload.audit_trail_access,
            "permissions": permissions,
            "copied_from": None,
            "created_at": _iso(_now()),
            "created_by": actor["email"],
            "updated_at": _iso(_now()),
            "updated_by": actor["email"],
        }
        await db.roles.insert_one(doc)
        await log_audit(
            actor=actor, action="ROLE_CREATE", entity_type="ROLE", entity_id=doc["id"],
            new_value={"code": code, "name": doc["name"]},
            reason=payload.reason,
        )
        return _serialize_role(doc)

    # ---- Update role ----
    @api.patch("/role-mgmt/roles/{role_id}")
    async def update_role(role_id: str, payload: RoleUpdateIn, actor: dict = Depends(admin_dep)):
        r = await db.roles.find_one({"$or": [{"id": role_id}, {"code": role_id}]})
        if not r:
            raise HTTPException(404, "Role not found")
        updates: Dict[str, Any] = {}
        for field in ["name", "description", "department_access", "module_access",
                      "workflow_access", "approval_access", "review_access",
                      "electronic_signature_access", "report_access", "audit_trail_access"]:
            v = getattr(payload, field)
            if v is not None:
                updates[field] = v
        if payload.permissions is not None:
            updates["permissions"] = _sanitize_permissions(payload.permissions)
        if not updates:
            raise HTTPException(400, "No fields to update")
        old = {k: r.get(k) for k in updates.keys()}
        updates["updated_at"] = _iso(_now())
        updates["updated_by"] = actor["email"]
        await db.roles.update_one({"id": r["id"]}, {"$set": updates})
        await log_audit(
            actor=actor, action="ROLE_UPDATE", entity_type="ROLE", entity_id=r["id"],
            old_value=old, new_value=updates, reason=payload.reason,
        )
        updated = await db.roles.find_one({"id": r["id"]}, {"_id": 0})
        return _serialize_role(updated)

    # ---- Copy role ----
    @api.post("/role-mgmt/roles/{role_id}/copy")
    async def copy_role(role_id: str, payload: RoleCopyIn, actor: dict = Depends(admin_dep)):
        src = await db.roles.find_one({"$or": [{"id": role_id}, {"code": role_id}]})
        if not src:
            raise HTTPException(404, "Role not found")
        code = payload.new_code.strip().lower().replace(" ", "_")
        if await db.roles.find_one({"code": code}):
            raise HTTPException(400, f"Role code '{code}' already exists")
        doc = {
            "id": str(uuid.uuid4()),
            "code": code,
            "name": payload.new_name.strip(),
            "description": f"Copied from {src.get('name', src.get('code'))}: {src.get('description', '')}",
            "active": True,
            "is_system": False,
            "department_access": list(src.get("department_access", [])),
            "module_access": list(src.get("module_access", [])),
            "workflow_access": src.get("workflow_access", False),
            "approval_access": src.get("approval_access", False),
            "review_access": src.get("review_access", False),
            "electronic_signature_access": src.get("electronic_signature_access", False),
            "report_access": src.get("report_access", False),
            "audit_trail_access": src.get("audit_trail_access", False),
            "permissions": _sanitize_permissions(src.get("permissions") or {}),
            "copied_from": src["id"],
            "created_at": _iso(_now()),
            "created_by": actor["email"],
            "updated_at": _iso(_now()),
            "updated_by": actor["email"],
        }
        await db.roles.insert_one(doc)
        await log_audit(
            actor=actor, action="ROLE_COPY", entity_type="ROLE", entity_id=doc["id"],
            new_value={"code": code, "copied_from": src["id"], "source_code": src.get("code")},
            reason=payload.reason,
        )
        return _serialize_role(doc)

    # ---- Activate / Deactivate role ----
    @api.post("/role-mgmt/roles/{role_id}/activate")
    async def set_role_active(role_id: str, payload: RoleActivateIn, actor: dict = Depends(admin_dep)):
        r = await db.roles.find_one({"$or": [{"id": role_id}, {"code": role_id}]})
        if not r:
            raise HTTPException(404, "Role not found")
        if r.get("is_system") and not payload.active and r.get("code") in {"super_admin", "admin"}:
            raise HTTPException(400, "System role super_admin/admin cannot be deactivated")
        old = {"active": r.get("active")}
        await db.roles.update_one(
            {"id": r["id"]},
            {"$set": {"active": payload.active, "updated_at": _iso(_now()), "updated_by": actor["email"]}},
        )
        await log_audit(
            actor=actor,
            action="ROLE_ACTIVATE" if payload.active else "ROLE_DEACTIVATE",
            entity_type="ROLE", entity_id=r["id"],
            old_value=old, new_value={"active": payload.active}, reason=payload.reason,
        )
        updated = await db.roles.find_one({"id": r["id"]}, {"_id": 0})
        return _serialize_role(updated)

    # ---- Audit trail of a role ----
    @api.get("/role-mgmt/roles/{role_id}/audit")
    async def role_audit(role_id: str, user: dict = Depends(get_current_user)):
        r = await db.roles.find_one({"$or": [{"id": role_id}, {"code": role_id}]})
        if not r:
            raise HTTPException(404, "Role not found")
        rows = await db.audit_trail.find(
            {"entity_type": "ROLE", "entity_id": r["id"]}, {"_id": 0}
        ).sort("timestamp", -1).to_list(500)
        return rows

    # ---- User effective permissions ----
    @api.get("/role-mgmt/users/{user_id}/permissions")
    async def user_perms(user_id: str, actor: dict = Depends(get_current_user)):
        target = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "password_history": 0})
        if not target:
            raise HTTPException(404, "User not found")
        payload = await get_effective_permissions(db, target)
        payload["user"] = {
            "id": target["id"], "name": target.get("name"), "email": target.get("email"),
            "roles": target.get("roles", []), "dynamic_role_ids": target.get("dynamic_role_ids", []),
        }
        return payload

    # ---- List user overrides ----
    @api.get("/role-mgmt/users/{user_id}/overrides")
    async def list_overrides(user_id: str, actor: dict = Depends(get_current_user)):
        target = await db.users.find_one({"id": user_id})
        if not target:
            raise HTTPException(404, "User not found")
        rows = await db.user_permission_overrides.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
        return [_serialize_override(r) for r in rows]

    # ---- Add user override ----
    @api.post("/role-mgmt/users/{user_id}/overrides")
    async def add_override(user_id: str, payload: OverrideCreateIn, actor: dict = Depends(admin_dep)):
        target = await db.users.find_one({"id": user_id})
        if not target:
            raise HTTPException(404, "User not found")
        if payload.effect not in {"ALLOW", "DENY"}:
            raise HTTPException(400, "effect must be ALLOW or DENY")
        if not _valid_module_action(payload.module, payload.action):
            raise HTTPException(400, f"Unknown module.action: {payload.module}.{payload.action}")
        expires_at = payload.expires_at
        if expires_at:
            try:
                datetime.fromisoformat(expires_at)
            except Exception:
                raise HTTPException(400, "expires_at must be ISO datetime")
        doc = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "module": payload.module,
            "action": payload.action,
            "effect": payload.effect,
            "expires_at": expires_at,
            "reason": payload.reason,
            "created_at": _iso(_now()),
            "created_by": actor["email"],
            "created_by_name": actor.get("name"),
        }
        await db.user_permission_overrides.insert_one(doc)
        await log_audit(
            actor=actor, action="USER_PERMISSION_ADD", entity_type="USER_PERMISSION", entity_id=user_id,
            new_value={
                "module": payload.module, "action": payload.action,
                "effect": payload.effect, "expires_at": expires_at,
            },
            reason=payload.reason,
        )
        return _serialize_override(doc)

    # ---- Delete user override ----
    @api.delete("/role-mgmt/users/{user_id}/overrides/{override_id}")
    async def delete_override(user_id: str, override_id: str, reason: str = "Override removed", actor: dict = Depends(admin_dep)):
        o = await db.user_permission_overrides.find_one({"id": override_id, "user_id": user_id})
        if not o:
            raise HTTPException(404, "Override not found")
        await db.user_permission_overrides.delete_one({"id": override_id})
        await log_audit(
            actor=actor, action="USER_PERMISSION_REMOVE", entity_type="USER_PERMISSION", entity_id=user_id,
            old_value={"module": o["module"], "action": o["action"], "effect": o["effect"]},
            reason=reason,
        )
        return {"ok": True}

    # ---- Assign dynamic role to user ----
    @api.post("/role-mgmt/users/{user_id}/assign-role")
    async def assign_role(user_id: str, body: Dict[str, Any], actor: dict = Depends(admin_dep)):
        role_id = body.get("role_id")
        reason = body.get("reason") or "Role assigned"
        if not role_id:
            raise HTTPException(400, "role_id required")
        role = await db.roles.find_one({"$or": [{"id": role_id}, {"code": role_id}]})
        if not role:
            raise HTTPException(404, "Role not found")
        target = await db.users.find_one({"id": user_id})
        if not target:
            raise HTTPException(404, "User not found")
        roles_list: List[str] = list(target.get("roles") or [])
        dyn_ids: List[str] = list(target.get("dynamic_role_ids") or [])
        # System roles attach by code on user.roles for back-compat; custom roles attach by id
        if role.get("is_system") and role["code"] not in roles_list:
            roles_list.append(role["code"])
        elif not role.get("is_system") and role["id"] not in dyn_ids:
            dyn_ids.append(role["id"])
        else:
            return {"ok": True, "already_assigned": True}
        old = {"roles": target.get("roles", []), "dynamic_role_ids": target.get("dynamic_role_ids", [])}
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"roles": roles_list, "dynamic_role_ids": dyn_ids}},
        )
        await log_audit(
            actor=actor, action="USER_ROLE_ASSIGN", entity_type="USER", entity_id=user_id,
            old_value=old, new_value={"roles": roles_list, "dynamic_role_ids": dyn_ids},
            reason=reason, extra={"role_id": role["id"], "role_code": role.get("code")},
        )
        return {"ok": True}

    # ---- Revoke dynamic role from user ----
    @api.post("/role-mgmt/users/{user_id}/revoke-role")
    async def revoke_role(user_id: str, body: Dict[str, Any], actor: dict = Depends(admin_dep)):
        role_id = body.get("role_id")
        reason = body.get("reason") or "Role revoked"
        if not role_id:
            raise HTTPException(400, "role_id required")
        role = await db.roles.find_one({"$or": [{"id": role_id}, {"code": role_id}]})
        if not role:
            raise HTTPException(404, "Role not found")
        target = await db.users.find_one({"id": user_id})
        if not target:
            raise HTTPException(404, "User not found")
        roles_list: List[str] = [r for r in (target.get("roles") or []) if r != role["code"]]
        dyn_ids: List[str] = [d for d in (target.get("dynamic_role_ids") or []) if d != role["id"]]
        if not roles_list:
            raise HTTPException(400, "User must have at least one role")
        old = {"roles": target.get("roles", []), "dynamic_role_ids": target.get("dynamic_role_ids", [])}
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"roles": roles_list, "dynamic_role_ids": dyn_ids}},
        )
        await log_audit(
            actor=actor, action="USER_ROLE_REVOKE", entity_type="USER", entity_id=user_id,
            old_value=old, new_value={"roles": roles_list, "dynamic_role_ids": dyn_ids},
            reason=reason, extra={"role_id": role["id"], "role_code": role.get("code")},
        )
        return {"ok": True}

    # ---- My permissions (the logged-in user) ----
    @api.get("/role-mgmt/my-permissions")
    async def my_perms(user: dict = Depends(get_current_user)):
        return await get_effective_permissions(db, user)

    # ---- Audit export (CSV / JSON) ----
    @api.get("/role-mgmt/audit/export")
    async def export_audit(
        format: str = "csv",
        entity_type: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        user: dict = Depends(get_current_user),
    ):
        from fastapi.responses import StreamingResponse, JSONResponse
        import csv, io
        q: Dict[str, Any] = {"entity_type": {"$in": ["ROLE", "USER_PERMISSION"]}}
        if entity_type:
            q["entity_type"] = entity_type
        if from_date or to_date:
            rng = {}
            if from_date: rng["$gte"] = from_date
            if to_date: rng["$lte"] = to_date
            q["timestamp"] = rng
        rows = await db.audit_trail.find(q, {"_id": 0}).sort("timestamp", -1).to_list(5000)
        if format == "json":
            return JSONResponse(rows)
        # CSV
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Timestamp", "User Email", "User Name", "Roles", "Action",
                    "Entity Type", "Entity ID", "Old Value", "New Value", "Reason"])
        for r in rows:
            w.writerow([
                r.get("timestamp"), r.get("user_email"), r.get("user_name"),
                ", ".join(r.get("user_roles") or []),
                r.get("action"), r.get("entity_type"), r.get("entity_id"),
                str(r.get("old_value") or ""), str(r.get("new_value") or ""),
                r.get("reason", ""),
            ])
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="role_matrix_audit.csv"'},
        )
