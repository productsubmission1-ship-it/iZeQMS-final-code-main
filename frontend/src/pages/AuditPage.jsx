import React, { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { humanizeAuditEntry } from "../lib/audit";
import { FileDown } from "lucide-react";
import { toast } from "sonner";

export default function AuditPage() {
  const [rows, setRows] = useState([]);
  const [filters, setFilters] = useState({ entity_type: "ALL", action: "", user_email: "", from_date: "", to_date: "" });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const t = setTimeout(load, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const load = async () => {
    setLoading(true);
    const qs = new URLSearchParams();
    if (filters.entity_type && filters.entity_type !== "ALL") qs.set("entity_type", filters.entity_type);
    if (filters.action) qs.set("action", filters.action);
    if (filters.user_email) qs.set("user_email", filters.user_email);
    if (filters.from_date) qs.set("from_date", new Date(filters.from_date).toISOString());
    if (filters.to_date) qs.set("to_date", new Date(filters.to_date).toISOString());
    const { data } = await api.get(`/audit?${qs.toString()}&limit=500`);
    setRows(data);
    setLoading(false);
  };

  return (
    <div className="space-y-5" data-testid="audit-page">
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500 mono">21 CFR Part 11</div>
          <h1 className="text-3xl font-semibold text-slate-950 tracking-tight mt-1" style={{ fontFamily: "Work Sans" }}>Global Audit Trail</h1>
          <p className="text-sm text-slate-500 mt-1">Immutable, time-stamped log of every action across the platform.</p>
        </div>
        <Button
          onClick={async () => {
            try {
              const qs = new URLSearchParams();
              if (filters.entity_type && filters.entity_type !== "ALL") qs.set("entity_type", filters.entity_type);
              if (filters.action) qs.set("action", filters.action);
              if (filters.user_email) qs.set("user_email", filters.user_email);
              if (filters.from_date) qs.set("from_date", new Date(filters.from_date).toISOString());
              if (filters.to_date) qs.set("to_date", new Date(filters.to_date).toISOString());
              const res = await api.get(`/audit/pdf?${qs.toString()}`, { responseType: "blob" });
              const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
              const a = document.createElement("a");
              a.href = url; a.download = `audit-trail-${new Date().toISOString().slice(0,10)}.pdf`;
              document.body.appendChild(a); a.click(); a.remove();
              window.URL.revokeObjectURL(url);
              toast.success("Audit PDF downloaded — download logged in audit trail");
            } catch (e) {
              toast.error(formatApiError(e.response?.data?.detail) || e.message);
            }
          }}
          className="bg-slate-900 hover:bg-slate-800 text-white"
          data-testid="audit-pdf-btn"
        >
          <FileDown size={14} className="mr-1" /> Download PDF
        </Button>
      </div>

      <div className="border border-slate-200 bg-white rounded-sm p-3 flex flex-wrap items-end gap-3">
        <div className="w-48">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Entity</label>
          <Select value={filters.entity_type} onValueChange={(v) => setFilters((p) => ({ ...p, entity_type: v }))}>
            <SelectTrigger data-testid="audit-entity-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All</SelectItem>
              <SelectItem value="RECORD">Records</SelectItem>
              <SelectItem value="USER">Users</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="w-48">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Action</label>
          <Input data-testid="audit-action-filter" value={filters.action} onChange={(e) => setFilters((p) => ({ ...p, action: e.target.value }))} placeholder="e.g. WORKFLOW_APPROVE" />
        </div>
        <div className="w-64">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">User Email</label>
          <Input data-testid="audit-user-filter" value={filters.user_email} onChange={(e) => setFilters((p) => ({ ...p, user_email: e.target.value }))} placeholder="user@izqms.com" />
        </div>
        <div>
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">From</label>
          <Input type="date" value={filters.from_date} onChange={(e) => setFilters((p) => ({ ...p, from_date: e.target.value }))} data-testid="audit-from" />
        </div>
        <div>
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">To</label>
          <Input type="date" value={filters.to_date} onChange={(e) => setFilters((p) => ({ ...p, to_date: e.target.value }))} data-testid="audit-to" />
        </div>
        <div className="text-[11px] text-slate-500 mono ml-auto">{rows.length} entries</div>
      </div>

      <div className="border border-slate-200 bg-white rounded-sm overflow-hidden">
        <div className="max-h-[700px] overflow-y-auto">
          <table className="w-full table-dense text-[12px]">
            <thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500 sticky top-0">
              <tr>
                <th className="text-left">Timestamp</th>
                <th className="text-left">User</th>
                <th className="text-left">Action</th>
                <th className="text-left">Detail</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={4} className="p-6 text-center text-slate-500" data-testid="audit-loading">Loading…</td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={4} className="p-6 text-center text-slate-500" data-testid="audit-empty">No audit entries.</td></tr>
              ) : (
                rows.map((a) => {
                  const h = humanizeAuditEntry(a);
                  return (
                    <tr key={a.id} className="border-t border-slate-100 align-top">
                      <td className="whitespace-nowrap mono">{new Date(a.timestamp).toLocaleString()}</td>
                      <td className="mono">{a.user_email}</td>
                      <td className="font-semibold text-slate-900">{a.action}</td>
                      <td className="max-w-xl break-words text-slate-700">
                        <div>{h.sentence}</div>
                        {h.diff && <div className="text-[11px] text-slate-500 mt-0.5">{h.diff}</div>}
                        {h.reason && <div className="text-[11px] text-slate-500 mt-0.5">Reason: {h.reason}</div>}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
