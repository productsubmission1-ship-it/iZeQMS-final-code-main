import React, { useMemo } from "react";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Label } from "./ui/label";
import { Checkbox } from "./ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Boxes, FileCheck2 } from "lucide-react";

/**
 * Renders any Module Framework template's form definition as a real,
 * controlled form. Used by legacy modules (CAPA / Change Control / Incident /
 * Event) so admins can edit the format in **Module Framework → Publish** and
 * the change reflects instantly in every legacy record screen, no deploy.
 *
 * Props:
 *   template:   the active PUBLISHED template object (with `form.sections`)
 *   value:      current { [field_key]: any } map
 *   onChange:   (next) => void — receives full next map
 *   readOnly:   bool — disable inputs
 *   testidPrefix: string — for data-testid prefixing
 */
export default function DynamicFrameworkForm({ template, value, onChange, readOnly = false, testidPrefix = "fw" }) {
  const sections = useMemo(() => template?.form?.sections || [], [template]);
  const v = value || {};

  const setField = (k, val) => {
    if (readOnly) return;
    onChange?.({ ...v, [k]: val });
  };

  if (!template) return null;

  return (
    <div className="space-y-4" data-testid={`${testidPrefix}-dynamic-form`}>
      <div className="border border-indigo-100 bg-indigo-50/50 rounded-sm px-3 py-2 flex items-center gap-2 text-xs">
        <Boxes size={14} className="text-indigo-700" />
        <span className="text-indigo-900">
          Live form from Module Framework template <b>{template.code}</b> · v{template.version}
        </span>
        <FileCheck2 size={12} className="text-emerald-600 ml-1" />
        <span className="text-[10px] mono uppercase text-emerald-700">{template.status}</span>
        <span className="ml-auto text-[10px] text-slate-500">
          Editable from <span className="underline">Module Framework</span> — publishing a new version updates this form everywhere.
        </span>
      </div>

      {sections.map((sec) => (
        <div key={sec.key} className="border border-slate-200 bg-white rounded-sm">
          <div className="px-4 py-2 border-b border-slate-200 text-sm font-semibold text-slate-900">{sec.label}</div>
          <div className="p-4 grid grid-cols-1 md:grid-cols-2 gap-4">
            {(sec.fields || []).map((f) => (
              <FieldRenderer
                key={f.key}
                field={f}
                value={v[f.key]}
                onChange={(val) => setField(f.key, val)}
                readOnly={readOnly}
                testid={`${testidPrefix}-${sec.key}-${f.key}`}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function FieldRenderer({ field, value, onChange, readOnly, testid }) {
  const wide = ["textarea", "attachment", "signature", "multiselect"].includes(field.type);
  const label = (
    <Label className="text-xs uppercase tracking-wide text-slate-500">
      {field.label}
      {field.required && <span className="text-rose-600 ml-1">*</span>}
    </Label>
  );

  const wrap = (inner) => (
    <div className={wide ? "md:col-span-2" : ""}>
      {label}
      <div className="mt-1">{inner}</div>
    </div>
  );

  switch (field.type) {
    case "textarea":
      return wrap(<Textarea rows={3} value={value || ""} onChange={(e) => onChange(e.target.value)} disabled={readOnly} data-testid={testid} />);
    case "number":
      return wrap(<Input type="number" value={value ?? ""} onChange={(e) => onChange(e.target.value)} disabled={readOnly} data-testid={testid} />);
    case "date":
      return wrap(<Input type="date" value={value || ""} onChange={(e) => onChange(e.target.value)} disabled={readOnly} data-testid={testid} />);
    case "datetime":
      return wrap(<Input type="datetime-local" value={value || ""} onChange={(e) => onChange(e.target.value)} disabled={readOnly} data-testid={testid} />);
    case "checkbox":
      return wrap(
        <div className="flex items-center gap-2">
          <Checkbox checked={!!value} onCheckedChange={(c) => onChange(!!c)} disabled={readOnly} data-testid={testid} />
          <span className="text-xs text-slate-600">{field.label}</span>
        </div>,
      );
    case "dropdown": {
      const hasOther = (field.options || []).includes("Other");
      const isOther = value && typeof value === "object" && value.value === "Other";
      const selectVal = isOther ? "Other" : (typeof value === "string" ? value : "");
      return wrap(
        <div className="space-y-2">
          <Select
            value={selectVal}
            onValueChange={(v) => {
              if (v === "Other" && hasOther) onChange({ value: "Other", other: (typeof value === "object" ? value?.other : "") || "" });
              else onChange(v);
            }}
            disabled={readOnly}
          >
            <SelectTrigger data-testid={testid}><SelectValue placeholder="Select…" /></SelectTrigger>
            <SelectContent>
              {(field.options || []).map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
            </SelectContent>
          </Select>
          {isOther && (
            <Input
              placeholder="Please specify…"
              value={value?.other || ""}
              disabled={readOnly}
              onChange={(e) => onChange({ value: "Other", other: e.target.value })}
              data-testid={`${testid}-other`}
            />
          )}
        </div>,
      );
    }
    case "radio": {
      const isOther = value && typeof value === "object" && value.value === "Other";
      const cmp = isOther ? "Other" : value;
      return wrap(
        <div className="flex flex-wrap items-center gap-3" data-testid={testid}>
          {(field.options || []).map((o) => (
            <label key={o} className="flex items-center gap-1.5 text-xs cursor-pointer">
              <input
                type="radio"
                name={field.key}
                checked={cmp === o}
                onChange={() => {
                  if (o === "Other") onChange({ value: "Other", other: (typeof value === "object" ? value?.other : "") || "" });
                  else onChange(o);
                }}
                disabled={readOnly}
                data-testid={`${testid}-${o.replace(/\W+/g, "_").toLowerCase()}`}
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
              data-testid={`${testid}-other`}
            />
          )}
        </div>,
      );
    }
    case "multiselect":
      return wrap(
        <div className="flex flex-wrap gap-2" data-testid={testid}>
          {(field.options || []).map((o) => {
            const arr = Array.isArray(value) ? value : [];
            const active = arr.includes(o);
            return (
              <button
                type="button"
                key={o}
                onClick={() => !readOnly && onChange(active ? arr.filter((x) => x !== o) : [...arr, o])}
                disabled={readOnly}
                className={`text-xs px-2 py-1 rounded-sm border transition-colors ${active ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50"}`}
                data-testid={`${testid}-${o.replace(/\W+/g, "_").toLowerCase()}`}>
                {o}
              </button>
            );
          })}
        </div>,
      );
    case "signature":
      return wrap(
        <div className="border border-dashed border-slate-300 rounded-sm p-3 bg-slate-50 text-xs text-slate-500" data-testid={testid}>
          E-signature block — captured via workflow transition (password + reason).
        </div>,
      );
    case "attachment":
      return wrap(
        <div className="border border-dashed border-slate-300 rounded-sm p-3 bg-slate-50 text-xs text-slate-500" data-testid={testid}>
          Use the <b>Attachments</b> panel on the record to upload supporting files. They will be listed here in the printed PDF.
        </div>,
      );
    case "approval":
      return wrap(
        <div className="border border-dashed border-amber-300 rounded-sm p-3 bg-amber-50 text-xs text-amber-800" data-testid={testid}>
          Approval block — completed via workflow action with e-signature.
        </div>,
      );
    case "department":
    case "user_picker":
    case "text":
    default:
      return wrap(<Input value={value || ""} onChange={(e) => onChange(e.target.value)} disabled={readOnly} data-testid={testid} />);
  }
}
