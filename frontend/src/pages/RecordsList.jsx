import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import api from "../lib/api";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import StatusBadge from "../components/StatusBadge";
import { Plus } from "lucide-react";

const TYPE_META = {
  ALL: { label: "All Records", prefix: "ALL" },
  CHANGE_CONTROL: { label: "Change Control", prefix: "CC" },
  DEVIATION: { label: "Deviation", prefix: "DEV" },
  CAPA: { label: "CAPA", prefix: "CAPA" },
  INCIDENT: { label: "Incident", prefix: "INC" },
  EVENT: { label: "Event", prefix: "EVT" },
};

export default function RecordsList() {
  const { type } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const initialQ = params.get("q") || "";
  const [q, setQ] = useState(initialQ);
  const [status, setStatus] = useState("ALL");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);

  const meta = TYPE_META[type] || TYPE_META.ALL;

  useEffect(() => {
    setQ(initialQ);
    setStatus("ALL");
  }, [type, initialQ]);

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [type, q, status]);

  const load = async () => {
    setLoading(true);
    const qs = new URLSearchParams();
    if (type && type !== "ALL") qs.set("type", type);
    if (status && status !== "ALL") qs.set("status", status);
    if (q) qs.set("q", q);
    const { data } = await api.get(`/records?${qs.toString()}`);
    setRows(data);
    setLoading(false);
  };

  const counts = useMemo(() => {
    const m = { OPEN: 0, IN_REVIEW: 0, APPROVED: 0, REJECTED: 0, CLOSED: 0 };
    rows.forEach((r) => { m[r.status] = (m[r.status] || 0) + 1; });
    return m;
  }, [rows]);

  return (
    <div className="space-y-5" data-testid="records-list-page">
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500 mono">{meta.prefix} · Module</div>
          <h1 className="text-3xl font-semibold text-slate-950 tracking-tight mt-1" style={{ fontFamily: "Work Sans" }}>{meta.label}</h1>
        </div>
        {type && type !== "ALL" && (
          <Button onClick={() => navigate(`/new/${type}`)} data-testid="new-record-btn" className="bg-slate-900 hover:bg-slate-800 text-white">
            <Plus size={16} className="mr-1" /> New {meta.label}
          </Button>
        )}
      </div>

      {/* Filters */}
      <div className="border border-slate-200 bg-white rounded-sm p-3 flex flex-wrap items-end gap-3">
        <div className="flex-1 min-w-[220px]">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Search</label>
          <Input data-testid="records-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Record number, title or description…" />
        </div>
        <div className="w-44">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Status</label>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger data-testid="records-status-filter"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All</SelectItem>
              <SelectItem value="OPEN">Open</SelectItem>
              <SelectItem value="IN_REVIEW">In Review</SelectItem>
              <SelectItem value="APPROVED">Approved</SelectItem>
              <SelectItem value="REJECTED">Rejected</SelectItem>
              <SelectItem value="CLOSED">Closed</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="text-[11px] text-slate-500 mono ml-auto">
          {Object.entries(counts).map(([s, c]) => <span key={s} className="ml-3">{s}:{c}</span>)}
        </div>
      </div>

      <div className="border border-slate-200 bg-white rounded-sm">
        <table className="w-full table-dense">
          <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
            <tr>
              <th className="text-left">Record No.</th>
              <th className="text-left">Type</th>
              <th className="text-left">Title</th>
              <th className="text-left">Department</th>
              <th className="text-left">Severity</th>
              <th className="text-left">Status</th>
              <th className="text-left">Due</th>
              <th className="text-left">Initiator</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} className="p-6 text-center text-sm text-slate-500" data-testid="records-loading">Loading…</td></tr>
            ) : rows.length === 0 ? (
              <tr><td colSpan={8} className="p-6 text-center text-sm text-slate-500" data-testid="records-empty">No records found.</td></tr>
            ) : (
              rows.map((r) => {
                const overdue = r.due_date && new Date(r.due_date) < new Date() && !["CLOSED", "APPROVED", "REJECTED"].includes(r.status);
                return (
                  <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="mono"><Link className="text-slate-900 hover:underline" to={`/record/${r.id}`} data-testid={`row-link-${r.record_number}`}>{r.record_number}</Link></td>
                    <td className="text-xs">{TYPE_META[r.type]?.label || r.type}</td>
                    <td className="max-w-md truncate">{r.title}</td>
                    <td className="text-xs">{r.department}</td>
                    <td className="text-xs">{r.severity}</td>
                    <td><StatusBadge status={r.status} overdue={overdue} /></td>
                    <td className="mono text-xs">{r.due_date ? new Date(r.due_date).toLocaleDateString() : "—"}</td>
                    <td className="text-xs">{r.initiator_name}</td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
