import React, { useEffect, useMemo, useState } from "react";
import api, { API_BASE } from "../lib/api";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Input } from "../components/ui/input";
import { Printer, Download, FileSpreadsheet, FileDown } from "lucide-react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend, LineChart, Line,
} from "recharts";
import { toast } from "sonner";

const TYPE_LABEL = { CHANGE_CONTROL: "Change Control", DEVIATION: "Deviation", CAPA: "CAPA", INCIDENT: "Incident", EVENT: "Event" };
const TYPE_COLOR = {
  CHANGE_CONTROL: "#0f172a",
  DEVIATION: "#dc2626",
  CAPA: "#0891b2",
  INCIDENT: "#ea580c",
  EVENT: "#7c3aed",
};

export default function Reports() {
  const [type, setType] = useState("ALL");
  const [status, setStatus] = useState("ALL");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [rows, setRows] = useState([]);
  const [trend, setTrend] = useState(null);
  const [aging, setAging] = useState(null);
  const [months, setMonths] = useState(6);

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [type, status, from, to]);
  useEffect(() => { loadCharts(); /* eslint-disable-next-line */ }, [months]);

  const params = () => {
    const qs = new URLSearchParams();
    if (type !== "ALL") qs.set("type", type);
    if (status !== "ALL") qs.set("status", status);
    if (from) qs.set("from_date", new Date(from).toISOString());
    if (to) qs.set("to_date", new Date(to).toISOString());
    return qs;
  };

  const load = async () => {
    const qs = params();
    qs.set("limit", "500");
    const { data } = await api.get(`/records?${qs.toString()}`);
    setRows(data);
  };

  const loadCharts = async () => {
    try {
      const [t, a] = await Promise.all([
        api.get(`/reports/trend?months=${months}`),
        api.get(`/reports/aging`),
      ]);
      setTrend(t.data);
      setAging(a.data);
    } catch (e) {
      // silent
    }
  };

  const trendData = useMemo(() => {
    if (!trend) return [];
    return trend.buckets.map((b) => {
      const row = { month: b };
      Object.keys(TYPE_LABEL).forEach((k) => { row[k] = trend.by_type[b]?.[k] || 0; });
      row.CLOSED = trend.closed_per_month[b] || 0;
      return row;
    });
  }, [trend]);

  const agingData = useMemo(() => {
    if (!aging) return [];
    return aging.bands.map((b) => {
      const row = { band: `${b} d` };
      Object.keys(TYPE_LABEL).forEach((k) => { row[k] = aging.by_type[k]?.[b] || 0; });
      return row;
    });
  }, [aging]);

  const downloadExport = async (fmt) => {
    const qs = params();
    const path = fmt === "csv" ? "/exports/records.csv" : "/exports/records.xlsx";
    try {
      const token = localStorage.getItem("izqms_token");
      const res = await fetch(`${API_BASE}${path}?${qs.toString()}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
      });
      if (!res.ok) throw new Error(`Export failed (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `izqms-records-${new Date().toISOString().slice(0, 10)}.${fmt}`;
      link.click();
      URL.revokeObjectURL(url);
      toast.success(`Downloaded ${fmt.toUpperCase()}`);
    } catch (e) {
      toast.error(e.message);
    }
  };

  const printReport = () => window.print();

  const downloadPdf = async () => {
    try {
      const qs = params();
      qs.set("include_workflows", "true");
      const res = await api.get(`/reports/pdf?${qs.toString()}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const a = document.createElement("a");
      a.href = url; a.download = `izqms-report-${new Date().toISOString().slice(0,10)}.pdf`;
      document.body.appendChild(a); a.click(); a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Report PDF downloaded — logged in audit trail");
    } catch (e) {
      toast.error(e.message);
    }
  };

  return (
    <div className="space-y-5" data-testid="reports-page">
      <div className="flex items-end justify-between print:hidden">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500 mono">Reports</div>
          <h1 className="text-3xl font-semibold text-slate-950 tracking-tight mt-1" style={{ fontFamily: "Work Sans" }}>QMS Activity Report</h1>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => downloadExport("csv")} data-testid="export-csv">
            <Download size={14} className="mr-1" /> CSV
          </Button>
          <Button variant="outline" onClick={() => downloadExport("xlsx")} data-testid="export-xlsx">
            <FileSpreadsheet size={14} className="mr-1" /> Excel
          </Button>
          <Button onClick={downloadPdf} data-testid="download-report-pdf" className="bg-slate-900 hover:bg-slate-800 text-white">
            <FileDown size={16} className="mr-1" /> Download PDF
          </Button>
          <Button variant="outline" onClick={printReport} data-testid="print-report">
            <Printer size={14} className="mr-1" /> Print
          </Button>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 print:hidden">
        <div className="border border-slate-200 bg-white rounded-sm p-4" data-testid="trend-chart">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-sm font-semibold text-slate-900">Monthly trend by module</div>
              <div className="text-[11px] text-slate-500 mono">Records created per month</div>
            </div>
            <Select value={String(months)} onValueChange={(v) => setMonths(parseInt(v, 10))}>
              <SelectTrigger className="w-28 h-8 text-xs" data-testid="trend-months"><SelectValue /></SelectTrigger>
              <SelectContent>
                {[3, 6, 12].map((n) => <SelectItem key={n} value={String(n)}>{n} months</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <LineChart data={trendData} margin={{ top: 8, right: 16, bottom: 8, left: -16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="month" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" allowDecimals={false} />
                <Tooltip contentStyle={{ fontSize: 12, border: "1px solid #e2e8f0", borderRadius: 2 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {Object.entries(TYPE_LABEL).map(([k, v]) => (
                  <Line key={k} type="monotone" dataKey={k} name={v} stroke={TYPE_COLOR[k]} strokeWidth={2} dot={{ r: 2 }} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="border border-slate-200 bg-white rounded-sm p-4" data-testid="aging-chart">
          <div className="mb-3">
            <div className="text-sm font-semibold text-slate-900">Aging of open records</div>
            <div className="text-[11px] text-slate-500 mono">By module — non-closed records grouped by age</div>
          </div>
          <div style={{ width: "100%", height: 260 }}>
            <ResponsiveContainer>
              <BarChart data={agingData} margin={{ top: 8, right: 16, bottom: 8, left: -16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="band" tick={{ fontSize: 11 }} stroke="#94a3b8" />
                <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" allowDecimals={false} />
                <Tooltip contentStyle={{ fontSize: 12, border: "1px solid #e2e8f0", borderRadius: 2 }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {Object.entries(TYPE_LABEL).map(([k, v]) => (
                  <Bar key={k} dataKey={k} name={v} stackId="age" fill={TYPE_COLOR[k]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="border border-slate-200 bg-white rounded-sm p-3 flex flex-wrap items-end gap-3 print:hidden">
        <div className="w-44">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Type</label>
          <Select value={type} onValueChange={setType}>
            <SelectTrigger data-testid="report-type"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All</SelectItem>
              {Object.entries(TYPE_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="w-44">
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Status</label>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger data-testid="report-status"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All</SelectItem>
              <SelectItem value="DRAFT">Draft</SelectItem>
              <SelectItem value="OPEN">Open</SelectItem>
              <SelectItem value="IN_REVIEW">In Review</SelectItem>
              <SelectItem value="APPROVED">Approved</SelectItem>
              <SelectItem value="REJECTED">Rejected</SelectItem>
              <SelectItem value="CLOSED">Closed</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">From</label>
          <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} data-testid="report-from" />
        </div>
        <div>
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">To</label>
          <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} data-testid="report-to" />
        </div>
        <div className="ml-auto text-[11px] text-slate-500 mono">{rows.length} records</div>
      </div>

      <div className="border border-slate-200 bg-white rounded-sm p-6" data-testid="report-content">
        <div className="flex items-center justify-between border-b border-slate-200 pb-3 mb-4">
          <div>
            <div className="font-bold text-slate-900 text-lg" style={{ fontFamily: "Work Sans" }}>izQMS — Quality Management Report</div>
            <div className="text-[11px] mono text-slate-500">Generated: {new Date().toLocaleString()} · Page 1 of 1</div>
          </div>
          <div className="text-right">
            <div className="w-10 h-10 bg-slate-900 text-white flex items-center justify-center rounded-sm font-bold tracking-tighter ml-auto">iz</div>
            <div className="text-[10px] mono text-slate-500 mt-1">21 CFR Part 11 · GxP</div>
          </div>
        </div>

        <table className="w-full table-dense">
          <thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500">
            <tr>
              <th className="text-left">Record No.</th><th className="text-left">Type</th><th className="text-left">Title</th><th className="text-left">Dept</th><th className="text-left">Severity</th><th className="text-left">Status</th><th className="text-left">Initiator</th><th className="text-left">Created</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-100">
                <td className="mono">{r.record_number}</td>
                <td className="text-xs">{TYPE_LABEL[r.type] || r.type}</td>
                <td className="text-xs max-w-md truncate">{r.title}</td>
                <td className="text-xs">{r.department}</td>
                <td className="text-xs">{r.severity}</td>
                <td className="text-xs">{r.status}</td>
                <td className="text-xs">{r.initiator_name}</td>
                <td className="mono text-[11px]">{new Date(r.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
