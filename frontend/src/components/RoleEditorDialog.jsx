import React, { useEffect, useMemo, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Switch } from "./ui/switch";
import { Checkbox } from "./ui/checkbox";
import { toast } from "sonner";
import api, { formatApiError } from "../lib/api";

function emptyMatrix(modules) {
  const out = {};
  for (const [mk, mv] of Object.entries(modules || {})) {
    out[mk] = {};
    for (const a of mv.actions || []) out[mk][a.key] = false;
  }
  return out;
}

export default function RoleEditorDialog({ open, onOpenChange, role, modules, onSaved, canManage }) {
  const isEdit = !!role?.id;
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    if (!open) return;
    if (isEdit) {
      setForm({
        code: role.code || "",
        name: role.name || "",
        description: role.description || "",
        department_access: role.department_access || [],
        module_access: role.module_access || [],
        workflow_access: !!role.workflow_access,
        approval_access: !!role.approval_access,
        review_access: !!role.review_access,
        electronic_signature_access: !!role.electronic_signature_access,
        report_access: !!role.report_access,
        audit_trail_access: !!role.audit_trail_access,
        permissions: role.permissions || emptyMatrix(modules),
        reason: "",
      });
    } else {
      setForm({
        code: "",
        name: "",
        description: "",
        department_access: ["ALL"],
        module_access: Object.keys(modules || {}),
        workflow_access: false,
        approval_access: false,
        review_access: false,
        electronic_signature_access: false,
        report_access: false,
        audit_trail_access: false,
        permissions: emptyMatrix(modules),
        reason: "",
      });
    }
  }, [open, role, modules, isEdit]);

  const grouped = useMemo(() => {
    const g = {};
    for (const [mk, mv] of Object.entries(modules || {})) {
      const grp = mv.group || "Other";
      if (!g[grp]) g[grp] = [];
      g[grp].push({ key: mk, ...mv });
    }
    return g;
  }, [modules]);

  if (!open || !form) return null;

  const setPerm = (mk, ak, val) => {
    setForm((p) => ({ ...p, permissions: { ...p.permissions, [mk]: { ...p.permissions[mk], [ak]: val } } }));
  };
  const setAllForModule = (mk, val) => {
    const acts = modules[mk]?.actions || [];
    const newM = {};
    for (const a of acts) newM[a.key] = val;
    setForm((p) => ({ ...p, permissions: { ...p.permissions, [mk]: newM } }));
  };
  const moduleAllChecked = (mk) => {
    const acts = modules[mk]?.actions || [];
    return acts.length > 0 && acts.every((a) => !!form.permissions?.[mk]?.[a.key]);
  };
  const moduleSomeChecked = (mk) => {
    const acts = modules[mk]?.actions || [];
    return acts.some((a) => !!form.permissions?.[mk]?.[a.key]);
  };
  const toggleModuleAccess = (mk, val) => {
    let arr = new Set(form.module_access || []);
    if (val) arr.add(mk); else arr.delete(mk);
    setForm((p) => ({ ...p, module_access: Array.from(arr) }));
    if (!val) setAllForModule(mk, false);
  };

  const save = async () => {
    if (!canManage) return;
    if (!isEdit) {
      if (!form.code || form.code.length < 2) return toast.error("Role code is required");
      if (!form.name || form.name.length < 2) return toast.error("Role name is required");
    }
    if (!form.reason || form.reason.trim().length < 3) {
      return toast.error("A reason for this change is required (min 3 chars)");
    }
    setBusy(true);
    try {
      if (isEdit) {
        await api.patch(`/role-mgmt/roles/${role.id}`, {
          name: form.name,
          description: form.description,
          department_access: form.department_access,
          module_access: form.module_access,
          workflow_access: form.workflow_access,
          approval_access: form.approval_access,
          review_access: form.review_access,
          electronic_signature_access: form.electronic_signature_access,
          report_access: form.report_access,
          audit_trail_access: form.audit_trail_access,
          permissions: form.permissions,
          reason: form.reason,
        });
        toast.success("Role updated");
      } else {
        await api.post("/role-mgmt/roles", {
          code: form.code,
          name: form.name,
          description: form.description,
          department_access: form.department_access,
          module_access: form.module_access,
          workflow_access: form.workflow_access,
          approval_access: form.approval_access,
          review_access: form.review_access,
          electronic_signature_access: form.electronic_signature_access,
          report_access: form.report_access,
          audit_trail_access: form.audit_trail_access,
          permissions: form.permissions,
          reason: form.reason,
        });
        toast.success("Role created");
      }
      onOpenChange(false);
      onSaved?.();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  const filterMatch = (label, key) => {
    if (!filter) return true;
    const q = filter.toLowerCase();
    return label.toLowerCase().includes(q) || key.toLowerCase().includes(q);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="max-w-5xl max-h-[90vh] flex flex-col"
        data-testid="role-editor-dialog"
      >
        <DialogHeader>
          <DialogTitle data-testid="role-editor-title">
            {isEdit ? `Edit role: ${role.name}` : "Create new role"}
          </DialogTitle>
          <DialogDescription>
            Define identity, scope, and the Yes/No permission matrix. All changes are written to the audit trail.
          </DialogDescription>
        </DialogHeader>

        <div className="overflow-y-auto pr-1 space-y-6 flex-1">
          {/* Identity */}
          <section>
            <div className="text-[11px] uppercase tracking-wide text-slate-500 mono mb-2">Identity</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-slate-600">Role code <span className="text-rose-600">*</span></label>
                <Input
                  value={form.code}
                  disabled={isEdit}
                  onChange={(e) => setForm((p) => ({ ...p, code: e.target.value.toLowerCase().replace(/\s+/g, "_") }))}
                  placeholder="e.g. plant_qa_reviewer"
                  data-testid="role-code-input"
                />
              </div>
              <div>
                <label className="text-xs text-slate-600">Role name <span className="text-rose-600">*</span></label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder="Plant QA Reviewer"
                  data-testid="role-name-input"
                />
              </div>
              <div className="md:col-span-2">
                <label className="text-xs text-slate-600">Description</label>
                <Textarea
                  value={form.description}
                  onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                  rows={2}
                  placeholder="What this role is for, when to assign it, who approves it…"
                  data-testid="role-description-input"
                />
              </div>
            </div>
          </section>

          {/* Scope flags */}
          <section>
            <div className="text-[11px] uppercase tracking-wide text-slate-500 mono mb-2">Scope &amp; Rights</div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {[
                ["review_access", "Review Access"],
                ["approval_access", "Approval Access"],
                ["electronic_signature_access", "E-Signature Rights"],
                ["report_access", "Report Access"],
                ["audit_trail_access", "Audit Trail Access"],
                ["workflow_access", "Workflow Configuration"],
              ].map(([k, label]) => (
                <label
                  key={k}
                  className="flex items-center justify-between gap-3 border border-slate-200 bg-white rounded-sm px-3 py-2"
                >
                  <span className="text-sm text-slate-800">{label}</span>
                  <Switch
                    checked={!!form[k]}
                    onCheckedChange={(v) => setForm((p) => ({ ...p, [k]: v }))}
                    data-testid={`scope-${k}`}
                  />
                </label>
              ))}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
              <div>
                <label className="text-xs text-slate-600">Department access (comma-separated; ALL = all)</label>
                <Input
                  value={(form.department_access || []).join(", ")}
                  onChange={(e) => setForm((p) => ({
                    ...p,
                    department_access: e.target.value.split(",").map((s) => s.trim()).filter(Boolean),
                  }))}
                  placeholder="ALL or Quality Assurance, Production"
                  data-testid="role-dept-access"
                />
              </div>
            </div>
          </section>

          {/* Permission matrix */}
          <section>
            <div className="flex items-end justify-between mb-2">
              <div>
                <div className="text-[11px] uppercase tracking-wide text-slate-500 mono">Module &amp; Action Permissions</div>
                <div className="text-xs text-slate-500">Toggle Yes/No for every module and every action. Disabling a module hides all its actions for the role.</div>
              </div>
              <Input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filter modules…"
                className="w-56 h-8"
                data-testid="perm-filter"
              />
            </div>

            <div className="space-y-4">
              {Object.entries(grouped).map(([grp, mods]) => (
                <div key={grp}>
                  <div className="text-[10px] uppercase tracking-widest text-slate-400 mono mb-1">{grp}</div>
                  <div className="grid grid-cols-1 gap-2">
                    {mods.filter((m) => filterMatch(m.label, m.key)).map((m) => {
                      const moduleEnabled = (form.module_access || []).includes(m.key);
                      const all = moduleAllChecked(m.key);
                      const some = !all && moduleSomeChecked(m.key);
                      return (
                        <div
                          key={m.key}
                          className="border border-slate-200 bg-white rounded-sm"
                          data-testid={`perm-module-${m.key}`}
                        >
                          <div className="flex items-center justify-between px-3 py-2 border-b border-slate-100 bg-slate-50">
                            <div className="flex items-center gap-3">
                              <Checkbox
                                checked={moduleEnabled}
                                onCheckedChange={(v) => toggleModuleAccess(m.key, !!v)}
                                data-testid={`module-access-${m.key}`}
                              />
                              <div>
                                <div className="text-sm font-medium text-slate-900">{m.label}</div>
                                <div className="text-[10px] mono text-slate-500">{m.key}</div>
                              </div>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="text-[11px] mono text-slate-500">
                                {Object.values(form.permissions[m.key] || {}).filter(Boolean).length}/{(m.actions || []).length} granted
                              </span>
                              <button
                                onClick={() => setAllForModule(m.key, !all)}
                                disabled={!moduleEnabled}
                                className="text-[10px] mono uppercase tracking-wide px-2 py-1 border border-slate-300 rounded-sm hover:bg-slate-100 disabled:opacity-40"
                                data-testid={`module-toggle-all-${m.key}`}
                              >
                                {all ? "Clear all" : some ? "Select all" : "Select all"}
                              </button>
                            </div>
                          </div>
                          <div className="p-3 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                            {(m.actions || []).map((a) => {
                              const val = !!form.permissions?.[m.key]?.[a.key];
                              return (
                                <label
                                  key={a.key}
                                  className={`flex items-center justify-between gap-2 border rounded-sm px-2 py-1.5 ${
                                    val ? "border-emerald-300 bg-emerald-50" : "border-slate-200 bg-white"
                                  } ${!moduleEnabled ? "opacity-40 pointer-events-none" : ""}`}
                                >
                                  <div>
                                    <div className="text-xs text-slate-800">{a.label}</div>
                                    <div className="text-[9px] mono text-slate-400">{a.key}</div>
                                  </div>
                                  <Switch
                                    checked={val}
                                    onCheckedChange={(v) => setPerm(m.key, a.key, v)}
                                    data-testid={`perm-${m.key}-${a.key}`}
                                  />
                                </label>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Reason */}
          <section>
            <div className="text-[11px] uppercase tracking-wide text-slate-500 mono mb-2">Reason for change *</div>
            <Textarea
              value={form.reason}
              onChange={(e) => setForm((p) => ({ ...p, reason: e.target.value }))}
              rows={2}
              placeholder="e.g. Granting Plant-1 QA reviewer access to close minor deviations per SOP-QA-014"
              data-testid="role-reason"
            />
          </section>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="role-editor-cancel">
            Cancel
          </Button>
          <Button
            onClick={save}
            disabled={busy || !canManage}
            className="bg-slate-900 hover:bg-slate-800 text-white"
            data-testid="role-editor-save"
          >
            {busy ? "Saving…" : isEdit ? "Save role" : "Create role"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
