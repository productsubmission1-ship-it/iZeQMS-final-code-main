import React, { useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "../components/ui/dialog";
import { Switch } from "../components/ui/switch";
import { toast } from "sonner";
import { ArrowLeft, Plus, FileDown, ArrowUpCircle } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { hasPermission } from "../lib/roles";

/**
 * Renders a single field. If the field's options array contains "Other",
 * selecting it opens an inline text input so the user can capture a
 * custom value. The value is then stored as
 *     { value: "Other", other: "<custom text>" }
 * which the PDF generator already handles.
 */
function FieldInput({ f, value, onChange, disabled, roleOptions }) {
  // Drop-down with "Other" handling
  const hasOther = Array.isArray(f.options) && f.options.includes("Other");

  // Effective options (centralised dropdowns when the field is named role / department / location)
  let effectiveOptions = f.options || [];
  if ((f.key === "role" || f.key === "user_role") && (!effectiveOptions.length || (effectiveOptions.length === 1 && effectiveOptions[0] === "Other"))) {
    effectiveOptions = [...roleOptions, ...effectiveOptions];
  }

  const isOtherSelected =
    value && typeof value === "object" && value.value === "Other";
  const selectValue = isOtherSelected ? "Other" : (typeof value === "string" ? value : "");

  switch (f.type) {
    case "textarea":
    case "comment":
      return <Textarea rows={3} value={value || ""} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
    case "number":
      return <Input type="number" value={value ?? ""} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
    case "date":
      return <Input type="date" value={value || ""} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
    case "datetime":
      return <Input type="datetime-local" value={value || ""} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
    case "dropdown":
    case "department":
      return (
        <div className="space-y-2">
          <Select
            value={selectValue}
            onValueChange={(v) => {
              if (v === "Other" && hasOther) {
                onChange({ value: "Other", other: (typeof value === "object" ? value?.other : "") || "" });
              } else {
                onChange(v);
              }
            }}
            disabled={disabled}
          >
            <SelectTrigger data-testid={`field-${f.key}`}><SelectValue placeholder="Select…" /></SelectTrigger>
            <SelectContent>
              {(effectiveOptions.length ? effectiveOptions : (f.type === "department" ? ["Quality Assurance", "Production", "Engineering", "IT", "Compliance"] : [])).map((o) =>
                <SelectItem key={o} value={o}>{o}</SelectItem>
              )}
            </SelectContent>
          </Select>
          {isOtherSelected && (
            <Input
              placeholder="Please specify…"
              value={value?.other || ""}
              disabled={disabled}
              onChange={(e) => onChange({ value: "Other", other: e.target.value })}
              data-testid={`field-${f.key}-other`}
            />
          )}
        </div>
      );
    case "multiselect":
      return (
        <Input
          value={(Array.isArray(value) ? value : []).join(", ")}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
          placeholder="comma-separated values"
        />
      );
    case "checkbox":
      return <Switch checked={!!value} disabled={disabled} onCheckedChange={onChange} />;
    case "radio":
      return (
        <div className="flex gap-3 flex-wrap items-center">
          {(f.options || []).map((o) => (
            <label key={o} className="flex items-center gap-1 text-xs">
              <input
                type="radio"
                name={f.key}
                checked={(isOtherSelected ? "Other" : value) === o}
                disabled={disabled}
                onChange={() => {
                  if (o === "Other") {
                    onChange({ value: "Other", other: (typeof value === "object" ? value?.other : "") || "" });
                  } else { onChange(o); }
                }}
              />
              <span>{o}</span>
            </label>
          ))}
          {isOtherSelected && (
            <Input
              className="max-w-xs"
              placeholder="Please specify…"
              value={value?.other || ""}
              disabled={disabled}
              onChange={(e) => onChange({ value: "Other", other: e.target.value })}
              data-testid={`field-${f.key}-other`}
            />
          )}
        </div>
      );
    case "attachment":
      return <div className="text-[11px] mono text-slate-500 border border-dashed border-slate-300 rounded-sm p-2">Attachment upload (placeholder)</div>;
    case "signature":
      return <div className="text-[11px] mono text-slate-500 border border-dashed border-slate-300 rounded-sm p-2">E-signature applied on transition</div>;
    case "approval":
      return <div className="text-[11px] mono text-slate-500 border border-dashed border-slate-300 rounded-sm p-2">Approval block — managed via workflow</div>;
    case "user_picker":
      return <Input value={value || ""} disabled={disabled} onChange={(e) => onChange(e.target.value)} placeholder="User email" />;
    default:
      return <Input value={value || ""} disabled={disabled} onChange={(e) => onChange(e.target.value)} />;
  }
}

export default function DynamicRecords() {
  const { template_id } = useParams();
  const { user: me } = useAuth();
  const [template, setTemplate] = useState(null);
  const [latestPublished, setLatestPublished] = useState(null);
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ title: "", form_data: {}, reason: "" });
  const [active, setActive] = useState(null);
  const [transitionForm, setTransitionForm] = useState({ to_stage: "", password: "", reason: "", comment: "" });
  const [dynamicPlantId, setDynamicPlantId] = useState(null); // Auto-resolved plant
  const [roleOptions, setRoleOptions] = useState([]);

  const canDownload = hasPermission(me, "export_reports") || hasPermission(me, "view_reports");
  const canMigrate = hasPermission(me, "manage_module_templates");

  const load = async () => {
    setLoading(true);
    try {
      const [t, r, rolesRes] = await Promise.all([
        api.get(`/module-framework/templates/${template_id}`),
        api.get(`/module-framework/records?template_id=${template_id}`),
        api.get("/role-mgmt/roles?active=true").catch(() => ({ data: [] })),
      ]);
      setTemplate(t.data);
      setRecords(r.data || []);
      // Build role options list (dynamic + canonical names)
      const names = (rolesRes.data || []).map((x) => x.name).filter(Boolean);
      setRoleOptions(Array.from(new Set(names)));
      // Resolve the latest PUBLISHED version for migration check
      try {
        const versions = await api.get(`/module-framework/templates/${t.data.id}/versions`);
        const pub = (versions.data || []).filter((v) => v.status === "PUBLISHED").sort((a, b) => b.version - a.version)[0];
        setLatestPublished(pub || null);
      } catch (e) { setLatestPublished(null); }

      // Auto-pick plant_id from any existing record or use a synthetic "GLOBAL" plant
      const plantsRes = await api.get("/module-framework/plants").catch(() => ({ data: [] }));
      const plants = plantsRes.data || [];
      let pid = null;
      if (t.data?.plant_id && t.data.plant_id !== "GLOBAL") {
        pid = t.data.plant_id;
      } else if (plants.length) {
        pid = (plants.find((p) => p.active) || plants[0])?.id || null;
      }
      setDynamicPlantId(pid);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [template_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const fieldsFlat = useMemo(() => {
    if (!template?.form?.sections) return [];
    return template.form.sections.flatMap((s) => (s.fields || []).map((f) => ({ ...f, section: s.label })));
  }, [template]);

  const create = async () => {
    if (!createForm.title) return toast.error("Title required");
    if (!createForm.reason || createForm.reason.length < 3) return toast.error("Reason required");
    if (!dynamicPlantId) return toast.error("No active plant available. Please contact admin.");
    try {
      await api.post("/module-framework/records", {
        template_id, plant_id: dynamicPlantId,
        title: createForm.title, form_data: createForm.form_data,
        reason: createForm.reason,
      });
      toast.success("Record created");
      setCreateOpen(false);
      setCreateForm({ title: "", form_data: {}, reason: "" });
      load();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail) || e.message); }
  };

  const allowedTransitions = (rec) => {
    const t = template?.workflow?.transitions || [];
    return t.filter((tr) => tr.from === rec.current_stage);
  };

  const transition = async () => {
    if (!transitionForm.to_stage) return toast.error("Pick an action");
    if (!transitionForm.password) return toast.error("Password is required for e-signature");
    if (!transitionForm.reason || transitionForm.reason.length < 3) return toast.error("Reason required");
    try {
      await api.post(`/module-framework/records/${active.id}/transition`, transitionForm);
      toast.success("Record transitioned");
      setActive(null);
      setTransitionForm({ to_stage: "", password: "", reason: "", comment: "" });
      load();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail) || e.message); }
  };

  const downloadPdf = async (rec) => {
    try {
      const res = await api.get(`/module-framework/records/${rec.id}/pdf`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url; a.download = `${rec.record_number || "record"}.pdf`;
      document.body.appendChild(a); a.click();
      a.remove(); window.URL.revokeObjectURL(url);
      toast.success("PDF downloaded — download logged in audit trail");
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  const migrateToLatest = async (rec) => {
    if (!latestPublished || latestPublished.version === rec.template_version) {
      toast.info("Record is already on the latest version");
      return;
    }
    if (!window.confirm(`Migrate ${rec.record_number} from v${rec.template_version} to v${latestPublished.version}?`)) return;
    try {
      const res = await api.post(`/module-framework/records/${rec.id}/migrate-version`);
      toast.success(`Migrated to v${res.data.to_version}`);
      load();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail) || e.message); }
  };

  if (loading) return <div className="text-sm text-slate-500" data-testid="dyn-loading">Loading…</div>;
  if (!template) return <div className="text-sm text-rose-700">Template not found.</div>;

  const stageColor = (s) => template.workflow?.stages?.find((st) => st.key === s)?.color || "#94A3B8";
  const stageLabel = (s) => template.workflow?.stages?.find((st) => st.key === s)?.label || s;
  const hasNewerVersion = (rec) => latestPublished && latestPublished.id !== rec.template_id;

  return (
    <div className="space-y-5" data-testid="dynamic-records-page">
      <div>
        <Link to="/module-framework" className="text-xs text-slate-500 inline-flex items-center gap-1 hover:underline mb-1">
          <ArrowLeft size={12} /> Back to templates
        </Link>
        <div className="flex items-end justify-between mt-1">
          <div>
            <div className="text-[11px] uppercase tracking-wide text-slate-500 mono">{template.code} · v{template.version} · {template.status}</div>
            <h1 className="text-3xl font-semibold text-slate-950 tracking-tight" style={{ fontFamily: "Work Sans" }}>{template.name}</h1>
            <div className="text-xs text-slate-500 mt-1">{template.description}</div>
            {latestPublished && latestPublished.version !== template.version && (
              <div className="text-[11px] mt-1 text-indigo-700 mono">
                A newer PUBLISHED version (v{latestPublished.version}) is available. Existing records can be migrated individually below.
              </div>
            )}
          </div>
          {template.status === "PUBLISHED" && (
            <Button onClick={() => setCreateOpen(true)} className="bg-slate-900 text-white hover:bg-slate-800" data-testid="new-dynamic-record">
              <Plus size={16} className="mr-1" /> New Record
            </Button>
          )}
        </div>
      </div>

      {/* Workflow legend */}
      <div className="border border-slate-200 bg-white rounded-sm p-3">
        <div className="text-[11px] uppercase mono text-slate-500 mb-2">Workflow</div>
        <div className="flex items-center gap-2 flex-wrap">
          {(template.workflow?.stages || []).map((s) => (
            <span key={s.key} className="inline-block px-2 py-0.5 text-[10px] mono font-semibold uppercase rounded-sm" style={{ background: s.color + "22", color: s.color, border: `1px solid ${s.color}55` }}>
              {s.label}
            </span>
          ))}
        </div>
      </div>

      {/* Records */}
      <div className="border border-slate-200 bg-white rounded-sm overflow-x-auto">
        <table className="w-full table-dense">
          <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
            <tr>
              <th className="text-left">Record #</th>
              <th className="text-left">Title</th>
              <th className="text-left">Stage</th>
              <th className="text-left">Tpl. Version</th>
              <th className="text-left">Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {records.length === 0 && <tr><td colSpan={6} className="text-center text-xs text-slate-500 py-6">No records yet.</td></tr>}
            {records.map((r) => (
              <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`dyn-row-${r.record_number}`}>
                <td className="mono text-xs">{r.record_number}</td>
                <td className="text-sm font-medium text-slate-900">{r.title}</td>
                <td>
                  <span className="inline-block px-2 py-0.5 text-[10px] mono font-semibold uppercase rounded-sm" style={{ color: stageColor(r.current_stage), background: stageColor(r.current_stage) + "22", border: `1px solid ${stageColor(r.current_stage)}55` }}>
                    {stageLabel(r.current_stage)}
                  </span>
                </td>
                <td className="text-xs mono">
                  v{r.template_version}
                  {hasNewerVersion(r) && <span className="ml-1 text-[10px] text-indigo-700">(v{latestPublished.version} avail.)</span>}
                </td>
                <td className="text-[11px] mono">{new Date(r.created_at).toLocaleString()}</td>
                <td className="text-right">
                  <div className="flex gap-1 justify-end items-center">
                    {canDownload && (
                      <button onClick={() => downloadPdf(r)} className="p-1.5 hover:bg-slate-200 rounded-sm" title="Download PDF" data-testid={`dyn-pdf-${r.record_number}`}>
                        <FileDown size={14} />
                      </button>
                    )}
                    {canMigrate && hasNewerVersion(r) && (
                      <button onClick={() => migrateToLatest(r)} className="p-1.5 hover:bg-indigo-100 rounded-sm text-indigo-700" title={`Migrate to v${latestPublished.version}`} data-testid={`dyn-migrate-${r.record_number}`}>
                        <ArrowUpCircle size={14} />
                      </button>
                    )}
                    <Button size="sm" variant="outline" onClick={() => { setActive(r); setTransitionForm({ to_stage: "", password: "", reason: "", comment: "" }); }} data-testid={`open-dyn-${r.record_number}`}>
                      Transition
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create record dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="dyn-create-dialog">
          <DialogHeader>
            <DialogTitle>New record · {template.name}</DialogTitle>
            <DialogDescription>Form fields are driven by template v{template.version}.</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-slate-600">Title *</label>
              <Input value={createForm.title} onChange={(e) => setCreateForm((p) => ({ ...p, title: e.target.value }))} data-testid="dyn-title" />
            </div>
            {template.form?.sections?.map((sec) => (
              <div key={sec.key} className="border border-slate-200 rounded-sm p-3 bg-slate-50">
                <div className="text-xs font-medium text-slate-700 mb-2">{sec.label}</div>
                <div className="grid grid-cols-1 gap-3">
                  {(sec.fields || []).map((f) => (
                    <div key={f.key}>
                      <label className="text-xs text-slate-600">{f.label}{f.required && <span className="text-rose-600"> *</span>}</label>
                      <FieldInput
                        f={f}
                        value={createForm.form_data?.[f.key]}
                        onChange={(val) => setCreateForm((p) => ({ ...p, form_data: { ...p.form_data, [f.key]: val } }))}
                        roleOptions={roleOptions}
                      />
                    </div>
                  ))}
                </div>
              </div>
            ))}
            <div>
              <label className="text-xs text-slate-600">Reason *</label>
              <Input value={createForm.reason} onChange={(e) => setCreateForm((p) => ({ ...p, reason: e.target.value }))} placeholder="Why this record is being created" data-testid="dyn-reason" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={create} className="bg-slate-900 text-white" data-testid="dyn-create-submit">Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Transition dialog */}
      <Dialog open={!!active} onOpenChange={(o) => !o && setActive(null)}>
        <DialogContent className="max-w-md" data-testid="dyn-transition-dialog">
          <DialogHeader>
            <DialogTitle>Workflow transition</DialogTitle>
            <DialogDescription>
              {active ? <>{active.record_number} · current stage: <b>{stageLabel(active.current_stage)}</b></> : null}
            </DialogDescription>
          </DialogHeader>
          {active && (
            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-600">Action</label>
                <Select value={transitionForm.to_stage} onValueChange={(v) => setTransitionForm((p) => ({ ...p, to_stage: v }))}>
                  <SelectTrigger data-testid="dyn-to-stage"><SelectValue placeholder="Pick a transition" /></SelectTrigger>
                  <SelectContent>
                    {allowedTransitions(active).map((t) => (
                      <SelectItem key={t.key} value={t.to}>{t.label} → {stageLabel(t.to)}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs text-slate-600">Reason *</label>
                <Input value={transitionForm.reason} onChange={(e) => setTransitionForm((p) => ({ ...p, reason: e.target.value }))} data-testid="dyn-trans-reason" />
              </div>
              <div>
                <label className="text-xs text-slate-600">Comment</label>
                <Textarea rows={2} value={transitionForm.comment} onChange={(e) => setTransitionForm((p) => ({ ...p, comment: e.target.value }))} data-testid="dyn-trans-comment" />
              </div>
              <div>
                <label className="text-xs text-slate-600">Your password (e-signature) *</label>
                <Input type="password" value={transitionForm.password} onChange={(e) => setTransitionForm((p) => ({ ...p, password: e.target.value }))} data-testid="dyn-trans-pw" />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setActive(null)}>Cancel</Button>
            <Button onClick={transition} className="bg-slate-900 text-white" data-testid="dyn-trans-submit">Sign & transition</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
