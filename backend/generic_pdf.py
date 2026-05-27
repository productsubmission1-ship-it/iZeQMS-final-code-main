"""
izQMS — Generic PDF generators.

1. build_dynamic_record_pdf  → PDF for any Module Framework dynamic record.
   Renders the template's defined sections / fields with the user-entered
   form_data, the workflow history, and the per-record audit trail.

2. build_audit_trail_pdf     → PDF for the global Audit Trail report.

Both PDFs include a compliant footer with:
    "Printed by <user>  ·  <generated at>  ·  Page X of Y"
which is required by URS izQMS §4.0 (Audit Trail & Report) and 21 CFR Part 11.
"""

from io import BytesIO
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _styles():
    base = getSampleStyleSheet()
    return {
        "title":   ParagraphStyle("title", parent=base["Title"], fontSize=15, leading=18,
                                  spaceAfter=2, alignment=0, textColor=colors.HexColor("#0f172a")),
        "sub":     ParagraphStyle("sub", parent=base["Normal"], fontSize=8.5, leading=11,
                                  textColor=colors.HexColor("#475569")),
        "h":       ParagraphStyle("h", parent=base["Heading2"], fontSize=11, leading=14,
                                  textColor=colors.white, backColor=colors.HexColor("#0f172a"),
                                  leftIndent=4, rightIndent=4, spaceBefore=8, spaceAfter=4,
                                  borderPadding=4),
        "section": ParagraphStyle("section", parent=base["Heading3"], fontSize=10, leading=13,
                                  textColor=colors.HexColor("#0f172a"), spaceBefore=6, spaceAfter=2),
        "label":   ParagraphStyle("label", parent=base["Normal"], fontSize=8.5, leading=11,
                                  textColor=colors.HexColor("#475569")),
        "val":     ParagraphStyle("val", parent=base["Normal"], fontSize=9, leading=12,
                                  textColor=colors.HexColor("#0f172a")),
        "small":   ParagraphStyle("small", parent=base["Normal"], fontSize=7.5, leading=10,
                                  textColor=colors.HexColor("#64748b")),
        "muted":   ParagraphStyle("muted", parent=base["Normal"], fontSize=8, leading=10,
                                  textColor=colors.HexColor("#94a3b8")),
    }


def _fmt_value(v: Any) -> str:
    if v is None or v == "":
        return "<font color='#94a3b8'>— not provided —</font>"
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, (list, tuple, set)):
        return ", ".join(str(x) for x in v) if v else "<font color='#94a3b8'>—</font>"
    if isinstance(v, dict):
        # Used for "Other" composite values e.g. {"value": "Other", "other": "Custom text"}
        if "other" in v and v.get("value") == "Other":
            return f"Other — {v.get('other') or '—'}"
        return ", ".join(f"{k}: {vv}" for k, vv in v.items())
    s = str(v).replace("\n", "<br/>")
    return s


def _fmt_dt(s) -> str:
    if not s:
        return "—"
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).strftime("%d-%b-%Y %H:%M")
    except Exception:
        return str(s)[:19]


# Footer factory bound to printer info
def _make_footer(*, printed_by_name: str, printed_by_email: str, header_title: str, record_label: str = ""):
    """Returns (onFirstPage, onLaterPages) callbacks. Uses canvas.getPageNumber and
    a single _page_count placeholder on the canvas which we set after build."""
    generated_at = datetime.now(timezone.utc).strftime("%d-%b-%Y %H:%M UTC")

    def _draw(canvas, doc_):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas.setLineWidth(0.4)
        canvas.line(15 * mm, 14 * mm, 195 * mm, 14 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#475569"))
        left = f"Printed by {printed_by_name} ({printed_by_email})  ·  {generated_at}"
        if record_label:
            left = f"{record_label}  ·  " + left
        canvas.drawString(15 * mm, 9 * mm, left)
        # Page X of Y — we draw "Page X" first; total pages stamped post-build via canvasmaker.
        page_no = canvas.getPageNumber()
        canvas.drawRightString(195 * mm, 9 * mm, f"Page {page_no} of {{TOTAL_PAGES}}")
        # Top-right small title for context
        canvas.setFont("Helvetica-Oblique", 7)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.drawRightString(195 * mm, 287 * mm, header_title)
        canvas.restoreState()
    return _draw


from reportlab.pdfgen import canvas as _canvas_mod  # noqa: E402


class _NumberedCanvas(_canvas_mod.Canvas):
    """Two-pass canvas that lets us stamp "Page X of Y"."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states = []

    def showPage(self):
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            # Re-draw the page-number placeholder with the real total
            self._stamp_total(total)
            super().showPage()
        super().save()

    def _stamp_total(self, total: int):
        # Cover the previously-drawn placeholder and re-draw with total
        self.saveState()
        self.setFillColor(colors.white)
        self.rect(170 * mm, 8 * mm, 25 * mm, 4 * mm, stroke=0, fill=1)
        self.setFillColor(colors.HexColor("#475569"))
        self.setFont("Helvetica", 7.5)
        page_no = self.getPageNumber()
        self.drawRightString(195 * mm, 9 * mm, f"Page {page_no} of {total}")
        self.restoreState()


# ---------------------------------------------------------------------------
# 1) Dynamic record PDF
# ---------------------------------------------------------------------------
def build_dynamic_record_pdf(
    *,
    record: Dict[str, Any],
    template: Dict[str, Any],
    audit_trail: List[Dict[str, Any]],
    printed_by: Dict[str, Any],
) -> bytes:
    buf = BytesIO()
    record_label = f"{template.get('name','Module')} · {record.get('record_number','')}"
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"{template.get('name','Module Record')} {record.get('record_number','')}",
        author=printed_by.get("name", ""),
    )
    s = _styles()
    story: List[Any] = []

    # ----- Header -----
    story.append(Paragraph(template.get("name") or "Module Record", s["title"]))
    story.append(Paragraph(
        f"<b>{record.get('record_number','—')}</b> · Template <b>{template.get('code','')}</b> v{template.get('version','')} "
        f"· Plant {record.get('plant_name','')} · Stage <b>{record.get('current_stage','')}</b>",
        s["sub"],
    ))
    story.append(Spacer(1, 4))

    # ----- Record meta -----
    story.append(Paragraph("Record Summary", s["h"]))
    meta_rows = [
        [Paragraph("Title", s["label"]),       Paragraph(_fmt_value(record.get("title")), s["val"])],
        [Paragraph("Record No.", s["label"]),  Paragraph(_fmt_value(record.get("record_number")), s["val"])],
        [Paragraph("Created at", s["label"]),  Paragraph(_fmt_dt(record.get("created_at")), s["val"])],
        [Paragraph("Created by", s["label"]),  Paragraph(_fmt_value(record.get("created_by")), s["val"])],
        [Paragraph("Updated at", s["label"]),  Paragraph(_fmt_dt(record.get("updated_at")), s["val"])],
        [Paragraph("Current stage", s["label"]),Paragraph(_fmt_value(record.get("current_stage")), s["val"])],
        [Paragraph("Template", s["label"]),    Paragraph(f"{template.get('name','')} ({template.get('code','')} v{template.get('version','')})", s["val"])],
    ]
    t = Table(meta_rows, colWidths=[45 * mm, 135 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 6))

    # ----- Form data section by section -----
    form_data = record.get("form_data") or {}
    sections = (template.get("form") or {}).get("sections") or []
    if not sections:
        story.append(Paragraph("Form Data", s["h"]))
        story.append(Paragraph("<i>This template has no form sections.</i>", s["small"]))
    for sec in sections:
        story.append(Paragraph(sec.get("label") or sec.get("key") or "Section", s["h"]))
        rows = []
        for f in (sec.get("fields") or []):
            label = f.get("label") or f.get("key") or ""
            raw = form_data.get(f.get("key"))
            rows.append([
                Paragraph(label, s["label"]),
                Paragraph(_fmt_value(raw), s["val"]),
            ])
        if not rows:
            rows = [[Paragraph("<i>No fields in this section.</i>", s["small"]), Paragraph("", s["val"])]]
        t = Table(rows, colWidths=[55 * mm, 125 * mm])
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(t)
        story.append(Spacer(1, 4))

    # ----- Workflow history -----
    story.append(Paragraph("Workflow History", s["h"]))
    history = record.get("history") or []
    if not history:
        story.append(Paragraph("<i>No workflow transitions yet.</i>", s["small"]))
    else:
        head = ["When (UTC)", "By", "Stage", "Reason / Comment"]
        data: List[List[Any]] = [[Paragraph(f"<b>{h}</b>", s["small"]) for h in head]]
        for h in history:
            data.append([
                Paragraph(_fmt_dt(h.get("at")), s["small"]),
                Paragraph(_fmt_value(h.get("by_user_name") or h.get("by_user_email")), s["small"]),
                Paragraph(_fmt_value(h.get("stage")), s["small"]),
                Paragraph(_fmt_value((h.get("reason") or "") + (("  ·  " + h.get("comment")) if h.get("comment") else "")), s["small"]),
            ])
        t = Table(data, colWidths=[30 * mm, 45 * mm, 30 * mm, 75 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t)

    # ----- Audit trail (per-record) -----
    story.append(Spacer(1, 6))
    story.append(Paragraph("Audit Trail · 21 CFR Part 11", s["h"]))
    if not audit_trail:
        story.append(Paragraph("<i>No audit entries.</i>", s["small"]))
    else:
        head = ["Timestamp (UTC)", "User", "Action", "Reason"]
        data = [[Paragraph(f"<b>{h}</b>", s["small"]) for h in head]]
        for a in audit_trail[:80]:
            data.append([
                Paragraph(_fmt_dt(a.get("timestamp")), s["small"]),
                Paragraph(_fmt_value(a.get("user_email")), s["small"]),
                Paragraph(_fmt_value(a.get("action")), s["small"]),
                Paragraph(_fmt_value((a.get("reason") or "")[:120]), s["small"]),
            ])
        t = Table(data, colWidths=[30 * mm, 45 * mm, 40 * mm, 65 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t)

    footer = _make_footer(
        printed_by_name=printed_by.get("name") or "—",
        printed_by_email=printed_by.get("email") or "",
        header_title=f"izQMS · {template.get('name','Module')} Report",
        record_label=record.get("record_number") or "",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer, canvasmaker=_NumberedCanvas)
    return buf.getvalue()


def build_audit_trail_pdf(
    *,
    rows: List[Dict[str, Any]],
    filters: Dict[str, Any],
    printed_by: Dict[str, Any],
) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title="izQMS Audit Trail Report",
        author=printed_by.get("name", ""),
    )
    s = _styles()
    story: List[Any] = []

    story.append(Paragraph("izQMS — Global Audit Trail Report", s["title"]))
    story.append(Paragraph(
        f"Generated {datetime.now(timezone.utc).strftime('%d-%b-%Y %H:%M UTC')} · {len(rows)} entries · 21 CFR Part 11 · EU Annex 11 · ALCOA++",
        s["sub"],
    ))
    story.append(Spacer(1, 4))

    # Filter summary
    flt_lines = []
    for k in ("entity_type", "action", "user_email", "from_date", "to_date"):
        v = filters.get(k)
        if v:
            flt_lines.append(f"<b>{k}</b>: {v}")
    if flt_lines:
        story.append(Paragraph("Filters applied: " + " · ".join(flt_lines), s["small"]))
        story.append(Spacer(1, 4))

    head = ["Timestamp (UTC)", "User", "Entity", "Action", "Detail / Reason"]
    data: List[List[Any]] = [[Paragraph(f"<b>{h}</b>", s["small"]) for h in head]]
    for a in rows:
        detail = a.get("reason") or ""
        # Inline old→new diff summary if present
        old, new = a.get("old_value"), a.get("new_value")
        diff = ""
        if old or new:
            try:
                if isinstance(old, dict) or isinstance(new, dict):
                    keys = sorted(set((old or {}).keys()) | set((new or {}).keys()))
                    pieces = []
                    for k in keys[:6]:
                        ov = (old or {}).get(k)
                        nv = (new or {}).get(k)
                        if ov != nv:
                            pieces.append(f"{k}: {ov!r} → {nv!r}")
                    diff = "; ".join(pieces)
            except Exception:
                pass
        cell_detail = detail
        if diff:
            cell_detail = (cell_detail + "  ·  " + diff) if cell_detail else diff
        data.append([
            Paragraph(_fmt_dt(a.get("timestamp")), s["small"]),
            Paragraph(_fmt_value(a.get("user_email")), s["small"]),
            Paragraph(_fmt_value(a.get("entity_type")), s["small"]),
            Paragraph(_fmt_value(a.get("action")), s["small"]),
            Paragraph(_fmt_value(cell_detail[:200]), s["small"]),
        ])
    t = Table(data, colWidths=[28 * mm, 42 * mm, 25 * mm, 35 * mm, 56 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#e2e8f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(t)

    footer = _make_footer(
        printed_by_name=printed_by.get("name") or "—",
        printed_by_email=printed_by.get("email") or "",
        header_title="izQMS · Audit Trail Report",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer, canvasmaker=_NumberedCanvas)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 3) Legacy QMS record PDF (Change Control / CAPA / Incident / Event / Deviation
#    when the Deviation 9-Part renderer is not used)
# ---------------------------------------------------------------------------
TYPE_LABEL = {
    "CHANGE_CONTROL": "Change Control",
    "DEVIATION": "Deviation",
    "CAPA": "CAPA",
    "INCIDENT": "Incident",
    "EVENT": "Event",
}


def build_legacy_record_pdf(
    *,
    record: Dict[str, Any],
    template: Optional[Dict[str, Any]],
    workflow: List[Dict[str, Any]],
    audit_trail: List[Dict[str, Any]],
    comments: List[Dict[str, Any]],
    printed_by: Dict[str, Any],
) -> bytes:
    buf = BytesIO()
    type_label = TYPE_LABEL.get(record.get("type", ""), record.get("type", "Record"))
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"{type_label} {record.get('record_number','')}",
        author=printed_by.get("name", ""),
    )
    s = _styles()
    story: List[Any] = []

    story.append(Paragraph(f"{type_label} Report", s["title"]))
    story.append(Paragraph(
        f"<b>{record.get('record_number','—')}</b> · {record.get('title','')} · Status <b>{record.get('status','')}</b>",
        s["sub"],
    ))
    story.append(Spacer(1, 4))

    story.append(Paragraph("Record Summary", s["h"]))
    meta = [
        [Paragraph("Title", s["label"]),       Paragraph(_fmt_value(record.get("title")), s["val"])],
        [Paragraph("Record No.", s["label"]),  Paragraph(_fmt_value(record.get("record_number")), s["val"])],
        [Paragraph("Type", s["label"]),        Paragraph(type_label, s["val"])],
        [Paragraph("Department", s["label"]),  Paragraph(_fmt_value(record.get("department")), s["val"])],
        [Paragraph("Location", s["label"]),    Paragraph(_fmt_value(record.get("location")), s["val"])],
        [Paragraph("Severity", s["label"]),    Paragraph(_fmt_value(record.get("severity")), s["val"])],
        [Paragraph("Priority", s["label"]),    Paragraph(_fmt_value(record.get("priority")), s["val"])],
        [Paragraph("Initiator", s["label"]),   Paragraph(_fmt_value(record.get("initiator_name")), s["val"])],
        [Paragraph("Status", s["label"]),      Paragraph(_fmt_value(record.get("status")), s["val"])],
        [Paragraph("Created", s["label"]),     Paragraph(_fmt_dt(record.get("created_at")), s["val"])],
        [Paragraph("Updated", s["label"]),     Paragraph(_fmt_dt(record.get("updated_at")), s["val"])],
        [Paragraph("Due date", s["label"]),    Paragraph(_fmt_dt(record.get("due_date")), s["val"])],
        [Paragraph("Closed", s["label"]),      Paragraph(_fmt_dt(record.get("closed_at")), s["val"])],
    ]
    t = Table(meta, colWidths=[45 * mm, 135 * mm])
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 6))

    # Framework form data — render template's sections/fields when bound
    framework_data = record.get("framework_form_data") or {}
    sections = (template or {}).get("form", {}).get("sections") or []
    if sections:
        for sec in sections:
            story.append(Paragraph(sec.get("label") or sec.get("key") or "Section", s["h"]))
            rows: List[List[Any]] = []
            for f in (sec.get("fields") or []):
                label = f.get("label") or f.get("key") or ""
                raw = framework_data.get(f.get("key"))
                rows.append([Paragraph(label, s["label"]), Paragraph(_fmt_value(raw), s["val"])])
            if not rows:
                rows = [[Paragraph("<i>No fields.</i>", s["small"]), Paragraph("", s["val"])]]
            t = Table(rows, colWidths=[55 * mm, 125 * mm])
            t.setStyle(TableStyle([
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(t)
            story.append(Spacer(1, 4))
    else:
        # Fall back to legacy free-text blocks (older records pre-framework)
        for key, label in (("description", "Description"), ("impact_assessment", "Impact Assessment"),
                           ("root_cause", "Root Cause"), ("proposed_action", "Proposed Action")):
            v = record.get(key)
            if v:
                story.append(Paragraph(label, s["section"]))
                story.append(Paragraph(_fmt_value(v), s["val"]))
                story.append(Spacer(1, 3))

    # Workflow
    story.append(Paragraph("Workflow History", s["h"]))
    if not workflow:
        story.append(Paragraph("<i>No workflow events.</i>", s["small"]))
    else:
        head = ["When (UTC)", "Actor", "Action", "Status", "Reason / Comment"]
        data: List[List[Any]] = [[Paragraph(f"<b>{h}</b>", s["small"]) for h in head]]
        for w in workflow:
            data.append([
                Paragraph(_fmt_dt(w.get("timestamp")), s["small"]),
                Paragraph(_fmt_value(w.get("actor_name") or w.get("actor_email")), s["small"]),
                Paragraph(_fmt_value(w.get("action")), s["small"]),
                Paragraph(f"{w.get('from_status','')} → {w.get('to_status','')}", s["small"]),
                Paragraph(_fmt_value((w.get("reason") or "") + (("  ·  " + w.get("comment")) if w.get("comment") else "")), s["small"]),
            ])
        t = Table(data, colWidths=[28 * mm, 38 * mm, 30 * mm, 30 * mm, 54 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t)

    # Comments
    if comments:
        story.append(Spacer(1, 6))
        story.append(Paragraph("Comments", s["h"]))
        for c in comments:
            story.append(Paragraph(
                f"<b>{_fmt_value(c.get('user_name'))}</b> · {_fmt_dt(c.get('timestamp'))}", s["small"]))
            story.append(Paragraph(_fmt_value(c.get("body")), s["val"]))
            story.append(Spacer(1, 2))

    # Audit
    story.append(Spacer(1, 6))
    story.append(Paragraph("Audit Trail · 21 CFR Part 11", s["h"]))
    if not audit_trail:
        story.append(Paragraph("<i>No audit entries.</i>", s["small"]))
    else:
        head = ["Timestamp (UTC)", "User", "Action", "Reason"]
        data = [[Paragraph(f"<b>{h}</b>", s["small"]) for h in head]]
        for a in audit_trail[:80]:
            data.append([
                Paragraph(_fmt_dt(a.get("timestamp")), s["small"]),
                Paragraph(_fmt_value(a.get("user_email")), s["small"]),
                Paragraph(_fmt_value(a.get("action")), s["small"]),
                Paragraph(_fmt_value((a.get("reason") or "")[:120]), s["small"]),
            ])
        t = Table(data, colWidths=[30 * mm, 45 * mm, 40 * mm, 65 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t)

    footer = _make_footer(
        printed_by_name=printed_by.get("name") or "—",
        printed_by_email=printed_by.get("email") or "",
        header_title=f"izQMS · {type_label} Report",
        record_label=record.get("record_number") or "",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer, canvasmaker=_NumberedCanvas)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 4) Reports PDF — aggregate report across all modules
# ---------------------------------------------------------------------------
def build_reports_pdf(
    *,
    rows: List[Dict[str, Any]],
    filters: Dict[str, Any],
    include_workflows: bool,
    workflows_by_id: Dict[str, List[Dict[str, Any]]],
    printed_by: Dict[str, Any],
) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title="izQMS Quality Management Report",
        author=printed_by.get("name", ""),
    )
    s = _styles()
    story: List[Any] = []

    story.append(Paragraph("izQMS — Quality Management Report", s["title"]))
    story.append(Paragraph(
        f"Generated {datetime.now(timezone.utc).strftime('%d-%b-%Y %H:%M UTC')} · {len(rows)} records · 21 CFR Part 11 · ALCOA++",
        s["sub"],
    ))

    flt = []
    for k in ("type", "status", "from_date", "to_date"):
        v = filters.get(k)
        if v and v != "ALL":
            flt.append(f"<b>{k}</b>: {v}")
    if flt:
        story.append(Paragraph("Filters: " + " · ".join(flt), s["small"]))
    story.append(Spacer(1, 4))

    # By-type summary
    summary: Dict[str, Dict[str, int]] = {}
    for r in rows:
        t = r.get("type", "UNKNOWN")
        st = r.get("status", "UNKNOWN")
        summary.setdefault(t, {}).setdefault(st, 0)
        summary[t][st] += 1
    if summary:
        story.append(Paragraph("Summary by Module & Status", s["h"]))
        status_keys = sorted({st for d in summary.values() for st in d.keys()})
        head = ["Module"] + status_keys + ["Total"]
        data: List[List[Any]] = [[Paragraph(f"<b>{h}</b>", s["small"]) for h in head]]
        for t, counts in summary.items():
            label = TYPE_LABEL.get(t, t)
            total = sum(counts.values())
            row = [Paragraph(label, s["small"])]
            for st in status_keys:
                row.append(Paragraph(str(counts.get(st, 0)), s["small"]))
            row.append(Paragraph(f"<b>{total}</b>", s["small"]))
            data.append(row)
        col = 30 * mm
        tbl = Table(data, colWidths=[40 * mm] + [25 * mm] * len(status_keys) + [20 * mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 6))

    # Records table
    story.append(Paragraph("Records", s["h"]))
    if not rows:
        story.append(Paragraph("<i>No records.</i>", s["small"]))
    else:
        head = ["Record No.", "Type", "Title", "Dept", "Severity", "Status", "Initiator", "Created", "Due", "Closed"]
        data = [[Paragraph(f"<b>{h}</b>", s["small"]) for h in head]]
        for r in rows:
            data.append([
                Paragraph(_fmt_value(r.get("record_number")), s["small"]),
                Paragraph(TYPE_LABEL.get(r.get("type", ""), r.get("type", "")), s["small"]),
                Paragraph(_fmt_value((r.get("title") or "")[:80]), s["small"]),
                Paragraph(_fmt_value(r.get("department")), s["small"]),
                Paragraph(_fmt_value(r.get("severity")), s["small"]),
                Paragraph(_fmt_value(r.get("status")), s["small"]),
                Paragraph(_fmt_value(r.get("initiator_name")), s["small"]),
                Paragraph(_fmt_dt(r.get("created_at"))[:11], s["small"]),
                Paragraph(_fmt_dt(r.get("due_date"))[:11], s["small"]),
                Paragraph(_fmt_dt(r.get("closed_at"))[:11], s["small"]),
            ])
        tbl = Table(data, colWidths=[24 * mm, 22 * mm, 38 * mm, 20 * mm, 16 * mm, 18 * mm, 22 * mm, 17 * mm, 16 * mm, 16 * mm], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        story.append(tbl)

    # Optional per-record workflow appendix
    if include_workflows and rows:
        story.append(PageBreak())
        story.append(Paragraph("Per-Record Workflow Appendix", s["h"]))
        for r in rows:
            wf = workflows_by_id.get(r.get("id"), [])
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"<b>{_fmt_value(r.get('record_number'))}</b> · {TYPE_LABEL.get(r.get('type',''), r.get('type',''))} · {_fmt_value(r.get('title'))} · status <b>{_fmt_value(r.get('status'))}</b>",
                s["sub"],
            ))
            if not wf:
                story.append(Paragraph("<i>No workflow events.</i>", s["small"]))
                continue
            head = ["When (UTC)", "Actor", "Action", "Status", "Reason"]
            data = [[Paragraph(f"<b>{h}</b>", s["small"]) for h in head]]
            for w in wf:
                data.append([
                    Paragraph(_fmt_dt(w.get("timestamp")), s["small"]),
                    Paragraph(_fmt_value(w.get("actor_name") or w.get("actor_email")), s["small"]),
                    Paragraph(_fmt_value(w.get("action")), s["small"]),
                    Paragraph(f"{w.get('from_status','')} → {w.get('to_status','')}", s["small"]),
                    Paragraph(_fmt_value((w.get("reason") or "")[:90]), s["small"]),
                ])
            tbl = Table(data, colWidths=[26 * mm, 36 * mm, 28 * mm, 30 * mm, 66 * mm])
            tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("BOX", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.15, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            story.append(tbl)

    footer = _make_footer(
        printed_by_name=printed_by.get("name") or "—",
        printed_by_email=printed_by.get("email") or "",
        header_title="izQMS · Quality Management Report",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer, canvasmaker=_NumberedCanvas)
    return buf.getvalue()
