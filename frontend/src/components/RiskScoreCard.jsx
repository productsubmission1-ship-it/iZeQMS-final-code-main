import React, { useState } from "react";
import api, { formatApiError } from "../lib/api";
import { Button } from "./ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { ShieldAlert } from "lucide-react";
import { toast } from "sonner";

const BAND_COLOR = {
  CRITICAL: "bg-red-100 text-red-800 border-red-200",
  HIGH: "bg-orange-100 text-orange-800 border-orange-200",
  MEDIUM: "bg-amber-100 text-amber-800 border-amber-200",
  LOW: "bg-emerald-100 text-emerald-800 border-emerald-200",
};

export const RiskScoreCard = ({ recordId, current, onUpdated, locked = false }) => {
  const [s, setS] = useState(current?.severity || 3);
  const [o, setO] = useState(current?.occurrence || 3);
  const [d, setD] = useState(current?.detection || 3);
  const [busy, setBusy] = useState(false);
  const rpn = s * o * d;
  const band = rpn >= 60 ? "CRITICAL" : rpn >= 30 ? "HIGH" : rpn >= 12 ? "MEDIUM" : "LOW";

  const save = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/records/${recordId}/risk-score`, {
        severity: s, occurrence: o, detection: d,
        reason: "Risk priority score recalculated",
      });
      toast.success(`Risk Priority Number set: ${data.rpn} (${data.band})`);
      onUpdated?.(data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  const Picker = ({ label, val, setVal, testid }) => (
    <div>
      <label className="text-[10px] uppercase tracking-wide text-slate-500 mono">{label}</label>
      <Select value={String(val)} onValueChange={(v) => setVal(parseInt(v, 10))} disabled={locked}>
        <SelectTrigger data-testid={testid}><SelectValue /></SelectTrigger>
        <SelectContent>
          {[1, 2, 3, 4, 5].map((n) => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );

  return (
    <div className="border border-slate-200 bg-white rounded-sm" data-testid="risk-score-card">
      <div className="px-4 py-2 border-b border-slate-200 text-sm font-semibold text-slate-900 flex items-center gap-2">
        <ShieldAlert size={14} /> Risk Priority (Severity × Occurrence × Detection)
      </div>
      <div className="p-4 grid grid-cols-3 gap-3 items-end">
        <Picker label="Severity (1-5)" val={s} setVal={setS} testid="risk-severity" />
        <Picker label="Occurrence (1-5)" val={o} setVal={setO} testid="risk-occurrence" />
        <Picker label="Detection (1-5)" val={d} setVal={setD} testid="risk-detection" />
      </div>
      <div className="px-4 pb-4 flex items-center justify-between">
        <div>
          <div className="text-[10px] uppercase tracking-wide text-slate-500 mono">Risk Priority Number</div>
          <div className="flex items-center gap-2 mt-1">
            <div className="text-3xl font-bold tracking-tight text-slate-950 mono" data-testid="risk-rpn">{rpn}</div>
            <span className={`text-[11px] px-2 py-0.5 rounded-sm border uppercase tracking-wide mono ${BAND_COLOR[band]}`} data-testid="risk-band">{band}</span>
          </div>
          {current?.scored_at && (
            <div className="text-[11px] text-slate-500 mono mt-1">
              Last scored {new Date(current.scored_at).toLocaleString()} · {current.scored_by_name}
            </div>
          )}
        </div>
        {!locked && (
          <Button onClick={save} disabled={busy} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="risk-save">
            {busy ? "Saving…" : "Save score"}
          </Button>
        )}
      </div>
    </div>
  );
};

export default RiskScoreCard;
