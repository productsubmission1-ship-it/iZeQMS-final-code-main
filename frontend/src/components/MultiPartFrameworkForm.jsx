/* eslint-disable react-hooks/exhaustive-deps */
import React, { useEffect, useMemo, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Switch } from "./ui/switch";
import { ChevronDown, ChevronUp, PenLine, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import ESignDialog from "./ESignDialog";
import { useAuth } from "../context/AuthContext";

/**
 * Renders any QMS record (Change Control / CAPA / Incident / Event) using the
 * bound module-framework template — Deviation-style — with per-section "Save"
 * and "Sign · {role}" buttons. Once a section is signed it becomes read-only
 * and cannot be edited again (matches DEV-2026 9-Part behaviour).
 */
function FieldRenderer({ field, value, onChange, readOnly, roleOptions }) {
  const hasOther = Array.isArray(field.options) && field.options.includes("Other");
  const isOther = value && typeof value === "object" && value.value === "Other";
  const tid = `field-${field.key}`;

  let opts = field.options || [];
  if ((field.key === "role" || field.key === "user_role") && (!opts.length || (opts.length === 1 && opts[0] === "Other"))) {
    opts = [...(roleOptions || []), ...opts];
  }

  switch (field.type) {
    case "textarea":
    case "comment":
      return <Textarea rows={3} value={value || ""} disabled={readOnly} onChange={(e) => onChange(e.target.value)} data-testid={tid} />;
    case "number":
      return <Input type="number" value={value ?? ""} disabled={readOnly} onChange={(e) => onChange(e.target.value)} data-testid={tid} />;
    case "date":
      return <Input type="date" value={value || ""} disabled={readOnly} onChange={(e) => onChange(e.target.value)} data-testid={tid} />;
    case "datetime":
      return <Input type="datetime-local" value={value || ""} disabled={readOnly} onChange={(e) => onChange(e.target.value)} data-testid={tid} />;
    case "checkbox":
      return <Switch checked={!!value} disabled={readOnly} onCheckedChange={onChange} data-testid={tid} />;
    case "dropdown":
    case "department":
      return (
        <div className="space-y-2">
          <Select
            value={isOther ? "Other" : (typeof value === "string" ? value : "")}
            onValueChange={(v) => {
              if (v === "Other" && hasOther) onChange({ value: "Other", other: (typeof value === "object" ? value?.other : "") || "" });
              else onChange(v);
            }}
            disabled={readOnly}
          >
            <SelectTrigger data-testid={tid}><SelectValue placeholder="Select…" /></SelectTrigger>
            <SelectContent>
              {(opts.length ? opts : (field.type === "department" ? ["Quality Assurance", "Production", "Engineering", "IT", "Compliance"] : [])).map((o) =>
                <SelectItem key={o} value={o}>{o}</SelectItem>
              )}
            </SelectContent>
          </Select>
          {isOther && (
            <Input
              placeholder="Please specify…"
              value={value?.other || ""}
              disabled={readOnly}
              onChange={(e) => onChange({ value: "Other", other: e.target.value })}
              data-testid={`${tid}-other`}
            />
          )}
        </div>
      );
    case "radio":
      return (
        <div className="flex flex-wrap items-center gap-3" data-testid={tid}>
          {(field.options || []).map((o) => (
            <label key={o} className="flex items-center gap-1.5 text-xs cursor-pointer">
              <input
                type="radio"
                name={field.key}
                checked={(isOther ? "Other" : value) === o}
                disabled={readOnly}
                onChange={() => {
                  if (o === "Other") onChange({ value: "Other", other: (typeof value === "object" ? value?.other : "") || "" });
                  else onChange(o);
                }}
              />
              <span>{o}</span>
            </label>
          ))}
          {isOther && (
            <Input
              className="max-w-xs"
              placeholder="Please specify…"
              value={value?.other || ""}
              disabled={readOnly}
              onChange={(e) => onChange({ value: "Other", other: e.target.value })}
              data-testid={`${tid}-other`}
            />
          )}
        </div>
      );
    case "multiselect": {
      const arr = Array.isArray(value) ? value : [];
      return (
        <div className="flex flex-wrap items-center gap-2" data-testid={tid}>
          {(field.options || []).map((o) => (
            <label key={o} className="flex items-center gap-1.5 text-xs cursor-pointer border border-slate-300 rounded-sm px-2 py-0.5">
              <input
                type="checkbox"
                checked={arr.includes(o)}
                disabled={readOnly}
                onChange={(e) => {
                  if (e.target.checked) onChange([...arr, o]);
                  else onChange(arr.filter((x) => x !== o));
                }}
              />
              <span>{o}</span>
            </label>
          ))}
        </div>
      );
    }
    case "user_picker":
      return <Input value={value || ""} disabled={readOnly} onChange={(e) => onChange(e.target.value)} placeholder="User email" data-testid={tid} />;
    default:
      return <Input value={value || ""} disabled={readOnly} onChange={(e) => onChange(e.target.value)} data-testid={tid} />;
  }
}


function Section({ section, sectionIndex, record, value, signatures, onValueChange, onSaved, onSigned, readOnlyAll, roleOptions }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(sectionIndex < 2); // first two open by default
  const [saving, setSaving] = useState(false);
  const [signing, setSigning] = useState(false);
  const [esign, setEsign] = useState(null); // { role, label } | null
  const sectionSigs = (signatures || []).filter((s) => s.section_key === section.key);
  const sectionIsLocked = readOnlyAll || sectionSigs.length > 0;
  // Sign roles available for this section — taken from the template if defined,
  // else inferred from the section position (matches Deviation: first sections
  // get "Recorded By / Reviewed By", later ones add "Approved By / Closed By").
  const signRoles = section.sign_roles && section.sign_roles.length
    ? section.sign_roles
    : (sectionIndex === 0
        ? [{ key: "initiator", label: "Recorded By" }, { key: "reviewer", label: "Reviewed By (HOD)" }]
        : sectionIndex === 1
          ? [{ key: "reviewer", label: "Reviewed By" }]
          : [{ key: "approver", label: "Approved By" }, { key: "qa_head", label: "QA Reviewed" }]);

  const save = async () => {
    setSaving(true);
    try {
      await api.post(`/records/${record.id}/section-save`, {
        section_key: section.key, data: value || {},
        reason: `Saved section ${section.label || section.key}`,
      });
      toast.success(`Section saved: ${section.label || section.key}`);
      onSaved && onSaved();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally { setSaving(false); }
  };

  const onSignSubmit = async ({ password, reason, comment }) => {
    setSigning(true);
    try {
      await api.post(`/records/${record.id}/section-sign`, {
        section_key: section.key,
        signer_role: esign?.label || esign?.key,
        password, reason, comment,
      });
      toast.success(`Signed · ${esign?.label}`);
      setEsign(null);
      onSigned && onSigned();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally { setSigning(false); }
  };

  return (
    <div className="border border-slate-200 bg-white rounded-sm" data-testid={`section-${section.key}`}>
      <button
        type="button"
        className="w-full flex items-center justify-between px-4 py-3 bg-slate-50 hover:bg-slate-100 border-b border-slate-200"
        onClick={() => setOpen((o) => !o)}
        data-testid={`toggle-section-${section.key}`}
      >
        <div className="flex items-center gap-2">
          <span className="font-medium text-slate-900 text-sm">{section.label || section.key}</span>
          {sectionSigs.length > 0 && (
            <span className="inline-flex items-center gap-1 text-[10px] mono text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-sm px-2 py-0.5">
              <CheckCircle2 size={11} /> Signed
            </span>
          )}
        </div>
        {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
      </button>
      {open && (
        <div className="p-4 space-y-3">
          {(section.fields || []).map((f) => (
            <div key={f.key} className="grid grid-cols-1 md:grid-cols-3 gap-3 items-start py-2 border-b border-slate-100 last:border-b-0">
              <div className="text-xs text-slate-600 md:col-span-1 pt-1">
                {f.label}{f.required && <span className="text-rose-600"> *</span>}
              </div>
              <div className="md:col-span-2">
                <FieldRenderer
                  field={f}
                  value={(value || {})[f.key]}
                  onChange={(val) => onValueChange({ ...(value || {}), [f.key]: val })}
                  readOnly={sectionIsLocked}
                  roleOptions={roleOptions}
                />
              </div>
            </div>
          ))}
          {sectionSigs.length > 0 && (
            <div className="border-t border-dashed border-slate-300 pt-3 space-y-1">
              {sectionSigs.map((s) => (
                <div key={s.id} className="text-[11px] mono text-slate-700 flex items-center gap-2">
                  <CheckCircle2 size={12} className="text-emerald-600" />
                  <span><b>{s.signer_role}</b> · {s.signer_name} ({s.signer_email}) · {new Date(s.timestamp).toLocaleString()}</span>
                  <span className="text-slate-400">— {s.reason}</span>
                </div>
              ))}
            </div>
          )}
          {!sectionIsLocked && (
            <div className="flex flex-wrap gap-2 pt-2">
              <Button
                size="sm"
                disabled={saving}
                onClick={save}
                className="bg-slate-900 text-white hover:bg-slate-800"
                data-testid={`save-section-${section.key}`}
              >
                {saving ? "Saving…" : `Save ${section.label || section.key}`}
              </Button>
              {signRoles.map((r) => (
                <Button
                  key={r.key}
                  size="sm"
                  variant="outline"
                  onClick={() => setEsign(r)}
                  data-testid={`sign-section-${section.key}-${r.key}`}
                >
                  <PenLine size={14} className="mr-1.5" /> Sign · {r.label}
                </Button>
              ))}
            </div>
          )}
        </div>
      )}
      <ESignDialog
        open={!!esign}
        onOpenChange={(o) => { if (!o) setEsign(null); }}
        action={`SIGN · ${esign?.label || ""}`}
        user={user}
        busy={signing}
        onConfirm={onSignSubmit}
      />
    </div>
  );
}


export default function MultiPartFrameworkForm({ record, template, readOnly, roleOptions }) {
  const [data, setData] = useState(record.framework_form_data || {});
  const [signatures, setSignatures] = useState([]);

  const loadSigs = async () => {
    try {
      const res = await api.get(`/records/${record.id}/signatures`);
      setSignatures(res.data || []);
    } catch (e) { /* ignore */ }
  };

  useEffect(() => { loadSigs(); }, [record.id]);

  // Sync from prop changes (after parent reloads)
  useEffect(() => { setData(record.framework_form_data || {}); }, [record.id, record.updated_at]);

  const sections = useMemo(() => template?.form?.sections || [], [template]);

  if (!template) {
    return (
      <div className="border border-dashed border-slate-300 bg-white rounded-sm p-6 text-sm text-slate-500" data-testid="no-template-bound">
        No published Module Framework template is bound to this record type yet.
        An admin can design and publish a template under <b>Module Framework</b> — the form will then appear here.
      </div>
    );
  }
  if (sections.length === 0) {
    return (
      <div className="border border-dashed border-slate-300 bg-white rounded-sm p-6 text-sm text-slate-500">
        Template has no form sections defined.
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="multipart-framework-form">
      <div className="text-[11px] mono text-slate-500">
        Template · {template.code} v{template.version} · {sections.length} sections · {signatures.length} signatures recorded
      </div>
      {sections.map((sec, idx) => (
        <Section
          key={sec.key}
          section={sec}
          sectionIndex={idx}
          record={record}
          value={data[sec.key] || {}}
          signatures={signatures}
          onValueChange={(newSecValue) => setData((p) => ({ ...p, [sec.key]: newSecValue }))}
          onSaved={loadSigs}
          onSigned={loadSigs}
          readOnlyAll={readOnly}
          roleOptions={roleOptions}
        />
      ))}
    </div>
  );
}
