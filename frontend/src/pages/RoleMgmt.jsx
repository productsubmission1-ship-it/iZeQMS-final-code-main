import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import {
  Plus, Copy, Edit3, Power, PowerOff, ShieldCheck, History, Lock, Download,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import { hasPermission } from "../lib/roles";
import RoleEditorDialog from "../components/RoleEditorDialog";
import RoleCopyDialog from "../components/RoleCopyDialog";
import RoleAuditDrawer from "../components/RoleAuditDrawer";

export default function RoleMgmt() {
  const { user: me } = useAuth();
  const canManage = hasPermission(me, "role_management");
  const navigate = useNavigate();

  const [roles, setRoles] = useState([]);
  const [modules, setModules] = useState({});
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ q: "", status: "ALL", kind: "ALL" });
  const [editorOpen, setEditorOpen] = useState(false);
  const [editorRole, setEditorRole] = useState(null);
  const [copyOpen, setCopyOpen] = useState(false);
  const [copySource, setCopySource] = useState(null);
  const [auditRole, setAuditRole] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const [rolesRes, modsRes] = await Promise.all([
        api.get("/role-mgmt/roles"),
        api.get("/role-mgmt/modules"),
      ]);
      setRoles(rolesRes.data || []);
      setModules(modsRes.data?.modules || {});
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const filtered = useMemo(() => roles.filter((r) => {
    const q = filters.q.toLowerCase();
    if (q && !`${r.code} ${r.name} ${r.description}`.toLowerCase().includes(q)) return false;
    if (filters.status === "ACTIVE" && !r.active) return false;
    if (filters.status === "INACTIVE" && r.active) return false;
    if (filters.kind === "SYSTEM" && !r.is_system) return false;
    if (filters.kind === "CUSTOM" && r.is_system) return false;
    return true;
  }), [roles, filters]);

  const countPerms = (r) => {
    let total = 0, granted = 0;
    for (const m of Object.values(r.permissions || {})) {
      for (const v of Object.values(m || {})) { total += 1; if (v) granted += 1; }
    }
    return { total, granted };
  };

  const toggleActive = async (r) => {
    const reason = window.prompt(
      `Reason for ${r.active ? "deactivating" : "activating"} role "${r.name}":`,
      r.active ? "Disabled by admin" : "Re-enabled by admin",
    );
    if (!reason || reason.trim().length < 3) return;
    try {
      await api.post(`/role-mgmt/roles/${r.id}/activate`, { active: !r.active, reason });
      toast.success(`Role ${r.active ? "deactivated" : "activated"}`);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  return (
    <div className="space-y-5" data-testid="role-mgmt-page">
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500 mono">Access Management</div>
          <h1 className="text-3xl font-semibold text-slate-950 tracking-tight mt-1" style={{ fontFamily: "Work Sans" }}>
            Role Matrix
          </h1>
          <div className="text-xs text-slate-500 mt-1">
            Define roles, module access, and Yes/No action permissions. Every change is captured in the audit trail.
          </div>
        </div>
        {canManage && (
          <div className="flex gap-2">
            <Button
              onClick={() => {
                const url = `${process.env.REACT_APP_BACKEND_URL}/api/role-mgmt/audit/export?format=csv`;
                const tok = localStorage.getItem("izqms_token");
                fetch(url, { headers: { Authorization: `Bearer ${tok}` }, credentials: "include" })
                  .then((r) => r.blob())
                  .then((b) => {
                    const a = document.createElement("a");
                    a.href = URL.createObjectURL(b);
                    a.download = `role_matrix_audit_${new Date().toISOString().slice(0, 10)}.csv`;
                    a.click();
                  });
              }}
              variant="outline"
              data-testid="export-audit-csv"
            >
              <Download size={14} className="mr-1" /> Export Audit (CSV)
            </Button>
            <Button
              onClick={() => { setEditorRole(null); setEditorOpen(true); }}
              className="bg-slate-900 hover:bg-slate-800 text-white"
              data-testid="new-role-btn"
            >
              <Plus size={16} className="mr-1" /> New Role
            </Button>
          </div>
        )}
      </div>

      {/* Filters */}
      <div className="border border-slate-200 bg-white rounded-sm p-3 flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[220px]">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Search</label>
          <Input
            value={filters.q}
            onChange={(e) => setFilters((p) => ({ ...p, q: e.target.value }))}
            placeholder="Role name, code or description"
            data-testid="role-search"
          />
        </div>
        <div className="w-44">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Status</label>
          <Select value={filters.status} onValueChange={(v) => setFilters((p) => ({ ...p, status: v }))}>
            <SelectTrigger data-testid="filter-role-status"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All</SelectItem>
              <SelectItem value="ACTIVE">Active</SelectItem>
              <SelectItem value="INACTIVE">Inactive</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="w-44">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Type</label>
          <Select value={filters.kind} onValueChange={(v) => setFilters((p) => ({ ...p, kind: v }))}>
            <SelectTrigger data-testid="filter-role-kind"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All</SelectItem>
              <SelectItem value="SYSTEM">System</SelectItem>
              <SelectItem value="CUSTOM">Custom</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="text-[11px] text-slate-500 mono ml-auto" data-testid="role-count">{filtered.length} roles</div>
      </div>

      {/* List */}
      <div className="border border-slate-200 bg-white rounded-sm overflow-x-auto">
        <table className="w-full table-dense">
          <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
            <tr>
              <th className="text-left">Role Code</th>
              <th className="text-left">Name</th>
              <th className="text-left">Description</th>
              <th className="text-left">Modules</th>
              <th className="text-left">Permissions</th>
              <th className="text-left">Users</th>
              <th className="text-left">Type</th>
              <th className="text-left">Status</th>
              <th className="text-left">Updated</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={10} className="text-center text-xs text-slate-500 py-6">Loading…</td></tr>
            )}
            {!loading && filtered.length === 0 && (
              <tr><td colSpan={10} className="text-center text-xs text-slate-500 py-6">No roles match.</td></tr>
            )}
            {filtered.map((r) => {
              const { total, granted } = countPerms(r);
              return (
                <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`role-row-${r.code}`}>
                  <td className="mono text-xs">{r.code}</td>
                  <td>
                    <div className="font-medium text-slate-900">{r.name}</div>
                  </td>
                  <td className="text-xs text-slate-600 max-w-md truncate">{r.description}</td>
                  <td className="text-xs">{(r.module_access || []).length}</td>
                  <td className="text-xs mono">
                    <span data-testid={`role-perm-count-${r.code}`}>{granted}</span>
                    <span className="text-slate-400"> / {total}</span>
                  </td>
                  <td className="text-xs mono">{r.user_count || 0}</td>
                  <td>
                    <span
                      className="inline-block px-2 py-0.5 text-[10px] mono font-semibold uppercase rounded-sm"
                      style={
                        r.is_system
                          ? { color: "#1D4ED8", background: "#EFF6FF", border: "1px solid #BFDBFE" }
                          : { color: "#475569", background: "#F1F5F9", border: "1px solid #CBD5E1" }
                      }
                    >
                      {r.is_system ? "SYSTEM" : "CUSTOM"}
                    </span>
                  </td>
                  <td>
                    <span
                      className="inline-block px-2 py-0.5 text-[10px] mono font-semibold uppercase rounded-sm"
                      style={
                        r.active
                          ? { color: "#047857", background: "#ECFDF5", border: "1px solid #A7F3D0" }
                          : { color: "#B91C1C", background: "#FEF2F2", border: "1px solid #FECACA" }
                      }
                      data-testid={`role-status-${r.code}`}
                    >
                      {r.active ? "ACTIVE" : "INACTIVE"}
                    </span>
                  </td>
                  <td className="mono text-[11px]">
                    {r.updated_at ? new Date(r.updated_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="text-right">
                    <div className="flex items-center gap-1 justify-end">
                      <button
                        title="Edit"
                        onClick={() => { setEditorRole(r); setEditorOpen(true); }}
                        data-testid={`edit-role-${r.code}`}
                        className="p-1.5 hover:bg-slate-200 rounded-sm"
                      >
                        <Edit3 size={14} />
                      </button>
                      {canManage && (
                        <button
                          title="Copy"
                          onClick={() => { setCopySource(r); setCopyOpen(true); }}
                          data-testid={`copy-role-${r.code}`}
                          className="p-1.5 hover:bg-slate-200 rounded-sm"
                        >
                          <Copy size={14} />
                        </button>
                      )}
                      {canManage && (
                        <button
                          title={r.active ? "Deactivate" : "Activate"}
                          onClick={() => toggleActive(r)}
                          disabled={r.code === "super_admin" || r.code === "admin"}
                          data-testid={`toggle-role-${r.code}`}
                          className="p-1.5 hover:bg-slate-200 rounded-sm disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          {r.active ? <PowerOff size={14} className="text-rose-600" /> : <Power size={14} className="text-emerald-600" />}
                        </button>
                      )}
                      <button
                        title="View audit"
                        onClick={() => setAuditRole(r)}
                        data-testid={`audit-role-${r.code}`}
                        className="p-1.5 hover:bg-slate-200 rounded-sm"
                      >
                        <History size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Quick links */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="border border-slate-200 bg-white rounded-sm p-4">
          <div className="flex items-center gap-2 text-slate-900 font-medium">
            <ShieldCheck size={16} /> About the Role Matrix
          </div>
          <p className="text-xs text-slate-600 mt-2 leading-relaxed">
            Every role exposes a Yes/No matrix per module and per action.
            Add or remove permissions instantly — no code changes required.
            All updates are captured in the immutable audit trail.
          </p>
        </div>
        <div className="border border-slate-200 bg-white rounded-sm p-4">
          <div className="flex items-center gap-2 text-slate-900 font-medium">
            <Lock size={16} /> User-Specific Overrides
          </div>
          <p className="text-xs text-slate-600 mt-2 leading-relaxed">
            Need to grant a single user an extra approval right, or restrict one action temporarily?
            Use the <Link to="/users" className="underline">Users</Link> page → row action → <i>Permissions</i> to layer additional, restricted, or time-limited overrides on top of their role.
          </p>
        </div>
        <div className="border border-slate-200 bg-white rounded-sm p-4">
          <div className="flex items-center gap-2 text-slate-900 font-medium">
            <History size={16} /> Compliance
          </div>
          <p className="text-xs text-slate-600 mt-2 leading-relaxed">
            Each permission change records actor, timestamp, old value, new value, and reason — satisfying 21 CFR Part 11 §11.10 (e), ALCOA++ and EU Annex 11 §9.
          </p>
        </div>
      </div>

      <RoleEditorDialog
        open={editorOpen}
        onOpenChange={(o) => { setEditorOpen(o); if (!o) setEditorRole(null); }}
        role={editorRole}
        modules={modules}
        onSaved={load}
        canManage={canManage}
      />
      <RoleCopyDialog
        open={copyOpen}
        onOpenChange={(o) => { setCopyOpen(o); if (!o) setCopySource(null); }}
        role={copySource}
        onCopied={load}
      />
      <RoleAuditDrawer
        role={auditRole}
        onClose={() => setAuditRole(null)}
      />
    </div>
  );
}
