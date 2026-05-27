# izQMS — Product Requirements Document

## Original Problem Statement
**Role Management** + **User-Specific Permissions** + **Plant/Site-Based Dynamic Module Framework**.

## Architecture
- **Frontend**: React 19 + Shadcn UI + React Router 7, Swiss/high-contrast theme (Work Sans / IBM Plex Sans / IBM Plex Mono).
- **Backend**: FastAPI single `server.py` + dedicated `role_mgmt.py` + dedicated `module_framework.py`.
- **Database**: MongoDB. Collections: `users`, `qms_records`, `audit_trail`, `counters`, `login_attempts`, `roles`, `user_permission_overrides`, **`plants`**, **`module_templates`**, **`dynamic_records`**.
- **Auth**: JWT (HS256) via httpOnly cookies + Bearer fallback, bcrypt, brute-force lockout, e-signature on every workflow action.

## What's Been Implemented

### Iteration 5 — Dynamic Role Matrix
- `role_mgmt.py` with module catalog, 7 seeded system roles, CRUD endpoints, user-specific overrides (additional / restricted / temporary).
- Front-end pages: `/roles` Role Matrix list with editor + copy + audit drawer; `/users/{id}/permissions` for per-user overrides.

### Iteration 6 — Workflow migration + Audit export + Plant/Site Framework
**Task 1 — Workflow now consumes dynamic Role Matrix (with backward-compat fallback)**
- `has_record_action(user, record_type, action)` resolves via dynamic role permissions first; falls back to the static `PERMISSION_MATRIX` so existing canonical roles stay unchanged.
- DENY (RESTRICTED) user overrides now block the REVIEW / APPROVE / REJECT / CLOSE actions on existing izQMS records.
- `get_current_user` caches `_dynamic_perms` and `_dynamic_denies` on the user dict for fast O(1) checks downstream.

**Task 2 — Audit-trail CSV/JSON export**
- `GET /api/role-mgmt/audit/export?format=csv|json` streams CSV (default) with columns: Timestamp / User Email / User Name / Roles / Action / Entity Type / Entity ID / Old / New / Reason.
- New "Export Audit (CSV)" button on the Role Matrix page.

**Task 3 — Plant/Site-Based Dynamic Module Framework (foundation, fully isolated)**
- New module `module_framework.py` with:
  - 14 form-field types (text, textarea, number, date, datetime, dropdown, multiselect, checkbox, radio, attachment, signature, approval, user_picker, department).
  - **Plants** CRUD (`/api/module-framework/plants`).
  - **Module Templates** with versioning (`DRAFT → PUBLISHED → RETIRED`) — every PUBLISHED version is immutable; editing creates a NEW draft version; publishing v2 automatically RETIRES v1 for the same code+plant.
  - **Dynamic Records** bound to immutable `(template_id, template_version)` — old records always render against their original template version.
  - Workflow transitions on dynamic records validate the transition exists in the template, require e-signature, and write `DYN_TRANSITION_<key>` audit entries.
  - Full audit trail across PLANT / MODULE_TEMPLATE / DYNAMIC_RECORD entities.
- 3 seeded plants: HQ, PLANT-1 (Bangalore), PLANT-2 (Pune).
- New front-end pages:
  - `/plants` — Plants CRUD (admin-only via `RequirePermission`).
  - `/module-framework` — Templates list + filters + publish/retire/copy + audit drawer.
  - `TemplateDesigner` modal — full designer with 4 tabs (workflow / form / pdf / advanced), supports stage colours, transitions with from/to/label/required_perm/e-sig, drag-to-reorder fields, JSON edit for PDF & approvals & role mappings.
  - `/dynamic-records/{template_id}` — Records list, create dialog with dynamic form generator, transition dialog with e-signature.
- Existing izQMS modules (Deviation, CAPA, Change Control, Incident, Event) **are completely untouched**.
- Client-side `RequirePermission` route guard on admin-only pages (`/roles`, `/plants`, `/module-framework`, `/users/{id}/permissions`).

## API Endpoints (this iteration)

### Role Matrix (`/api/role-mgmt/*`)
| Method | Path | Notes |
|---|---|---|
| GET | `/modules` | Module + action catalog (12 modules × ~60 actions) |
| GET | `/roles?active=` | List with user counts |
| POST | `/roles` | Create (admin) |
| PATCH | `/roles/{id}` | Update (admin) |
| POST | `/roles/{id}/copy` | Copy (admin) |
| POST | `/roles/{id}/activate` | Toggle active (admin; system roles guarded) |
| GET | `/roles/{id}/audit` | Audit history |
| GET | `/users/{uid}/permissions` | Effective permissions |
| GET | `/users/{uid}/overrides` | List overrides |
| POST | `/users/{uid}/overrides` | Add ADDITIONAL/RESTRICTED/TEMPORARY (admin) |
| DELETE | `/users/{uid}/overrides/{oid}` | Remove (admin) |
| POST | `/users/{uid}/assign-role` | Assign (admin) |
| POST | `/users/{uid}/revoke-role` | Revoke (admin) |
| GET | `/my-permissions` | Current user's effective perms |
| **GET** | **`/audit/export?format=csv\|json`** | **New CSV / JSON export** |

### Plant/Site Framework (`/api/module-framework/*`)
| Method | Path | Notes |
|---|---|---|
| GET | `/field-types` | Catalog of field types + default templates |
| GET | `/plants` | List plants |
| POST | `/plants` | Create (admin) |
| PATCH | `/plants/{id}` | Update (admin; supports activate/deactivate via `active`) |
| GET | `/templates` | List with filters (plant/status/category) |
| GET | `/templates/{id}` | Detail |
| GET | `/templates/{id}/versions` | All versions for code+plant |
| POST | `/templates` | Create DRAFT (admin) |
| PATCH | `/templates/{id}` | Update DRAFT only (admin) |
| POST | `/templates/{id}/publish` | DRAFT → PUBLISHED; auto-retires previous PUBLISHED (admin) |
| POST | `/templates/{id}/retire` | PUBLISHED → RETIRED (admin) |
| POST | `/templates/{id}/copy` | Copy across plants (admin) |
| GET | `/templates/{id}/audit` | Audit history |
| GET | `/records` | List dynamic records (any user) |
| POST | `/records` | Create (any user) |
| GET | `/records/{id}` | Detail |
| POST | `/records/{id}/transition` | Workflow transition with e-sig |
| GET | `/records/{id}/audit` | Per-record audit |

## Seed Users (per `/app/memory/test_credentials.md`)
| Role | Email | Password |
|---|---|---|
| Super Admin | admin@izqms.com | Admin@2026 |
| Admin | admin.user@izqms.com | AdminUser@2026 |
| QA Manager | qa.manager@izqms.com | QaManager@2026 |
| QA Reviewer | qa.reviewer@izqms.com | QaReviewer@2026 |
| Department Manager | dept.manager@izqms.com | DeptMgr@2026 |
| Employee | employee@izqms.com | Employee@2026 |
| Auditor | auditor@izqms.com | Auditor@2026 |

## Testing
- `tests/test_role_mgmt.py` — 16 tests (CRUD + overrides + audit)
- `tests/test_role_mgmt_extra.py` — 8 tests (edge cases)
- `tests/test_module_framework.py` — 9 tests (plants + templates lifecycle + dynamic records + e-sig + RBAC + CSV export)
- `tests/test_iter6_regression.py` — 7 tests (legacy QMS regression + DENY blocks APPROVE + auto-retire)
- `tests/test_role_matrix.py` — 46/50 passing (4 pre-existing failures unrelated to this work)
- Testing subagent end-to-end pass on iter 6: **24/24 backend + frontend 100%**.

## Backlog
### P1 — already filed
- Deprecate the static `PERMISSION_MATRIX` once the dynamic resolver covers every workflow surface.

### P2
- Full PDF rendering using the template's pdf_template config (today only stored; rendering placeholder).
- Approval chain execution (multi-level with role escalation).
- Pre-validation on template publish (must have ≥1 stage, ≥1 transition, ≥1 form field).
- Plant-scoped reporting + dashboards.
- LDAP / SSO integration.

## Next Tasks
1. Use the Plant/Site Framework to onboard real plants & create the first non-Deviation module (e.g., "Equipment Calibration" or "OOS Investigation") without code changes.
2. PDF rendering against template pdf_template config.
3. Multi-level approval chain in template designer.
