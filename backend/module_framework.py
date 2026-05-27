"""
izQMS — Plant/Site-Based Dynamic Module Framework (Foundation v1)
-----------------------------------------------------------------
Allows authorised admins to:
- Define plants/sites (multi-plant deployment).
- Design module templates dynamically:
    * Workflow stages + transitions
    * Form sections + fields (text/dropdown/date/checkbox/comment/file/sign/approval)
    * PDF layout sections (header / signature block / numbering)
    * Approval chain (multi-level)
    * Role mapping per stage
- Version control: DRAFT → PUBLISHED → RETIRED. Once published, a version is
  IMMUTABLE.  New edits create a NEW version.  Existing dynamic records stay
  bound to the version they were created against.
- Create dynamic records against a PUBLISHED template + plant.
- Execute the template's workflow with audit & e-signature on every transition.

This module is fully **isolated** from the existing izQMS QMS records
(`qms_records` collection / `/api/records/*`).  It uses its own collections
(`plants`, `module_templates`, `dynamic_records`) and lives entirely under
`/api/module-framework/*`.  Nothing in the legacy stack changes.

Compliance: every plant / template / record change writes to the existing
`audit_trail` collection with `entity_type` ∈ {PLANT, MODULE_TEMPLATE,
DYNAMIC_RECORD} and the actor / timestamp / old / new / reason.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field


# ============================================================================
# Field type catalog — single source of truth for what designers can put on a form.
# ============================================================================
FIELD_TYPES = [
    {"key": "text",        "label": "Short text"},
    {"key": "textarea",    "label": "Long text / Comment"},
    {"key": "number",      "label": "Number"},
    {"key": "date",        "label": "Date"},
    {"key": "datetime",    "label": "Date & Time"},
    {"key": "dropdown",    "label": "Dropdown (single)"},
    {"key": "multiselect", "label": "Dropdown (multi)"},
    {"key": "checkbox",    "label": "Checkbox"},
    {"key": "radio",       "label": "Radio group"},
    {"key": "attachment",  "label": "File attachment"},
    {"key": "signature",   "label": "Electronic signature"},
    {"key": "approval",    "label": "Approval block"},
    {"key": "user_picker", "label": "User picker"},
    {"key": "department",  "label": "Department picker"},
]


# ============================================================================
# Helpers
# ============================================================================
def _iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() or c == "_" else "_" for c in (s or "").lower()).strip("_")


# ============================================================================
# Pydantic schemas
# ============================================================================
class PlantIn(BaseModel):
    code: str = Field(..., min_length=2, max_length=30)
    name: str = Field(..., min_length=2, max_length=120)
    location: str = ""
    address: str = ""
    gmp_zone: str = ""
    time_zone: str = "UTC"
    description: str = ""


class PlantUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    address: Optional[str] = None
    gmp_zone: Optional[str] = None
    time_zone: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    reason: str = "Plant updated"


class ModuleTemplateIn(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    name: str = Field(..., min_length=2, max_length=120)
    category: str = "CUSTOM"   # DEVIATION / CAPA / CHANGE_CONTROL / CUSTOM / ...
    description: str = ""
    plant_id: Optional[str] = None   # None or "GLOBAL" → applies to all plants by default
    workflow: Dict[str, Any] = {}
    form: Dict[str, Any] = {}
    pdf_template: Dict[str, Any] = {}
    approvals: List[Dict[str, Any]] = []
    role_mapping: Dict[str, List[str]] = {}
    notes: str = ""


class ModuleTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    workflow: Optional[Dict[str, Any]] = None
    form: Optional[Dict[str, Any]] = None
    pdf_template: Optional[Dict[str, Any]] = None
    approvals: Optional[List[Dict[str, Any]]] = None
    role_mapping: Optional[Dict[str, List[str]]] = None
    notes: Optional[str] = None
    reason: str = "Template updated"


class TemplateActionIn(BaseModel):
    reason: str = Field(..., min_length=3)


class TemplateCopyIn(BaseModel):
    new_code: str = Field(..., min_length=2)
    new_name: str = Field(..., min_length=2)
    target_plant_id: Optional[str] = None
    reason: str = "Template copied"


class DynamicRecordIn(BaseModel):
    template_id: str
    plant_id: str
    title: str = Field(..., min_length=2)
    form_data: Dict[str, Any] = {}
    reason: str = "Record created"


class DynamicTransitionIn(BaseModel):
    to_stage: str
    password: str       # e-signature
    reason: str = Field(..., min_length=3)
    form_patch: Optional[Dict[str, Any]] = None  # optional updates with the transition
    comment: Optional[str] = ""


# ============================================================================
# Default workflow shape — used as a starting point in the designer
# ============================================================================
DEFAULT_WORKFLOW = {
    "stages": [
        {"key": "INITIATION", "label": "Initiation", "color": "#94A3B8"},
        {"key": "REVIEW",     "label": "Review",     "color": "#2563EB"},
        {"key": "APPROVAL",   "label": "Approval",   "color": "#D97706"},
        {"key": "CLOSED",     "label": "Closed",     "color": "#059669"},
        {"key": "REJECTED",   "label": "Rejected",   "color": "#DC2626"},
    ],
    "initial_stage": "INITIATION",
    "transitions": [
        {"key": "SUBMIT",  "from": "INITIATION", "to": "REVIEW",   "label": "Submit for review",   "required_perm": None,             "esignature": True},
        {"key": "REVIEW",  "from": "REVIEW",     "to": "APPROVAL", "label": "Review",              "required_perm": "review_record",  "esignature": True},
        {"key": "APPROVE", "from": "APPROVAL",   "to": "CLOSED",   "label": "Approve & close",     "required_perm": "approve_record", "esignature": True},
        {"key": "REJECT",  "from": "REVIEW",     "to": "REJECTED", "label": "Reject",              "required_perm": "reject_record",  "esignature": True},
        {"key": "REOPEN",  "from": "REJECTED",   "to": "INITIATION","label": "Reopen / correct",   "required_perm": None,             "esignature": True},
    ],
}

DEFAULT_FORM = {
    "sections": [
        {
            "key": "general",
            "label": "General",
            "fields": [
                {"key": "description", "label": "Description", "type": "textarea", "required": True},
                {"key": "department",  "label": "Department",  "type": "department", "required": True},
                {"key": "severity",    "label": "Severity",    "type": "dropdown", "options": ["Low", "Medium", "High", "Critical"], "required": True},
                {"key": "due_date",    "label": "Due date",    "type": "date"},
            ],
        },
    ],
}

DEFAULT_PDF = {
    "header": {"title": "{{template.name}}", "show_logo": True, "show_record_number": True},
    "sections": [
        {"key": "summary",     "label": "Record Summary",      "show_fields": ["description", "department", "severity", "due_date"]},
        {"key": "workflow",    "label": "Workflow Timeline",   "show_history": True},
        {"key": "signatures",  "label": "Electronic Signatures","show_signatures": True},
        {"key": "audit",       "label": "Audit Trail",         "show_audit": True},
    ],
    "footer": {"text": "21 CFR Part 11 · EU Annex 11 · ALCOA++"},
}


# ============================================================================
# Seed
# ============================================================================
async def seed_default_plants(db) -> None:
    if await db.plants.count_documents({}) > 0:
        return
    for p in [
        {"code": "HQ",      "name": "Headquarters",        "location": "HQ",      "gmp_zone": "Office",    "time_zone": "UTC"},
        {"code": "PLANT-1", "name": "Plant 1 — Bangalore", "location": "Plant-1", "gmp_zone": "GMP Grade A", "time_zone": "Asia/Kolkata"},
        {"code": "PLANT-2", "name": "Plant 2 — Pune",      "location": "Plant-2", "gmp_zone": "GMP Grade B", "time_zone": "Asia/Kolkata"},
    ]:
        await db.plants.insert_one({
            "id": str(uuid.uuid4()),
            "code": p["code"],
            "name": p["name"],
            "location": p["location"],
            "address": "",
            "gmp_zone": p["gmp_zone"],
            "time_zone": p["time_zone"],
            "description": "",
            "active": True,
            "created_at": _iso(_now()),
            "created_by": "SYSTEM",
        })


# ============================================================================
# Counter helper
# ============================================================================
async def _next_dynamic_record_number(db, template_code: str) -> str:
    year = _now().year
    key = f"DYN-{template_code}-{year}"
    counter = await db.counters.find_one_and_update(
        {"key": key}, {"$inc": {"seq": 1}}, upsert=True, return_document=True,
    )
    seq = counter["seq"] if counter and "seq" in counter else 1
    return f"{template_code}-{year}-{seq:04d}"


# ============================================================================
# Router builder
# ============================================================================
def register_module_framework_routes(
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

    admin_dep = require_role(ROLE_ADMIN, ROLE_SUPER_ADMIN)

    # ---------- Field types catalog ----------
    @api.get("/module-framework/field-types")
    async def field_types(user: dict = Depends(get_current_user)):
        return {"field_types": FIELD_TYPES, "default_workflow": DEFAULT_WORKFLOW, "default_form": DEFAULT_FORM, "default_pdf": DEFAULT_PDF}

    # ---------- Active template lookup (framework → legacy module binding) ----------
    # Returns the latest PUBLISHED GLOBAL template for a given category
    # (DEVIATION / CAPA / CHANGE_CONTROL / INCIDENT / EVENT). Used by legacy
    # module pages to render the PDF-aligned form fields live.  When an admin
    # publishes a new version of the template in the Framework, this endpoint
    # immediately starts returning the new version — no deploy needed.
    @api.get("/module-framework/active-template")
    async def get_active_template(
        category: str,
        user: dict = Depends(get_current_user),
    ):
        cat = (category or "").strip().upper()
        if not cat:
            raise HTTPException(400, "category is required")
        tpl = await db.module_templates.find_one(
            {"category": cat, "plant_id": "GLOBAL", "status": "PUBLISHED"},
            {"_id": 0},
            sort=[("version", -1)],
        )
        return {"category": cat, "template": tpl}

    # ---------- Category preset (default scaffold used by Template Designer) ----------
    # When an admin picks a category in "New module template", the designer
    # calls this to fetch the matching seeded compliant template's workflow,
    # form, PDF layout and role mapping as a starting point. This guarantees
    # admins always start from the **current PDF-aligned default** for that
    # category rather than a blank slate — fully editable thereafter.
    @api.get("/module-framework/category-preset")
    async def get_category_preset(
        category: str,
        user: dict = Depends(get_current_user),
    ):
        cat = (category or "").strip().upper()
        if not cat or cat == "CUSTOM":
            return {"category": cat, "preset": None}
        # Prefer the latest PUBLISHED; fall back to latest DRAFT to support
        # admins who haven't published their custom default yet.
        tpl = await db.module_templates.find_one(
            {"category": cat, "plant_id": "GLOBAL", "status": "PUBLISHED"},
            {"_id": 0}, sort=[("version", -1)],
        )
        if not tpl:
            tpl = await db.module_templates.find_one(
                {"category": cat, "plant_id": "GLOBAL"},
                {"_id": 0}, sort=[("version", -1)],
            )
        if not tpl:
            return {"category": cat, "preset": None}
        return {
            "category": cat,
            "source": {"id": tpl.get("id"), "code": tpl.get("code"), "version": tpl.get("version"), "status": tpl.get("status")},
            "preset": {
                "workflow": tpl.get("workflow") or {},
                "form": tpl.get("form") or {"sections": []},
                "pdf_template": tpl.get("pdf_template") or {},
                "approvals": tpl.get("approvals") or [],
                "role_mapping": tpl.get("role_mapping") or {},
                "notes": tpl.get("notes") or "",
            },
        }

    # ---------- Cleanup: drop stray DRAFT templates created during testing ----------
    # Admin-only convenience to wipe junk rows (e.g. earlier copy_xxx templates
    # that were never used). Hard-deletes only DRAFT, non-source templates.
    @api.delete("/module-framework/templates/{template_id}")
    async def delete_template(template_id: str, actor: dict = Depends(admin_dep)):
        t = await db.module_templates.find_one({"id": template_id})
        if not t:
            raise HTTPException(404, "Template not found")
        if t.get("status") != "DRAFT":
            raise HTTPException(400, "Only DRAFT templates can be deleted")
        used = await db.dynamic_records.count_documents({"template_id": template_id})
        if used:
            raise HTTPException(400, f"Template has {used} dependent records; cannot delete")
        await db.module_templates.delete_one({"id": template_id})
        await log_audit(actor=actor, action="TEMPLATE_DELETE", entity_type="MODULE_TEMPLATE", entity_id=template_id,
                        old_value={"code": t.get("code"), "version": t.get("version"), "plant_id": t.get("plant_id")},
                        reason="DRAFT template removed")
        return {"ok": True, "deleted": template_id}

    # ---------- Plants CRUD ----------
    @api.get("/module-framework/plants")
    async def list_plants(active: Optional[bool] = None, user: dict = Depends(get_current_user)):
        q: Dict[str, Any] = {}
        if active is not None:
            q["active"] = active
        rows = await db.plants.find(q, {"_id": 0}).sort("code", 1).to_list(200)
        return rows

    @api.post("/module-framework/plants")
    async def create_plant(payload: PlantIn, actor: dict = Depends(admin_dep)):
        code = payload.code.strip().upper()
        if await db.plants.find_one({"code": code}):
            raise HTTPException(400, f"Plant code '{code}' already exists")
        doc = {
            "id": str(uuid.uuid4()),
            "code": code,
            "name": payload.name,
            "location": payload.location,
            "address": payload.address,
            "gmp_zone": payload.gmp_zone,
            "time_zone": payload.time_zone,
            "description": payload.description,
            "active": True,
            "created_at": _iso(_now()),
            "created_by": actor["email"],
        }
        await db.plants.insert_one(doc)
        await log_audit(actor=actor, action="PLANT_CREATE", entity_type="PLANT", entity_id=doc["id"],
                        new_value={"code": code, "name": doc["name"]}, reason="Plant created")
        doc.pop("_id", None)
        return doc

    @api.patch("/module-framework/plants/{plant_id}")
    async def update_plant(plant_id: str, payload: PlantUpdate, actor: dict = Depends(admin_dep)):
        p = await db.plants.find_one({"id": plant_id})
        if not p:
            raise HTTPException(404, "Plant not found")
        updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if k != "reason"}
        if not updates:
            raise HTTPException(400, "No fields to update")
        old = {k: p.get(k) for k in updates.keys()}
        updates["updated_at"] = _iso(_now())
        updates["updated_by"] = actor["email"]
        await db.plants.update_one({"id": plant_id}, {"$set": updates})
        await log_audit(actor=actor, action="PLANT_UPDATE", entity_type="PLANT", entity_id=plant_id,
                        old_value=old, new_value=updates, reason=payload.reason)
        return await db.plants.find_one({"id": plant_id}, {"_id": 0})

    # ---------- Module Templates ----------
    @api.get("/module-framework/templates")
    async def list_templates(
        plant_id: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        code: Optional[str] = None,
        user: dict = Depends(get_current_user),
    ):
        q: Dict[str, Any] = {}
        if plant_id:
            q["$or"] = [{"plant_id": plant_id}, {"plant_id": None}, {"plant_id": "GLOBAL"}]
        if status:
            q["status"] = status
        if category:
            q["category"] = category
        if code:
            q["code"] = code
        rows = await db.module_templates.find(q, {"_id": 0}).sort([("code", 1), ("version", -1)]).to_list(500)
        return rows

    @api.get("/module-framework/templates/{template_id}")
    async def get_template(template_id: str, user: dict = Depends(admin_dep)):
        t = await db.module_templates.find_one({"id": template_id}, {"_id": 0})
        if not t:
            raise HTTPException(404, "Template not found")
        return t

    @api.get("/module-framework/templates/{template_id}/versions")
    async def template_versions(template_id: str, user: dict = Depends(admin_dep)):
        t = await db.module_templates.find_one({"id": template_id}, {"_id": 0})
        if not t:
            raise HTTPException(404, "Template not found")
        all_versions = await db.module_templates.find(
            {"code": t["code"], "plant_id": t.get("plant_id")}, {"_id": 0},
        ).sort("version", -1).to_list(50)
        return all_versions

    @api.post("/module-framework/templates")
    async def create_template(payload: ModuleTemplateIn, actor: dict = Depends(admin_dep)):
        code = _slug(payload.code)
        if not code:
            raise HTTPException(400, "Invalid code")
        # Determine next version (within same code + plant scope)
        existing = await db.module_templates.find_one(
            {"code": code, "plant_id": payload.plant_id},
            sort=[("version", -1)],
        )
        version = (existing.get("version", 0) + 1) if existing else 1
        # Validate plant
        if payload.plant_id and payload.plant_id != "GLOBAL":
            if not await db.plants.find_one({"id": payload.plant_id}):
                raise HTTPException(400, "Plant not found")
        doc = {
            "id": str(uuid.uuid4()),
            "code": code,
            "name": payload.name,
            "description": payload.description,
            "category": payload.category,
            "plant_id": payload.plant_id or "GLOBAL",
            "version": version,
            "status": "DRAFT",
            "workflow": payload.workflow or DEFAULT_WORKFLOW,
            "form": payload.form or DEFAULT_FORM,
            "pdf_template": payload.pdf_template or DEFAULT_PDF,
            "approvals": payload.approvals,
            "role_mapping": payload.role_mapping,
            "notes": payload.notes,
            "created_at": _iso(_now()),
            "created_by": actor["email"],
            "published_at": None,
            "published_by": None,
            "retired_at": None,
            "retired_by": None,
        }
        await db.module_templates.insert_one(doc)
        await log_audit(actor=actor, action="TEMPLATE_CREATE", entity_type="MODULE_TEMPLATE", entity_id=doc["id"],
                        new_value={"code": code, "version": version, "plant_id": doc["plant_id"]},
                        reason="Template draft created")
        doc.pop("_id", None)
        return doc

    @api.patch("/module-framework/templates/{template_id}")
    async def update_template(template_id: str, payload: ModuleTemplateUpdate, actor: dict = Depends(admin_dep)):
        t = await db.module_templates.find_one({"id": template_id})
        if not t:
            raise HTTPException(404, "Template not found")
        if t["status"] != "DRAFT":
            raise HTTPException(400, f"Template is {t['status']}. Only DRAFT versions can be edited. Create a new version instead.")
        updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if k != "reason"}
        if not updates:
            raise HTTPException(400, "No fields to update")
        old = {k: t.get(k) for k in updates.keys()}
        updates["updated_at"] = _iso(_now())
        updates["updated_by"] = actor["email"]
        await db.module_templates.update_one({"id": template_id}, {"$set": updates})
        await log_audit(actor=actor, action="TEMPLATE_UPDATE", entity_type="MODULE_TEMPLATE", entity_id=template_id,
                        old_value=old, new_value=updates, reason=payload.reason)
        return await db.module_templates.find_one({"id": template_id}, {"_id": 0})

    @api.post("/module-framework/templates/{template_id}/publish")
    async def publish_template(template_id: str, payload: TemplateActionIn, actor: dict = Depends(admin_dep)):
        t = await db.module_templates.find_one({"id": template_id})
        if not t:
            raise HTTPException(404, "Template not found")
        if t["status"] != "DRAFT":
            raise HTTPException(400, f"Template is {t['status']}; only DRAFT can be published")
        # Retire any previously published version for same code+plant
        await db.module_templates.update_many(
            {"code": t["code"], "plant_id": t.get("plant_id"), "status": "PUBLISHED"},
            {"$set": {"status": "RETIRED", "retired_at": _iso(_now()), "retired_by": actor["email"]}},
        )
        await db.module_templates.update_one(
            {"id": template_id},
            {"$set": {"status": "PUBLISHED", "published_at": _iso(_now()), "published_by": actor["email"]}},
        )
        await log_audit(actor=actor, action="TEMPLATE_PUBLISH", entity_type="MODULE_TEMPLATE", entity_id=template_id,
                        new_value={"status": "PUBLISHED", "version": t["version"]},
                        reason=payload.reason)
        return await db.module_templates.find_one({"id": template_id}, {"_id": 0})

    @api.post("/module-framework/templates/{template_id}/retire")
    async def retire_template(template_id: str, payload: TemplateActionIn, actor: dict = Depends(admin_dep)):
        t = await db.module_templates.find_one({"id": template_id})
        if not t:
            raise HTTPException(404, "Template not found")
        if t["status"] != "PUBLISHED":
            raise HTTPException(400, "Only PUBLISHED templates can be retired")
        await db.module_templates.update_one(
            {"id": template_id},
            {"$set": {"status": "RETIRED", "retired_at": _iso(_now()), "retired_by": actor["email"]}},
        )
        await log_audit(actor=actor, action="TEMPLATE_RETIRE", entity_type="MODULE_TEMPLATE", entity_id=template_id,
                        new_value={"status": "RETIRED"}, reason=payload.reason)
        return await db.module_templates.find_one({"id": template_id}, {"_id": 0})

    @api.post("/module-framework/templates/{template_id}/copy")
    async def copy_template(template_id: str, payload: TemplateCopyIn, actor: dict = Depends(admin_dep)):
        src = await db.module_templates.find_one({"id": template_id})
        if not src:
            raise HTTPException(404, "Template not found")
        code = _slug(payload.new_code)
        new_plant = payload.target_plant_id or src.get("plant_id") or "GLOBAL"
        if new_plant != "GLOBAL" and not await db.plants.find_one({"id": new_plant}):
            raise HTTPException(400, "Target plant not found")
        existing = await db.module_templates.find_one(
            {"code": code, "plant_id": new_plant}, sort=[("version", -1)],
        )
        version = (existing.get("version", 0) + 1) if existing else 1
        doc = {
            **{k: src[k] for k in (
                "category", "workflow", "form", "pdf_template", "approvals", "role_mapping", "notes",
            ) if k in src},
            "id": str(uuid.uuid4()),
            "code": code,
            "name": payload.new_name,
            "description": f"Copied from {src.get('code')} v{src.get('version')}",
            "plant_id": new_plant,
            "version": version,
            "status": "DRAFT",
            "copied_from": src["id"],
            "created_at": _iso(_now()),
            "created_by": actor["email"],
            "published_at": None,
            "published_by": None,
            "retired_at": None,
            "retired_by": None,
        }
        await db.module_templates.insert_one(doc)
        await log_audit(actor=actor, action="TEMPLATE_COPY", entity_type="MODULE_TEMPLATE", entity_id=doc["id"],
                        new_value={"code": code, "plant_id": new_plant, "copied_from": src["id"]},
                        reason=payload.reason)
        doc.pop("_id", None)
        return doc

    @api.get("/module-framework/templates/{template_id}/audit")
    async def template_audit(template_id: str, user: dict = Depends(get_current_user)):
        rows = await db.audit_trail.find(
            {"entity_type": "MODULE_TEMPLATE", "entity_id": template_id}, {"_id": 0},
        ).sort("timestamp", -1).to_list(500)
        return rows

    # ---------- Dynamic Records ----------
    @api.get("/module-framework/records")
    async def list_dynamic_records(
        template_id: Optional[str] = None,
        plant_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        user: dict = Depends(get_current_user),
    ):
        q: Dict[str, Any] = {}
        if template_id:
            q["template_id"] = template_id
        if plant_id:
            q["plant_id"] = plant_id
        if status:
            q["status"] = status
        rows = await db.dynamic_records.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)
        return rows

    @api.get("/module-framework/records/{record_id}")
    async def get_dynamic_record(record_id: str, user: dict = Depends(get_current_user)):
        r = await db.dynamic_records.find_one({"id": record_id}, {"_id": 0})
        if not r:
            raise HTTPException(404, "Dynamic record not found")
        return r

    @api.post("/module-framework/records")
    async def create_dynamic_record(payload: DynamicRecordIn, user: dict = Depends(get_current_user)):
        tpl = await db.module_templates.find_one({"id": payload.template_id})
        if not tpl:
            raise HTTPException(404, "Template not found")
        if tpl["status"] != "PUBLISHED":
            raise HTTPException(400, "Template is not PUBLISHED")
        plant = await db.plants.find_one({"id": payload.plant_id})
        if not plant:
            raise HTTPException(404, "Plant not found")
        # The template must apply to the plant (GLOBAL or exact match)
        if tpl.get("plant_id") not in ("GLOBAL", payload.plant_id):
            raise HTTPException(400, "Template is not applicable to that plant")
        rno = await _next_dynamic_record_number(db, tpl["code"].upper())
        initial_stage = (tpl.get("workflow") or {}).get("initial_stage") or "INITIATION"
        doc = {
            "id": str(uuid.uuid4()),
            "record_number": rno,
            "template_id": tpl["id"],
            "template_code": tpl["code"],
            "template_version": tpl["version"],
            "template_name": tpl["name"],
            "plant_id": plant["id"],
            "plant_code": plant["code"],
            "plant_name": plant["name"],
            "title": payload.title,
            "form_data": payload.form_data or {},
            "status": initial_stage,
            "current_stage": initial_stage,
            "history": [{
                "stage": initial_stage, "by_user_id": user["id"], "by_user_name": user["name"],
                "at": _iso(_now()), "reason": payload.reason, "comment": "Created",
            }],
            "created_at": _iso(_now()),
            "created_by": user["email"],
            "created_by_id": user["id"],
            "updated_at": _iso(_now()),
            "closed_at": None,
        }
        await db.dynamic_records.insert_one(doc)
        await log_audit(actor=user, action="DYN_RECORD_CREATE", entity_type="DYNAMIC_RECORD", entity_id=doc["id"],
                        new_value={"record_number": rno, "template_code": tpl["code"], "plant_code": plant["code"]},
                        reason=payload.reason)
        doc.pop("_id", None)
        return doc

    @api.post("/module-framework/records/{record_id}/transition")
    async def transition_dynamic_record(record_id: str, payload: DynamicTransitionIn, user: dict = Depends(get_current_user)):
        rec = await db.dynamic_records.find_one({"id": record_id})
        if not rec:
            raise HTTPException(404, "Record not found")
        tpl = await db.module_templates.find_one({"id": rec["template_id"]})
        if not tpl:
            raise HTTPException(400, "Bound template no longer exists")
        # Validate transition against the template's workflow
        wf = tpl.get("workflow") or {}
        transitions = wf.get("transitions") or []
        current = rec["current_stage"]
        transition = next(
            (t for t in transitions
             if t.get("from") == current and t.get("to") == payload.to_stage),
            None,
        )
        if not transition:
            raise HTTPException(400, f"No transition from {current!r} to {payload.to_stage!r}")
        # E-signature
        await verify_esignature(user, payload.password, payload.reason, transition.get("key", payload.to_stage),
                                "DYNAMIC_RECORD", record_id)
        # Permission check: use legacy has_permission helper from server.py via lambda passed in.
        required_perm = transition.get("required_perm")
        if required_perm:
            # Resolve permission via dynamic resolver first, falling back to legacy.
            from role_mgmt import get_effective_permissions
            eff = await get_effective_permissions(db, user)
            module = tpl["code"]  # treat the template code as a module key for dynamic perm
            action = transition.get("key", "transition").lower()
            allowed = False
            # Try dynamic: module=template_code, action=transition_key
            allowed = bool(((eff.get("permissions") or {}).get(module) or {}).get(action))
            if not allowed:
                # Fall back to legacy named perm via server.py helper provided in user object?
                # We can't import has_permission here without circular import; use simple check:
                from server import has_permission  # type: ignore
                allowed = has_permission(user, required_perm)
            if not allowed:
                raise HTTPException(403, f"Permission denied: {required_perm}")
        # Apply form patch if any
        form_data = dict(rec.get("form_data") or {})
        if payload.form_patch:
            form_data.update(payload.form_patch)
        history = list(rec.get("history") or [])
        history.append({
            "stage": payload.to_stage,
            "from_stage": current,
            "transition": transition.get("key"),
            "by_user_id": user["id"],
            "by_user_name": user["name"],
            "by_user_email": user["email"],
            "at": _iso(_now()),
            "reason": payload.reason,
            "comment": payload.comment or "",
            "esignature": True,
        })
        updates: Dict[str, Any] = {
            "current_stage": payload.to_stage,
            "status": payload.to_stage,
            "form_data": form_data,
            "history": history,
            "updated_at": _iso(_now()),
        }
        if payload.to_stage in {"CLOSED", "RETIRED"}:
            updates["closed_at"] = _iso(_now())
        await db.dynamic_records.update_one({"id": record_id}, {"$set": updates})
        await log_audit(
            actor=user, action=f"DYN_TRANSITION_{transition.get('key', payload.to_stage)}",
            entity_type="DYNAMIC_RECORD", entity_id=record_id,
            old_value={"stage": current}, new_value={"stage": payload.to_stage},
            reason=payload.reason, extra={"esignature": True, "comment": payload.comment},
        )
        return await db.dynamic_records.find_one({"id": record_id}, {"_id": 0})

    @api.get("/module-framework/records/{record_id}/audit")
    async def dynamic_record_audit(record_id: str, user: dict = Depends(get_current_user)):
        rows = await db.audit_trail.find(
            {"entity_type": "DYNAMIC_RECORD", "entity_id": record_id}, {"_id": 0},
        ).sort("timestamp", -1).to_list(500)
        return rows
