import React, { useEffect, useMemo, useState } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { toast } from "sonner";
import { ArrowLeft, Plus, Trash2, CheckCircle2, XCircle, Clock, ShieldOff } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { hasPermission } from "../lib/roles";

export default function UserPermissions() {
  const { user_id } = useParams();
  const navigate = useNavigate();
  const { user: me } = useAuth();
  const canManage = hasPermission(me, "role_management");

  const [data, setData] = useState(null);
  const [overrides, setOverrides] = useState([]);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [allRoles, setAllRoles] = useState([]);

  const [form, setForm] = useState({ module: "", action: "", effect: "ALLOW", kind: "ADDITIONAL", expires_at: "", reason: "" });
  const [assignRoleId, setAssignRoleId] = useState("");
  const [assignReason, setAssignReason] = useState("");

  const load = async () => {
    setLoading(true);
    try {
      const [p, o, r] = await Promise.all([
        api.get(`/role-mgmt/users/${user_id}/permissions`),
        api.get(`/role-mgmt/users/${user_id}/overrides`),
        api.get(`/role-mgmt/roles`),
      ]);
      setData(p.data);
      setOverrides(o.data || []);
      setAllRoles(r.data || []);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, [user_id]);

  const modules = data?.modules || {};

  const moduleActions = useMemo(() => modules[form.module]?.actions || [], [modules, form.module]);

  const submitOverride = async () => {
    if (!form.module || !form.action) return toast.error("Module and action required");
    if (!form.reason || form.reason.trim().length < 3) return toast.error("Reason required");
    let expires = null;
    let effect = form.effect;
    if (form.kind === "TEMPORARY") {
      effect = "ALLOW";
      if (!form.expires_at) return toast.error("Expiry datetime is required for temporary access");
      expires = new Date(form.expires_at).toISOString();
    } else if (form.kind === "RESTRICTED") {
      effect = "DENY";
    } else {
      effect = "ALLOW";
    }
    try {
      await api.post(`/role-mgmt/users/${user_id}/overrides`, {
        module: form.module,
        action: form.action,
        effect,
        expires_at: expires,
        reason: form.reason,
      });
      toast.success("Override applied");
      setAdding(false);
      setForm({ module: "", action: "", effect: "ALLOW", kind: "ADDITIONAL", expires_at: "", reason: "" });
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  const removeOverride = async (o) => {
    const reason = window.prompt("Reason for removing this override:", "Override removed");
    if (!reason || reason.trim().length < 3) return;
    try {
      await api.delete(`/role-mgmt/users/${user_id}/overrides/${o.id}`, { params: { reason } });
      toast.success("Override removed");
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  const assignRole = async () => {
    if (!assignRoleId) return toast.error("Pick a role");
    if (!assignReason || assignReason.trim().length < 3) return toast.error("Reason required");
    try {
      await api.post(`/role-mgmt/users/${user_id}/assign-role`, { role_id: assignRoleId, reason: assignReason });
      toast.success("Role assigned");
      setAssignRoleId("");
      setAssignReason("");
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  const revokeRole = async (role) => {
    const reason = window.prompt(`Reason for revoking "${role.name}":`, "Role revoked");
    if (!reason || reason.trim().length < 3) return;
    try {
      await api.post(`/role-mgmt/users/${user_id}/revoke-role`, { role_id: role.id, reason });
      toast.success("Role revoked");
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  if (loading) return <div className="text-sm text-slate-500" data-testid="user-perm-loading">Loading…</div>;
  if (!data) return <div className="text-sm text-rose-700">User not found.</div>;

  const additionalCount = Object.values(data.additional || {}).reduce((s, m) => s + Object.keys(m).length, 0);
  const restrictedCount = Object.values(data.restricted || {}).reduce((s, m) => s + Object.keys(m).length, 0);

  return (
    <div className="space-y-5" data-testid="user-permissions-page">
      <div className="flex items-end justify-between">
        <div>
          <button
            onClick={() => navigate(-1)}
            className="text-xs text-slate-500 inline-flex items-center gap-1 hover:underline mb-1"
            data-testid="back-to-users"
          >
            <ArrowLeft size={12} /> Back
          </button>
          <div className="text-[11px] uppercase tracking-wide text-slate-500 mono">User Permissions</div>
          <h1 className="text-3xl font-semibold text-slate-950 tracking-tight mt-1" style={{ fontFamily: "Work Sans" }}>
            {data.user?.name}
          </h1>
          <div className="text-xs text-slate-500 mono mt-1">{data.user?.email}</div>
        </div>

        <div className="flex items-center gap-6 text-xs">
          <div>
            <div className="text-[10px] uppercase mono text-slate-500">Roles applied</div>
            <div className="text-lg font-semibold text-slate-900" data-testid="roles-applied-count">
              {(data.roles_applied || []).length}
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase mono text-emerald-600">Additional</div>
            <div className="text-lg font-semibold text-emerald-700" data-testid="additional-count">{additionalCount}</div>
          </div>
          <div>
            <div className="text-[10px] uppercase mono text-rose-600">Restricted</div>
            <div className="text-lg font-semibold text-rose-700" data-testid="restricted-count">{restrictedCount}</div>
          </div>
        </div>
      </div>

      {/* Roles assigned */}
      <section className="border border-slate-200 bg-white rounded-sm p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-medium text-slate-900">Assigned roles</div>
        </div>
        <div className="flex flex-wrap gap-2 mb-4">
          {(data.roles_applied || []).map((r) => (
            <div
              key={r.id}
              className="inline-flex items-center gap-2 border border-slate-200 bg-slate-50 rounded-sm px-2 py-1"
              data-testid={`role-pill-${r.code}`}
            >
              <span className="text-xs font-medium text-slate-800">{r.name}</span>
              <span className="text-[10px] mono text-slate-500">({r.code})</span>
              {canManage && (
                <button
                  onClick={() => revokeRole(r)}
                  className="text-rose-600 hover:text-rose-800 ml-1"
                  data-testid={`revoke-role-${r.code}`}
                  title="Revoke"
                >
                  <Trash2 size={12} />
                </button>
              )}
            </div>
          ))}
          {(data.roles_applied || []).length === 0 && (
            <div className="text-xs text-slate-500">No roles assigned.</div>
          )}
        </div>
        {canManage && (
          <div className="grid grid-cols-1 md:grid-cols-[1fr_2fr_auto] gap-2 items-end pt-3 border-t border-slate-100">
            <div>
              <label className="text-[11px] mono uppercase text-slate-500">Assign role</label>
              <Select value={assignRoleId} onValueChange={setAssignRoleId}>
                <SelectTrigger data-testid="assign-role-select">
                  <SelectValue placeholder="Pick a role…" />
                </SelectTrigger>
                <SelectContent>
                  {allRoles.filter((r) => r.active).map((r) => (
                    <SelectItem key={r.id} value={r.id}>{r.name} <span className="text-slate-400 mono text-[10px]">({r.code})</span></SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-[11px] mono uppercase text-slate-500">Reason</label>
              <Input
                value={assignReason}
                onChange={(e) => setAssignReason(e.target.value)}
                placeholder="Reason for assignment"
                data-testid="assign-role-reason"
              />
            </div>
            <Button onClick={assignRole} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="assign-role-btn">
              <Plus size={14} className="mr-1" /> Assign
            </Button>
          </div>
        )}
      </section>

      {/* Effective permissions + overrides */}
      <Tabs defaultValue="effective" className="w-full">
        <TabsList>
          <TabsTrigger value="effective" data-testid="tab-effective">Effective Permissions</TabsTrigger>
          <TabsTrigger value="overrides" data-testid="tab-overrides">
            User-Specific Overrides ({overrides.length})
          </TabsTrigger>
        </TabsList>

        <TabsContent value="effective" className="mt-3">
          <div className="border border-slate-200 bg-white rounded-sm overflow-hidden">
            <div className="grid grid-cols-3 px-4 py-2 border-b border-slate-200 bg-slate-50 text-[10px] uppercase mono tracking-wide text-slate-500">
              <div>Module → Action</div>
              <div className="text-center">From Role(s)</div>
              <div className="text-center">Effective</div>
            </div>
            {Object.entries(modules).map(([mk, mv]) => (
              <div key={mk} className="border-b border-slate-100">
                <div className="px-4 py-2 bg-slate-50 text-xs font-medium text-slate-800 flex items-center justify-between">
                  <span>{mv.label}</span>
                  <span className="text-[10px] mono text-slate-500">{mk}</span>
                </div>
                {(mv.actions || []).map((a) => {
                  const fromRole = !!data.role_permissions?.[mk]?.[a.key];
                  const isEff = !!data.permissions?.[mk]?.[a.key];
                  const addedExtra = !!data.additional?.[mk]?.[a.key];
                  const denied = !!data.restricted?.[mk]?.[a.key];
                  return (
                    <div
                      key={`${mk}.${a.key}`}
                      className="grid grid-cols-3 px-4 py-1.5 items-center text-xs hover:bg-slate-50"
                      data-testid={`eff-row-${mk}-${a.key}`}
                    >
                      <div className="text-slate-700">{a.label} <span className="text-[10px] mono text-slate-400 ml-1">{a.key}</span></div>
                      <div className="text-center">
                        {fromRole ? (
                          <CheckCircle2 size={14} className="inline text-emerald-600" />
                        ) : (
                          <XCircle size={14} className="inline text-slate-300" />
                        )}
                      </div>
                      <div className="text-center">
                        {isEff ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] mono font-semibold uppercase rounded-sm bg-emerald-50 text-emerald-700 border border-emerald-200">
                            <CheckCircle2 size={12} /> Allow {addedExtra && !fromRole && "(+)"}
                          </span>
                        ) : denied ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] mono font-semibold uppercase rounded-sm bg-rose-50 text-rose-700 border border-rose-200">
                            <ShieldOff size={12} /> Denied
                          </span>
                        ) : (
                          <span className="text-[10px] mono text-slate-400">—</span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="overrides" className="mt-3 space-y-3">
          {canManage && (
            <div className="flex justify-end">
              <Button onClick={() => setAdding(true)} className="bg-slate-900 text-white hover:bg-slate-800" data-testid="add-override-btn">
                <Plus size={14} className="mr-1" /> Add override
              </Button>
            </div>
          )}

          {adding && (
            <div className="border border-slate-200 bg-white rounded-sm p-4 space-y-3" data-testid="add-override-form">
              <div className="text-sm font-medium text-slate-900">New user-specific permission</div>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <div>
                  <label className="text-[11px] mono uppercase text-slate-500">Type</label>
                  <Select value={form.kind} onValueChange={(v) => setForm((p) => ({ ...p, kind: v }))}>
                    <SelectTrigger data-testid="override-kind"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ADDITIONAL">Additional access</SelectItem>
                      <SelectItem value="RESTRICTED">Restricted access</SelectItem>
                      <SelectItem value="TEMPORARY">Temporary access</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-[11px] mono uppercase text-slate-500">Module</label>
                  <Select value={form.module} onValueChange={(v) => setForm((p) => ({ ...p, module: v, action: "" }))}>
                    <SelectTrigger data-testid="override-module"><SelectValue placeholder="Pick module" /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(modules).map(([mk, mv]) => (
                        <SelectItem key={mk} value={mk}>{mv.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-[11px] mono uppercase text-slate-500">Action</label>
                  <Select value={form.action} onValueChange={(v) => setForm((p) => ({ ...p, action: v }))} disabled={!form.module}>
                    <SelectTrigger data-testid="override-action"><SelectValue placeholder="Pick action" /></SelectTrigger>
                    <SelectContent>
                      {moduleActions.map((a) => (
                        <SelectItem key={a.key} value={a.key}>{a.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {form.kind === "TEMPORARY" && (
                  <div>
                    <label className="text-[11px] mono uppercase text-slate-500">Expires at</label>
                    <Input
                      type="datetime-local"
                      value={form.expires_at}
                      onChange={(e) => setForm((p) => ({ ...p, expires_at: e.target.value }))}
                      data-testid="override-expires"
                    />
                  </div>
                )}
              </div>
              <div>
                <label className="text-[11px] mono uppercase text-slate-500">Reason *</label>
                <Textarea
                  rows={2}
                  value={form.reason}
                  onChange={(e) => setForm((p) => ({ ...p, reason: e.target.value }))}
                  placeholder="e.g. Cover for QA Manager during Nov audit; reverts on 30 Nov"
                  data-testid="override-reason"
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setAdding(false)}>Cancel</Button>
                <Button onClick={submitOverride} className="bg-slate-900 text-white hover:bg-slate-800" data-testid="override-save">Save override</Button>
              </div>
            </div>
          )}

          <div className="border border-slate-200 bg-white rounded-sm overflow-x-auto">
            <table className="w-full table-dense">
              <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="text-left">Type</th>
                  <th className="text-left">Module · Action</th>
                  <th className="text-left">Effect</th>
                  <th className="text-left">Expires</th>
                  <th className="text-left">Reason</th>
                  <th className="text-left">By</th>
                  <th className="text-left">Date</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {overrides.length === 0 && (
                  <tr><td colSpan={8} className="text-center text-xs text-slate-500 py-6">No overrides on this user.</td></tr>
                )}
                {overrides.map((o) => (
                  <tr key={o.id} className="border-t border-slate-100" data-testid={`override-row-${o.id}`}>
                    <td>
                      <span
                        className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] mono font-semibold uppercase rounded-sm"
                        style={
                          o.kind === "ADDITIONAL"
                            ? { color: "#047857", background: "#ECFDF5", border: "1px solid #A7F3D0" }
                            : o.kind === "RESTRICTED"
                            ? { color: "#B91C1C", background: "#FEF2F2", border: "1px solid #FECACA" }
                            : { color: "#1D4ED8", background: "#EFF6FF", border: "1px solid #BFDBFE" }
                        }
                      >
                        {o.kind === "ADDITIONAL" && <Plus size={10} />}
                        {o.kind === "RESTRICTED" && <ShieldOff size={10} />}
                        {o.kind === "TEMPORARY" && <Clock size={10} />}
                        {o.kind}
                      </span>
                    </td>
                    <td className="text-xs mono">{o.module}.{o.action}</td>
                    <td>
                      {o.effect === "ALLOW" ? (
                        <span className="text-[10px] mono uppercase font-semibold text-emerald-700">Allow</span>
                      ) : (
                        <span className="text-[10px] mono uppercase font-semibold text-rose-700">Deny</span>
                      )}
                    </td>
                    <td className="text-[11px] mono">
                      {o.expires_at ? (
                        <span className={o.expired ? "text-slate-400 line-through" : "text-slate-700"}>
                          {new Date(o.expires_at).toLocaleString()}
                        </span>
                      ) : "—"}
                    </td>
                    <td className="text-xs italic text-slate-600 max-w-xs truncate" title={o.reason}>{o.reason}</td>
                    <td className="text-[11px] mono">{o.created_by}</td>
                    <td className="text-[11px] mono">{o.created_at ? new Date(o.created_at).toLocaleString() : "—"}</td>
                    <td className="text-right">
                      {canManage && (
                        <button
                          onClick={() => removeOverride(o)}
                          className="p-1 hover:bg-rose-50 rounded-sm text-rose-600"
                          data-testid={`remove-override-${o.id}`}
                          title="Remove"
                        >
                          <Trash2 size={14} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
