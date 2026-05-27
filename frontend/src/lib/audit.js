/**
 * Format an audit value pair into a human-readable sentence.
 * Falls back to a compact key/value listing.
 */
export function humanizeAuditValue(value) {
  if (value == null || value === "") return "—";
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object") {
    return Object.entries(value)
      .map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`)
      .join(" · ");
  }
  return String(value);
}

const FIELD_LABELS = {
  status: "Status",
  active: "Active",
  locked: "Locked",
  roles: "Roles",
  department: "Department",
  location: "Location",
  approval_status: "Approval status",
  expiry_date: "Expiry date",
  due_date: "Due date",
  severity: "Severity",
  priority: "Priority",
  title: "Title",
  description: "Description",
  impact_assessment: "Impact assessment",
  root_cause: "Root cause",
  proposed_action: "Proposed action",
};

const ACTION_VERB = {
  CREATE: "created",
  UPDATE: "updated",
  USER_CREATE: "created user",
  USER_ACTIVATE: "activated user",
  USER_DEACTIVATE: "deactivated user",
  USER_LOCK: "locked user",
  USER_UNLOCK: "unlocked user",
  USER_APPROVE: "approved user",
  USER_REJECT: "rejected user",
  USER_RESET_PASSWORD: "reset password for",
  USER_EXTEND_EXPIRY: "extended expiry for",
  WORKFLOW_REVIEW: "marked reviewed",
  WORKFLOW_APPROVE: "approved",
  WORKFLOW_REJECT: "rejected",
  WORKFLOW_CLOSE: "closed",
  WORKFLOW_REOPEN: "reopened",
  WORKFLOW_SUBMIT_REVIEW: "submitted for review",
  LOGIN: "signed in",
  LOGOUT: "signed out",
  LOGIN_FAILED: "failed to sign in",
  ESIGN_FAILED: "failed e-signature",
  PASSWORD_CHANGED: "changed password",
  PASSWORD_RESET_REQUESTED: "requested password reset",
  SESSION_REVOKED: "session revoked for",
  POLICY_UPDATE: "updated password policy",
  COMMENT: "commented on",
  CREATE_DRAFT: "saved draft",
};

export function humanizeAuditEntry(a) {
  const verb = ACTION_VERB[a.action] || a.action.toLowerCase().replace(/_/g, " ");
  const actor = a.user_name || a.user_email;
  let target = "";
  if (a.entity_type === "RECORD") target = ` record ${(a.entity_id || "").slice(0, 8)}`;
  if (a.entity_type === "USER" && a.action !== "LOGIN" && a.action !== "LOGOUT" && a.action !== "LOGIN_FAILED" && a.action !== "PASSWORD_CHANGED") {
    target = ` ${(a.entity_id || "").slice(0, 8)}`;
  }

  // Diff
  const oldV = a.old_value || {};
  const newV = a.new_value || {};
  let diff = "";
  if (typeof oldV === "object" && typeof newV === "object" && oldV && newV) {
    const keys = Array.from(new Set([...Object.keys(oldV), ...Object.keys(newV)]));
    const parts = keys.map((k) => {
      if (k === "extra" || k === "updated_at") return null;
      if (JSON.stringify(oldV[k]) === JSON.stringify(newV[k])) return null;
      const label = FIELD_LABELS[k] || k;
      const left = humanizeAuditValue(oldV[k]);
      const right = humanizeAuditValue(newV[k]);
      return `${label}: ${left} → ${right}`;
    }).filter(Boolean);
    diff = parts.join(" · ");
  }

  return {
    sentence: `${actor} ${verb}${target}`.trim(),
    diff,
    reason: a.reason || "",
  };
}
