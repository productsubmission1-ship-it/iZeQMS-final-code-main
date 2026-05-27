import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "../lib/api";
import StatusBadge from "../components/StatusBadge";
import { TrendingUp, AlertTriangle, ClipboardList, Clock } from "lucide-react";

const TYPE_LABEL = {
  CHANGE_CONTROL: "Change Control",
  DEVIATION: "Deviation",
  CAPA: "CAPA",
  INCIDENT: "Incident",
  EVENT: "Event",
};
const TYPE_ROUTE = {
  CHANGE_CONTROL: "/records/CHANGE_CONTROL",
  DEVIATION: "/records/DEVIATION",
  CAPA: "/records/CAPA",
  INCIDENT: "/records/INCIDENT",
  EVENT: "/records/EVENT",
};

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [tasks, setTasks] = useState([]);

  useEffect(() => {
    (async () => {
      const [s, t] = await Promise.all([api.get("/dashboard/summary"), api.get("/dashboard/my-tasks")]);
      setSummary(s.data);
      setTasks(t.data);
    })();
  }, []);

  if (!summary) return <div className="text-slate-500 text-sm" data-testid="dashboard-loading">Loading dashboard…</div>;

  const kpis = [
    { label: "Open", value: summary.totals.OPEN || 0, icon: ClipboardList, key: "open" },
    { label: "In Review", value: summary.totals.IN_REVIEW || 0, icon: TrendingUp, key: "review" },
    { label: "Overdue", value: summary.overdue_count, icon: AlertTriangle, key: "overdue", danger: true },
    { label: "Closed", value: summary.totals.CLOSED || 0, icon: Clock, key: "closed" },
  ];

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      <div>
        <h1 className="text-3xl font-semibold text-slate-950 tracking-tight" style={{ fontFamily: "Work Sans" }}>Quality Dashboard</h1>
        <p className="text-sm text-slate-500 mt-1">Real-time operational view across all QMS modules.</p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {kpis.map((k) => (
          <div key={k.key} data-testid={`kpi-${k.key}`} className={`border bg-white p-4 rounded-sm ${k.danger && k.value > 0 ? "border-red-300" : "border-slate-200"}`}>
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-wide text-slate-500">{k.label}</span>
              <k.icon size={16} className={k.danger && k.value > 0 ? "text-red-600" : "text-slate-500"} />
            </div>
            <div className={`text-3xl mt-2 font-semibold mono ${k.danger && k.value > 0 ? "text-red-700" : "text-slate-950"}`}>{k.value}</div>
          </div>
        ))}
      </div>

      {/* By type */}
      <div className="border border-slate-200 bg-white rounded-sm">
        <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-slate-900">QMS Modules · Distribution</div>
            <div className="text-[11px] text-slate-500 mono">Count by type and current status</div>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-5 divide-y md:divide-y-0 md:divide-x divide-slate-200">
          {Object.keys(TYPE_LABEL).map((t) => {
            const bucket = summary.by_type[t] || {};
            const total = Object.values(bucket).reduce((a, b) => a + b, 0);
            return (
              <Link to={TYPE_ROUTE[t]} key={t} className="p-4 hover:bg-slate-50 transition-colors" data-testid={`type-card-${t}`}>
                <div className="text-xs uppercase tracking-wide text-slate-500">{TYPE_LABEL[t]}</div>
                <div className="text-2xl mono font-semibold text-slate-950 mt-1">{total}</div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {Object.entries(bucket).map(([s, c]) => (
                    <span key={s} className="text-[10px] mono text-slate-600">{s}:{c}</span>
                  ))}
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      {/* My tasks */}
      <div className="border border-slate-200 bg-white rounded-sm">
        <div className="px-4 py-3 border-b border-slate-200">
          <div className="text-sm font-semibold text-slate-900">My Pending Tasks</div>
          <div className="text-[11px] text-slate-500 mono">Records awaiting your review or approval</div>
        </div>
        {tasks.length === 0 ? (
          <div className="p-6 text-sm text-slate-500" data-testid="no-tasks">No pending tasks.</div>
        ) : (
          <table className="w-full table-dense" data-testid="my-tasks-table">
            <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
              <tr><th className="text-left">Record</th><th className="text-left">Type</th><th className="text-left">Title</th><th className="text-left">Status</th><th className="text-left">Due</th></tr>
            </thead>
            <tbody>
              {tasks.map((r) => {
                const overdue = r.due_date && new Date(r.due_date) < new Date() && !["CLOSED", "APPROVED", "REJECTED"].includes(r.status);
                return (
                  <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="mono"><Link className="text-slate-900 underline-offset-2 hover:underline" to={`/record/${r.id}`} data-testid={`task-link-${r.record_number}`}>{r.record_number}</Link></td>
                    <td>{TYPE_LABEL[r.type]}</td>
                    <td className="max-w-md truncate">{r.title}</td>
                    <td><StatusBadge status={r.status} overdue={overdue} /></td>
                    <td className="mono text-xs">{r.due_date ? new Date(r.due_date).toLocaleDateString() : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Recent */}
      <div className="border border-slate-200 bg-white rounded-sm">
        <div className="px-4 py-3 border-b border-slate-200">
          <div className="text-sm font-semibold text-slate-900">Recent Activity</div>
        </div>
        <table className="w-full table-dense">
          <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
            <tr><th className="text-left">Record</th><th className="text-left">Type</th><th className="text-left">Title</th><th className="text-left">Status</th><th className="text-left">Updated</th></tr>
          </thead>
          <tbody>
            {summary.recent.map((r) => (
              <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                <td className="mono"><Link className="text-slate-900 underline-offset-2 hover:underline" to={`/record/${r.id}`}>{r.record_number}</Link></td>
                <td>{TYPE_LABEL[r.type] || r.type}</td>
                <td className="max-w-md truncate">{r.title}</td>
                <td><StatusBadge status={r.status} /></td>
                <td className="mono text-xs">{new Date(r.updated_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
