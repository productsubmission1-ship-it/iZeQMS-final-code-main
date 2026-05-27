import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuSeparator } from "../components/ui/dropdown-menu";
import { Plus, MoreHorizontal } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import NewUserDialog from "../components/NewUserDialog";
import UserActionDialog from "../components/UserActionDialog";
import { CANONICAL_ROLES, ROLE_LABELS, hasPermission, hasRole, ROLES, canonicalize } from "../lib/roles";

const STATIC_ROLES = CANONICAL_ROLES;

const ACTION_DEFS = {
  activate: { title: "Activate user", desc: "Restore login access" },
  deactivate: { title: "Deactivate user", desc: "Remove login access" },
  lock: { title: "Lock user account", desc: "Temporarily block login" },
  unlock: { title: "Unlock user account", desc: "Allow login again" },
  approve: { title: "Approve user request", desc: "Advance through approval workflow" },
  reject: { title: "Reject user request", desc: "Decline user creation request" },
  "reset-password": { title: "Reset password", desc: "Generate temporary password" },
  "extend-expiry": { title: "Extend expiry", desc: "Update account expiry date", requireExtra: true, extraLabel: "New expiry date" },
};

export default function Users() {
  const { user: me } = useAuth();
  const navigate = useNavigate();
  // Per User Role Matrix: only Admin / Super Admin manage users (full).
  // QA Manager can only act on the APPROVE step of the user-approval workflow.
  const canManageUsers = hasPermission(me, "user_management");
  const canManagePerms = hasPermission(me, "role_management");
  const canApproveOnly = !canManageUsers && hasRole(me, ROLES.QA_MANAGER);
  const isAdminOrQA = canManageUsers || canApproveOnly;
  const [rows, setRows] = useState([]);
  const [filters, setFilters] = useState({ q: "", department: "ALL", role: "ALL", status: "ALL", location: "ALL" });
  const [newOpen, setNewOpen] = useState(false);
  const [actionState, setActionState] = useState(null); // {user, key}
  const [busy, setBusy] = useState(false);
  const [tempPw, setTempPw] = useState(null);
  const [dynamicRoles, setDynamicRoles] = useState([]);

  const load = async () => {
    const { data } = await api.get("/users");
    setRows(data);
  };
  useEffect(() => {
    load();
    api.get("/role-mgmt/roles?active=true").then((res) => setDynamicRoles(res.data || [])).catch(() => setDynamicRoles([]));
  }, []);

  const ALL_ROLES = useMemo(() => {
    const out = [...STATIC_ROLES];
    const seen = new Set(out);
    for (const r of dynamicRoles) if (r.code && !seen.has(r.code)) { out.push(r.code); seen.add(r.code); }
    return out;
  }, [dynamicRoles]);

  const roleLabel = (code) => ROLE_LABELS[canonicalize(code)] || (dynamicRoles.find((r) => r.code === code)?.name) || code;

  const departments = useMemo(() => Array.from(new Set(rows.map((r) => r.department).filter(Boolean))), [rows]);
  const locations = useMemo(() => Array.from(new Set(rows.map((r) => r.location).filter(Boolean))), [rows]);

  const filtered = useMemo(() => rows.filter((u) => {
    const q = filters.q.toLowerCase();
    if (q && !`${u.name} ${u.email} ${u.employee_id} ${u.username}`.toLowerCase().includes(q)) return false;
    if (filters.department !== "ALL" && u.department !== filters.department) return false;
    if (filters.role !== "ALL" && !(u.roles || []).includes(filters.role)) return false;
    if (filters.location !== "ALL" && u.location !== filters.location) return false;
    if (filters.status === "ACTIVE" && !(u.active && !u.locked)) return false;
    if (filters.status === "INACTIVE" && u.active) return false;
    if (filters.status === "LOCKED" && !u.locked) return false;
    if (filters.status === "PENDING" && u.approval_status === "ACTIVE") return false;
    return true;
  }), [rows, filters]);

  const runAction = async (payload) => {
    const { user: target, key } = actionState;
    setBusy(true);
    try {
      const { data } = await api.post(`/users/${target.id}/${key}`, payload);
      toast.success(`${ACTION_DEFS[key].title} successful`);
      if (data?.temp_password) setTempPw(data.temp_password);
      setActionState(null);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  const statusOf = (u) => {
    if (!u.active) return { label: "INACTIVE", color: "#64748B", bg: "#F1F5F9" };
    if (u.locked) return { label: "LOCKED", color: "#B91C1C", bg: "#FEF2F2" };
    if (u.approval_status === "PENDING_QA") return { label: "PENDING QA", color: "#B45309", bg: "#FFFBEB" };
    if (u.approval_status === "PENDING_ADMIN") return { label: "PENDING ADMIN", color: "#1D4ED8", bg: "#EFF6FF" };
    if (u.approval_status === "REJECTED") return { label: "REJECTED", color: "#B91C1C", bg: "#FEF2F2" };
    return { label: "ACTIVE", color: "#047857", bg: "#ECFDF5" };
  };

  return (
    <div className="space-y-5" data-testid="users-page">
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500 mono">Access Management</div>
          <h1 className="text-3xl font-semibold text-slate-950 tracking-tight mt-1" style={{ fontFamily: "Work Sans" }}>Users & Roles</h1>
        </div>
        {isAdminOrQA && (
          <Button onClick={() => setNewOpen(true)} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="open-new-user">
            <Plus size={16} className="mr-1" /> New User
          </Button>
        )}
      </div>

      <div className="border border-slate-200 bg-white rounded-sm p-3 flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[220px]">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Search</label>
          <Input value={filters.q} onChange={(e) => setFilters((p) => ({ ...p, q: e.target.value }))} placeholder="Name, email, employee ID, username" data-testid="users-search" />
        </div>
        <div className="w-44">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Department</label>
          <Select value={filters.department} onValueChange={(v) => setFilters((p) => ({ ...p, department: v }))}>
            <SelectTrigger data-testid="filter-dept"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All</SelectItem>
              {departments.map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="w-44">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Role</label>
          <Select value={filters.role} onValueChange={(v) => setFilters((p) => ({ ...p, role: v }))}>
            <SelectTrigger data-testid="filter-role"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All</SelectItem>
              {ALL_ROLES.map((r) => <SelectItem key={r} value={r}>{roleLabel(r)}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="w-44">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Location</label>
          <Select value={filters.location} onValueChange={(v) => setFilters((p) => ({ ...p, location: v }))}>
            <SelectTrigger data-testid="filter-location"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All</SelectItem>
              {locations.map((l) => <SelectItem key={l} value={l}>{l}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="w-44">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Status</label>
          <Select value={filters.status} onValueChange={(v) => setFilters((p) => ({ ...p, status: v }))}>
            <SelectTrigger data-testid="filter-status"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All</SelectItem>
              <SelectItem value="ACTIVE">Active</SelectItem>
              <SelectItem value="INACTIVE">Inactive</SelectItem>
              <SelectItem value="LOCKED">Locked</SelectItem>
              <SelectItem value="PENDING">Pending approval</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="text-[11px] text-slate-500 mono ml-auto">{filtered.length} users</div>
      </div>

      <div className="border border-slate-200 bg-white rounded-sm overflow-x-auto">
        <table className="w-full table-dense">
          <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
            <tr>
              <th className="text-left">Employee ID</th>
              <th className="text-left">Name</th>
              <th className="text-left">Email</th>
              <th className="text-left">Department</th>
              <th className="text-left">Location</th>
              <th className="text-left">Roles</th>
              <th className="text-left">Status</th>
              <th className="text-left">Last login</th>
              <th className="text-left">Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((u) => {
              const st = statusOf(u);
              return (
                <tr key={u.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`user-row-${u.email}`}>
                  <td className="mono text-xs">{u.employee_id || "—"}</td>
                  <td><div className="font-medium text-slate-900">{u.name}</div><div className="text-[11px] mono text-slate-500">{u.username}</div></td>
                  <td className="mono text-xs">{u.email}</td>
                  <td className="text-xs">{u.department}</td>
                  <td className="text-xs">{u.location}</td>
                  <td className="text-xs">{(u.roles || []).map((r) => roleLabel(r)).join(", ")}</td>
                  <td>
                    <span className="inline-block px-2 py-0.5 text-[10px] mono font-semibold uppercase rounded-sm" style={{ color: st.color, background: st.bg, border: `1px solid ${st.color}33` }} data-testid={`user-status-${u.email}`}>{st.label}</span>
                  </td>
                  <td className="mono text-[11px]">{u.last_login ? new Date(u.last_login).toLocaleString() : "—"}</td>
                  <td className="mono text-[11px]">{u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}</td>
                  <td className="text-right">
                    <div className="flex items-center gap-1 justify-end">
                      {canManagePerms && (
                        <Link
                          to={`/users/${u.id}/permissions`}
                          data-testid={`user-perms-${u.email}`}
                          className="text-[10px] mono uppercase tracking-wide px-2 py-1 border border-slate-300 rounded-sm hover:bg-slate-100 text-slate-700"
                          title="Manage user-specific permissions"
                        >
                          Permissions
                        </Link>
                      )}
                      {isAdminOrQA && (
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button data-testid={`user-actions-${u.email}`} className="p-1 hover:bg-slate-200 rounded-sm"><MoreHorizontal size={16} /></button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-52">
                          {u.approval_status !== "ACTIVE" && u.approval_status !== "REJECTED" && (
                            <>
                              <DropdownMenuItem onClick={() => setActionState({ user: u, key: "approve" })} data-testid={`user-act-approve-${u.email}`}>Approve</DropdownMenuItem>
                              <DropdownMenuItem onClick={() => setActionState({ user: u, key: "reject" })} data-testid={`user-act-reject-${u.email}`}>Reject</DropdownMenuItem>
                              <DropdownMenuSeparator />
                            </>
                          )}
                          {u.active ? (
                            <DropdownMenuItem onClick={() => setActionState({ user: u, key: "deactivate" })} data-testid={`user-act-deactivate-${u.email}`}>Deactivate</DropdownMenuItem>
                          ) : (
                            <DropdownMenuItem onClick={() => setActionState({ user: u, key: "activate" })} data-testid={`user-act-activate-${u.email}`}>Activate</DropdownMenuItem>
                          )}
                          {u.locked ? (
                            <DropdownMenuItem onClick={() => setActionState({ user: u, key: "unlock" })} data-testid={`user-act-unlock-${u.email}`}>Unlock</DropdownMenuItem>
                          ) : (
                            <DropdownMenuItem onClick={() => setActionState({ user: u, key: "lock" })} data-testid={`user-act-lock-${u.email}`}>Lock</DropdownMenuItem>
                          )}
                          <DropdownMenuItem onClick={() => setActionState({ user: u, key: "reset-password" })} data-testid={`user-act-reset-${u.email}`}>Reset password</DropdownMenuItem>
                          <DropdownMenuItem onClick={() => setActionState({ user: u, key: "extend-expiry" })} data-testid={`user-act-expiry-${u.email}`}>Extend expiry</DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <NewUserDialog open={newOpen} onOpenChange={setNewOpen} onCreated={load} currentUser={me} />

      <UserActionDialog
        open={!!actionState}
        onOpenChange={(o) => !o && setActionState(null)}
        title={actionState ? `${ACTION_DEFS[actionState.key].title}: ${actionState.user.name}` : ""}
        description={actionState ? ACTION_DEFS[actionState.key].desc : ""}
        onConfirm={runAction}
        busy={busy}
        requireExtra={actionState && ACTION_DEFS[actionState.key].requireExtra}
        extraLabel={actionState && ACTION_DEFS[actionState.key].extraLabel}
      />

      {tempPw && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" data-testid="temp-pw-modal">
          <div className="bg-white p-6 rounded-sm max-w-md w-full mx-4 border border-slate-200">
            <div className="text-sm font-semibold text-slate-900">Temporary password generated</div>
            <div className="mono text-xl font-bold mt-3 select-all p-3 bg-slate-50 border border-slate-200 rounded-sm" data-testid="reset-temp-pw">{tempPw}</div>
            <div className="text-xs text-slate-600 mt-2">Share securely. User must change at next login.</div>
            <div className="mt-4 flex justify-end"><Button onClick={() => setTempPw(null)} className="bg-slate-900 text-white" data-testid="close-temp-pw">Done</Button></div>
          </div>
        </div>
      )}
    </div>
  );
}
