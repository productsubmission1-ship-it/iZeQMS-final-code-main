import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Save } from "lucide-react";
import DynamicFrameworkForm from "../components/DynamicFrameworkForm";

const TYPE_LABEL = {
  CHANGE_CONTROL: "Change Control",
  DEVIATION: "Deviation",
  CAPA: "CAPA",
  INCIDENT: "Incident",
  EVENT: "Event",
};

// Legacy Deviation form continues to render its custom hard-coded UI in
// RecordDetail.jsx. The other 4 categories use the Module Framework's published
// template — so admins can edit the format and have it reflected live.
const FRAMEWORK_DRIVEN = new Set(["CAPA", "CHANGE_CONTROL", "INCIDENT", "EVENT"]);

export default function NewRecord() {
  const { type } = useParams();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    type: type || "DEVIATION",
    title: "",
    description: "",
    department: "Quality Assurance",
    location: "Plant-1",
    severity: "Medium",
    priority: "Medium",
    due_date: "",
    impact_assessment: "",
    root_cause: "",
    proposed_action: "",
  });
  const [busy, setBusy] = useState(false);
  const [draftId, setDraftId] = useState(null);
  const [savingDraft, setSavingDraft] = useState(false);
  const [activeTpl, setActiveTpl] = useState(null);
  const [fwData, setFwData] = useState({});

  // Whenever the type changes (incl. initial mount), load the active framework
  // template for that category so the dynamic PDF-aligned form is rendered.
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      if (!FRAMEWORK_DRIVEN.has(form.type)) { setActiveTpl(null); return; }
      try {
        const { data } = await api.get("/module-framework/active-template", { params: { category: form.type } });
        if (cancelled) return;
        setActiveTpl(data?.template || null);
      } catch (e) {
        if (!cancelled) setActiveTpl(null);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [form.type]);

  // Auto-save every 30s if title+description provided and no draft yet
  React.useEffect(() => {
    if (!form.title || !form.description) return;
    const t = setInterval(() => { saveDraft(true); }, 30000);
    return () => clearInterval(t);
    // eslint-disable-next-line
  }, [form.title, form.description, draftId]);

  const saveDraft = async (silent = false) => {
    if (savingDraft) return;
    setSavingDraft(true);
    try {
      const payload = { ...form };
      if (payload.due_date) payload.due_date = new Date(payload.due_date).toISOString();
      if (activeTpl) {
        payload.framework_template_id = activeTpl.id;
        payload.framework_template_version = activeTpl.version;
        payload.framework_form_data = fwData;
      }
      if (!draftId) {
        const { data } = await api.post("/records/draft", payload);
        setDraftId(data.id);
        if (!silent) toast.success(`Draft ${data.record_number} saved`);
      } else {
        await api.patch(`/records/${draftId}`, { ...payload, reason: "Draft auto-save" });
        if (!silent) toast.success("Draft updated");
      }
    } catch (e) {
      if (!silent) toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setSavingDraft(false);
    }
  };

  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const payload = { ...form };
      if (payload.due_date) payload.due_date = new Date(payload.due_date).toISOString();
      if (activeTpl) {
        payload.framework_template_id = activeTpl.id;
        payload.framework_template_version = activeTpl.version;
        payload.framework_form_data = fwData;
      }
      const { data } = await api.post("/records", payload);
      toast.success(`Record ${data.record_number} created.`);
      navigate(`/record/${data.id}`);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-6 max-w-4xl" data-testid="new-record-page">
      <div>
        <div className="text-[11px] uppercase tracking-wide text-slate-500 mono">New Record</div>
        <h1 className="text-3xl font-semibold text-slate-950 tracking-tight mt-1" style={{ fontFamily: "Work Sans" }}>Initiate {TYPE_LABEL[form.type] || "Record"}</h1>
        <p className="text-sm text-slate-500 mt-1">All fields are audit-tracked. Record number is auto-generated upon creation.</p>
      </div>

      <Section title="1. General Information">
        <Grid>
          <Field label="Type *">
            <Select value={form.type} onValueChange={(v) => set("type", v)}>
              <SelectTrigger data-testid="form-type"><SelectValue /></SelectTrigger>
              <SelectContent>
                {Object.entries(TYPE_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
              </SelectContent>
            </Select>
          </Field>
          <Field label="Department">
            <Input value={form.department} onChange={(e) => set("department", e.target.value)} data-testid="form-department" />
          </Field>
          <Field label="Location">
            <Input value={form.location} onChange={(e) => set("location", e.target.value)} data-testid="form-location" />
          </Field>
          <Field label="Severity">
            <Select value={form.severity} onValueChange={(v) => set("severity", v)}>
              <SelectTrigger data-testid="form-severity"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Low">Low</SelectItem>
                <SelectItem value="Medium">Medium</SelectItem>
                <SelectItem value="High">High</SelectItem>
                <SelectItem value="Critical">Critical</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label="Priority">
            <Select value={form.priority} onValueChange={(v) => set("priority", v)}>
              <SelectTrigger data-testid="form-priority"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Low">Low</SelectItem>
                <SelectItem value="Medium">Medium</SelectItem>
                <SelectItem value="High">High</SelectItem>
              </SelectContent>
            </Select>
          </Field>
          <Field label="Target due date">
            <Input type="date" value={form.due_date} onChange={(e) => set("due_date", e.target.value)} data-testid="form-due-date" />
          </Field>
        </Grid>
      </Section>

      <Section title="2. Title & Description">
        <Field label="Title *">
          <Input required value={form.title} onChange={(e) => set("title", e.target.value)} data-testid="form-title" placeholder="Concise summary of the record" />
        </Field>
        <Field label="Description *">
          <Textarea required rows={4} value={form.description} onChange={(e) => set("description", e.target.value)} data-testid="form-description" placeholder="Detailed description of what happened or what is being requested." />
        </Field>
      </Section>

      <Section title="3. Investigation & Action">
        <Field label="Impact Assessment">
          <Textarea rows={3} value={form.impact_assessment} onChange={(e) => set("impact_assessment", e.target.value)} data-testid="form-impact" placeholder="Patient safety / product quality / regulatory impact" />
        </Field>
        <Field label="Root Cause (preliminary)">
          <Textarea rows={3} value={form.root_cause} onChange={(e) => set("root_cause", e.target.value)} data-testid="form-root-cause" />
        </Field>
        <Field label="Proposed Action">
          <Textarea rows={3} value={form.proposed_action} onChange={(e) => set("proposed_action", e.target.value)} data-testid="form-proposed-action" />
        </Field>
      </Section>

      {activeTpl && (
        <div data-testid={`framework-form-${form.type}`}>
          <div className="text-[11px] uppercase tracking-wide text-slate-500 mono mb-2">4. {TYPE_LABEL[form.type] || form.type} — Form (from Module Framework)</div>
          <DynamicFrameworkForm
            template={activeTpl}
            value={fwData}
            onChange={setFwData}
            testidPrefix={`new-${form.type.toLowerCase()}`}
          />
        </div>
      )}

      <div className="flex gap-3 justify-end">
        <Button type="button" variant="outline" onClick={() => navigate(-1)} data-testid="form-cancel">Cancel</Button>
        <Button type="button" variant="outline" onClick={() => saveDraft(false)} disabled={savingDraft || !form.title} data-testid="form-save-draft">
          <Save size={14} className="mr-1" /> {savingDraft ? "Saving…" : draftId ? "Update draft" : "Save draft"}
        </Button>
        <Button type="submit" disabled={busy || !form.title || !form.description} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="form-submit">
          {busy ? "Creating…" : "Create record"}
        </Button>
      </div>
    </form>
  );
}

const Section = ({ title, children }) => (
  <div className="border border-slate-200 bg-white rounded-sm">
    <div className="px-4 py-2 border-b border-slate-200 text-sm font-semibold text-slate-900">{title}</div>
    <div className="p-4 space-y-4">{children}</div>
  </div>
);

const Grid = ({ children }) => <div className="grid grid-cols-1 md:grid-cols-3 gap-4">{children}</div>;

const Field = ({ label, children }) => (
  <div>
    <Label className="text-xs uppercase tracking-wide text-slate-500">{label}</Label>
    {children}
  </div>
);
