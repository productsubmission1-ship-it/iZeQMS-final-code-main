import React from "react";

const STYLES = {
  DRAFT: { bg: "#F1F5F9", text: "#475569", border: "#CBD5E1" },
  OPEN: { bg: "#FFFBEB", text: "#B45309", border: "#FDE68A" },
  IN_REVIEW: { bg: "#EFF6FF", text: "#1D4ED8", border: "#BFDBFE" },
  APPROVED: { bg: "#ECFDF5", text: "#047857", border: "#A7F3D0" },
  REJECTED: { bg: "#FEF2F2", text: "#B91C1C", border: "#FECACA" },
  CLOSED: { bg: "#F1F5F9", text: "#0F172A", border: "#CBD5E1" },
  OVERDUE: { bg: "#FEF2F2", text: "#B91C1C", border: "#FECACA" },
};

export default function StatusBadge({ status, className = "", overdue = false, testid }) {
  const s = STYLES[status] || STYLES.DRAFT;
  const label = overdue ? "OVERDUE" : (status || "—").replace("_", " ");
  const style = overdue ? STYLES.OVERDUE : s;
  return (
    <span
      data-testid={testid || `status-badge-${(label || "").toLowerCase().replace(/\s/g, "-")}`}
      className={`inline-flex items-center px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide border rounded-sm ${overdue ? "overdue-pulse" : ""} ${className}`}
      style={{ backgroundColor: style.bg, color: style.text, borderColor: style.border, fontFamily: "IBM Plex Mono, monospace" }}
    >
      {label}
    </span>
  );
}
