import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { Plus, Edit3, Copy, FileCheck2, FileX2, ChevronRight, Eye, Trash2 } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { hasPermission } from "../lib/roles";
import TemplateDesigner from "../components/TemplateDesigner";

const STATUS_STYLES = {
  DRAFT:     { color: "#475569", bg: "#F1F5F9", border: "#CBD5E1" },
  PUBLISHED: { color: "#047857", bg: "#ECFDF5", border: "#A7F3D0" },
  RETIRED:   { color: "#B91C1C", bg: "#FEF2F2", border: "#FECACA" },
};

export default function ModuleFramework() {
  const { user: me } = useAuth();
  const canView = hasPermission(me, "view_module_framework");
  const canManage = hasPermission(me, "manage_module_templates");
  const canPublish = hasPermission(me, "publish_module_templates");
  const canRetire = hasPermission(me, "retire_module_templates");
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ q: "", status: "ALL", category: "ALL" });
  const [designerOpen, setDesignerOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const tpls = await api.get("/module-framework/templates");
      setTemplates(tpls.data || []);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => templates.filter((t) => {
    const q = filter.q.toLowerCase();
    if (q && !`${t.code} ${t.name} ${t.description}`.toLowerCase().includes(q)) return false;
    if (filter.status !== "ALL" && t.status !== filter.status) return false;
    if (filter.category !== "ALL" && t.category !== filter.category) return false;
    return true;
  }), [templates, filter]);

  const openNew = () => { setEditingTemplate(null); setDesignerOpen(true); };
  const openEdit = (t) => { setEditingTemplate(t); setDesignerOpen(true); };

  const publish = async (t) => {
    const reason = window.prompt(`Publish "${t.name}" v${t.version}? This will retire any previous PUBLISHED version for the same code+plant.`, "Approved by Change Control");
    if (!reason || reason.length < 3) return;
    try {
      await api.post(`/module-framework/templates/${t.id}/publish`, { reason });
      toast.success(`Published v${t.version}`); load();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail) || e.message); }
  };

  const retire = async (t) => {
    const reason = window.prompt(`Retire "${t.name}" v${t.version}? Existing records will keep using this version.`, "Decommissioned");
    if (!reason || reason.length < 3) return;
    try {
      await api.post(`/module-framework/templates/${t.id}/retire`, { reason });
      toast.success("Retired"); load();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail) || e.message); }
  };

  const copyTemplate = async (t) => {
    const newCode = window.prompt(`New template code (current: ${t.code})`, `${t.code}_copy`);
    if (!newCode) return;
    const newName = window.prompt("New template name", `${t.name} (copy)`);
    if (!newName) return;
    const reason = window.prompt("Reason for copy", "New rollout");
    if (!reason || reason.length < 3) return;
    try {
      await api.post(`/module-framework/templates/${t.id}/copy`, {
        new_code: newCode, new_name: newName, target_plant_id: null, reason,
      });
      toast.success("Template copied"); load();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail) || e.message); }
  };

  const deleteTemplate = async (t) => {
    if (!window.confirm(`Delete DRAFT template "${t.name}"? This cannot be undone.`)) return;
    try {
      await api.delete(`/module-framework/templates/${t.id}`);
      toast.success("Template deleted"); load();
    } catch (e) { toast.error(formatApiError(e.response?.data?.detail) || e.message); }
  };

  return (
    <div className="space-y-5" data-testid="module-framework-page">
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500 mono">Framework · Versioned</div>
          <h1 className="text-3xl font-semibold text-slate-950 tracking-tight mt-1" style={{ fontFamily: "Work Sans" }}>Module Framework</h1>
          <div className="text-xs text-slate-500 mt-1">
            Design dynamic modules — workflows, forms, approvals, PDFs, role mappings — versioned and audited.
            Publish a new version to roll it out across every live module.
          </div>
        </div>
        <div className="flex gap-2">
          {canManage && (
            <Button onClick={openNew} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="new-template-btn">
              <Plus size={16} className="mr-1" /> New Template
            </Button>
          )}
        </div>
      </div>

      <div className="border border-slate-200 bg-white rounded-sm p-3 flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[200px]">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Search</label>
          <Input value={filter.q} onChange={(e) => setFilter((p) => ({ ...p, q: e.target.value }))} data-testid="template-search" />
        </div>
        <div className="w-40">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Status</label>
          <Select value={filter.status} onValueChange={(v) => setFilter((p) => ({ ...p, status: v }))}>
            <SelectTrigger data-testid="filter-status"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All</SelectItem>
              <SelectItem value="DRAFT">Draft</SelectItem>
              <SelectItem value="PUBLISHED">Published</SelectItem>
              <SelectItem value="RETIRED">Retired</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="w-44">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Category</label>
          <Select value={filter.category} onValueChange={(v) => setFilter((p) => ({ ...p, category: v }))}>
            <SelectTrigger data-testid="filter-category"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All</SelectItem>
              <SelectItem value="DEVIATION">Deviation-like</SelectItem>
              <SelectItem value="CAPA">CAPA-like</SelectItem>
              <SelectItem value="CHANGE_CONTROL">Change Control-like</SelectItem>
              <SelectItem value="INCIDENT">Incident-like</SelectItem>
              <SelectItem value="EVENT">Event-like</SelectItem>
              <SelectItem value="CUSTOM">Custom</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="text-[11px] text-slate-500 mono ml-auto" data-testid="template-count">{filtered.length} templates</div>
      </div>

      <div className="border border-slate-200 bg-white rounded-sm overflow-x-auto">
        <table className="w-full table-dense">
          <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
            <tr>
              <th className="text-left">Code</th>
              <th className="text-left">Name</th>
              <th className="text-left">Category</th>
              <th className="text-left">Version</th>
              <th className="text-left">Status</th>
              <th className="text-left">Stages</th>
              <th className="text-left">Fields</th>
              <th className="text-left">Updated</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={9} className="text-center text-xs text-slate-500 py-6">Loading…</td></tr>}
            {!loading && filtered.length === 0 && (
              <tr><td colSpan={9} className="text-center text-xs text-slate-500 py-6">No templates yet. Click "New Template" to design your first dynamic module.</td></tr>
            )}
            {filtered.map((t) => {
              const st = STATUS_STYLES[t.status] || STATUS_STYLES.DRAFT;
              const stages = (t.workflow?.stages || []).length;
              const fields = (t.form?.sections || []).reduce((s, sec) => s + (sec.fields || []).length, 0);
              return (
                <tr key={t.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`template-row-${t.code}-v${t.version}`}>
                  <td className="mono text-xs">{t.code}</td>
                  <td><div className="font-medium text-slate-900">{t.name}</div><div className="text-[10px] mono text-slate-500 truncate max-w-xs">{t.description}</div></td>
                  <td className="text-xs">{t.category}</td>
                  <td className="mono text-xs">v{t.version}</td>
                  <td>
                    <span className="inline-block px-2 py-0.5 text-[10px] mono font-semibold uppercase rounded-sm"
                      style={{ color: st.color, background: st.bg, border: `1px solid ${st.border}` }}
                      data-testid={`template-status-${t.code}-v${t.version}`}>
                      {t.status}
                    </span>
                  </td>
                  <td className="text-xs mono">{stages}</td>
                  <td className="text-xs mono">{fields}</td>
                  <td className="mono text-[11px]">{t.updated_at ? new Date(t.updated_at).toLocaleDateString() : new Date(t.created_at).toLocaleDateString()}</td>
                  <td className="text-right">
                    <div className="flex gap-1 justify-end">
                      <button onClick={() => openEdit(t)} title={t.status === "DRAFT" ? "Edit (draft)" : "View"} className="p-1.5 hover:bg-slate-200 rounded-sm" data-testid={`edit-template-${t.code}-v${t.version}`}>
                        {t.status === "DRAFT" ? <Edit3 size={14} /> : <Eye size={14} />}
                      </button>
                      {canManage && (
                        <button onClick={() => copyTemplate(t)} title="Copy" className="p-1.5 hover:bg-slate-200 rounded-sm" data-testid={`copy-template-${t.code}-v${t.version}`}><Copy size={14} /></button>
                      )}
                      {canPublish && t.status === "DRAFT" && (
                        <button onClick={() => publish(t)} title="Publish" className="p-1.5 hover:bg-slate-200 rounded-sm" data-testid={`publish-template-${t.code}-v${t.version}`}><FileCheck2 size={14} className="text-emerald-600" /></button>
                      )}
                      {canManage && t.status === "DRAFT" && (
                        <button onClick={() => deleteTemplate(t)} title="Delete DRAFT" className="p-1.5 hover:bg-rose-50 rounded-sm" data-testid={`delete-template-${t.code}-v${t.version}`}><Trash2 size={14} className="text-rose-600" /></button>
                      )}
                      {canRetire && t.status === "PUBLISHED" && (
                        <button onClick={() => retire(t)} title="Retire" className="p-1.5 hover:bg-slate-200 rounded-sm" data-testid={`retire-template-${t.code}-v${t.version}`}><FileX2 size={14} className="text-rose-600" /></button>
                      )}
                      {t.status === "PUBLISHED" && (
                        <Link to={`/dynamic-records/${t.id}`} title="Use this template" className="p-1.5 hover:bg-slate-200 rounded-sm" data-testid={`use-template-${t.code}-v${t.version}`}><ChevronRight size={14} /></Link>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="border border-slate-200 bg-white rounded-sm p-4">
          <div className="text-sm font-medium text-slate-900">How it works</div>
          <ol className="text-xs text-slate-600 list-decimal pl-4 mt-2 leading-relaxed space-y-1">
            <li>Design a module template (workflow + form + PDF + role mapping).</li>
            <li>Save as DRAFT — keep editing freely.</li>
            <li>PUBLISH when ready — version becomes immutable.</li>
            <li>Users create records against the PUBLISHED version.</li>
            <li>Edits → new version. Live records can be migrated to the latest version in one click.</li>
          </ol>
        </div>
        <div className="border border-slate-200 bg-white rounded-sm p-4">
          <div className="text-sm font-medium text-slate-900">Versioning & Publish</div>
          <p className="text-xs text-slate-600 mt-2 leading-relaxed">
            Publishing a new version automatically retires the previous one. Every record carries the exact template version it was created with — and admins can roll forward live records to the latest version when ready.
          </p>
        </div>
        <div className="border border-slate-200 bg-white rounded-sm p-4">
          <div className="text-sm font-medium text-slate-900">Compliance</div>
          <p className="text-xs text-slate-600 mt-2 leading-relaxed">
            Every template change is audited (actor / timestamp / old / new / reason). PDF exports are also logged. Satisfies ALCOA++, 21 CFR Part 11 §11.10 (e), and EU Annex 11.
          </p>
        </div>
      </div>

      <TemplateDesigner
        open={designerOpen}
        onOpenChange={setDesignerOpen}
        template={editingTemplate}
        plants={[]}
        onSaved={() => { setDesignerOpen(false); load(); }}
        canManage={canManage}
      />
    </div>
  );
}
