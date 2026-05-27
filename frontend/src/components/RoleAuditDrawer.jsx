import React, { useEffect, useState } from "react";
import { X } from "lucide-react";
import api from "../lib/api";

export default function RoleAuditDrawer({ role, onClose }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!role) return;
    setLoading(true);
    api.get(`/role-mgmt/roles/${role.id}/audit`)
      .then((r) => setRows(r.data || []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  }, [role]);

  if (!role) return null;

  return (
    <div className="fixed inset-0 z-50 flex" data-testid="role-audit-drawer">
      <div className="flex-1 bg-black/30" onClick={onClose} />
      <div className="w-[640px] max-w-full bg-white border-l border-slate-200 flex flex-col">
        <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
          <div>
            <div className="text-[10px] uppercase tracking-wide text-slate-500 mono">Audit Trail</div>
            <div className="text-base font-semibold text-slate-900">{role.name}</div>
            <div className="text-[10px] mono text-slate-500">{role.code}</div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-sm" data-testid="close-audit-drawer">
            <X size={16} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {loading && <div className="text-xs text-slate-500">Loading…</div>}
          {!loading && rows.length === 0 && (
            <div className="text-xs text-slate-500">No audit entries yet.</div>
          )}
          {rows.map((e) => (
            <div key={e.id} className="border border-slate-200 rounded-sm p-3 bg-slate-50" data-testid={`audit-entry-${e.id}`}>
              <div className="flex items-center justify-between">
                <div className="text-xs font-semibold text-slate-900">{e.action}</div>
                <div className="text-[10px] mono text-slate-500">{e.timestamp}</div>
              </div>
              <div className="text-xs text-slate-700 mt-1">
                <span className="mono">{e.user_email}</span> {e.user_name ? `(${e.user_name})` : ""}
              </div>
              {e.reason && (
                <div className="text-xs italic text-slate-600 mt-1">"{e.reason}"</div>
              )}
              {(e.old_value || e.new_value) && (
                <div className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
                  <div className="border border-rose-100 bg-rose-50 rounded-sm p-2">
                    <div className="text-[10px] uppercase mono text-rose-700 mb-1">Old</div>
                    <pre className="whitespace-pre-wrap break-all mono text-rose-900">{JSON.stringify(e.old_value, null, 1)}</pre>
                  </div>
                  <div className="border border-emerald-100 bg-emerald-50 rounded-sm p-2">
                    <div className="text-[10px] uppercase mono text-emerald-700 mb-1">New</div>
                    <pre className="whitespace-pre-wrap break-all mono text-emerald-900">{JSON.stringify(e.new_value, null, 1)}</pre>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
