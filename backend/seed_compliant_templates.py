"""
Ready-made compliant Module Templates seeded from the QA005F0x QMS forms.

Templates are seeded as DRAFT, GLOBAL, and IDEMPOTENT — they will only be
inserted if their `code` does not already exist.  Once seeded, every field
remains fully editable in the Module Framework UI until the admin chooses to
PUBLISH the template (after which the version becomes immutable as per
21 CFR Part 11 record-locking requirements).

Source documents (uploaded by the customer):
  - QA005F02-00 Deviation Form.pdf       → code: qa005f02_deviation
  - QA005F06-00 CAPA Form.pdf            → code: qa005f06_capa
  - QA004F02-00 Change Control Form.pdf  → code: qa004f02_change_control
  - QA005F04-00 Incident Form.pdf        → code: qa005f04_incident
  - QA005F08-00 Event Log.pdf            → code: qa005f08_event_log
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


# Reusable colour palette per workflow stage type
COLOR_INIT = "#94A3B8"
COLOR_REVIEW = "#2563EB"
COLOR_QA = "#0EA5E9"
COLOR_APPROVE = "#D97706"
COLOR_IMPL = "#7C3AED"
COLOR_CLOSE = "#059669"
COLOR_EXT = "#EAB308"
COLOR_REJECT = "#DC2626"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# A. DEVIATION (QA005F02-00)
# ---------------------------------------------------------------------------
DEVIATION_TEMPLATE = {
    "code": "qa005f02_deviation",
    "name": "Deviation (QA005F02-00)",
    "description": "Ready-made compliant Deviation template based on QA005F02-00. Initiation → Review → Investigation/RCA → Corrective → Preventive → QA Review → Closure with extension handling.",
    "category": "DEVIATION",
    "notes": "Numbering: DEV/YYYY/NNNN",
    "workflow": {
        "initial_stage": "INITIATION",
        "stages": [
            {"key": "INITIATION", "label": "Initiation", "color": COLOR_INIT},
            {"key": "REVIEW", "label": "Review", "color": COLOR_REVIEW},
            {"key": "INVESTIGATION", "label": "Investigation / RCA", "color": COLOR_REVIEW},
            {"key": "CORRECTIVE", "label": "Corrective Actions", "color": COLOR_APPROVE},
            {"key": "PREVENTIVE", "label": "Preventive Actions", "color": COLOR_APPROVE},
            {"key": "EXTENSION", "label": "Extension of Closure", "color": COLOR_EXT},
            {"key": "QA_REVIEW", "label": "QA Review & Closure", "color": COLOR_QA},
            {"key": "CLOSED", "label": "Closed", "color": COLOR_CLOSE},
            {"key": "REJECTED", "label": "Rejected", "color": COLOR_REJECT},
        ],
        "transitions": [
            {"key": "SUBMIT_REVIEW", "from": "INITIATION", "to": "REVIEW", "label": "Submit for Review", "required_perm": None, "esignature": True},
            {"key": "APPROVE_INVESTIGATION", "from": "REVIEW", "to": "INVESTIGATION", "label": "Approve for Investigation", "required_perm": "review_record", "esignature": True},
            {"key": "REJECT_REVIEW", "from": "REVIEW", "to": "REJECTED", "label": "Reject", "required_perm": "reject_record", "esignature": True},
            {"key": "GO_CORRECTIVE", "from": "INVESTIGATION", "to": "CORRECTIVE", "label": "Document Corrective Actions", "required_perm": "review_record", "esignature": True},
            {"key": "GO_PREVENTIVE", "from": "CORRECTIVE", "to": "PREVENTIVE", "label": "Document Preventive Actions", "required_perm": "review_record", "esignature": True},
            {"key": "SUBMIT_QA", "from": "PREVENTIVE", "to": "QA_REVIEW", "label": "Submit for QA Review", "required_perm": None, "esignature": True},
            {"key": "REQUEST_EXTENSION", "from": "QA_REVIEW", "to": "EXTENSION", "label": "Request Extension", "required_perm": None, "esignature": True},
            {"key": "RETURN_FROM_EXTENSION", "from": "EXTENSION", "to": "QA_REVIEW", "label": "Resubmit for QA Review", "required_perm": "approve_record", "esignature": True},
            {"key": "APPROVE_CLOSURE", "from": "QA_REVIEW", "to": "CLOSED", "label": "Approve Closure", "required_perm": "approve_record", "esignature": True},
            {"key": "REJECT_QA", "from": "QA_REVIEW", "to": "REJECTED", "label": "Reject", "required_perm": "reject_record", "esignature": True},
            {"key": "REOPEN", "from": "REJECTED", "to": "INITIATION", "label": "Reopen / Correct", "required_perm": None, "esignature": True},
        ],
    },
    "form": {"sections": [
        {"key": "deviation_assignment", "label": "Deviation No. & Assignment", "fields": [
            {"key": "deviation_no", "label": "Deviation No.", "type": "text", "required": False},
            {"key": "assigned_by_qa", "label": "Assigned by QA (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "part_1_initial_information", "label": "Part 1: Initial Information", "fields": [
            {"key": "initiating_department", "label": "a) Initiating Department", "type": "department", "required": True},
            {"key": "protocol_sop_others", "label": "b) Protocol No. / SOP No. / Others", "type": "text", "required": False},
            {"key": "affected_document_title", "label": "c) Affected Protocol/SOP / Other Document Title", "type": "text", "required": True},
            {"key": "affected_project_details", "label": "d) Affected Project Details", "type": "textarea", "required": False},
            {"key": "source_of_identification", "label": "e) Source(s) of identification of deviation", "type": "multiselect", "required": True,
             "options": ["Self", "QA observation", "Internal Audit Observation", "Sponsor observation", "Regulatory observation", "Other (specify)"]},
            {"key": "type_of_deviation", "label": "f) Type of deviation", "type": "radio", "required": True,
             "options": ["Planned Deviation", "Unplanned Deviation"]},
            {"key": "description_in_protocol_sop", "label": "g) Description mentioned in Protocol / SOP / document / defined requirement", "type": "textarea", "required": False},
            {"key": "deviation_description", "label": "h) Deviation description", "type": "textarea", "required": True},
            {"key": "date_of_deviation_occurrence", "label": "i) Date of Deviation Occurrence", "type": "date", "required": True},
            {"key": "deviation_unknown_date", "label": "Unknown (occurrence date)", "type": "checkbox", "required": False},
            {"key": "date_of_deviation_identification", "label": "j) Date of Deviation Identification", "type": "date", "required": True},
            {"key": "deviation_initiation_date", "label": "Deviation Initiation Date", "type": "date", "required": False},
            {"key": "deviation_target_closure_date", "label": "k) Deviation Target Closure Date", "type": "date", "required": True},
            {"key": "initiated_by_signature", "label": "Initiated By (Sign & Date)", "type": "signature", "required": True},
            {"key": "reviewed_by_signature", "label": "Reviewed By (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "part_2_classification_impact", "label": "Part 2: Classification and Impact", "fields": [
            {"key": "classification", "label": "a) Classification", "type": "radio", "required": True,
             "options": ["Critical", "Major", "Minor"]},
            {"key": "impact_drug_quality", "label": "b-i) Risk to drug quality?", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "impact_project_data", "label": "b-ii) Risk to project data?", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "impact_system", "label": "b-iii) Risk to system?", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "other_comments_impact", "label": "c) Other Comments", "type": "textarea", "required": False},
        ]},
        {"key": "part_3_regulatory_attachments", "label": "Part 3: Regulatory / Sponsor Notifications and Attachments", "fields": [
            {"key": "regulatory_notification_required", "label": "a) Regulatory agency notification / approval required?", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "sponsor_notification_required", "label": "b) Notification to sponsor required?", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "other_dept_notification_required", "label": "c) Notification to other departments required?", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "other_departments_names", "label": "If yes, mention name of departments", "type": "text", "required": False},
            {"key": "list_of_attachments_part3", "label": "d) List of attachments", "type": "attachment", "required": False},
            {"key": "recorded_by_part3", "label": "Recorded By (Sign & Date)", "type": "signature", "required": False},
            {"key": "reviewed_by_part3", "label": "Reviewed By (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "part_4_investigation_rca", "label": "Part 4: Investigation / Root Cause Analysis", "fields": [
            {"key": "investigation_description", "label": "a) Investigation Description", "type": "textarea", "required": True},
            {"key": "root_cause_type", "label": "b) Root cause", "type": "radio", "required": True, "options": ["Assignable", "Non-assignable"]},
            {"key": "assignable_root_cause", "label": "c) If assignable, root cause", "type": "multiselect", "required": False,
             "options": ["Manpower", "Machine", "Material", "Measurement", "Method", "Mother Nature (environment)", "Other (specify)"]},
            {"key": "assignable_root_cause_other", "label": "Other root cause (specify)", "type": "text", "required": False},
        ]},
        {"key": "part_5_corrective_actions", "label": "Part 5: Corrective Actions", "fields": [
            {"key": "corrective_actions_options", "label": "a) Corrective actions (multiple options possible)", "type": "multiselect", "required": True,
             "options": ["Data exclusion", "Documentation / correction", "Procedure revision / amendment", "Project / Study termination", "Reperforming affected activities", "Other"]},
            {"key": "corrective_actions_description", "label": "b) Description", "type": "textarea", "required": True},
        ]},
        {"key": "part_6_preventive_actions", "label": "Part 6: Preventive Actions", "fields": [
            {"key": "preventive_actions_options", "label": "a) Preventive actions (multiple options possible)", "type": "multiselect", "required": True,
             "options": ["Training", "Change in systems", "Change in procedures", "Software upgrade / change", "Enhanced oversight", "Further calibration / validation", "Other"]},
            {"key": "preventive_actions_description", "label": "b) Description", "type": "textarea", "required": True},
            {"key": "recorded_by_part6", "label": "Recorded By (Sign & Date)", "type": "signature", "required": False},
            {"key": "reviewed_by_part6", "label": "Reviewed By (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "part_7_extension_closure", "label": "Part 7: Extension of Deviation Closure", "fields": [
            {"key": "revised_target_completion_date", "label": "a) Revised Target Completion Date", "type": "date", "required": True},
            {"key": "reason_justification_extension", "label": "b) Reason / Justification", "type": "textarea", "required": True},
            {"key": "requested_by_extension", "label": "Requested By (Sign & Date)", "type": "signature", "required": False},
            {"key": "hod_designee_extension", "label": "HOD/Designee (Sign & Date)", "type": "signature", "required": False},
            {"key": "qa_head_extension", "label": "QA Head/Designee (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "part_8_other_dept_comments", "label": "Part 8: Other department comments", "fields": [
            {"key": "other_dept_comments", "label": "Comments / Remarks", "type": "textarea", "required": False},
            {"key": "other_dept_signature", "label": "Signature & Date", "type": "signature", "required": False},
        ]},
        {"key": "part_9_qa_review_closure", "label": "Part 9: QA Review and Closure", "fields": [
            {"key": "details_acceptable", "label": "a) Details completed are acceptable?", "type": "radio", "required": True, "options": ["Yes", "No"]},
            {"key": "reason_if_no", "label": "If No, mention reason / comments", "type": "textarea", "required": False},
            {"key": "communicated_to_management", "label": "b) Communicated to Management / Management Representative", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "capa_closed", "label": "c) CAPA closed?", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "other_comments_qa_review", "label": "d) Other comments", "type": "textarea", "required": False},
            {"key": "qa_reviewed_signature", "label": "e) QA Reviewed by (Sign & Date)", "type": "signature", "required": True},
            {"key": "deviation_closure_comments", "label": "f) Deviation Closure Comments", "type": "textarea", "required": False},
            {"key": "deviation_closure_date", "label": "g) Deviation Closure Date", "type": "date", "required": True},
            {"key": "capa_effectiveness_required", "label": "h) CAPA Implementation Effectiveness Verification Requirement", "type": "radio", "required": False, "options": ["Yes", "No"]},
            {"key": "qa_head_designee_closure", "label": "i) QA Head / Designee (Sign & Date)", "type": "signature", "required": True},
        ]},
    ]},
    "pdf_template": {
        "header": {"title": "QA005F02-00 — Deviation Report", "show_logo": True, "show_record_number": True, "numbering_format": "DEV/YYYY/NNNN"},
        "sections": [
            {"key": "deviation_assignment", "label": "Deviation No. & Assignment", "show_section": "deviation_assignment"},
            {"key": "part_1", "label": "Part 1: Initial Information", "show_section": "part_1_initial_information"},
            {"key": "part_2", "label": "Part 2: Classification and Impact", "show_section": "part_2_classification_impact"},
            {"key": "part_3", "label": "Part 3: Regulatory / Sponsor Notifications and Attachments", "show_section": "part_3_regulatory_attachments"},
            {"key": "part_4", "label": "Part 4: Investigation / Root Cause Analysis", "show_section": "part_4_investigation_rca"},
            {"key": "part_5", "label": "Part 5: Corrective Actions", "show_section": "part_5_corrective_actions"},
            {"key": "part_6", "label": "Part 6: Preventive Actions", "show_section": "part_6_preventive_actions"},
            {"key": "part_7", "label": "Part 7: Extension of Deviation Closure", "show_section": "part_7_extension_closure"},
            {"key": "part_8", "label": "Part 8: Other department comments", "show_section": "part_8_other_dept_comments"},
            {"key": "part_9", "label": "Part 9: QA Review and Closure", "show_section": "part_9_qa_review_closure"},
            {"key": "workflow_history", "label": "Workflow Timeline", "show_history": True},
            {"key": "signatures", "label": "Electronic Signatures", "show_signatures": True},
            {"key": "audit", "label": "Audit Trail", "show_audit": True},
        ],
        "footer": {"text": "QA005F02-00 · 21 CFR Part 11 · EU Annex 11 · ALCOA++"},
    },
    "approvals": [
        {"level": 1, "stage": "REVIEW", "role": "qa_reviewer", "label": "Reviewer"},
        {"level": 2, "stage": "QA_REVIEW", "role": "qa_manager", "label": "QA Head / Designee"},
    ],
    "role_mapping": {
        "INITIATION": ["employee_operator", "department_manager"],
        "REVIEW": ["qa_reviewer", "department_manager"],
        "INVESTIGATION": ["qa_reviewer", "department_manager"],
        "CORRECTIVE": ["department_manager", "qa_reviewer"],
        "PREVENTIVE": ["department_manager", "qa_reviewer"],
        "QA_REVIEW": ["qa_manager"],
        "EXTENSION": ["qa_manager"],
        "CLOSED": ["qa_manager"],
        "REJECTED": ["qa_reviewer", "qa_manager"],
    },
}


# ---------------------------------------------------------------------------
# B. CAPA (QA005F06-00)
# ---------------------------------------------------------------------------
CAPA_TEMPLATE = {
    "code": "qa005f06_capa",
    "name": "CAPA (QA005F06-00)",
    "description": "Ready-made compliant CAPA template based on QA005F06-00. Initiation → Review → QA Review → Approval → Closure with extension, rejection and effectiveness check.",
    "category": "CAPA",
    "notes": "Numbering: CAPA/YYYY/NNNN",
    "workflow": {
        "initial_stage": "INITIATION",
        "stages": [
            {"key": "INITIATION", "label": "Initiation", "color": COLOR_INIT},
            {"key": "REVIEW", "label": "Review", "color": COLOR_REVIEW},
            {"key": "QA_REVIEW", "label": "QA Review", "color": COLOR_QA},
            {"key": "APPROVAL", "label": "Approval", "color": COLOR_APPROVE},
            {"key": "EXTENSION", "label": "Extension", "color": COLOR_EXT},
            {"key": "CLOSED", "label": "Closure", "color": COLOR_CLOSE},
            {"key": "EFFECTIVENESS_CHECK", "label": "Effectiveness Check", "color": COLOR_IMPL},
            {"key": "REJECTED", "label": "Rejected", "color": COLOR_REJECT},
        ],
        "transitions": [
            {"key": "SUBMIT_REVIEW", "from": "INITIATION", "to": "REVIEW", "label": "Submit for Review", "required_perm": None, "esignature": True},
            {"key": "REQUEST_CHANGES", "from": "REVIEW", "to": "INITIATION", "label": "Request Changes", "required_perm": "review_record", "esignature": True},
            {"key": "SUBMIT_QA", "from": "REVIEW", "to": "QA_REVIEW", "label": "Submit for QA Review", "required_perm": "review_record", "esignature": True},
            {"key": "QA_REQUEST_CHANGES", "from": "QA_REVIEW", "to": "REVIEW", "label": "Request Changes", "required_perm": "review_record", "esignature": True},
            {"key": "SUBMIT_APPROVAL", "from": "QA_REVIEW", "to": "APPROVAL", "label": "Submit for Approval", "required_perm": "review_record", "esignature": True},
            {"key": "REQUEST_EXTENSION", "from": "APPROVAL", "to": "EXTENSION", "label": "Request Extension", "required_perm": None, "esignature": True},
            {"key": "REJECT", "from": "APPROVAL", "to": "REJECTED", "label": "Reject CAPA", "required_perm": "reject_record", "esignature": True},
            {"key": "APPROVE", "from": "APPROVAL", "to": "CLOSED", "label": "Approve CAPA", "required_perm": "approve_record", "esignature": True},
            {"key": "APPROVE_EXTENSION", "from": "EXTENSION", "to": "APPROVAL", "label": "Approve Extension", "required_perm": "approve_record", "esignature": True},
            {"key": "REJECT_EXTENSION", "from": "EXTENSION", "to": "REJECTED", "label": "Reject Extension", "required_perm": "reject_record", "esignature": True},
            {"key": "GO_EFFECTIVENESS", "from": "CLOSED", "to": "EFFECTIVENESS_CHECK", "label": "Effectiveness Verification", "required_perm": "approve_record", "esignature": True},
            {"key": "REOPEN_CLOSURE", "from": "CLOSED", "to": "INITIATION", "label": "Reopen CAPA", "required_perm": "approve_record", "esignature": True},
            {"key": "EFFECTIVENESS_PASS", "from": "EFFECTIVENESS_CHECK", "to": "CLOSED", "label": "Effectiveness Pass", "required_perm": "approve_record", "esignature": True},
            {"key": "EFFECTIVENESS_FAIL", "from": "EFFECTIVENESS_CHECK", "to": "INITIATION", "label": "Effectiveness Fail — Reopen", "required_perm": "approve_record", "esignature": True},
        ],
    },
    "form": {"sections": [
        {"key": "part1_initial_information", "label": "Part 1: Initial Information", "fields": [
            {"key": "capa_no", "label": "CAPA No.", "type": "text", "required": False},
            {"key": "assigned_by_qa", "label": "Assigned by QA (Sign & Date)", "type": "signature", "required": False},
            {"key": "initiating_department", "label": "Initiating Department", "type": "department", "required": True},
            {"key": "affected_systems", "label": "Affected Systems", "type": "multiselect", "required": False,
             "options": ["Document", "Facility", "Process", "Equipment", "Projects", "Software", "Validated Excel Spreadsheet", "Non-Listed Categories"]},
            {"key": "affected_systems_reference", "label": "Affected Systems Reference No. / Title / other details", "type": "textarea", "required": False},
            {"key": "affected_project_details", "label": "Affected Project Details", "type": "textarea", "required": False},
            {"key": "source_of_identification", "label": "Source(s) of identification of CAPA", "type": "multiselect", "required": True,
             "options": ["Self/Internal", "Customer Complaints", "External Audit Observations", "Internal Audit Observations", "Other (specify)"]},
            {"key": "description_non_conformance", "label": "Description Non-Conformance / Problem", "type": "textarea", "required": True},
            {"key": "date_of_capa_initiation", "label": "Date of CAPA Initiation", "type": "date", "required": True},
            {"key": "capa_target_closure_date", "label": "CAPA Target Closure Date", "type": "date", "required": True},
            {"key": "list_of_attachments", "label": "List of Attachments", "type": "attachment", "required": False},
            {"key": "initiated_by", "label": "Initiated By (Sign & Date)", "type": "signature", "required": True},
            {"key": "reviewed_by", "label": "Reviewed By (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "part2_investigation_rca", "label": "Part 2: Investigation / Root Cause Analysis", "fields": [
            {"key": "investigation_description", "label": "Investigation Description", "type": "textarea", "required": True},
            {"key": "root_cause_type", "label": "Root cause", "type": "radio", "required": True, "options": ["Assignable", "Non-assignable"]},
            {"key": "assignable_root_cause", "label": "If assignable, root cause", "type": "multiselect", "required": False,
             "options": ["Manpower", "Machine", "Material", "Method", "Measurement", "Mother Nature (environment)", "Other (specify)"]},
        ]},
        {"key": "part3_corrective_actions", "label": "Part 3: Corrective Actions", "fields": [
            {"key": "corrective_actions_options", "label": "Corrective actions (multiple options possible)", "type": "multiselect", "required": True,
             "options": ["Data exclusion", "Documentation / correction", "Procedure revision / amendment", "Reperforming affected activities", "Project / Study termination", "Other"]},
            {"key": "corrective_actions_description", "label": "Description", "type": "textarea", "required": True},
        ]},
        {"key": "part4_preventive_actions", "label": "Part 4: Preventive Actions", "fields": [
            {"key": "preventive_actions_options", "label": "Preventive actions (multiple options possible)", "type": "multiselect", "required": True,
             "options": ["Training", "Change in systems", "Software upgrade / change", "Change in procedures", "Enhanced oversight", "Further calibration / validation", "Other"]},
            {"key": "preventive_actions_description", "label": "Description", "type": "textarea", "required": True},
            {"key": "recorded_by_preventive", "label": "Recorded By (Sign & Date)", "type": "signature", "required": False},
            {"key": "reviewed_by_preventive", "label": "Reviewed By (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "part5_impact_assessment", "label": "Part 5: Impact Assessment", "fields": [
            {"key": "impact_drug_quality", "label": "Risk to drug quality?", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "impact_project_data", "label": "Risk to project data?", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "impact_system", "label": "Risk to system?", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "impact_other_comments", "label": "Other Comments", "type": "textarea", "required": False},
        ]},
        {"key": "part6_extension_closure", "label": "Part 6: Extension of CAPA Closure", "fields": [
            {"key": "revised_target_completion_date", "label": "Revised Target Completion Date", "type": "date", "required": True},
            {"key": "reason_justification_extension", "label": "Reason / Justification", "type": "textarea", "required": True},
            {"key": "requested_by_extension", "label": "Requested By (Sign & Date)", "type": "signature", "required": False},
            {"key": "hod_designee_extension", "label": "HOD/Designee (Sign & Date)", "type": "signature", "required": False},
            {"key": "qa_head_extension", "label": "QA Head/Designee (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "part7_implementation_details", "label": "Part 7: CAPA Implementation Details", "fields": [
            {"key": "implementation_date", "label": "Implementation Date(s)", "type": "date", "required": False},
            {"key": "reference_document_remarks", "label": "Reference Document No. / Remarks", "type": "textarea", "required": False},
            {"key": "recorded_by_implementation", "label": "Recorded By (Sign & Date)", "type": "signature", "required": False},
            {"key": "reviewed_by_implementation", "label": "Reviewed By (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "part8_other_dept_comments", "label": "Part 8: Other department comments", "fields": [
            {"key": "other_dept_comments", "label": "Comments / Remarks", "type": "textarea", "required": False},
            {"key": "other_dept_signature", "label": "Signature & Date", "type": "signature", "required": False},
        ]},
        {"key": "part9_qa_review_closure", "label": "Part 9: QA Review and Closure", "fields": [
            {"key": "details_acceptable", "label": "Details completed are acceptable?", "type": "radio", "required": True, "options": ["Yes", "No"]},
            {"key": "reason_if_no", "label": "If No, mention reason / comments", "type": "textarea", "required": False},
            {"key": "communicated_to_management", "label": "Communicated to Management / Management Representative", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "capa_closed", "label": "CAPA closed?", "type": "radio", "required": True, "options": ["Yes", "No"]},
            {"key": "other_comments_qa_closure", "label": "Other comments", "type": "textarea", "required": False},
            {"key": "qa_reviewed_by", "label": "QA Reviewed by (Sign & Date)", "type": "signature", "required": True},
            {"key": "capa_form_closure_comments", "label": "CAPA Form Closure Comments", "type": "textarea", "required": False},
            {"key": "capa_form_closure_date", "label": "CAPA Form Closure Date", "type": "date", "required": True},
            {"key": "capa_effectiveness_required", "label": "CAPA Implementation Effectiveness Verification Requirement", "type": "radio", "required": False, "options": ["Yes", "No"]},
            {"key": "qa_head_designee_closure", "label": "QA Head / Designee (Sign & Date)", "type": "signature", "required": True},
        ]},
    ]},
    "pdf_template": {
        "header": {"title": "QA005F06-00 — CAPA Form", "show_logo": True, "show_record_number": True, "numbering_format": "CAPA/YYYY/NNNN"},
        "sections": [
            {"key": f"part{i+1}", "label": label, "show_section": skey}
            for i, (skey, label) in enumerate([
                ("part1_initial_information", "Part 1: Initial Information"),
                ("part2_investigation_rca", "Part 2: Investigation / Root Cause Analysis"),
                ("part3_corrective_actions", "Part 3: Corrective Actions"),
                ("part4_preventive_actions", "Part 4: Preventive Actions"),
                ("part5_impact_assessment", "Part 5: Impact Assessment"),
                ("part6_extension_closure", "Part 6: Extension of CAPA Closure"),
                ("part7_implementation_details", "Part 7: CAPA Implementation Details"),
                ("part8_other_dept_comments", "Part 8: Other department comments"),
                ("part9_qa_review_closure", "Part 9: QA Review and Closure"),
            ])
        ] + [
            {"key": "workflow_history", "label": "Workflow Timeline", "show_history": True},
            {"key": "signatures", "label": "Electronic Signatures", "show_signatures": True},
            {"key": "audit", "label": "Audit Trail", "show_audit": True},
        ],
        "footer": {"text": "QA005F06-00 · 21 CFR Part 11 · EU Annex 11 · ALCOA++"},
    },
    "approvals": [
        {"level": 1, "stage": "REVIEW", "role": "qa_reviewer", "label": "Reviewer"},
        {"level": 2, "stage": "QA_REVIEW", "role": "qa_manager", "label": "QA Review"},
        {"level": 3, "stage": "APPROVAL", "role": "qa_manager", "label": "QA Head / Designee"},
    ],
    "role_mapping": {
        "INITIATION": ["employee_operator", "department_manager"],
        "REVIEW": ["qa_reviewer", "department_manager"],
        "QA_REVIEW": ["qa_manager"],
        "APPROVAL": ["qa_manager"],
        "EXTENSION": ["qa_manager"],
        "CLOSED": ["qa_manager"],
        "EFFECTIVENESS_CHECK": ["qa_manager", "qa_reviewer"],
        "REJECTED": ["qa_manager"],
    },
}


# ---------------------------------------------------------------------------
# C. CHANGE CONTROL (QA004F02-00)
# ---------------------------------------------------------------------------
CHANGE_CONTROL_TEMPLATE = {
    "code": "qa004f02_change_control",
    "name": "Change Control (QA004F02-00)",
    "description": "Ready-made compliant Change Control template based on QA004F02-00. Initiation → Impact Assessment → Review → QA Review → Approval → Implementation → Closure with extension and rejection handling.",
    "category": "CHANGE_CONTROL",
    "notes": "Numbering: CC/YYYY/NNNN",
    "workflow": {
        "initial_stage": "INITIATION",
        "stages": [
            {"key": "INITIATION", "label": "Initiation", "color": COLOR_INIT},
            {"key": "IMPACT_ASSESSMENT", "label": "Impact Assessment", "color": COLOR_REVIEW},
            {"key": "REVIEW", "label": "Cross-functional Review", "color": COLOR_REVIEW},
            {"key": "QA_REVIEW", "label": "QA Review", "color": COLOR_QA},
            {"key": "APPROVAL", "label": "Approval", "color": COLOR_APPROVE},
            {"key": "IMPLEMENTATION", "label": "Implementation", "color": COLOR_IMPL},
            {"key": "EXTENSION", "label": "Extension", "color": COLOR_EXT},
            {"key": "CLOSED", "label": "Closed", "color": COLOR_CLOSE},
            {"key": "REJECTED", "label": "Rejected", "color": COLOR_REJECT},
        ],
        "transitions": [
            {"key": "GO_IMPACT", "from": "INITIATION", "to": "IMPACT_ASSESSMENT", "label": "Submit for Impact Assessment", "required_perm": None, "esignature": True},
            {"key": "GO_REVIEW", "from": "IMPACT_ASSESSMENT", "to": "REVIEW", "label": "Submit for Review", "required_perm": "review_record", "esignature": True},
            {"key": "GO_QA", "from": "REVIEW", "to": "QA_REVIEW", "label": "Submit for QA Review", "required_perm": "review_record", "esignature": True},
            {"key": "QA_TO_APPROVAL", "from": "QA_REVIEW", "to": "APPROVAL", "label": "Submit for Approval", "required_perm": "review_record", "esignature": True},
            {"key": "REJECT_REVIEW", "from": "REVIEW", "to": "REJECTED", "label": "Reject", "required_perm": "reject_record", "esignature": True},
            {"key": "REJECT_QA", "from": "QA_REVIEW", "to": "REJECTED", "label": "Reject", "required_perm": "reject_record", "esignature": True},
            {"key": "APPROVE_CC", "from": "APPROVAL", "to": "IMPLEMENTATION", "label": "Approve for Implementation", "required_perm": "approve_record", "esignature": True},
            {"key": "REJECT_APPROVAL", "from": "APPROVAL", "to": "REJECTED", "label": "Reject", "required_perm": "reject_record", "esignature": True},
            {"key": "REQUEST_EXTENSION", "from": "IMPLEMENTATION", "to": "EXTENSION", "label": "Request Extension", "required_perm": None, "esignature": True},
            {"key": "APPROVE_EXTENSION", "from": "EXTENSION", "to": "IMPLEMENTATION", "label": "Approve Extension", "required_perm": "approve_record", "esignature": True},
            {"key": "REJECT_EXTENSION", "from": "EXTENSION", "to": "REJECTED", "label": "Reject Extension", "required_perm": "reject_record", "esignature": True},
            {"key": "GO_CLOSURE", "from": "IMPLEMENTATION", "to": "CLOSED", "label": "Complete & Close", "required_perm": "approve_record", "esignature": True},
        ],
    },
    "form": {"sections": [
        {"key": "basic_information", "label": "1. Basic Information", "fields": [
            {"key": "change_control_no", "label": "Change Control No.", "type": "text", "required": False},
            {"key": "initiating_department", "label": "Initiating Department", "type": "department", "required": True},
            {"key": "cc_no_assigned_by_qa", "label": "CC No. Assigned by QA", "type": "text", "required": False},
            {"key": "qa_sign_date_basic", "label": "QA Sign & Date", "type": "signature", "required": False},
            {"key": "area_of_change", "label": "Area of Change", "type": "multiselect", "required": True,
             "options": ["SOP/Documents", "Instrument", "Software", "Facility", "Others (specify)"]},
            {"key": "reference_sop_document", "label": "Reference SOP/Document No. and Title / Instrument Name and ID / Software / Others", "type": "textarea", "required": False},
            {"key": "type_of_change", "label": "Type of Change", "type": "multiselect", "required": True,
             "options": ["New Introduction", "Revision/Change", "Obsolete", "Other (specify)"]},
        ]},
        {"key": "change_details", "label": "2. Change Details", "fields": [
            {"key": "existing_procedure_1", "label": "Existing Procedure / System / Condition (1)", "type": "textarea", "required": True},
            {"key": "proposed_change_1", "label": "Proposed Change(s) (1)", "type": "textarea", "required": True},
            {"key": "reason_justification_1", "label": "Reason / Justification for Change (1)", "type": "textarea", "required": True},
            {"key": "existing_procedure_2", "label": "Existing Procedure / System / Condition (2)", "type": "textarea", "required": False},
            {"key": "proposed_change_2", "label": "Proposed Change(s) (2)", "type": "textarea", "required": False},
            {"key": "reason_justification_2", "label": "Reason / Justification for Change (2)", "type": "textarea", "required": False},
            {"key": "attachments_list", "label": "Attachments (if any)", "type": "attachment", "required": False},
            {"key": "change_initiator_sign_date", "label": "Change Initiator (Sign & Date)", "type": "signature", "required": True},
        ]},
        {"key": "impact_assessment", "label": "3. Impact Assessment of Change", "fields": [
            {"key": "impact_other_sops", "label": "Impact in other SOPs/Documents/Forms/Logbooks (cross-referred documents)", "type": "checkbox", "required": False},
            {"key": "impact_other_sops_comments", "label": "Comments / Risk Assessment — Cross-referred documents", "type": "textarea", "required": False},
            {"key": "impact_qualification", "label": "Impact in instrument / area qualification / validation or calibration / preventive maintenance of instruments", "type": "checkbox", "required": False},
            {"key": "impact_qualification_comments", "label": "Comments / Risk Assessment — Qualification", "type": "textarea", "required": False},
            {"key": "impact_calibration_schedule", "label": "Impact in instrument calibration / preventive maintenance planner / schedules", "type": "checkbox", "required": False},
            {"key": "impact_calibration_comments", "label": "Comments / Risk Assessment — Calibration schedule", "type": "textarea", "required": False},
            {"key": "impact_training", "label": "Impact in training (requirement of retraining)", "type": "checkbox", "required": False},
            {"key": "impact_training_comments", "label": "Comments / Risk Assessment — Training", "type": "textarea", "required": False},
            {"key": "impact_facility", "label": "Impact in Facility Layout / Floor plan", "type": "checkbox", "required": False},
            {"key": "impact_facility_comments", "label": "Comments / Risk Assessment — Facility", "type": "textarea", "required": False},
            {"key": "impact_approvals", "label": "Impact on approvals / licenses / certifications / accreditations etc.", "type": "checkbox", "required": False},
            {"key": "impact_approvals_comments", "label": "Comments / Risk Assessment — Approvals", "type": "textarea", "required": False},
            {"key": "impact_software", "label": "Impact on Software Qualification / Validation or other IT systems / procedures", "type": "checkbox", "required": False},
            {"key": "impact_software_comments", "label": "Comments / Risk Assessment — Software", "type": "textarea", "required": False},
            {"key": "impact_project_protocols", "label": "Impact on project / study related protocols / reports / specification / STPs / other relevant documents", "type": "checkbox", "required": False},
            {"key": "impact_project_comments", "label": "Comments / Risk Assessment — Project / study", "type": "textarea", "required": False},
            {"key": "impact_other", "label": "Impact on Other(s)", "type": "checkbox", "required": False},
            {"key": "impact_other_comments", "label": "Comments / Risk Assessment — Other", "type": "textarea", "required": False},
            {"key": "reviewed_by_impact_sign", "label": "Reviewed By (Sign & Date)", "type": "signature", "required": True},
            {"key": "reviewed_by_qa_impact_sign", "label": "Reviewed By QA (Sign & Date)", "type": "signature", "required": True},
            {"key": "change_initiator_impact_sign", "label": "Change Initiator (Sign & Date)", "type": "signature", "required": False},
            {"key": "dept_head_impact_sign", "label": "Reviewed By Department Head/Designee (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "cross_functional_review", "label": "4. Change Control Review By Cross-Functional Department (including QA)", "fields": [
            {"key": "cf_department", "label": "Department", "type": "text", "required": False},
            {"key": "cf_comments", "label": "Comments / Impacts / Risk Assessment (if any)", "type": "textarea", "required": False},
            {"key": "cf_signature", "label": "Sign & Date", "type": "signature", "required": False},
        ]},
        {"key": "change_control_approval", "label": "5. Change Control Approval", "fields": [
            {"key": "change_category", "label": "Change Category", "type": "radio", "required": True, "options": ["Minor", "Major"]},
            {"key": "change_status", "label": "Change Status", "type": "radio", "required": True, "options": ["Approved", "Rejected"]},
            {"key": "remarks_approval", "label": "Remarks / Comments (if any)", "type": "textarea", "required": False},
            {"key": "qa_head_approval_sign", "label": "QA Head/Designee (Sign & Date)", "type": "signature", "required": True},
        ]},
        {"key": "timeline_and_extensions", "label": "6. Change Control Timeline and Extensions", "fields": [
            {"key": "target_completion_date", "label": "Target Completion Date", "type": "date", "required": True},
            {"key": "initiator_timeline_sign", "label": "Initiator (Sign & Date)", "type": "signature", "required": False},
            {"key": "revised_target_completion_date", "label": "Revised Target Completion Date", "type": "date", "required": False},
            {"key": "reason_justification_extension", "label": "Reason / Justification", "type": "textarea", "required": False},
            {"key": "requested_by_extension", "label": "Requested By (Sign & Date)", "type": "signature", "required": False},
            {"key": "hod_designee_extension", "label": "HOD/Designee (Sign & Date)", "type": "signature", "required": False},
            {"key": "qa_head_extension_sign", "label": "QA Head/Designee (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "implementation_details", "label": "7. Change Implementation Details", "fields": [
            {"key": "implementation_details_text", "label": "Implementation Details (Revised Document No. and Name / Activity Details / Implementation Date etc.)", "type": "textarea", "required": True},
            {"key": "initiator_impl_sign", "label": "Initiator (Sign & Date)", "type": "signature", "required": False},
            {"key": "reason_unimplemented", "label": "Reason / Justification for any unimplemented change", "type": "textarea", "required": False},
            {"key": "initiator_unimpl_sign", "label": "Initiator (Sign & Date) — unimplemented", "type": "signature", "required": False},
        ]},
        {"key": "change_control_closure", "label": "8. Change Control Closure", "fields": [
            {"key": "reviewed_by_hod_closure_sign", "label": "Reviewed By HOD/Designee (Sign & Date)", "type": "signature", "required": False},
            {"key": "reviewed_by_qa_closure_sign", "label": "Reviewed By QA (Sign & Date)", "type": "signature", "required": False},
            {"key": "cc_closure_date", "label": "Change Control Closure Date", "type": "date", "required": True},
            {"key": "closure_remarks", "label": "Remarks / Comments (if any)", "type": "textarea", "required": False},
            {"key": "effectiveness_requirement", "label": "Change Control Post Implementation Effectiveness Requirement", "type": "radio", "required": False, "options": ["No", "Yes", "Not Applicable"]},
            {"key": "effectiveness_record_no", "label": "If yes, Controlled Stationary Page No. of Change Control Effectiveness Verification Record", "type": "text", "required": False},
            {"key": "qa_head_closure_sign", "label": "QA Head/Designee (Sign & Date)", "type": "signature", "required": True},
        ]},
    ]},
    "pdf_template": {
        "header": {"title": "QA004F02-00 — Change Control", "show_logo": True, "show_record_number": True, "numbering_format": "CC/YYYY/NNNN"},
        "sections": [
            {"key": "s1", "label": "1. Basic Information", "show_section": "basic_information"},
            {"key": "s2", "label": "2. Change Details", "show_section": "change_details"},
            {"key": "s3", "label": "3. Impact Assessment of Change", "show_section": "impact_assessment"},
            {"key": "s4", "label": "4. Change Control Review By Cross-Functional Department (including QA)", "show_section": "cross_functional_review"},
            {"key": "s5", "label": "5. Change Control Approval", "show_section": "change_control_approval"},
            {"key": "s6", "label": "6. Change Control Timeline and Extensions", "show_section": "timeline_and_extensions"},
            {"key": "s7", "label": "7. Change Implementation Details", "show_section": "implementation_details"},
            {"key": "s8", "label": "8. Change Control Closure", "show_section": "change_control_closure"},
            {"key": "workflow_history", "label": "Workflow Timeline", "show_history": True},
            {"key": "signatures", "label": "Electronic Signatures", "show_signatures": True},
            {"key": "audit", "label": "Audit Trail", "show_audit": True},
        ],
        "footer": {"text": "QA004F02-00 · 21 CFR Part 11 · EU Annex 11 · ALCOA++"},
    },
    "approvals": [
        {"level": 1, "stage": "REVIEW", "role": "department_manager", "label": "Department Head / Designee"},
        {"level": 2, "stage": "QA_REVIEW", "role": "qa_reviewer", "label": "QA Review"},
        {"level": 3, "stage": "APPROVAL", "role": "qa_manager", "label": "QA Head / Designee"},
    ],
    "role_mapping": {
        "INITIATION": ["employee_operator", "department_manager"],
        "IMPACT_ASSESSMENT": ["department_manager", "qa_reviewer"],
        "REVIEW": ["department_manager", "qa_reviewer"],
        "QA_REVIEW": ["qa_reviewer", "qa_manager"],
        "APPROVAL": ["qa_manager"],
        "IMPLEMENTATION": ["department_manager"],
        "EXTENSION": ["qa_manager"],
        "CLOSED": ["qa_manager"],
        "REJECTED": ["qa_manager"],
    },
}


# ---------------------------------------------------------------------------
# D. INCIDENT (QA005F04-00)
# ---------------------------------------------------------------------------
INCIDENT_TEMPLATE = {
    "code": "qa005f04_incident",
    "name": "Incident (QA005F04-00)",
    "description": "Ready-made compliant Incident template based on QA005F04-00. Initiation → Review → QA Review → Approval → Closure with extension and rejection handling.",
    "category": "INCIDENT",
    "notes": "Numbering: INC/YYYY/NNNN",
    "workflow": {
        "initial_stage": "INITIATION",
        "stages": [
            {"key": "INITIATION", "label": "Initiation", "color": COLOR_INIT},
            {"key": "REVIEW", "label": "Review", "color": COLOR_REVIEW},
            {"key": "QA_REVIEW", "label": "QA Review", "color": COLOR_QA},
            {"key": "APPROVAL", "label": "Approval", "color": COLOR_APPROVE},
            {"key": "EXTENSION", "label": "Extension", "color": COLOR_EXT},
            {"key": "CLOSED", "label": "Closed", "color": COLOR_CLOSE},
            {"key": "REJECTED", "label": "Rejected", "color": COLOR_REJECT},
        ],
        "transitions": [
            {"key": "SUBMIT_REVIEW", "from": "INITIATION", "to": "REVIEW", "label": "Submit for Review", "required_perm": None, "esignature": True},
            {"key": "REQUEST_REWORK", "from": "REVIEW", "to": "INITIATION", "label": "Request Rework", "required_perm": "review_record", "esignature": True},
            {"key": "SUBMIT_QA", "from": "REVIEW", "to": "QA_REVIEW", "label": "Submit for QA Review", "required_perm": "review_record", "esignature": True},
            {"key": "QA_REQUEST_CHANGES", "from": "QA_REVIEW", "to": "REVIEW", "label": "Request Changes", "required_perm": "review_record", "esignature": True},
            {"key": "SUBMIT_APPROVAL", "from": "QA_REVIEW", "to": "APPROVAL", "label": "Submit for Approval", "required_perm": "review_record", "esignature": True},
            {"key": "REQUEST_EXTENSION", "from": "APPROVAL", "to": "EXTENSION", "label": "Request Extension", "required_perm": None, "esignature": True},
            {"key": "APPROVE_EXTENSION", "from": "EXTENSION", "to": "APPROVAL", "label": "Approve Extension", "required_perm": "approve_record", "esignature": True},
            {"key": "REJECT_EXTENSION", "from": "EXTENSION", "to": "REJECTED", "label": "Reject Extension", "required_perm": "reject_record", "esignature": True},
            {"key": "APPROVE", "from": "APPROVAL", "to": "CLOSED", "label": "Approve & Close Incident", "required_perm": "approve_record", "esignature": True},
            {"key": "REJECT", "from": "APPROVAL", "to": "REJECTED", "label": "Reject", "required_perm": "reject_record", "esignature": True},
        ],
    },
    "form": {"sections": [
        {"key": "incident_header", "label": "Incident Header", "fields": [
            {"key": "incident_no", "label": "Incident No.", "type": "text", "required": False},
            {"key": "assigned_by_qa", "label": "Assigned by QA (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "part_1_initial_information", "label": "Part 1: Initial Information", "fields": [
            {"key": "initiating_department", "label": "a) Initiating Department", "type": "department", "required": True},
            {"key": "affected_systems", "label": "b) Affected Systems", "type": "multiselect", "required": False,
             "options": ["Document", "Facility", "Process", "Equipment", "Projects", "Software", "Non-Listed Categories"]},
            {"key": "affected_systems_reference_no", "label": "c) Affected Systems Reference No. / Title / other details", "type": "text", "required": False},
            {"key": "affected_project_details", "label": "d) Affected Project Details", "type": "textarea", "required": False},
            {"key": "description_incident", "label": "e) Description Incident", "type": "textarea", "required": True},
            {"key": "date_of_incident_occurrence", "label": "f) Date of Incident Occurrence", "type": "date", "required": True},
            {"key": "unknown_occurrence_date", "label": "Unknown (occurrence date)", "type": "checkbox", "required": False},
            {"key": "date_of_incident_identification", "label": "g) Date of Incident Identification", "type": "date", "required": True},
            {"key": "incident_initiation_date", "label": "Incident Initiation Date", "type": "date", "required": False},
            {"key": "incident_target_closure_date", "label": "h) Incident Target Closure Date", "type": "date", "required": True},
            {"key": "list_of_attachments", "label": "i) List of Attachments", "type": "attachment", "required": False},
            {"key": "initiated_by", "label": "Initiated By (Sign & Date)", "type": "signature", "required": True},
            {"key": "reviewed_by", "label": "Reviewed By (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "part_2_impact_assessment", "label": "Part 2: Impact Assessment", "fields": [
            {"key": "impact_drug_quality", "label": "i) Risk to drug quality?", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "impact_project_data", "label": "ii) Risk to project data?", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "impact_system", "label": "iii) Risk to system?", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "impact_comments", "label": "b) Impact Assessment Comments", "type": "textarea", "required": False},
        ]},
        {"key": "part_3_investigation_rca", "label": "Part 3: Investigation / Root Cause Analysis", "fields": [
            {"key": "investigation_description", "label": "a) Investigation Description", "type": "textarea", "required": True},
            {"key": "root_cause_type", "label": "b) Root cause", "type": "radio", "required": True, "options": ["Assignable", "Non-assignable"]},
            {"key": "assignable_root_cause", "label": "c) If assignable, root cause", "type": "multiselect", "required": False,
             "options": ["Method", "Manpower", "Machine", "Material", "Measurement", "Mother Nature (environment)"]},
            {"key": "assignable_root_cause_other", "label": "Other (specify)", "type": "text", "required": False},
        ]},
        {"key": "part_4_corrective_actions", "label": "Part 4: Corrective Actions", "fields": [
            {"key": "corrective_actions", "label": "a) Corrective actions (multiple options possible)", "type": "multiselect", "required": True,
             "options": ["Data exclusion", "Documentation / correction", "Procedure revision / amendment", "Project / Study termination", "Reperforming affected activities", "Other"]},
            {"key": "corrective_actions_description", "label": "b) Description", "type": "textarea", "required": True},
        ]},
        {"key": "part_5_preventive_actions", "label": "Part 5: Preventive Actions", "fields": [
            {"key": "preventive_actions", "label": "a) Preventive actions (multiple options possible)", "type": "multiselect", "required": True,
             "options": ["Training", "Change in systems", "Change in procedures", "Software upgrade / change", "Enhanced oversight", "Further calibration / validation", "Other"]},
            {"key": "preventive_actions_description", "label": "b) Description", "type": "textarea", "required": True},
            {"key": "recorded_by_sign", "label": "Recorded By (Sign & Date)", "type": "signature", "required": False},
            {"key": "reviewed_by_sign", "label": "Reviewed By (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "part_6_extension_closure", "label": "Part 6: Extension of Incident Closure", "fields": [
            {"key": "revised_target_completion_date", "label": "a) Revised Target Completion Date", "type": "date", "required": True},
            {"key": "reason_justification", "label": "b) Reason / Justification", "type": "textarea", "required": True},
        ]},
        {"key": "part_7_other_dept_comments", "label": "Part 7: Other department comments", "fields": [
            {"key": "requested_by_sign", "label": "Requested By (Sign & Date)", "type": "signature", "required": False},
            {"key": "dept_head_sign", "label": "Department Head/Designee (Sign & Date)", "type": "signature", "required": False},
            {"key": "qa_head_part7_sign", "label": "QA Head/Designee (Sign & Date)", "type": "signature", "required": False},
            {"key": "other_dept_comments", "label": "Comments / Remarks", "type": "textarea", "required": False},
            {"key": "other_dept_signature", "label": "Signature & Date", "type": "signature", "required": False},
        ]},
        {"key": "part_8_qa_review_closure", "label": "Part 8: QA Review and Closure", "fields": [
            {"key": "details_acceptable", "label": "a) Details completed are acceptable?", "type": "radio", "required": True, "options": ["Yes", "No"]},
            {"key": "reason_if_no", "label": "If No, mention reason / comments", "type": "textarea", "required": False},
            {"key": "communicated_to_management", "label": "b) Communicated to Management / Management Representative", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "capa_closed", "label": "c) CAPA closed?", "type": "radio", "required": True, "options": ["Yes", "No", "Not applicable"]},
            {"key": "other_comments_qa", "label": "d) Other comments", "type": "textarea", "required": False},
            {"key": "qa_reviewed_by", "label": "e) QA Reviewed by (Sign & Date)", "type": "signature", "required": True},
            {"key": "incident_closure_comments", "label": "f) Incident Form Closure Comments", "type": "textarea", "required": False},
            {"key": "incident_closure_date", "label": "g) Incident Form Closure Date", "type": "date", "required": True},
            {"key": "capa_effectiveness_required", "label": "h) CAPA Implementation Effectiveness Verification Requirement", "type": "radio", "required": False, "options": ["Yes", "No"]},
            {"key": "qa_head_designee_closure", "label": "i) QA Head / Designee (Sign & Date)", "type": "signature", "required": True},
        ]},
    ]},
    "pdf_template": {
        "header": {"title": "QA005F04-00 — Incident Form", "show_logo": True, "show_record_number": True, "numbering_format": "INC/YYYY/NNNN"},
        "sections": [
            {"key": "sh", "label": "Incident Header", "show_section": "incident_header"},
            {"key": "s1", "label": "Part 1: Initial Information", "show_section": "part_1_initial_information"},
            {"key": "s2", "label": "Part 2: Impact Assessment", "show_section": "part_2_impact_assessment"},
            {"key": "s3", "label": "Part 3: Investigation / Root Cause Analysis", "show_section": "part_3_investigation_rca"},
            {"key": "s4", "label": "Part 4: Corrective Actions", "show_section": "part_4_corrective_actions"},
            {"key": "s5", "label": "Part 5: Preventive Actions", "show_section": "part_5_preventive_actions"},
            {"key": "s6", "label": "Part 6: Extension of Incident Closure", "show_section": "part_6_extension_closure"},
            {"key": "s7", "label": "Part 7: Other department comments", "show_section": "part_7_other_dept_comments"},
            {"key": "s8", "label": "Part 8: QA Review and Closure", "show_section": "part_8_qa_review_closure"},
            {"key": "workflow_history", "label": "Workflow Timeline", "show_history": True},
            {"key": "signatures", "label": "Electronic Signatures", "show_signatures": True},
            {"key": "audit", "label": "Audit Trail", "show_audit": True},
        ],
        "footer": {"text": "QA005F04-00 · 21 CFR Part 11 · EU Annex 11 · ALCOA++"},
    },
    "approvals": [
        {"level": 1, "stage": "REVIEW", "role": "qa_reviewer", "label": "Reviewer"},
        {"level": 2, "stage": "QA_REVIEW", "role": "qa_manager", "label": "QA Review"},
        {"level": 3, "stage": "APPROVAL", "role": "qa_manager", "label": "QA Head / Designee"},
    ],
    "role_mapping": {
        "INITIATION": ["employee_operator", "department_manager"],
        "REVIEW": ["qa_reviewer", "department_manager"],
        "QA_REVIEW": ["qa_manager"],
        "APPROVAL": ["qa_manager"],
        "EXTENSION": ["qa_manager"],
        "CLOSED": ["qa_manager"],
        "REJECTED": ["qa_manager"],
    },
}


# ---------------------------------------------------------------------------
# E. EVENT LOG (QA005F08-00)
# ---------------------------------------------------------------------------
EVENT_LOG_TEMPLATE = {
    "code": "qa005f08_event_log",
    "name": "Event Log (QA005F08-00)",
    "description": "Ready-made compliant Event Log template based on QA005F08-00. Tabular event record with recording → review → closure.",
    "category": "EVENT",
    "notes": "Sequential event entries. No fixed numbering format — use Event No. as sequence ID.",
    "workflow": {
        "initial_stage": "RECORDED",
        "stages": [
            {"key": "RECORDED", "label": "Recorded", "color": COLOR_INIT},
            {"key": "REVIEW", "label": "Review", "color": COLOR_REVIEW},
            {"key": "CLOSED", "label": "Closed", "color": COLOR_CLOSE},
            {"key": "REJECTED", "label": "Rejected", "color": COLOR_REJECT},
        ],
        "transitions": [
            {"key": "SUBMIT_REVIEW", "from": "RECORDED", "to": "REVIEW", "label": "Submit for Review", "required_perm": None, "esignature": True},
            {"key": "APPROVE", "from": "REVIEW", "to": "CLOSED", "label": "Approve & Close", "required_perm": "approve_record", "esignature": True},
            {"key": "REJECT", "from": "REVIEW", "to": "REJECTED", "label": "Reject", "required_perm": "reject_record", "esignature": True},
            {"key": "REOPEN", "from": "REJECTED", "to": "RECORDED", "label": "Reopen / Correct", "required_perm": None, "esignature": True},
        ],
    },
    "form": {"sections": [
        {"key": "event_log", "label": "Event Log", "fields": [
            {"key": "event_no", "label": "Event No.", "type": "text", "required": True},
            {"key": "sequence_batch_result_id", "label": "Sequence / Batch / Result ID", "type": "text", "required": True},
            {"key": "brief_event_details", "label": "Brief Event Details", "type": "textarea", "required": True},
            {"key": "recorded_by_sign", "label": "Recorded By (Sign & Date)", "type": "signature", "required": True},
            {"key": "closure_date", "label": "Closure Date", "type": "date", "required": False},
            {"key": "closure_recorded_by_sign", "label": "Closure Recorded By (Sign & Date)", "type": "signature", "required": False},
        ]},
        {"key": "remarks", "label": "Remarks", "fields": [
            {"key": "remarks_text", "label": "Remarks", "type": "textarea", "required": False},
        ]},
        {"key": "review", "label": "Review", "fields": [
            {"key": "reviewed_by_sign", "label": "Reviewed By (Sign & Date)", "type": "signature", "required": True},
        ]},
    ]},
    "pdf_template": {
        "header": {"title": "QA005F08-00 — Event Log", "show_logo": True, "show_record_number": True, "numbering_format": "EVT/YYYY/NNNN"},
        "sections": [
            {"key": "event_log_table", "label": "Event Log", "show_section": "event_log",
             "table_columns": ["Event No.", "Sequence / Batch / Result ID", "Brief Event Details", "Recorded By (Sign & Date)", "Closure Date", "Recorded By (Sign & Date)"]},
            {"key": "remarks", "label": "Remarks", "show_section": "remarks"},
            {"key": "review", "label": "Reviewed By (Sign & Date)", "show_section": "review"},
            {"key": "workflow_history", "label": "Workflow Timeline", "show_history": True},
            {"key": "signatures", "label": "Electronic Signatures", "show_signatures": True},
            {"key": "audit", "label": "Audit Trail", "show_audit": True},
        ],
        "footer": {"text": "QA005F08-00 · 21 CFR Part 11 · EU Annex 11 · ALCOA++"},
    },
    "approvals": [
        {"level": 1, "stage": "REVIEW", "role": "qa_reviewer", "label": "Reviewer"},
    ],
    "role_mapping": {
        "RECORDED": ["employee_operator", "department_manager"],
        "REVIEW": ["qa_reviewer", "qa_manager"],
        "CLOSED": ["qa_manager"],
        "REJECTED": ["qa_reviewer", "qa_manager"],
    },
}


ALL_TEMPLATES = [
    DEVIATION_TEMPLATE,
    CAPA_TEMPLATE,
    CHANGE_CONTROL_TEMPLATE,
    INCIDENT_TEMPLATE,
    EVENT_LOG_TEMPLATE,
]


async def seed_compliant_module_templates(db) -> None:
    """Idempotently seed ready-made compliant templates as PUBLISHED, GLOBAL.

    Strategy:
      1. If a template with the same `code` + `plant_id="GLOBAL"` does not exist,
         insert it as **PUBLISHED v1** (so legacy modules immediately render the
         PDF-aligned form out-of-the-box).
      2. If it already exists with status="DRAFT" (i.e. previous fork seeded it
         as DRAFT) AND has no published_at timestamp, auto-publish that row.
         This is a one-time upgrade — once it's PUBLISHED, future edits go
         through the standard Framework "new version" workflow.
      3. Anything else (admin already edited, retired, or a newer version
         exists) is left untouched. Admin retains full control via the UI.

    Editing remains possible at any time:
       PUBLISHED  →  admin clicks "New Version" / edits → DRAFT v2 → publish v2
    Every change is captured in `audit_trail` (entity_type = MODULE_TEMPLATE).
    """
    now = _now_iso()
    for tpl in ALL_TEMPLATES:
        existing = await db.module_templates.find_one({
            "code": tpl["code"],
            "plant_id": "GLOBAL",
        })

        if existing:
            # One-time upgrade of legacy DRAFTs from prior seed runs.
            if existing.get("status") == "DRAFT" and not existing.get("published_at"):
                await db.module_templates.update_one(
                    {"id": existing["id"]},
                    {"$set": {
                        "status": "PUBLISHED",
                        "published_at": now,
                        "published_by": "SYSTEM",
                    }},
                )
            continue

        doc = {
            "id": str(uuid.uuid4()),
            "code": tpl["code"],
            "name": tpl["name"],
            "description": tpl["description"],
            "category": tpl["category"],
            "plant_id": "GLOBAL",
            "version": 1,
            "status": "PUBLISHED",  # Live in legacy modules. Edits → new version.
            "workflow": tpl["workflow"],
            "form": tpl["form"],
            "pdf_template": tpl["pdf_template"],
            "approvals": tpl.get("approvals", []),
            "role_mapping": tpl.get("role_mapping", {}),
            "notes": tpl.get("notes", ""),
            "copied_from": None,
            "created_at": now,
            "created_by": "SYSTEM",
            "published_at": now,
            "published_by": "SYSTEM",
            "retired_at": None,
            "retired_by": None,
        }
        await db.module_templates.insert_one(doc)
