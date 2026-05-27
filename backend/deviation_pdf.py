"""
izQMS — Deviation PDF generator
Renders the exact 9-Part form layout from the controlled template.

Structure (per template):
  Part 1: Initial Information
  Part 2: Classification and Impact
  Part 3: Regulatory / Sponsor Notifications and Attachments
  Part 4: Investigation / Root Cause Analysis
  Part 5: Corrective Actions
  Part 6: Preventive Actions
  Part 7: Extension of Deviation Closure
  Part 8: Other Department Comments
  Part 9: QA Review and Closure
"""

from io import BytesIO
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether,
)


# ---------- helpers ----------
def _styles():
    base = getSampleStyleSheet()
    s = {
        "title": ParagraphStyle("title", parent=base["Title"], fontSize=14, leading=18,
                                spaceAfter=4, alignment=1, textColor=colors.HexColor("#0f172a")),
        "subtitle": ParagraphStyle("subtitle", parent=base["Normal"], fontSize=8.5, leading=11,
                                   alignment=1, textColor=colors.HexColor("#64748b")),
        "h": ParagraphStyle("h", parent=base["Heading2"], fontSize=11, leading=14,
                            textColor=colors.white, backColor=colors.HexColor("#0f172a"),
                            leftIndent=4, rightIndent=4, spaceBefore=8, spaceAfter=4,
                            borderPadding=4),
        "label": ParagraphStyle("label", parent=base["Normal"], fontSize=8.5, leading=11,
                                textColor=colors.HexColor("#475569")),
        "val": ParagraphStyle("val", parent=base["Normal"], fontSize=9, leading=12,
                              textColor=colors.HexColor("#0f172a")),
        "small": ParagraphStyle("small", parent=base["Normal"], fontSize=7.5, leading=10,
                                textColor=colors.HexColor("#64748b")),
        "sig": ParagraphStyle("sig", parent=base["Normal"], fontSize=8, leading=11,
                              textColor=colors.HexColor("#0f172a")),
    }
    return s


def _checkbox_line(label: str, checked: bool) -> str:
    mark = "[X]" if checked else "[ ]"
    return f"<font face='Courier' size='9'>{mark}</font> {label}"


def _bool_set(value: Any, option: str) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, tuple, set)):
        return option in value
    if isinstance(value, str):
        return value.strip().lower() == option.strip().lower()
    if isinstance(value, dict):
        return bool(value.get(option))
    return False


def _txt(s):
    if s is None or s == "":
        return "<font color='#94a3b8'>—</font>"
    return str(s).replace("\n", "<br/>")


def _date_str(s):
    if not s:
        return "—"
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%d-%b-%Y")
    except Exception:
        return str(s)[:10]


def _kv_table(rows: List[List[Any]], col_widths=None) -> Table:
    t = Table(rows, colWidths=col_widths or [40 * mm, 140 * mm], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e2e8f0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _signature_block(label: str, sig: Optional[Dict[str, Any]], styles) -> Table:
    name = (sig or {}).get("user_name") or ""
    email = (sig or {}).get("user_email") or ""
    ts = (sig or {}).get("timestamp")
    meaning = (sig or {}).get("meaning") or label
    when = ""
    if ts:
        try:
            when = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%d-%b-%Y %H:%M UTC")
        except Exception:
            when = str(ts)
    if name:
        sig_html = (
            f"<b>{name}</b><br/>"
            f"<font size='7' color='#64748b'>{email}</font><br/>"
            f"<font size='7' color='#64748b'>{meaning}</font><br/>"
            f"<font size='7' color='#0f172a'>{when}</font>"
        )
    else:
        sig_html = "<font color='#94a3b8'>— not signed —</font>"
    t = Table([[Paragraph(label, styles["label"]), Paragraph(sig_html, styles["sig"])]],
              colWidths=[55 * mm, 125 * mm])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _checkbox_row(opts: List[str], selected) -> Paragraph:
    parts = [_checkbox_line(o, _bool_set(selected, o)) for o in opts]
    return Paragraph(" &nbsp;&nbsp;&nbsp; ".join(parts), ParagraphStyle("cb", fontSize=9, leading=12))


# ---------- main builder ----------
def build_deviation_pdf(record: Dict[str, Any], signatures: List[Dict[str, Any]], audit_trail: List[Dict[str, Any]]) -> bytes:
    d: Dict[str, Any] = record.get("deviation_data") or {}
    p1 = d.get("part1", {})
    p2 = d.get("part2", {})
    p3 = d.get("part3", {})
    p4 = d.get("part4", {})
    p5 = d.get("part5", {})
    p6 = d.get("part6", {})
    p7 = d.get("part7", {})
    p8_list = d.get("part8", [])
    p9 = d.get("part9", {})

    sigs_by_block = {s.get("block"): s for s in (signatures or [])}

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=18 * mm,
        title=f"Deviation Report {record.get('record_number','')}",
    )
    styles = _styles()
    story: List[Any] = []

    # Header
    story.append(Paragraph("DEVIATION REPORT", styles["title"]))
    story.append(Paragraph("izQMS · 21 CFR Part 11 · EU Annex 11 · ALCOA+", styles["subtitle"]))
    story.append(Spacer(1, 4))

    header_table = _kv_table([
        [Paragraph("<b>Deviation No.</b>", styles["label"]), Paragraph(_txt(record.get("record_number")), styles["val"])],
        [Paragraph("<b>Title</b>", styles["label"]), Paragraph(_txt(record.get("title")), styles["val"])],
        [Paragraph("<b>Status</b>", styles["label"]), Paragraph(_txt(record.get("status")), styles["val"])],
        [Paragraph("<b>Initiated</b>", styles["label"]), Paragraph(_date_str(record.get("created_at")), styles["val"])],
    ], col_widths=[40 * mm, 140 * mm])
    story.append(header_table)
    story.append(Spacer(1, 4))
    story.append(_signature_block("Assigned by QA (Sign & Date)", sigs_by_block.get("assigned_by_qa"), styles))
    story.append(Spacer(1, 6))

    # --- Part 1 ---
    story.append(Paragraph("Part 1: Initial Information", styles["h"]))
    rows = [
        [Paragraph("a) Initiating Department", styles["label"]), Paragraph(_txt(p1.get("initiating_department")), styles["val"])],
        [Paragraph("b) Protocol No. / SOP No. / Others", styles["label"]), Paragraph(_txt(p1.get("protocol_or_sop_no")), styles["val"])],
        [Paragraph("c) Affected Protocol / SOP / Other Document Title", styles["label"]), Paragraph(_txt(p1.get("affected_document_title")), styles["val"])],
        [Paragraph("d) Affected Project Details", styles["label"]), Paragraph(_txt(p1.get("affected_project_details")), styles["val"])],
        [Paragraph("e) Source(s) of identification", styles["label"]),
         _checkbox_row(["Self", "QA observation", "Internal Audit Observation", "Regulatory observation", "Sponsor observation", "Other"], p1.get("identification_sources", []))],
    ]
    if _bool_set(p1.get("identification_sources", []), "Other"):
        rows.append([Paragraph("&nbsp;&nbsp;Other (specify)", styles["label"]), Paragraph(_txt(p1.get("identification_other")), styles["val"])])
    rows += [
        [Paragraph("f) Type of deviation", styles["label"]),
         _checkbox_row(["Planned Deviation", "Unplanned Deviation"], p1.get("deviation_type"))],
        [Paragraph("g) Description in Protocol/SOP/Defined requirement", styles["label"]), Paragraph(_txt(p1.get("defined_requirement")), styles["val"])],
        [Paragraph("h) Deviation description", styles["label"]), Paragraph(_txt(p1.get("deviation_description")), styles["val"])],
        [Paragraph("i) Date of Deviation Occurrence", styles["label"]),
         Paragraph(("Unknown" if p1.get("occurrence_unknown") else _date_str(p1.get("occurrence_date"))), styles["val"])],
        [Paragraph("j) Date of Deviation Identification", styles["label"]), Paragraph(_date_str(p1.get("identification_date")), styles["val"])],
        [Paragraph("&nbsp;&nbsp;Deviation Initiation Date", styles["label"]), Paragraph(_date_str(p1.get("initiation_date")), styles["val"])],
        [Paragraph("k) Deviation Target Closure Date", styles["label"]), Paragraph(_date_str(p1.get("target_closure_date")), styles["val"])],
    ]
    story.append(_kv_table(rows, col_widths=[70 * mm, 110 * mm]))
    story.append(Spacer(1, 4))
    story.append(_signature_block("Initiated By (Sign & Date)", sigs_by_block.get("part1_initiated_by"), styles))
    story.append(_signature_block("Reviewed By (Sign & Date)", sigs_by_block.get("part1_reviewed_by"), styles))

    # --- Part 2 ---
    story.append(Paragraph("Part 2: Classification and Impact", styles["h"]))
    rows = [
        [Paragraph("a) Classification", styles["label"]),
         _checkbox_row(["Critical", "Major", "Minor"], p2.get("classification"))],
        [Paragraph("b.i) Risk to drug quality?", styles["label"]),
         _checkbox_row(["Yes", "No", "Not applicable"], p2.get("risk_drug_quality"))],
        [Paragraph("b.ii) Risk to project data?", styles["label"]),
         _checkbox_row(["Yes", "No", "Not applicable"], p2.get("risk_project_data"))],
        [Paragraph("b.iii) Risk to system?", styles["label"]),
         _checkbox_row(["Yes", "No", "Not applicable"], p2.get("risk_system"))],
        [Paragraph("c) Other Comments", styles["label"]), Paragraph(_txt(p2.get("other_comments")), styles["val"])],
    ]
    story.append(_kv_table(rows, col_widths=[55 * mm, 125 * mm]))

    # --- Part 3 ---
    story.append(Paragraph("Part 3: Regulatory / Sponsor Notifications and Attachments", styles["h"]))
    rows = [
        [Paragraph("a) Regulatory agency notification / approval required?", styles["label"]),
         _checkbox_row(["Yes", "No", "Not applicable"], p3.get("regulatory_notification"))],
        [Paragraph("b) Notification to sponsor required?", styles["label"]),
         _checkbox_row(["Yes", "No", "Not applicable"], p3.get("sponsor_notification"))],
        [Paragraph("c) Notification to other departments required?", styles["label"]),
         _checkbox_row(["Yes", "No", "Not applicable"], p3.get("other_dept_notification"))],
    ]
    if _bool_set(p3.get("other_dept_notification"), "Yes"):
        rows.append([Paragraph("&nbsp;&nbsp;Departments", styles["label"]), Paragraph(_txt(p3.get("other_dept_names")), styles["val"])])
    rows.append([Paragraph("d) List of attachments", styles["label"]), Paragraph(_txt(p3.get("attachments_list")), styles["val"])])
    story.append(_kv_table(rows, col_widths=[70 * mm, 110 * mm]))
    story.append(Spacer(1, 4))
    story.append(_signature_block("Recorded By (Sign & Date)", sigs_by_block.get("part3_recorded_by"), styles))
    story.append(_signature_block("Reviewed By (Sign & Date)", sigs_by_block.get("part3_reviewed_by"), styles))

    # --- Part 4 ---
    story.append(Paragraph("Part 4: Investigation / Root Cause Analysis", styles["h"]))
    rows = [
        [Paragraph("a) Investigation Description", styles["label"]), Paragraph(_txt(p4.get("investigation_description")), styles["val"])],
        [Paragraph("b) Root cause", styles["label"]),
         _checkbox_row(["Assignable", "Non-assignable"], p4.get("root_cause_type"))],
        [Paragraph("c) If assignable, root cause (6M)", styles["label"]),
         _checkbox_row(["Method", "Manpower", "Machine", "Material", "Measurement", "Mother Nature", "Other"], p4.get("root_cause_6m", []))],
    ]
    if _bool_set(p4.get("root_cause_6m", []), "Other"):
        rows.append([Paragraph("&nbsp;&nbsp;Other (specify)", styles["label"]), Paragraph(_txt(p4.get("root_cause_other")), styles["val"])])
    story.append(_kv_table(rows, col_widths=[70 * mm, 110 * mm]))

    # --- Part 5 ---
    story.append(Paragraph("Part 5: Corrective Actions", styles["h"]))
    rows = [
        [Paragraph("a) Corrective actions (multiple)", styles["label"]),
         _checkbox_row(["Data exclusion", "Documentation/correction", "Procedure revision/amendment",
                        "Project/Study termination", "Reperforming affected activities", "Other"],
                       p5.get("corrective_actions", []))],
    ]
    if _bool_set(p5.get("corrective_actions", []), "Other"):
        rows.append([Paragraph("&nbsp;&nbsp;Other (specify)", styles["label"]), Paragraph(_txt(p5.get("corrective_other")), styles["val"])])
    rows.append([Paragraph("b) Description", styles["label"]), Paragraph(_txt(p5.get("corrective_description")), styles["val"])])
    story.append(_kv_table(rows, col_widths=[60 * mm, 120 * mm]))

    # --- Part 6 ---
    story.append(Paragraph("Part 6: Preventive Actions", styles["h"]))
    rows = [
        [Paragraph("a) Preventive actions (multiple)", styles["label"]),
         _checkbox_row(["Training", "Change in systems", "Change in procedures", "Software upgrade/change",
                        "Enhanced oversight", "Further calibration/validation", "Other"],
                       p6.get("preventive_actions", []))],
    ]
    if _bool_set(p6.get("preventive_actions", []), "Other"):
        rows.append([Paragraph("&nbsp;&nbsp;Other (specify)", styles["label"]), Paragraph(_txt(p6.get("preventive_other")), styles["val"])])
    rows.append([Paragraph("b) Description", styles["label"]), Paragraph(_txt(p6.get("preventive_description")), styles["val"])])
    story.append(_kv_table(rows, col_widths=[60 * mm, 120 * mm]))
    story.append(Spacer(1, 4))
    story.append(_signature_block("Recorded By (Sign & Date)", sigs_by_block.get("part6_recorded_by"), styles))
    story.append(_signature_block("Reviewed By (Sign & Date)", sigs_by_block.get("part6_reviewed_by"), styles))

    # --- Part 7 (extensions: list) ---
    story.append(Paragraph("Part 7: Extension of Deviation Closure", styles["h"]))
    extensions = p7.get("extensions", []) if isinstance(p7, dict) else (p7 or [])
    if not extensions:
        story.append(Paragraph("<font color='#94a3b8'>No extension requested.</font>", styles["small"]))
    else:
        for idx, ext in enumerate(extensions, start=1):
            rows = [
                [Paragraph(f"Extension #{idx}", styles["label"]), ""],
                [Paragraph("a) Revised Target Completion Date", styles["label"]), Paragraph(_date_str(ext.get("revised_target_date")), styles["val"])],
                [Paragraph("b) Reason / Justification", styles["label"]), Paragraph(_txt(ext.get("justification")), styles["val"])],
            ]
            story.append(_kv_table(rows, col_widths=[60 * mm, 120 * mm]))
            story.append(Spacer(1, 3))
            story.append(_signature_block(f"Requested By (Ext #{idx})", sigs_by_block.get(f"part7_requested_{idx}"), styles))
            story.append(_signature_block(f"HOD/Designee (Ext #{idx})", sigs_by_block.get(f"part7_hod_{idx}"), styles))
            story.append(_signature_block(f"QA Head/Designee (Ext #{idx})", sigs_by_block.get(f"part7_qa_{idx}"), styles))
            story.append(Spacer(1, 4))

    # --- Part 8 ---
    story.append(Paragraph("Part 8: Other Department Comments", styles["h"]))
    if not p8_list:
        story.append(Paragraph("<font color='#94a3b8'>No department comments captured.</font>", styles["small"]))
    else:
        for idx, c in enumerate(p8_list, start=1):
            story.append(_kv_table([
                [Paragraph(f"Department #{idx}", styles["label"]), Paragraph(_txt(c.get("department")), styles["val"])],
                [Paragraph("Comments / Remarks", styles["label"]), Paragraph(_txt(c.get("comments")), styles["val"])],
            ], col_widths=[60 * mm, 120 * mm]))
            story.append(_signature_block(f"Signature & Date (Dept #{idx})", sigs_by_block.get(f"part8_dept_{idx}"), styles))
            story.append(Spacer(1, 3))
    story.append(Paragraph("<i>Note: Communication of review / comments can be received by an email. In such cases, append mail communication with the form.</i>", styles["small"]))

    # --- Part 9 ---
    story.append(Paragraph("Part 9: QA Review and Closure", styles["h"]))
    rows = [
        [Paragraph("a) Details completed are acceptable?", styles["label"]),
         _checkbox_row(["Yes", "No"], p9.get("acceptable"))],
    ]
    if _bool_set(p9.get("acceptable"), "No"):
        rows.append([Paragraph("&nbsp;&nbsp;Reason / Comments", styles["label"]), Paragraph(_txt(p9.get("unacceptable_reason")), styles["val"])])
    rows += [
        [Paragraph("b) Communicated to Management", styles["label"]),
         _checkbox_row(["Yes", "No", "Not applicable"], p9.get("management_communicated"))],
        [Paragraph("c) CAPA closed?", styles["label"]),
         _checkbox_row(["Yes", "No", "Not applicable"], p9.get("capa_closed"))],
        [Paragraph("d) Other comments", styles["label"]), Paragraph(_txt(p9.get("other_comments")), styles["val"])],
        [Paragraph("f) Deviation Closure Comments", styles["label"]), Paragraph(_txt(p9.get("closure_comments")), styles["val"])],
        [Paragraph("g) Deviation Closure Date", styles["label"]), Paragraph(_date_str(p9.get("closure_date")), styles["val"])],
        [Paragraph("h) CAPA Effectiveness Verification Required", styles["label"]),
         _checkbox_row(["Yes", "No"], p9.get("effectiveness_verification"))],
    ]
    story.append(_kv_table(rows, col_widths=[70 * mm, 110 * mm]))
    story.append(Spacer(1, 4))
    story.append(_signature_block("e) QA Reviewed By (Sign & Date)", sigs_by_block.get("part9_qa_reviewed_by"), styles))
    story.append(_signature_block("i) QA Head / Designee (Sign & Date)", sigs_by_block.get("part9_qa_head_closure"), styles))

    # Audit trail summary
    story.append(Paragraph("Audit Trail (excerpt)", styles["h"]))
    if not audit_trail:
        story.append(Paragraph("<font color='#94a3b8'>No audit entries.</font>", styles["small"]))
    else:
        head = ["When", "User", "Action", "Reason"]
        data = [[Paragraph(f"<b>{h}</b>", styles["small"]) for h in head]]
        for a in audit_trail[:40]:
            when = a.get("timestamp", "")
            try:
                when = datetime.fromisoformat(when.replace("Z", "+00:00")).strftime("%d-%b %H:%M")
            except Exception:
                pass
            data.append([
                Paragraph(when, styles["small"]),
                Paragraph(a.get("user_email", "") or "", styles["small"]),
                Paragraph(a.get("action", "") or "", styles["small"]),
                Paragraph((a.get("reason") or "")[:80], styles["small"]),
            ])
        t = Table(data, colWidths=[28 * mm, 50 * mm, 40 * mm, 62 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#e2e8f0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t)

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.drawString(15 * mm, 10 * mm,
                          f"izQMS Deviation Report · {record.get('record_number','')} · Generated {datetime.utcnow().strftime('%d-%b-%Y %H:%M UTC')}")
        canvas.drawRightString(195 * mm, 10 * mm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
