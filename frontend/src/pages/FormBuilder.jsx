import React, { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Switch } from "../components/ui/switch";
import { Plus, Trash2, Save, GripVertical } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import { hasPermission } from "../lib/roles";

const MODULES = [
  ["CHANGE_CONTROL", "Change Control"],
  ["DEVIATION", "Deviation"],
  ["CAPA", "CAPA"],
  ["INCIDENT", "Incident"],
  ["EVENT", "Event"],
];

const FIELD_TYPES = [
  ["text", "Text"],
  ["textarea", "Long text"],
  ["number", "Number"],
  ["select", "Select"],
  ["date", "Date"],
  ["checkbox", "Checkbox"],
];

export default function FormBuilder() {
  const { user } = useAuth();
  // Per User Role Matrix: only Admin / Super Admin can configure workflows.
  const canEdit = hasPermission(user, "workflow_config");
  const [module, setModule] = useState("DEVIATION");
  const [fields, setFields] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = async (m) => {
    try {
      const { data } = await api.get(`/form-schemas/${m}`);
      setFields(data.fields || []);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  useEffect(() => { load(module); }, [module]);

  const addField = () => setFields((f) => [...f, {
    key: `field_${f.length + 1}`, label: "New field", type: "text", required: false, options: [], section: "Additional Details", placeholder: "",
  }]);

  const updateField = (i, patch) => setFields((f) => f.map((row, idx) => idx === i ? { ...row, ...patch } : row));
  const removeField = (i) => setFields((f) => f.filter((_, idx) => idx !== i));
  const moveField = (i, dir) => {
    setFields((f) => {
      const next = [...f];
      const j = i + dir;
      if (j < 0 || j >= next.length) return next;
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  };

  const save = async () => {
    setBusy(true);
    try {
      const cleaned = fields.map((f) => ({
        key: f.key.trim(),
        label: f.label.trim(),
        type: f.type,
        required: !!f.required,
        options: f.type === "select" ? (Array.isArray(f.options) ? f.options : (f.options || "").split("\n").map((s) => s.trim()).filter(Boolean)) : null,
        placeholder: f.placeholder || "",
        section: f.section || "Additional Details",
      }));
      await api.put(`/form-schemas/${module}`, {
        module, fields: cleaned, reason: "Form schema updated",
      });
      toast.success("Form schema saved");
      await load(module);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5" data-testid="form-builder-page">
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500 mono">Configuration</div>
          <h1 className="text-3xl font-semibold text-slate-950 tracking-tight mt-1" style={{ fontFamily: "Work Sans" }}>Form Builder</h1>
          <div className="text-xs text-slate-500 mt-1">Configure additional fields per module. Changes apply to new records only.</div>
        </div>
        {canEdit && (
          <Button onClick={save} disabled={busy} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="form-builder-save">
            <Save size={14} className="mr-1" /> {busy ? "Saving…" : "Save schema"}
          </Button>
        )}
      </div>

      <div className="border border-slate-200 bg-white rounded-sm p-3 flex items-end gap-3">
        <div className="w-60">
          <Label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Module</Label>
          <Select value={module} onValueChange={setModule}>
            <SelectTrigger data-testid="form-builder-module"><SelectValue /></SelectTrigger>
            <SelectContent>
              {MODULES.map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        {canEdit && (
          <Button variant="outline" onClick={addField} data-testid="form-builder-add">
            <Plus size={14} className="mr-1" /> Add field
          </Button>
        )}
        <div className="ml-auto text-[11px] text-slate-500 mono">{fields.length} fields</div>
      </div>

      <div className="border border-slate-200 bg-white rounded-sm">
        {fields.length === 0 ? (
          <div className="p-6 text-sm text-slate-500" data-testid="form-builder-empty">No additional fields configured for this module.</div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {fields.map((f, i) => (
              <li key={i} className="p-3 grid grid-cols-12 gap-3 items-end" data-testid={`form-field-${i}`}>
                <div className="col-span-1 flex flex-col gap-1 pt-5">
                  <button onClick={() => moveField(i, -1)} className="text-slate-400 hover:text-slate-900 text-xs" disabled={!canEdit}><GripVertical size={14} /></button>
                </div>
                <div className="col-span-2">
                  <Label className="text-[10px] uppercase tracking-wide text-slate-500 mono">Key</Label>
                  <Input value={f.key} onChange={(e) => updateField(i, { key: e.target.value })} disabled={!canEdit} data-testid={`field-key-${i}`} />
                </div>
                <div className="col-span-3">
                  <Label className="text-[10px] uppercase tracking-wide text-slate-500 mono">Label</Label>
                  <Input value={f.label} onChange={(e) => updateField(i, { label: e.target.value })} disabled={!canEdit} data-testid={`field-label-${i}`} />
                </div>
                <div className="col-span-2">
                  <Label className="text-[10px] uppercase tracking-wide text-slate-500 mono">Type</Label>
                  <Select value={f.type} onValueChange={(v) => updateField(i, { type: v })} disabled={!canEdit}>
                    <SelectTrigger data-testid={`field-type-${i}`}><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {FIELD_TYPES.map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="col-span-2">
                  <Label className="text-[10px] uppercase tracking-wide text-slate-500 mono">Section</Label>
                  <Input value={f.section || ""} onChange={(e) => updateField(i, { section: e.target.value })} disabled={!canEdit} data-testid={`field-section-${i}`} />
                </div>
                <div className="col-span-1 flex flex-col items-center">
                  <Label className="text-[10px] uppercase tracking-wide text-slate-500 mono">Req</Label>
                  <Switch checked={!!f.required} onCheckedChange={(v) => updateField(i, { required: v })} disabled={!canEdit} data-testid={`field-required-${i}`} />
                </div>
                <div className="col-span-1 text-right">
                  {canEdit && (
                    <Button size="icon" variant="ghost" onClick={() => removeField(i)} data-testid={`field-remove-${i}`}>
                      <Trash2 size={14} className="text-red-600" />
                    </Button>
                  )}
                </div>
                {f.type === "select" && (
                  <div className="col-span-12 -mt-1">
                    <Label className="text-[10px] uppercase tracking-wide text-slate-500 mono">Options (one per line)</Label>
                    <textarea
                      className="w-full border border-slate-300 rounded-sm p-2 text-sm font-mono"
                      rows={3}
                      value={Array.isArray(f.options) ? f.options.join("\n") : (f.options || "")}
                      onChange={(e) => updateField(i, { options: e.target.value })}
                      disabled={!canEdit}
                      data-testid={`field-options-${i}`}
                    />
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
