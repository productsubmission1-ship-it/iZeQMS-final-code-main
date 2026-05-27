// User Role Matrix — canonical roles + permission helpers
// Source: Recommended_User_Role_Matrix_izQMS.docx
//
// Hierarchy: super_admin > admin > qa_manager > qa_reviewer
//                                             > department_manager
//                                             > employee_operator
//            auditor (read-only, separate track)

export const ROLES = {
  SUPER_ADMIN: "super_admin",
  ADMIN: "admin",
  QA_MANAGER: "qa_manager",
  QA_REVIEWER: "qa_reviewer",
  DEPARTMENT_MANAGER: "department_manager",
  EMPLOYEE: "employee_operator",
  AUDITOR: "auditor",
};

export const CANONICAL_ROLES = [
  ROLES.SUPER_ADMIN,
  ROLES.ADMIN,
  ROLES.QA_MANAGER,
  ROLES.QA_REVIEWER,
  ROLES.DEPARTMENT_MANAGER,
  ROLES.EMPLOYEE,
  ROLES.AUDITOR,
];

export const ROLE_LABELS = {
  super_admin: "Super Admin",
  admin: "Admin",
  qa_manager: "QA Manager",
  qa_reviewer: "QA Reviewer",
  department_manager: "Department Manager",
  employee_operator: "Employee / Operator",
  auditor: "Auditor (Read-only)",
};

export const ROLE_DESCRIPTIONS = {
  super_admin:
    "Full system access. User & role management, workflow configuration, audit trail (full), system settings, archives.",
  admin:
    "User management, role assignment, password reset, department/location mapping, workflow monitoring, audit trail (full).",
  qa_manager:
    "Review and approve QMS records (CAPA, Deviation, Change Control, Incident, Event). E-signature approval, record closure, audit trail (view).",
  qa_reviewer:
    "Review/verify records, add comments, reject/send for correction, view reports and audit logs.",
  department_manager:
    "Create records, review department records, assign tasks, track pending activities, department reporting.",
  employee_operator:
    "Create requests, submit forms, edit draft records, view assigned records, add comments.",
  auditor:
    "Read-only access for inspection: view audit trail, records, reports; can export reports. Cannot edit or approve anything.",
};

// Legacy role names that may still appear in older user docs (auto-mapped server-side)
const LEGACY_TO_CANONICAL = {
  initiator: ROLES.EMPLOYEE,
  reviewer: ROLES.QA_REVIEWER,
  approver: ROLES.QA_MANAGER,
  qa_head: ROLES.QA_MANAGER,
};

const ROLE_EXPANSION = {
  [ROLES.SUPER_ADMIN]: new Set([
    ROLES.SUPER_ADMIN, ROLES.ADMIN, ROLES.QA_MANAGER, ROLES.QA_REVIEWER,
    ROLES.DEPARTMENT_MANAGER, ROLES.EMPLOYEE, ROLES.AUDITOR,
  ]),
  [ROLES.ADMIN]: new Set([
    ROLES.ADMIN, ROLES.QA_MANAGER, ROLES.QA_REVIEWER,
    ROLES.DEPARTMENT_MANAGER, ROLES.EMPLOYEE,
  ]),
  [ROLES.QA_MANAGER]: new Set([ROLES.QA_MANAGER, ROLES.QA_REVIEWER, ROLES.EMPLOYEE]),
  [ROLES.QA_REVIEWER]: new Set([ROLES.QA_REVIEWER, ROLES.EMPLOYEE]),
  [ROLES.DEPARTMENT_MANAGER]: new Set([ROLES.DEPARTMENT_MANAGER, ROLES.EMPLOYEE, ROLES.QA_REVIEWER]),
  [ROLES.EMPLOYEE]: new Set([ROLES.EMPLOYEE]),
  [ROLES.AUDITOR]: new Set([ROLES.AUDITOR]),
};

const PERMISSION_MATRIX = {
  create_record:    new Set([ROLES.EMPLOYEE, ROLES.DEPARTMENT_MANAGER, ROLES.QA_REVIEWER, ROLES.QA_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN]),
  edit_draft:       new Set([ROLES.EMPLOYEE, ROLES.DEPARTMENT_MANAGER, ROLES.QA_REVIEWER, ROLES.QA_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN]),
  view_all_records: new Set([ROLES.DEPARTMENT_MANAGER, ROLES.QA_REVIEWER, ROLES.QA_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN, ROLES.AUDITOR]),
  review_record:    new Set([ROLES.QA_REVIEWER, ROLES.DEPARTMENT_MANAGER, ROLES.QA_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN]),
  approve_record:   new Set([ROLES.QA_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN]),
  reject_record:    new Set([ROLES.QA_REVIEWER, ROLES.QA_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN]),
  close_record:     new Set([ROLES.QA_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN]),
  view_reports:     new Set([ROLES.EMPLOYEE, ROLES.DEPARTMENT_MANAGER, ROLES.QA_REVIEWER, ROLES.QA_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN, ROLES.AUDITOR]),
  export_reports:   new Set([ROLES.QA_REVIEWER, ROLES.QA_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN, ROLES.AUDITOR]),
  user_management:  new Set([ROLES.ADMIN, ROLES.SUPER_ADMIN]),
  role_management:  new Set([ROLES.ADMIN, ROLES.SUPER_ADMIN]),
  workflow_config:  new Set([ROLES.ADMIN, ROLES.SUPER_ADMIN]),
  audit_trail_view: new Set([ROLES.QA_REVIEWER, ROLES.QA_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN, ROLES.AUDITOR]),
  audit_trail_full: new Set([ROLES.ADMIN, ROLES.SUPER_ADMIN]),
  assign_tasks:     new Set([ROLES.DEPARTMENT_MANAGER, ROLES.QA_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN]),
  // Module Framework (matches role_mgmt.py MODULE_CATALOG.module_framework)
  view_module_framework:    new Set([ROLES.QA_REVIEWER, ROLES.QA_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN]),
  manage_module_templates:  new Set([ROLES.QA_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN]),
  publish_module_templates: new Set([ROLES.QA_MANAGER, ROLES.ADMIN, ROLES.SUPER_ADMIN]),
  retire_module_templates:  new Set([ROLES.ADMIN, ROLES.SUPER_ADMIN]),
};

export function canonicalize(role) {
  return LEGACY_TO_CANONICAL[role] || role;
}

export function effectiveRoles(user) {
  const out = new Set();
  (user?.roles || []).forEach((r) => {
    const c = canonicalize(r);
    (ROLE_EXPANSION[c] || new Set([c])).forEach((x) => out.add(x));
  });
  return out;
}

export function hasRole(user, ...roles) {
  const eff = effectiveRoles(user);
  return roles.some((r) => eff.has(canonicalize(r)));
}

export function hasPermission(user, permission) {
  const eff = effectiveRoles(user);
  const allowed = PERMISSION_MATRIX[permission];
  if (!allowed) return false;
  for (const r of eff) if (allowed.has(r)) return true;
  return false;
}

export function isAuditor(user) {
  const roles = user?.roles || [];
  // Auditor is the user's primary identity if their only role is auditor.
  return roles.length === 1 && canonicalize(roles[0]) === ROLES.AUDITOR;
}
