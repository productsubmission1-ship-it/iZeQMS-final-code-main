import React, { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import UserActionDialog from "../components/UserActionDialog";
import { hasPermission } from "../lib/roles";

export default function Settings() {
  const { user } = useAuth();
  // Per User Role Matrix: only Admin / Super Admin manage roles & workflow config.
  const isAdmin = hasPermission(user, "role_management");
  const [policy, setPolicy] = useState({});
  const [sessions, setSessions] = useState([]);
  const [busy, setBusy] = useState(false);
  const [revokeTarget, setRevokeTarget] = useState(null);

  const loadAll = async () => {
    const [p, s] = await Promise.all([
      api.get("/settings/password-policy"),
      isAdmin ? api.get("/sessions") : Promise.resolve({ data: [] }),
    ]);
    setPolicy(p.data);
    setSessions(s.data);
  };
  useEffect(() => { loadAll(); /* eslint-disable-next-line */ }, [isAdmin]);

  const savePolicy = async () => {
    if (!isAdmin) return;
    setBusy(true);
    try {
      const payload = { ...policy };
      delete payload.key;
      await api.patch("/settings/password-policy", payload);
      toast.success("Password policy updated");
      loadAll();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (payload) => {
    setBusy(true);
    try {
      await api.post(`/sessions/${revokeTarget.id}/revoke`, payload);
      toast.success("Session revoked");
      setRevokeTarget(null);
      loadAll();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="settings-page">
      <div>
        <div className="text-[11px] uppercase tracking-wide text-slate-500 mono">Administration</div>
        <h1 className="text-3xl font-semibold text-slate-950 tracking-tight mt-1" style={{ fontFamily: "Work Sans" }}>Settings</h1>
      </div>

      <div className="border border-slate-200 bg-white rounded-sm">
        <div className="px-4 py-2 border-b border-slate-200 text-sm font-semibold text-slate-900">Password Policy</div>
        <div className="p-4 grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            ["min_length", "Min length", "number"],
            ["expiry_days", "Expiry (days)", "number"],
            ["max_failed_attempts", "Max failed attempts", "number"],
            ["lockout_minutes", "Lockout (min)", "number"],
            ["session_timeout_minutes", "Session timeout (min)", "number"],
            ["history_size", "Password history", "number"],
          ].map(([k, l]) => (
            <div key={k}>
              <Label className="text-xs uppercase tracking-wide text-slate-500">{l}</Label>
              <Input
                type="number"
                value={policy[k] ?? ""}
                onChange={(e) => setPolicy((p) => ({ ...p, [k]: parseInt(e.target.value || "0", 10) }))}
                disabled={!isAdmin}
                data-testid={`policy-${k}`}
              />
            </div>
          ))}
          {["require_upper", "require_lower", "require_digit", "require_special"].map((k) => (
            <div key={k} className="flex items-center justify-between border border-slate-100 rounded-sm px-3 py-2">
              <Label className="text-xs uppercase tracking-wide text-slate-500">{k.replace("require_", "Require ")}</Label>
              <Switch checked={!!policy[k]} onCheckedChange={(v) => setPolicy((p) => ({ ...p, [k]: v }))} disabled={!isAdmin} data-testid={`policy-${k}`} />
            </div>
          ))}
        </div>
        {isAdmin && (
          <div className="px-4 py-3 border-t border-slate-200 flex justify-end">
            <Button onClick={savePolicy} disabled={busy} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="policy-save">{busy ? "Saving…" : "Save policy"}</Button>
          </div>
        )}
      </div>

      {isAdmin && (
        <div className="border border-slate-200 bg-white rounded-sm">
          <div className="px-4 py-2 border-b border-slate-200 text-sm font-semibold text-slate-900">Active Sessions</div>
          {sessions.length === 0 ? (
            <div className="p-6 text-sm text-slate-500" data-testid="sessions-empty">No active sessions.</div>
          ) : (
            <table className="w-full table-dense">
              <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
                <tr><th className="text-left">User</th><th className="text-left">Roles</th><th className="text-left">Last login</th><th></th></tr>
              </thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.id} className="border-t border-slate-100" data-testid={`session-row-${s.email}`}>
                    <td><div className="font-medium text-slate-900">{s.name}</div><div className="text-xs text-slate-500 mono">{s.email}</div></td>
                    <td className="text-xs">{(s.roles || []).join(", ")}</td>
                    <td className="mono text-xs">{new Date(s.last_login).toLocaleString()}</td>
                    <td className="text-right">
                      <Button variant="outline" size="sm" onClick={() => setRevokeTarget(s)} data-testid={`revoke-${s.email}`}>Force logout</Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <UserActionDialog
        open={!!revokeTarget}
        onOpenChange={(o) => !o && setRevokeTarget(null)}
        title={`Force logout ${revokeTarget?.name || ""}`}
        description="This will invalidate all active sessions for the user"
        onConfirm={revoke}
        busy={busy}
      />
    </div>
  );
}
