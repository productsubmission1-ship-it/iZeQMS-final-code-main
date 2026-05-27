import React, { useCallback, useEffect, useMemo, useState } from "react";
import api, { API_BASE, formatApiError } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Checkbox } from "./ui/checkbox";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "./ui/accordion";
import { Download, ShieldCheck, Plus, X, FileSignature } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import { hasRole } from "../lib/roles";

const PARTS = [
  ["part1", "Part 1: Initial Information"],
  ["part2", "Part 2: Classification and Impact"],
  ["part3", "Part 3: Regulatory / Sponsor Notifications and Attachments"],
  ["part4", "Part 4: Investigation / Root Cause Analysis"],
  ["part5", "Part 5: Corrective Actions"],
  ["part6", "Part 6: Preventive Actions"],
  ["part7", "Part 7: Extension of Deviation Closure"],
  ["part8", "Part 8: Other Department Comments"],
  ["part9", "Part 9: QA Review and Closure"],
];

const PART_LOCK_BLOCKS = {
  part1: ["part1_initiated_by", "part1_reviewed_by"],
  part3: ["part3_recorded_by", "part3_reviewed_by"],
  part6: ["part6_recorded_by", "part6_reviewed_by"],
  part9: ["part9_qa_reviewed_by", "part9_qa_head_closure"],
};

const SECTION_BLOCKS_UNUSED = [
  { block: "assigned_by_qa",        label: "Assigned by QA (Sign & Date)",         roles: ["qa_head", "admin"] },
  { block: "part1_initiated_by",    label: "Part 1 · Initiated By",                roles: ["initiator", "admin"] },
  { block: "part1_reviewed_by",     label: "Part 1 · Reviewed By (HOD/Designee)",  roles: ["reviewer", "admin", "qa_head"] },
  { block: "part3_recorded_by",     label: "Part 3 · Recorded By",                 roles: ["initiator", "admin"] },
  { block: "part3_reviewed_by",     label: "Part 3 · Reviewed By (HOD/Designee)",  roles: ["reviewer", "admin", "qa_head"] },
  { block: "part6_recorded_by",     label: "Part 6 · Recorded By (CAPA)",          roles: ["initiator", "admin"] },
  { block: "part6_reviewed_by",     label: "Part 6 · Reviewed By (HOD/Designee)",  roles: ["reviewer", "admin", "qa_head"] },
  { block: "part9_qa_reviewed_by",  label: "Part 9 · QA Reviewed By",              roles: ["qa_head", "admin"] },
  { block: "part9_qa_head_closure", label: "Part 9 · QA Head/Designee — Closure", roles: ["qa_head", "admin"] },
];

const CheckGroup = ({ options, value, onChange, multi = false, disabled = false, testid }) => {
  const arr = Array.isArray(value) ? value : (value ? [value] : []);
  const toggle = (opt) => {
    if (multi) {
      const next = arr.includes(opt) ? arr.filter((x) => x !== opt) : [...arr, opt];
      onChange(next);
    } else {
      onChange(opt);
    }
  };
  return (
    <div className="flex flex-wrap gap-3" data-testid={testid}>
      {options.map((o) => (
        <label key={o} className="inline-flex items-center gap-1.5 text-sm">
          <Checkbox checked={arr.includes(o)} onCheckedChange={() => toggle(o)} disabled={disabled} />
          <span>{o}</span>
        </label>
      ))}
    </div>
  );
};

const FieldRow = ({ label, children }) => (
  <div className="grid grid-cols-12 gap-3 py-2 border-b border-slate-100 last:border-0">
    <div className="col-span-12 sm:col-span-5 text-xs text-slate-600 mono pt-2">{label}</div>
    <div className="col-span-12 sm:col-span-7">{children}</div>
  </div>
);

function ESignButton({ block, label, onSigned, disabled, signed }) {
  const [open, setOpen] = useState(false);
  const [pw, setPw] = useState("");
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!pw) return toast.error("Password required");
    setBusy(true);
    try {
      await onSigned({ password: pw, comment });
      setOpen(false); setPw(""); setComment("");
    } catch (e) {
      // toast handled upstream
    } finally { setBusy(false); }
  };

  if (signed) {
    return (
      <div className="border border-emerald-200 bg-emerald-50 rounded-sm p-2.5 text-xs flex items-center justify-between">
        <div>
          <div className="font-medium text-emerald-900 flex items-center gap-1.5"><ShieldCheck size={13} /> Signed</div>
          <div className="text-emerald-800 mono text-[11px]">
            {signed.user_name} · {new Date(signed.timestamp).toLocaleString()}
          </div>
        </div>
        <span className="text-emerald-700 mono text-[10px] uppercase">{label}</span>
      </div>
    );
  }
  return (
    <>
      <Button
        size="sm" variant="outline" disabled={disabled}
        className="text-xs"
        onClick={() => setOpen(true)}
        data-testid={`esign-${block}`}
      >
        <FileSignature size={12} className="mr-1" /> Sign · {label}
      </Button>
      {open && (
        <div className="fixed inset-0 bg-slate-900/50 z-50 flex items-center justify-center p-4" onClick={() => setOpen(false)}>
          <div className="bg-white border border-slate-200 rounded-sm shadow-2xl w-full max-w-md p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <div className="font-semibold text-slate-900">Electronic Signature</div>
              <button onClick={() => setOpen(false)} className="text-slate-500 hover:text-slate-900"><X size={16} /></button>
            </div>
            <div className="text-xs text-slate-600 mb-3">Meaning: <b>{label}</b><br />Re-enter your password to apply the e-signature. This action is audit-trailed and final.</div>
            <Label className="text-[10px] uppercase tracking-wide text-slate-500 mono">Password</Label>
            <Input type="password" value={pw} onChange={(e) => setPw(e.target.value)} data-testid={`esign-pw-${block}`} />
            <Label className="text-[10px] uppercase tracking-wide text-slate-500 mono mt-2">Comment (optional)</Label>
            <Textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={2} data-testid={`esign-comment-${block}`} />
            <div className="flex justify-end gap-2 mt-3">
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={submit} disabled={busy} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid={`esign-submit-${block}`}>
                {busy ? "Signing…" : "Apply signature"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default function DeviationForm({ record, onChanged }) {
  const { user } = useAuth();
  const [data, setData] = useState(record.deviation_data || {});
  const [signatures, setSignatures] = useState(record.signatures || []);
  const [savingPart, setSavingPart] = useState(null);
  const closed = record.status === "CLOSED";
  const roles = user?.roles || [];

  const sigByBlock = useMemo(() => {
    const m = {};
    (signatures || []).forEach((s) => { m[s.block] = s; });
    return m;
  }, [signatures]);

  const reload = useCallback(async () => {
    const { data: rec } = await api.get(`/deviations/${record.id}`);
    setData(rec.deviation_data || {});
    setSignatures(rec.signatures || []);
    onChanged?.(rec);
  }, [record.id, onChanged]);

  useEffect(() => { reload(); /* eslint-disable-next-line */ }, [record.id]);

  const updatePart = (partKey, patch) => {
    setData((d) => ({ ...d, [partKey]: { ...(d[partKey] || {}), ...patch } }));
  };

  const partLocked = (partKey) => {
    if (closed) return true;
    const blocks = PART_LOCK_BLOCKS[partKey] || [];
    return blocks.some((b) => sigByBlock[b]);
  };

  const savePart = async (partKey) => {
    setSavingPart(partKey);
    try {
      await api.put(`/deviations/${record.id}/parts`, {
        part: partKey, data: data[partKey] || {}, reason: `Updated ${partKey}`,
      });
      toast.success(`${partKey.toUpperCase()} saved`);
      await reload();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally { setSavingPart(null); }
  };

  const sign = async (block, payload) => {
    try {
      await api.post(`/deviations/${record.id}/sign`, { block, ...payload });
      toast.success("Signature applied");
      await reload();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
      throw e;
    }
  };

  const downloadPdf = async () => {
    try {
      const token = localStorage.getItem("izqms_token");
      const res = await fetch(`${API_BASE}/deviations/${record.id}/pdf`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
      });
      if (!res.ok) throw new Error(`PDF download failed (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = `${record.record_number}.pdf`; link.click();
      URL.revokeObjectURL(url);
    } catch (e) { toast.error(e.message); }
  };

  // Uses canonical role helper from lib/roles.js — accepts legacy role names
  // (initiator/reviewer/approver/qa_head) AND canonical names, and honors the
  // full hierarchy (super_admin > admin > qa_manager > qa_reviewer > employee_operator).
  const canSignBlock = (b) => hasRole(user, ...(b.roles || []));

  const p1 = data.part1 || {};
  const p2 = data.part2 || {};
  const p3 = data.part3 || {};
  const p4 = data.part4 || {};
  const p5 = data.part5 || {};
  const p6 = data.part6 || {};
  const p7 = data.part7 || {};
  const p8 = data.part8 || [];
  const p9 = data.part9 || {};
  const extensions = (p7.extensions) || [];

  return (
    <div className="space-y-3" data-testid="deviation-form">
      <div className="flex items-center justify-between bg-slate-900 text-white px-4 py-2 rounded-sm">
        <div className="font-semibold tracking-tight">Deviation Report — 9-Part Form</div>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" className="bg-transparent border-white/30 text-white hover:bg-white/10" onClick={downloadPdf} data-testid="deviation-pdf-btn">
            <Download size={14} className="mr-1" /> Download PDF
          </Button>
        </div>
      </div>

      {/* Assigned by QA */}
      <div className="border border-slate-200 bg-white rounded-sm p-3">
        <div className="text-sm font-semibold text-slate-900 mb-2">Deviation No.: <span className="mono">{record.record_number}</span></div>
        {canSignBlock({ roles: ["qa_head", "admin"] }) && (
          <ESignButton block="assigned_by_qa" label="Assigned by QA"
            signed={sigByBlock.assigned_by_qa}
            disabled={closed}
            onSigned={(p) => sign("assigned_by_qa", p)} />
        )}
      </div>

      <Accordion type="multiple" defaultValue={["part1"]} className="space-y-2">
        {/* PART 1 */}
        <AccordionItem value="part1" className="border border-slate-200 rounded-sm bg-white">
          <AccordionTrigger className="px-4 py-2 text-sm font-semibold">{PARTS[0][1]}</AccordionTrigger>
          <AccordionContent className="px-4 pb-4">
            <FieldRow label="a) Initiating Department">
              <Input value={p1.initiating_department || ""} onChange={(e) => updatePart("part1", { initiating_department: e.target.value })} disabled={partLocked("part1")} data-testid="p1-dept" />
            </FieldRow>
            <FieldRow label="b) Protocol No. / SOP No. / Others">
              <Input value={p1.protocol_or_sop_no || ""} onChange={(e) => updatePart("part1", { protocol_or_sop_no: e.target.value })} disabled={partLocked("part1")} />
            </FieldRow>
            <FieldRow label="c) Affected Protocol / SOP / Document Title">
              <Input value={p1.affected_document_title || ""} onChange={(e) => updatePart("part1", { affected_document_title: e.target.value })} disabled={partLocked("part1")} />
            </FieldRow>
            <FieldRow label="d) Affected Project Details">
              <Textarea value={p1.affected_project_details || ""} rows={2} onChange={(e) => updatePart("part1", { affected_project_details: e.target.value })} disabled={partLocked("part1")} />
            </FieldRow>
            <FieldRow label="e) Source(s) of identification">
              <CheckGroup
                options={["Self", "QA observation", "Internal Audit Observation", "Regulatory observation", "Sponsor observation", "Other"]}
                value={p1.identification_sources || []}
                onChange={(v) => updatePart("part1", { identification_sources: v })}
                multi disabled={partLocked("part1")}
                testid="p1-sources"
              />
              {(p1.identification_sources || []).includes("Other") && (
                <Input className="mt-2" placeholder="Specify other source" value={p1.identification_other || ""} onChange={(e) => updatePart("part1", { identification_other: e.target.value })} disabled={partLocked("part1")} />
              )}
            </FieldRow>
            <FieldRow label="f) Type of deviation">
              <CheckGroup options={["Planned Deviation", "Unplanned Deviation"]} value={p1.deviation_type} onChange={(v) => updatePart("part1", { deviation_type: v })} disabled={partLocked("part1")} testid="p1-type" />
            </FieldRow>
            <FieldRow label="g) Description in Protocol/SOP/Requirement">
              <Textarea rows={2} value={p1.defined_requirement || ""} onChange={(e) => updatePart("part1", { defined_requirement: e.target.value })} disabled={partLocked("part1")} />
            </FieldRow>
            <FieldRow label="h) Deviation description">
              <Textarea rows={3} value={p1.deviation_description || ""} onChange={(e) => updatePart("part1", { deviation_description: e.target.value })} disabled={partLocked("part1")} data-testid="p1-description" />
            </FieldRow>
            <FieldRow label="i) Date of Deviation Occurrence">
              <div className="flex items-center gap-2">
                <Input type="date" value={p1.occurrence_date || ""} onChange={(e) => updatePart("part1", { occurrence_date: e.target.value, occurrence_unknown: false })} disabled={partLocked("part1") || p1.occurrence_unknown} />
                <label className="inline-flex items-center gap-1.5 text-xs">
                  <Checkbox checked={!!p1.occurrence_unknown} onCheckedChange={(v) => updatePart("part1", { occurrence_unknown: v, occurrence_date: v ? "" : (p1.occurrence_date || "") })} disabled={partLocked("part1")} />
                  Unknown
                </label>
              </div>
            </FieldRow>
            <FieldRow label="j) Date of Deviation Identification">
              <Input type="date" value={p1.identification_date || ""} onChange={(e) => updatePart("part1", { identification_date: e.target.value })} disabled={partLocked("part1")} />
            </FieldRow>
            <FieldRow label="Deviation Initiation Date">
              <Input type="date" value={p1.initiation_date || ""} onChange={(e) => updatePart("part1", { initiation_date: e.target.value })} disabled={partLocked("part1")} />
            </FieldRow>
            <FieldRow label="k) Deviation Target Closure Date">
              <Input type="date" value={p1.target_closure_date || ""} onChange={(e) => updatePart("part1", { target_closure_date: e.target.value })} disabled={partLocked("part1")} />
            </FieldRow>
            <div className="flex gap-2 mt-3">
              {!partLocked("part1") && <Button size="sm" onClick={() => savePart("part1")} disabled={savingPart === "part1"} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="p1-save">{savingPart === "part1" ? "Saving…" : "Save Part 1"}</Button>}
              {canSignBlock({ roles: ["initiator", "admin"] }) && <ESignButton block="part1_initiated_by" label="Initiated By" signed={sigByBlock.part1_initiated_by} disabled={closed} onSigned={(p) => sign("part1_initiated_by", p)} />}
              {canSignBlock({ roles: ["reviewer", "qa_head", "admin"] }) && <ESignButton block="part1_reviewed_by" label="Reviewed By (HOD)" signed={sigByBlock.part1_reviewed_by} disabled={closed || !sigByBlock.part1_initiated_by} onSigned={(p) => sign("part1_reviewed_by", p)} />}
            </div>
          </AccordionContent>
        </AccordionItem>

        {/* PART 2 */}
        <AccordionItem value="part2" className="border border-slate-200 rounded-sm bg-white">
          <AccordionTrigger className="px-4 py-2 text-sm font-semibold">{PARTS[1][1]}</AccordionTrigger>
          <AccordionContent className="px-4 pb-4">
            <FieldRow label="a) Classification">
              <CheckGroup options={["Critical", "Major", "Minor"]} value={p2.classification} onChange={(v) => updatePart("part2", { classification: v })} disabled={closed} testid="p2-classification" />
            </FieldRow>
            <FieldRow label="b.i) Risk to drug quality?">
              <CheckGroup options={["Yes", "No", "Not applicable"]} value={p2.risk_drug_quality} onChange={(v) => updatePart("part2", { risk_drug_quality: v })} disabled={closed} />
            </FieldRow>
            <FieldRow label="b.ii) Risk to project data?">
              <CheckGroup options={["Yes", "No", "Not applicable"]} value={p2.risk_project_data} onChange={(v) => updatePart("part2", { risk_project_data: v })} disabled={closed} />
            </FieldRow>
            <FieldRow label="b.iii) Risk to system?">
              <CheckGroup options={["Yes", "No", "Not applicable"]} value={p2.risk_system} onChange={(v) => updatePart("part2", { risk_system: v })} disabled={closed} />
            </FieldRow>
            <FieldRow label="c) Other Comments">
              <Textarea rows={2} value={p2.other_comments || ""} onChange={(e) => updatePart("part2", { other_comments: e.target.value })} disabled={closed} />
            </FieldRow>
            <div className="flex gap-2 mt-3">
              {!closed && <Button size="sm" onClick={() => savePart("part2")} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="p2-save">Save Part 2</Button>}
            </div>
          </AccordionContent>
        </AccordionItem>

        {/* PART 3 */}
        <AccordionItem value="part3" className="border border-slate-200 rounded-sm bg-white">
          <AccordionTrigger className="px-4 py-2 text-sm font-semibold">{PARTS[2][1]}</AccordionTrigger>
          <AccordionContent className="px-4 pb-4">
            <FieldRow label="a) Regulatory agency notification / approval required?">
              <CheckGroup options={["Yes", "No", "Not applicable"]} value={p3.regulatory_notification} onChange={(v) => updatePart("part3", { regulatory_notification: v })} disabled={partLocked("part3")} />
            </FieldRow>
            <FieldRow label="b) Notification to sponsor required?">
              <CheckGroup options={["Yes", "No", "Not applicable"]} value={p3.sponsor_notification} onChange={(v) => updatePart("part3", { sponsor_notification: v })} disabled={partLocked("part3")} />
            </FieldRow>
            <FieldRow label="c) Notification to other departments required?">
              <CheckGroup options={["Yes", "No", "Not applicable"]} value={p3.other_dept_notification} onChange={(v) => updatePart("part3", { other_dept_notification: v })} disabled={partLocked("part3")} />
              {p3.other_dept_notification === "Yes" && (
                <Input className="mt-2" placeholder="Department names" value={p3.other_dept_names || ""} onChange={(e) => updatePart("part3", { other_dept_names: e.target.value })} disabled={partLocked("part3")} />
              )}
            </FieldRow>
            <FieldRow label="d) List of attachments">
              <Textarea rows={2} value={p3.attachments_list || ""} onChange={(e) => updatePart("part3", { attachments_list: e.target.value })} disabled={partLocked("part3")} />
            </FieldRow>
            <div className="flex gap-2 mt-3">
              {!partLocked("part3") && <Button size="sm" onClick={() => savePart("part3")} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="p3-save">Save Part 3</Button>}
              {canSignBlock({ roles: ["initiator", "admin"] }) && <ESignButton block="part3_recorded_by" label="Recorded By" signed={sigByBlock.part3_recorded_by} disabled={closed} onSigned={(p) => sign("part3_recorded_by", p)} />}
              {canSignBlock({ roles: ["reviewer", "qa_head", "admin"] }) && <ESignButton block="part3_reviewed_by" label="Reviewed By" signed={sigByBlock.part3_reviewed_by} disabled={closed || !sigByBlock.part3_recorded_by} onSigned={(p) => sign("part3_reviewed_by", p)} />}
            </div>
          </AccordionContent>
        </AccordionItem>

        {/* PART 4 */}
        <AccordionItem value="part4" className="border border-slate-200 rounded-sm bg-white">
          <AccordionTrigger className="px-4 py-2 text-sm font-semibold">{PARTS[3][1]}</AccordionTrigger>
          <AccordionContent className="px-4 pb-4">
            <FieldRow label="a) Investigation Description">
              <Textarea rows={3} value={p4.investigation_description || ""} onChange={(e) => updatePart("part4", { investigation_description: e.target.value })} disabled={closed} />
            </FieldRow>
            <FieldRow label="b) Root cause">
              <CheckGroup options={["Assignable", "Non-assignable"]} value={p4.root_cause_type} onChange={(v) => updatePart("part4", { root_cause_type: v })} disabled={closed} testid="p4-rc-type" />
            </FieldRow>
            <FieldRow label="c) If assignable, root cause (6M)">
              <CheckGroup options={["Method", "Manpower", "Machine", "Material", "Measurement", "Mother Nature", "Other"]} value={p4.root_cause_6m || []} onChange={(v) => updatePart("part4", { root_cause_6m: v })} multi disabled={closed || p4.root_cause_type !== "Assignable"} />
              {(p4.root_cause_6m || []).includes("Other") && (
                <Input className="mt-2" placeholder="Specify other root cause" value={p4.root_cause_other || ""} onChange={(e) => updatePart("part4", { root_cause_other: e.target.value })} disabled={closed} />
              )}
            </FieldRow>
            {!closed && <Button size="sm" onClick={() => savePart("part4")} className="mt-3 bg-slate-900 hover:bg-slate-800 text-white" data-testid="p4-save">Save Part 4</Button>}
          </AccordionContent>
        </AccordionItem>

        {/* PART 5 */}
        <AccordionItem value="part5" className="border border-slate-200 rounded-sm bg-white">
          <AccordionTrigger className="px-4 py-2 text-sm font-semibold">{PARTS[4][1]}</AccordionTrigger>
          <AccordionContent className="px-4 pb-4">
            <FieldRow label="a) Corrective actions (multiple)">
              <CheckGroup options={["Data exclusion", "Documentation/correction", "Procedure revision/amendment", "Project/Study termination", "Reperforming affected activities", "Other"]} value={p5.corrective_actions || []} onChange={(v) => updatePart("part5", { corrective_actions: v })} multi disabled={closed} />
              {(p5.corrective_actions || []).includes("Other") && (
                <Input className="mt-2" placeholder="Specify" value={p5.corrective_other || ""} onChange={(e) => updatePart("part5", { corrective_other: e.target.value })} disabled={closed} />
              )}
            </FieldRow>
            <FieldRow label="b) Description">
              <Textarea rows={3} value={p5.corrective_description || ""} onChange={(e) => updatePart("part5", { corrective_description: e.target.value })} disabled={closed} />
            </FieldRow>
            {!closed && <Button size="sm" onClick={() => savePart("part5")} className="mt-3 bg-slate-900 hover:bg-slate-800 text-white" data-testid="p5-save">Save Part 5</Button>}
          </AccordionContent>
        </AccordionItem>

        {/* PART 6 */}
        <AccordionItem value="part6" className="border border-slate-200 rounded-sm bg-white">
          <AccordionTrigger className="px-4 py-2 text-sm font-semibold">{PARTS[5][1]}</AccordionTrigger>
          <AccordionContent className="px-4 pb-4">
            <FieldRow label="a) Preventive actions (multiple)">
              <CheckGroup options={["Training", "Change in systems", "Change in procedures", "Software upgrade/change", "Enhanced oversight", "Further calibration/validation", "Other"]} value={p6.preventive_actions || []} onChange={(v) => updatePart("part6", { preventive_actions: v })} multi disabled={partLocked("part6")} />
              {(p6.preventive_actions || []).includes("Other") && (
                <Input className="mt-2" placeholder="Specify" value={p6.preventive_other || ""} onChange={(e) => updatePart("part6", { preventive_other: e.target.value })} disabled={partLocked("part6")} />
              )}
            </FieldRow>
            <FieldRow label="b) Description">
              <Textarea rows={3} value={p6.preventive_description || ""} onChange={(e) => updatePart("part6", { preventive_description: e.target.value })} disabled={partLocked("part6")} />
            </FieldRow>
            <div className="flex gap-2 mt-3">
              {!partLocked("part6") && <Button size="sm" onClick={() => savePart("part6")} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="p6-save">Save Part 6</Button>}
              {canSignBlock({ roles: ["initiator", "admin"] }) && <ESignButton block="part6_recorded_by" label="Recorded By" signed={sigByBlock.part6_recorded_by} disabled={closed} onSigned={(p) => sign("part6_recorded_by", p)} />}
              {canSignBlock({ roles: ["reviewer", "qa_head", "admin"] }) && <ESignButton block="part6_reviewed_by" label="Reviewed By" signed={sigByBlock.part6_reviewed_by} disabled={closed || !sigByBlock.part6_recorded_by} onSigned={(p) => sign("part6_reviewed_by", p)} />}
            </div>
          </AccordionContent>
        </AccordionItem>

        {/* PART 7 — Extensions */}
        <AccordionItem value="part7" className="border border-slate-200 rounded-sm bg-white">
          <AccordionTrigger className="px-4 py-2 text-sm font-semibold">{PARTS[6][1]}</AccordionTrigger>
          <AccordionContent className="px-4 pb-4">
            <ExtensionsManager
              record={record}
              extensions={extensions}
              sigByBlock={sigByBlock}
              roles={roles}
              closed={closed}
              onSigned={sign}
              onReload={reload}
              user={user}
            />
          </AccordionContent>
        </AccordionItem>

        {/* PART 8 */}
        <AccordionItem value="part8" className="border border-slate-200 rounded-sm bg-white">
          <AccordionTrigger className="px-4 py-2 text-sm font-semibold">{PARTS[7][1]}</AccordionTrigger>
          <AccordionContent className="px-4 pb-4">
            <DeptCommentsManager
              record={record}
              comments={p8}
              sigByBlock={sigByBlock}
              roles={roles}
              closed={closed}
              onSigned={sign}
              onReload={reload}
            />
          </AccordionContent>
        </AccordionItem>

        {/* PART 9 */}
        <AccordionItem value="part9" className="border border-slate-200 rounded-sm bg-white">
          <AccordionTrigger className="px-4 py-2 text-sm font-semibold">{PARTS[8][1]}</AccordionTrigger>
          <AccordionContent className="px-4 pb-4">
            <FieldRow label="a) Details completed are acceptable?">
              <CheckGroup options={["Yes", "No"]} value={p9.acceptable} onChange={(v) => updatePart("part9", { acceptable: v })} disabled={partLocked("part9")} testid="p9-acceptable" />
              {p9.acceptable === "No" && <Textarea className="mt-2" rows={2} placeholder="Reason / Comments" value={p9.unacceptable_reason || ""} onChange={(e) => updatePart("part9", { unacceptable_reason: e.target.value })} disabled={partLocked("part9")} />}
            </FieldRow>
            <FieldRow label="b) Communicated to Management">
              <CheckGroup options={["Yes", "No", "Not applicable"]} value={p9.management_communicated} onChange={(v) => updatePart("part9", { management_communicated: v })} disabled={partLocked("part9")} />
            </FieldRow>
            <FieldRow label="c) CAPA closed?">
              <CheckGroup options={["Yes", "No", "Not applicable"]} value={p9.capa_closed} onChange={(v) => updatePart("part9", { capa_closed: v })} disabled={partLocked("part9")} />
            </FieldRow>
            <FieldRow label="d) Other comments">
              <Textarea rows={2} value={p9.other_comments || ""} onChange={(e) => updatePart("part9", { other_comments: e.target.value })} disabled={partLocked("part9")} />
            </FieldRow>
            <FieldRow label="f) Deviation Closure Comments">
              <Textarea rows={3} value={p9.closure_comments || ""} onChange={(e) => updatePart("part9", { closure_comments: e.target.value })} disabled={partLocked("part9")} />
            </FieldRow>
            <FieldRow label="g) Deviation Closure Date">
              <Input type="date" value={p9.closure_date || ""} onChange={(e) => updatePart("part9", { closure_date: e.target.value })} disabled={partLocked("part9")} />
            </FieldRow>
            <FieldRow label="h) CAPA Effectiveness Verification Required">
              <CheckGroup options={["Yes", "No"]} value={p9.effectiveness_verification} onChange={(v) => updatePart("part9", { effectiveness_verification: v })} disabled={partLocked("part9")} />
            </FieldRow>
            <div className="flex gap-2 mt-3 flex-wrap">
              {!partLocked("part9") && <Button size="sm" onClick={() => savePart("part9")} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="p9-save">Save Part 9</Button>}
              {canSignBlock({ roles: ["qa_head", "admin"] }) && <ESignButton block="part9_qa_reviewed_by" label="QA Reviewed" signed={sigByBlock.part9_qa_reviewed_by} disabled={closed} onSigned={(p) => sign("part9_qa_reviewed_by", p)} />}
              {canSignBlock({ roles: ["qa_head", "admin"] }) && <ESignButton block="part9_qa_head_closure" label="QA Head — Close" signed={sigByBlock.part9_qa_head_closure} disabled={closed || !sigByBlock.part9_qa_reviewed_by} onSigned={(p) => sign("part9_qa_head_closure", p)} />}
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}

function ExtensionsManager({ record, extensions, sigByBlock, roles, closed, onSigned, onReload, user }) {
  const [open, setOpen] = useState(false);
  const [date, setDate] = useState("");
  const [just, setJust] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!date || !just) return toast.error("Date and justification are required");
    setBusy(true);
    try {
      await api.post(`/deviations/${record.id}/extensions`, { revised_target_date: date, justification: just, reason: "Closure extension requested" });
      toast.success("Extension requested");
      setOpen(false); setDate(""); setJust("");
      await onReload();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally { setBusy(false); }
  };
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs text-slate-500 mono">{extensions.length} extension(s) requested</div>
        {!closed && (
          <Button size="sm" variant="outline" onClick={() => setOpen(true)} data-testid="ext-new"><Plus size={12} className="mr-1" /> Request extension</Button>
        )}
      </div>
      <ul className="space-y-3">
        {extensions.map((e, i) => {
          const idx = i + 1;
          return (
            <li key={e.id || i} className="border border-slate-200 rounded-sm p-3 bg-slate-50">
              <div className="text-xs text-slate-500 mono">Extension #{idx}</div>
              <div className="text-sm text-slate-900 mt-1">Revised target: <b>{e.revised_target_date}</b></div>
              <div className="text-xs text-slate-700 mt-1 whitespace-pre-wrap">{e.justification}</div>
              <div className="text-[11px] text-slate-500 mono mt-2">Requested by {e.requested_by_name} on {new Date(e.requested_at).toLocaleString()}</div>
              <div className="flex gap-2 mt-3 flex-wrap">
                <ESignButton block={`part7_requested_${idx}`} label={`Requested · Ext #${idx}`} signed={sigByBlock[`part7_requested_${idx}`]} disabled={closed} onSigned={(p) => onSigned(`part7_requested_${idx}`, p)} />
                {hasRole(user, "reviewer", "qa_head", "admin") && (
                  <ESignButton block={`part7_hod_${idx}`} label={`HOD · Ext #${idx}`} signed={sigByBlock[`part7_hod_${idx}`]} disabled={closed || !sigByBlock[`part7_requested_${idx}`]} onSigned={(p) => onSigned(`part7_hod_${idx}`, p)} />
                )}
                {hasRole(user, "qa_head", "admin") && (
                  <ESignButton block={`part7_qa_${idx}`} label={`QA · Ext #${idx}`} signed={sigByBlock[`part7_qa_${idx}`]} disabled={closed || !sigByBlock[`part7_hod_${idx}`]} onSigned={(p) => onSigned(`part7_qa_${idx}`, p)} />
                )}
              </div>
            </li>
          );
        })}
      </ul>

      {open && (
        <div className="fixed inset-0 bg-slate-900/50 z-50 flex items-center justify-center p-4" onClick={() => setOpen(false)}>
          <div className="bg-white border border-slate-200 rounded-sm shadow-2xl w-full max-w-md p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <div className="font-semibold text-slate-900">Request closure extension</div>
              <button onClick={() => setOpen(false)} className="text-slate-500 hover:text-slate-900"><X size={16} /></button>
            </div>
            <Label className="text-[10px] uppercase tracking-wide text-slate-500 mono">a) Revised Target Completion Date</Label>
            <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} data-testid="ext-date" />
            <Label className="text-[10px] uppercase tracking-wide text-slate-500 mono mt-2">b) Reason / Justification</Label>
            <Textarea rows={3} value={just} onChange={(e) => setJust(e.target.value)} data-testid="ext-just" />
            <div className="flex justify-end gap-2 mt-3">
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={submit} disabled={busy} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="ext-submit">{busy ? "Submitting…" : "Submit"}</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DeptCommentsManager({ record, comments, sigByBlock, roles, closed, onSigned, onReload }) {
  const [open, setOpen] = useState(false);
  const [dept, setDept] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!dept || !body) return toast.error("Department and comments are required");
    setBusy(true);
    try {
      await api.post(`/deviations/${record.id}/department-comments`, { department: dept, comments: body, reason: "Other-department comment" });
      toast.success("Comment recorded");
      setOpen(false); setDept(""); setBody("");
      await onReload();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally { setBusy(false); }
  };
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs text-slate-500 mono">{comments.length} comment(s)</div>
        {!closed && <Button size="sm" variant="outline" onClick={() => setOpen(true)} data-testid="dept-new"><Plus size={12} className="mr-1" /> Add department comment</Button>}
      </div>
      <ul className="space-y-3">
        {comments.map((c, i) => {
          const idx = i + 1;
          return (
            <li key={c.id || i} className="border border-slate-200 rounded-sm p-3 bg-slate-50">
              <div className="text-xs text-slate-500 mono">Department #{idx} · {c.department}</div>
              <div className="text-sm text-slate-900 mt-1 whitespace-pre-wrap">{c.comments}</div>
              <div className="text-[11px] text-slate-500 mono mt-2">By {c.by_user_name} on {new Date(c.at).toLocaleString()}</div>
              <div className="mt-2">
                <ESignButton block={`part8_dept_${idx}`} label={`Sign · ${c.department}`} signed={sigByBlock[`part8_dept_${idx}`]} disabled={closed} onSigned={(p) => onSigned(`part8_dept_${idx}`, p)} />
              </div>
            </li>
          );
        })}
      </ul>
      <p className="text-[11px] text-slate-500 italic mt-3">Note: Communication of review / comments can be received by an email. In such cases, append mail communication with the form.</p>

      {open && (
        <div className="fixed inset-0 bg-slate-900/50 z-50 flex items-center justify-center p-4" onClick={() => setOpen(false)}>
          <div className="bg-white border border-slate-200 rounded-sm shadow-2xl w-full max-w-md p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <div className="font-semibold text-slate-900">Add department comment</div>
              <button onClick={() => setOpen(false)} className="text-slate-500 hover:text-slate-900"><X size={16} /></button>
            </div>
            <Label className="text-[10px] uppercase tracking-wide text-slate-500 mono">Department</Label>
            <Input value={dept} onChange={(e) => setDept(e.target.value)} data-testid="dept-name" />
            <Label className="text-[10px] uppercase tracking-wide text-slate-500 mono mt-2">Comments / Remarks</Label>
            <Textarea rows={3} value={body} onChange={(e) => setBody(e.target.value)} data-testid="dept-body" />
            <div className="flex justify-end gap-2 mt-3">
              <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
              <Button onClick={submit} disabled={busy} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="dept-submit">{busy ? "Saving…" : "Save"}</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
