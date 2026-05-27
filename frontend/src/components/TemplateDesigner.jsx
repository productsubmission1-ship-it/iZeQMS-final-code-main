import React, { useEffect, useState, useMemo } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Switch } from "./ui/switch";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import { Plus, Trash2, ArrowUp, ArrowDown, GitBranch, FileType, FileText, Settings as SettingsIcon } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiError } from "../lib/api";

const STAGE_COLORS = ["#94A3B8", "#2563EB", "#D97706", "#059669", "#DC2626", "#7C3AED", "#0EA5E9"];

function emptyTemplate(plants) {
  return {
    code: "",
    name: "",
    description: "",
    category: "CUSTOM",
    plant_id: "GLOBAL",
    workflow: {
      stages: [
        { key: "INITIATION", label: "Initiation", color: "#94A3B8" },
        { key: "REVIEW", label: "Review", color: "#2563EB" },
        { key: "APPROVAL", label: "Approval", color: "#D97706" },
        { key: "CLOSED", label: "Closed", color: "#059669" },
        { key: "REJECTED", label: "Rejected", color: "#DC2626" },
      ],
      initial_stage: "INITIATION",
      transitions: [
        { key: "SUBMIT", from: "INITIATION", to: "REVIEW", label: "Submit", required_perm: null, esignature: true },
        { key: "REVIEW", from: "REVIEW", to: "APPROVAL", label: "Review", required_perm: "review_record", esignature: true },
        { key: "APPROVE", from: "APPROVAL", to: "CLOSED", label: "Approve & close", required_perm: "approve_record", esignature: true },
        { key: "REJECT", from: "REVIEW", to: "REJECTED", label: "Reject", required_perm: "reject_record", esignature: true },
        { key: "REOPEN", from: "REJECTED", to: "INITIATION", label: "Reopen", required_perm: null, esignature: true },
      ],
    },
    form: {
      sections: [
        {
          key: "general", label: "General",
          fields: [
            { key: "description", label: "Description", type: "textarea", required: true },
            { key: "department", label: "Department", type: "department", required: true },
            { key: "severity", label: "Severity", type: "dropdown", options: ["Low", "Medium", "High", "Critical"], required: true },
            { key: "due_date", label: "Due date", type: "date" },
          ],
        },
      ],
    },
    pdf_template: {
      header: { title: "{{template.name}}", show_logo: true, show_record_number: true },
      sections: [
        { key: "summary", label: "Record Summary", show_fields: ["description", "department", "severity", "due_date"] },
        { key: "workflow", label: "Workflow Timeline", show_history: true },
        { key: "signatures", label: "Electronic Signatures", show_signatures: true },
        { key: "audit", label: "Audit Trail", show_audit: true },
      ],
      footer: { text: "21 CFR Part 11 · EU Annex 11 · ALCOA++" },
    },
    approvals: [],
    role_mapping: {},
    notes: "",
  };
}

const FIELD_TYPES = [
  { key: "text", label: "Short text" },
  { key: "textarea", label: "Long text / Comment" },
  { key: "number", label: "Number" },
  { key: "date", label: "Date" },
  { key: "datetime", label: "Date & Time" },
  { key: "dropdown", label: "Dropdown" },
  { key: "multiselect", label: "Multi-select" },
  { key: "checkbox", label: "Checkbox" },
  { key: "radio", label: "Radio group" },
  { key: "attachment", label: "File attachment" },
  { key: "signature", label: "E-signature" },
  { key: "approval", label: "Approval block" },
  { key: "user_picker", label: "User picker" },
  { key: "department", label: "Department" },
];

export default function TemplateDesigner({ open, onOpenChange, template, plants, onSaved, canManage }) {
  const isEdit = !!template?.id;
  const isReadOnly = isEdit && template?.status !== "DRAFT";
  const [form, setForm] = useState(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [presetSource, setPresetSource] = useState(null);
  const [loadingPreset, setLoadingPreset] = useState(false);

  useEffect(() => {
    if (!open) return;
    if (isEdit) setForm(JSON.parse(JSON.stringify(template)));
    else setForm(emptyTemplate(plants));
    setReason("");
    setPresetSource(null);
  }, [open, template, plants, isEdit]);

  // When the admin picks a category in NEW mode, pre-fill workflow/form/PDF
  // /roles from the matching seeded compliant template (the current PDF-aligned
  // default). This avoids forcing admins to rebuild standard forms from
  // scratch. Editing a published template is read-only here so we skip.
  const applyCategoryPreset = async (cat) => {
    if (isEdit || isReadOnly) return;
    if (!cat || cat === "CUSTOM") {
      setPresetSource(null);
      // Reset to the empty starter when switching back to Custom
      setForm((p) => {
        const fresh = emptyTemplate(plants);
        return {
          ...p,
          category: "CUSTOM",
          workflow: fresh.workflow,
          form: fresh.form,
          pdf_template: fresh.pdf_template,
          approvals: fresh.approvals,
          role_mapping: fresh.role_mapping,
        };
      });
      return;
    }
    setLoadingPreset(true);
    try {
      const { data } = await api.get("/module-framework/category-preset", { params: { category: cat } });
      if (data?.preset) {
        setPresetSource(data.source || null);
        setForm((p) => ({
          ...p,
          category: cat,
          workflow: data.preset.workflow || p.workflow,
          form: data.preset.form || p.form,
          pdf_template: data.preset.pdf_template || p.pdf_template,
          approvals: data.preset.approvals || [],
          role_mapping: data.preset.role_mapping || {},
          notes: p.notes || data.preset.notes || "",
        }));
        toast.success(`Pre-filled from ${data.source?.code || cat} (v${data.source?.version || 1}) — fully editable`);
      } else {
        setPresetSource(null);
        setForm((p) => ({ ...p, category: cat }));
        toast.info("No default template found for this category — starting blank");
      }
    } catch (e) {
      setForm((p) => ({ ...p, category: cat }));
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setLoadingPreset(false);
    }
  };

  if (!open || !form) return null;

  // Workflow helpers
  const addStage = () => {
    const idx = (form.workflow.stages || []).length;
    setForm((p) => ({
      ...p,
      workflow: {
        ...p.workflow,
        stages: [...(p.workflow.stages || []), {
          key: `STAGE_${idx + 1}`, label: `Stage ${idx + 1}`,
          color: STAGE_COLORS[idx % STAGE_COLORS.length],
        }],
      },
    }));
  };
  const removeStage = (i) => {
    const stages = [...form.workflow.stages]; stages.splice(i, 1);
    setForm((p) => ({ ...p, workflow: { ...p.workflow, stages } }));
  };
  const updateStage = (i, field, val) => {
    const stages = [...form.workflow.stages];
    stages[i] = { ...stages[i], [field]: val };
    setForm((p) => ({ ...p, workflow: { ...p.workflow, stages } }));
  };
  const addTransition = () => {
    setForm((p) => ({
      ...p,
      workflow: {
        ...p.workflow,
        transitions: [...(p.workflow.transitions || []), {
          key: `T_${(p.workflow.transitions || []).length + 1}`,
          from: p.workflow.stages?.[0]?.key || "INITIATION",
          to: p.workflow.stages?.[1]?.key || "REVIEW",
          label: "Transition",
          required_perm: null, esignature: true,
        }],
      },
    }));
  };
  const removeTransition = (i) => {
    const transitions = [...form.workflow.transitions]; transitions.splice(i, 1);
    setForm((p) => ({ ...p, workflow: { ...p.workflow, transitions } }));
  };
  const updateTransition = (i, field, val) => {
    const transitions = [...form.workflow.transitions];
    transitions[i] = { ...transitions[i], [field]: val };
    setForm((p) => ({ ...p, workflow: { ...p.workflow, transitions } }));
  };

  // Form helpers
  const addSection = () => {
    const idx = (form.form.sections || []).length;
    setForm((p) => ({ ...p, form: { ...p.form, sections: [...(p.form.sections || []), { key: `section_${idx + 1}`, label: `Section ${idx + 1}`, fields: [] }] } }));
  };
  const removeSection = (i) => {
    const sections = [...form.form.sections]; sections.splice(i, 1);
    setForm((p) => ({ ...p, form: { ...p.form, sections } }));
  };
  const updateSection = (i, field, val) => {
    const sections = [...form.form.sections];
    sections[i] = { ...sections[i], [field]: val };
    setForm((p) => ({ ...p, form: { ...p.form, sections } }));
  };
  const addField = (si) => {
    const sections = [...form.form.sections];
    const fields = [...(sections[si].fields || [])];
    fields.push({ key: `field_${fields.length + 1}`, label: `Field ${fields.length + 1}`, type: "text", required: false });
    sections[si] = { ...sections[si], fields };
    setForm((p) => ({ ...p, form: { ...p.form, sections } }));
  };
  const removeField = (si, fi) => {
    const sections = [...form.form.sections];
    const fields = [...sections[si].fields]; fields.splice(fi, 1);
    sections[si] = { ...sections[si], fields };
    setForm((p) => ({ ...p, form: { ...p.form, sections } }));
  };
  const updateField = (si, fi, key, val) => {
    const sections = [...form.form.sections];
    const fields = [...sections[si].fields];
    fields[fi] = { ...fields[fi], [key]: val };
    sections[si] = { ...sections[si], fields };
    setForm((p) => ({ ...p, form: { ...p.form, sections } }));
  };
  const moveField = (si, fi, dir) => {
    const sections = [...form.form.sections];
    const fields = [...sections[si].fields];
    const ni = fi + dir; if (ni < 0 || ni >= fields.length) return;
    [fields[fi], fields[ni]] = [fields[ni], fields[fi]];
    sections[si] = { ...sections[si], fields };
    setForm((p) => ({ ...p, form: { ...p.form, sections } }));
  };

  const save = async () => {
    if (isReadOnly) return;
    if (!form.code || form.code.length < 2) return toast.error("Code is required");
    if (!form.name || form.name.length < 2) return toast.error("Name is required");
    if (isEdit && (!reason || reason.length < 3)) return toast.error("Reason required");
    setBusy(true);
    try {
      if (isEdit) {
        await api.patch(`/module-framework/templates/${template.id}`, {
          name: form.name, description: form.description, workflow: form.workflow,
          form: form.form, pdf_template: form.pdf_template, approvals: form.approvals,
          role_mapping: form.role_mapping, notes: form.notes, reason,
        });
        toast.success("Template draft updated");
      } else {
        await api.post(`/module-framework/templates`, {
          code: form.code, name: form.name, description: form.description, category: form.category,
          plant_id: form.plant_id === "GLOBAL" ? null : form.plant_id,
          workflow: form.workflow, form: form.form, pdf_template: form.pdf_template,
          approvals: form.approvals, role_mapping: form.role_mapping, notes: form.notes,
        });
        toast.success("Template created (DRAFT)");
      }
      onSaved?.();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail) || e.message); }
    finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-6xl max-h-[92vh] flex flex-col" data-testid="template-designer">
        <DialogHeader>
          <DialogTitle data-testid="designer-title">
            {isEdit
              ? `${isReadOnly ? "View" : "Edit"} template: ${template.name} (v${template.version}, ${template.status})`
              : "New module template"}
          </DialogTitle>
          <DialogDescription>
            {isReadOnly
              ? "Published / Retired templates are immutable. Copy to a new version to make changes."
              : "Design workflow + form + PDF layout. Save as DRAFT; publish when validated."}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto pr-1">
          {/* Identity */}
          <section className="space-y-3 pb-4 border-b border-slate-200">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-slate-600">Code *</label>
                <Input value={form.code} disabled={isEdit} onChange={(e) => setForm((p) => ({ ...p, code: e.target.value.toLowerCase().replace(/\s+/g, "_") }))} data-testid="tpl-code" />
              </div>
              <div>
                <label className="text-xs text-slate-600">Name *</label>
                <Input value={form.name} disabled={isReadOnly} onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} data-testid="tpl-name" />
              </div>
              <div>
                <label className="text-xs text-slate-600">Category</label>
                <Select value={form.category} onValueChange={applyCategoryPreset} disabled={isEdit}>
                  <SelectTrigger data-testid="tpl-category"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="CUSTOM">Custom</SelectItem>
                    <SelectItem value="DEVIATION">Deviation-like</SelectItem>
                    <SelectItem value="CAPA">CAPA-like</SelectItem>
                    <SelectItem value="CHANGE_CONTROL">Change Control-like</SelectItem>
                    <SelectItem value="INCIDENT">Incident-like</SelectItem>
                    <SelectItem value="EVENT">Event-like</SelectItem>
                  </SelectContent>
                </Select>
                {loadingPreset && (
                  <div className="text-[10px] text-slate-500 mt-1 mono">Loading default…</div>
                )}
                {presetSource && !loadingPreset && (
                  <div className="text-[10px] text-indigo-700 mt-1 mono" data-testid="tpl-preset-source">
                    Pre-filled from <b>{presetSource.code}</b> v{presetSource.version}
                  </div>
                )}
              </div>
              <div className="hidden">
                <Select value={form.plant_id || "GLOBAL"} onValueChange={(v) => setForm((p) => ({ ...p, plant_id: v }))} disabled={isEdit}>
                  <SelectTrigger data-testid="tpl-plant"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="GLOBAL">Global (all plants)</SelectItem>
                    {(plants || []).map((p) => <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="md:col-span-2">
                <label className="text-xs text-slate-600">Description</label>
                <Input value={form.description} disabled={isReadOnly} onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))} data-testid="tpl-desc" />
              </div>
            </div>
          </section>

          {/* Tabs */}
          <Tabs defaultValue="workflow" className="mt-4">
            <TabsList>
              <TabsTrigger value="workflow" data-testid="tab-workflow"><GitBranch size={13} className="mr-1" />Workflow</TabsTrigger>
              <TabsTrigger value="form" data-testid="tab-form"><FileType size={13} className="mr-1" />Form Fields</TabsTrigger>
              <TabsTrigger value="pdf" data-testid="tab-pdf"><FileText size={13} className="mr-1" />PDF Layout</TabsTrigger>
              <TabsTrigger value="advanced" data-testid="tab-advanced"><SettingsIcon size={13} className="mr-1" />Advanced</TabsTrigger>
            </TabsList>

            {/* Workflow */}
            <TabsContent value="workflow" className="space-y-4 mt-3">
              <div className="border border-slate-200 rounded-sm p-3 bg-white">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-sm font-medium text-slate-900">Stages</div>
                  {!isReadOnly && (
                    <Button size="sm" variant="outline" onClick={addStage} data-testid="add-stage"><Plus size={12} className="mr-1" />Add stage</Button>
                  )}
                </div>
                <div className="space-y-2">
                  {(form.workflow.stages || []).map((s, i) => (
                    <div key={i} className="grid grid-cols-[80px_1fr_1fr_60px_40px] gap-2 items-center" data-testid={`stage-row-${i}`}>
                      <Input value={s.key} disabled={isReadOnly} onChange={(e) => updateStage(i, "key", e.target.value.toUpperCase().replace(/\s+/g, "_"))} className="mono text-xs" />
                      <Input value={s.label} disabled={isReadOnly} onChange={(e) => updateStage(i, "label", e.target.value)} placeholder="Display label" />
                      <Input value={s.color} disabled={isReadOnly} onChange={(e) => updateStage(i, "color", e.target.value)} placeholder="#colour" className="mono text-xs" />
                      <div className="w-6 h-6 rounded-sm border border-slate-200" style={{ background: s.color }} />
                      {!isReadOnly && (<button onClick={() => removeStage(i)} className="text-rose-600 p-1"><Trash2 size={14} /></button>)}
                    </div>
                  ))}
                </div>
              </div>

              <div className="border border-slate-200 rounded-sm p-3 bg-white">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-sm font-medium text-slate-900">Transitions</div>
                  {!isReadOnly && (
                    <Button size="sm" variant="outline" onClick={addTransition} data-testid="add-transition"><Plus size={12} className="mr-1" />Add transition</Button>
                  )}
                </div>
                <div className="space-y-2">
                  {(form.workflow.transitions || []).map((t, i) => (
                    <div key={i} className="grid grid-cols-[100px_1fr_1fr_1fr_150px_60px_40px] gap-2 items-center" data-testid={`transition-row-${i}`}>
                      <Input value={t.key} disabled={isReadOnly} onChange={(e) => updateTransition(i, "key", e.target.value.toUpperCase().replace(/\s+/g, "_"))} className="mono text-xs" />
                      <Select value={t.from} onValueChange={(v) => updateTransition(i, "from", v)} disabled={isReadOnly}>
                        <SelectTrigger><SelectValue placeholder="From" /></SelectTrigger>
                        <SelectContent>{form.workflow.stages.map((s) => <SelectItem key={s.key} value={s.key}>{s.label}</SelectItem>)}</SelectContent>
                      </Select>
                      <Select value={t.to} onValueChange={(v) => updateTransition(i, "to", v)} disabled={isReadOnly}>
                        <SelectTrigger><SelectValue placeholder="To" /></SelectTrigger>
                        <SelectContent>{form.workflow.stages.map((s) => <SelectItem key={s.key} value={s.key}>{s.label}</SelectItem>)}</SelectContent>
                      </Select>
                      <Input value={t.label} disabled={isReadOnly} onChange={(e) => updateTransition(i, "label", e.target.value)} placeholder="Button label" />
                      <Input value={t.required_perm || ""} disabled={isReadOnly} onChange={(e) => updateTransition(i, "required_perm", e.target.value || null)} placeholder="e.g. review_record" className="mono text-xs" />
                      <div className="flex items-center gap-1">
                        <Switch checked={!!t.esignature} onCheckedChange={(v) => updateTransition(i, "esignature", v)} disabled={isReadOnly} />
                        <span className="text-[10px] mono text-slate-500">e-sig</span>
                      </div>
                      {!isReadOnly && (<button onClick={() => removeTransition(i)} className="text-rose-600 p-1"><Trash2 size={14} /></button>)}
                    </div>
                  ))}
                </div>
              </div>
            </TabsContent>

            {/* Form fields */}
            <TabsContent value="form" className="space-y-4 mt-3">
              {(form.form.sections || []).map((sec, si) => (
                <div key={si} className="border border-slate-200 rounded-sm bg-white" data-testid={`form-section-${si}`}>
                  <div className="px-3 py-2 border-b border-slate-100 bg-slate-50 flex items-center gap-2">
                    <Input value={sec.key} disabled={isReadOnly} onChange={(e) => updateSection(si, "key", e.target.value.toLowerCase().replace(/\s+/g, "_"))} className="mono text-xs w-40" />
                    <Input value={sec.label} disabled={isReadOnly} onChange={(e) => updateSection(si, "label", e.target.value)} placeholder="Section label" className="flex-1" />
                    {!isReadOnly && (
                      <>
                        <Button size="sm" variant="outline" onClick={() => addField(si)} data-testid={`add-field-${si}`}><Plus size={12} className="mr-1" />Field</Button>
                        <button onClick={() => removeSection(si)} className="text-rose-600 p-1"><Trash2 size={14} /></button>
                      </>
                    )}
                  </div>
                  <div className="p-3 space-y-1">
                    {(sec.fields || []).map((f, fi) => (
                      <div key={fi} className="grid grid-cols-[100px_1fr_140px_80px_1fr_60px_60px] gap-2 items-center" data-testid={`field-row-${si}-${fi}`}>
                        <Input value={f.key} disabled={isReadOnly} onChange={(e) => updateField(si, fi, "key", e.target.value.toLowerCase().replace(/\s+/g, "_"))} className="mono text-xs" />
                        <Input value={f.label} disabled={isReadOnly} onChange={(e) => updateField(si, fi, "label", e.target.value)} />
                        <Select value={f.type} onValueChange={(v) => updateField(si, fi, "type", v)} disabled={isReadOnly}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>{FIELD_TYPES.map((t) => <SelectItem key={t.key} value={t.key}>{t.label}</SelectItem>)}</SelectContent>
                        </Select>
                        <label className="flex items-center gap-1 text-[10px] mono text-slate-600">
                          <Switch checked={!!f.required} onCheckedChange={(v) => updateField(si, fi, "required", v)} disabled={isReadOnly} />
                          required
                        </label>
                        <Input
                          value={(f.options || []).join(", ")} disabled={isReadOnly}
                          onChange={(e) => updateField(si, fi, "options", e.target.value.split(",").map(s => s.trim()).filter(Boolean))}
                          placeholder={(f.type === "dropdown" || f.type === "radio" || f.type === "multiselect") ? "Options (comma-separated)" : "—"}
                        />
                        <div className="flex gap-0.5">
                          {!isReadOnly && (
                            <>
                              <button onClick={() => moveField(si, fi, -1)} className="p-1 hover:bg-slate-100 rounded-sm"><ArrowUp size={12} /></button>
                              <button onClick={() => moveField(si, fi, 1)} className="p-1 hover:bg-slate-100 rounded-sm"><ArrowDown size={12} /></button>
                            </>
                          )}
                        </div>
                        {!isReadOnly && (<button onClick={() => removeField(si, fi)} className="text-rose-600 p-1"><Trash2 size={14} /></button>)}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
              {!isReadOnly && (
                <Button variant="outline" onClick={addSection} data-testid="add-section"><Plus size={12} className="mr-1" />Add section</Button>
              )}
            </TabsContent>

            {/* PDF */}
            <TabsContent value="pdf" className="space-y-4 mt-3">
              <div className="border border-slate-200 rounded-sm p-3 bg-white space-y-3">
                <div>
                  <label className="text-xs text-slate-600">Header title</label>
                  <Input value={form.pdf_template?.header?.title || ""} disabled={isReadOnly}
                    onChange={(e) => setForm((p) => ({ ...p, pdf_template: { ...p.pdf_template, header: { ...p.pdf_template?.header, title: e.target.value } } }))}
                    data-testid="pdf-header-title" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <label className="flex items-center justify-between border border-slate-200 rounded-sm px-3 py-2">
                    <span className="text-sm">Show logo</span>
                    <Switch checked={!!form.pdf_template?.header?.show_logo} disabled={isReadOnly}
                      onCheckedChange={(v) => setForm((p) => ({ ...p, pdf_template: { ...p.pdf_template, header: { ...p.pdf_template?.header, show_logo: v } } }))} />
                  </label>
                  <label className="flex items-center justify-between border border-slate-200 rounded-sm px-3 py-2">
                    <span className="text-sm">Show record number</span>
                    <Switch checked={!!form.pdf_template?.header?.show_record_number} disabled={isReadOnly}
                      onCheckedChange={(v) => setForm((p) => ({ ...p, pdf_template: { ...p.pdf_template, header: { ...p.pdf_template?.header, show_record_number: v } } }))} />
                  </label>
                </div>
                <div>
                  <label className="text-xs text-slate-600">Footer text</label>
                  <Input value={form.pdf_template?.footer?.text || ""} disabled={isReadOnly}
                    onChange={(e) => setForm((p) => ({ ...p, pdf_template: { ...p.pdf_template, footer: { text: e.target.value } } }))}
                    data-testid="pdf-footer" />
                </div>
                <div>
                  <label className="text-xs text-slate-600">PDF sections (JSON)</label>
                  <Textarea
                    rows={6}
                    value={JSON.stringify(form.pdf_template?.sections || [], null, 2)}
                    disabled={isReadOnly}
                    onChange={(e) => {
                      try {
                        const sections = JSON.parse(e.target.value);
                        setForm((p) => ({ ...p, pdf_template: { ...p.pdf_template, sections } }));
                      } catch { /* ignore until valid */ }
                    }}
                    className="mono text-[11px]"
                    data-testid="pdf-sections-json"
                  />
                </div>
              </div>
            </TabsContent>

            {/* Advanced */}
            <TabsContent value="advanced" className="space-y-4 mt-3">
              <div className="border border-slate-200 rounded-sm p-3 bg-white space-y-3">
                <div>
                  <label className="text-xs text-slate-600">Approvals (JSON, e.g. <code>[{"{level:1, role:'qa_manager'}"}]</code>)</label>
                  <Textarea
                    rows={4}
                    value={JSON.stringify(form.approvals || [], null, 2)}
                    disabled={isReadOnly}
                    onChange={(e) => { try { setForm((p) => ({ ...p, approvals: JSON.parse(e.target.value) })); } catch { } }}
                    className="mono text-[11px]" data-testid="approvals-json"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-600">Role mapping (JSON, stage_key → [role_codes])</label>
                  <Textarea
                    rows={4}
                    value={JSON.stringify(form.role_mapping || {}, null, 2)}
                    disabled={isReadOnly}
                    onChange={(e) => { try { setForm((p) => ({ ...p, role_mapping: JSON.parse(e.target.value) })); } catch { } }}
                    className="mono text-[11px]" data-testid="role-mapping-json"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-600">Notes</label>
                  <Textarea rows={2} value={form.notes || ""} disabled={isReadOnly} onChange={(e) => setForm((p) => ({ ...p, notes: e.target.value }))} data-testid="tpl-notes" />
                </div>
              </div>
            </TabsContent>
          </Tabs>

          {isEdit && !isReadOnly && (
            <div className="mt-4">
              <label className="text-xs text-slate-600">Reason for change *</label>
              <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Added rejection comment field per QA review" data-testid="tpl-reason" />
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="designer-cancel">Close</Button>
          {!isReadOnly && (
            <Button onClick={save} disabled={busy || !canManage} className="bg-slate-900 text-white hover:bg-slate-800" data-testid="designer-save">
              {busy ? "Saving…" : isEdit ? "Save draft" : "Create draft"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
