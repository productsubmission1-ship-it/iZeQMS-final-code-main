import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { Button } from "../components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Textarea } from "../components/ui/textarea";
import StatusBadge from "../components/StatusBadge";
import ESignDialog from "../components/ESignDialog";
import WorkflowProgressBar from "../components/WorkflowProgressBar";
import Attachments from "../components/Attachments";
import RiskScoreCard from "../components/RiskScoreCard";
import DeviationForm from "../components/DeviationForm";
import DynamicFrameworkForm from "../components/DynamicFrameworkForm";
import MultiPartFrameworkForm from "../components/MultiPartFrameworkForm";
import { humanizeAuditEntry } from "../lib/audit";
import { toast } from "sonner";
import { useAuth } from "../context/AuthContext";
import { ChevronLeft } from "lucide-react";
import { hasPermission } from "../lib/roles";

const TYPE_LABEL = {
  CHANGE_CONTROL: "Change Control", DEVIATION: "Deviation", CAPA: "CAPA", INCIDENT: "Incident", EVENT: "Event",
};

const NEXT_ACTIONS = {
  DRAFT: ["SUBMIT_REVIEW"],
  OPEN: ["REVIEW", "REJECT"],
  IN_REVIEW: ["APPROVE", "REJECT"],
  APPROVED: ["CLOSE"],
  REJECTED: ["REOPEN"],
  CLOSED: [],
};

// Per User Role Matrix — which permission each workflow action requires.
const ACTION_PERMISSION = {
  SUBMIT_REVIEW: "create_record",
  REVIEW: "review_record",
  APPROVE: "approve_record",
  REJECT: "reject_record",
  CLOSE: "close_record",
  REOPEN: "review_record",
};

const ACTION_LABEL = {
  SUBMIT_REVIEW: "Submit for Review",
  REVIEW: "Mark Reviewed",
  APPROVE: "Approve",
  REJECT: "Reject",
  CLOSE: "Close",
  REOPEN: "Re-open",
};

export default function RecordDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [rec, setRec] = useState(null);
  const [audit, setAudit] = useState([]);
  const [workflow, setWorkflow] = useState([]);
  const [comments, setComments] = useState([]);
  const [commentText, setCommentText] = useState("");
  const [esign, setEsign] = useState({ open: false, action: null });
  const [busy, setBusy] = useState(false);
  const [activeTpl, setActiveTpl] = useState(null);
  const [fwDirty, setFwDirty] = useState(false);
  const [savingFw, setSavingFw] = useState(false);

  const load = useCallback(async () => {
    const [r, a, w, c] = await Promise.all([
      api.get(`/records/${id}`),
      api.get(`/records/${id}/audit`),
      api.get(`/records/${id}/workflow`),
      api.get(`/records/${id}/comments`),
    ]);
    setRec(r.data); setAudit(a.data); setWorkflow(w.data); setComments(c.data);
    setFwDirty(false);
    // Resolve the framework template the record is bound to (or the current
    // active one for the type). The dynamic form is render-only for DEVIATION
    // (since DeviationForm handles it), but is interactive for the others.
    const tplId = r.data?.framework_template_id;
    if (tplId) {
      try {
        const { data } = await api.get(`/module-framework/templates/${tplId}`);
        setActiveTpl(data || null);
      } catch (e) { setActiveTpl(null); }
    } else if (r.data?.type && r.data.type !== "DEVIATION") {
      try {
        const { data } = await api.get("/module-framework/active-template", { params: { category: r.data.type } });
        setActiveTpl(data?.template || null);
      } catch (e) { setActiveTpl(null); }
    } else {
      setActiveTpl(null);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const submitAction = async ({ password, reason, comment }) => {
    setBusy(true);
    try {
      await api.post(`/records/${id}/action`, { password, reason, comment, action: esign.action });
      toast.success(`${ACTION_LABEL[esign.action]} successful`);
      setEsign({ open: false, action: null });
      await load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  const addComment = async () => {
    if (!commentText.trim()) return;
    try {
      await api.post(`/records/${id}/comments`, { body: commentText.trim() });
      setCommentText("");
      const { data } = await api.get(`/records/${id}/comments`);
      setComments(data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  if (!rec) return <div className="text-slate-500 text-sm">Loading…</div>;

  const overdue = rec.due_date && new Date(rec.due_date) < new Date() && !["CLOSED", "APPROVED", "REJECTED"].includes(rec.status);
  const actions = (NEXT_ACTIONS[rec.status] || []).filter((a) => {
    const perm = ACTION_PERMISSION[a];
    return !perm || hasPermission(user, perm);
  });

  return (
    <div className="space-y-5" data-testid="record-detail-page">
      <button onClick={() => navigate(-1)} className="text-xs text-slate-500 hover:text-slate-900 flex items-center gap-1" data-testid="back-btn">
        <ChevronLeft size={14} /> Back
      </button>

      <div className="border border-slate-200 bg-white rounded-sm p-5">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="mono text-slate-500 text-sm" data-testid="record-number">{rec.record_number}</span>
              <span className="text-xs text-slate-400">·</span>
              <span className="text-xs text-slate-600">{TYPE_LABEL[rec.type]}</span>
              <StatusBadge status={rec.status} overdue={overdue} />
            </div>
            <h1 className="text-2xl font-semibold text-slate-950 mt-2 tracking-tight" style={{ fontFamily: "Work Sans" }} data-testid="record-title">{rec.title}</h1>
            <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-2 text-xs">
              <Meta label="Department" value={rec.department} />
              <Meta label="Location" value={rec.location} />
              <Meta label="Severity" value={rec.severity} />
              <Meta label="Priority" value={rec.priority} />
              <Meta label="Initiator" value={rec.initiator_name} />
              <Meta label="Created" value={new Date(rec.created_at).toLocaleString()} mono />
              <Meta label="Updated" value={new Date(rec.updated_at).toLocaleString()} mono />
              <Meta label="Due" value={rec.due_date ? new Date(rec.due_date).toLocaleDateString() : "—"} mono />
            </div>
          </div>

          <div className="flex flex-col gap-2" data-testid="record-actions">
            {actions.map((a) => (
              <Button
                key={a}
                data-testid={`action-${a}`}
                variant={a === "REJECT" ? "outline" : "default"}
                className={a === "REJECT" ? "border-red-300 text-red-700 hover:bg-red-50" : "bg-slate-900 hover:bg-slate-800 text-white"}
                onClick={() => setEsign({ open: true, action: a })}
              >
                {ACTION_LABEL[a]}
              </Button>
            ))}
            <Button
              variant="outline"
              className="text-slate-700"
              onClick={async () => {
                try {
                  const url2 = rec.type === "DEVIATION" ? `/deviations/${rec.id}/pdf` : `/records/${rec.id}/pdf`;
                  const res = await api.get(url2, { responseType: "blob" });
                  const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
                  const a = document.createElement("a");
                  a.href = url; a.download = `${rec.record_number || "record"}.pdf`;
                  document.body.appendChild(a); a.click(); a.remove();
                  window.URL.revokeObjectURL(url);
                  toast.success("PDF downloaded — logged in audit trail");
                } catch (e) { toast.error(formatApiError(e.response?.data?.detail) || e.message); }
              }}
              data-testid="download-pdf-btn"
            >Download PDF</Button>
          </div>
        </div>
        <WorkflowProgressBar status={rec.status} />
      </div>

      <Tabs defaultValue="details" className="w-full">
        <TabsList className="bg-transparent border-b border-slate-200 rounded-none p-0 h-auto w-full justify-start">
          {[
            ["details", "Record Details"],
            ["workflow", "Workflow"],
            ["comments", `Comments (${comments.length})`],
            ["audit", `Audit Trail (${audit.length})`],
          ].map(([k, l]) => (
            <TabsTrigger key={k} value={k} data-testid={`tab-${k}`} className="rounded-none data-[state=active]:border-b-2 data-[state=active]:border-slate-900 data-[state=active]:shadow-none px-4 py-2 bg-transparent">{l}</TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="details" className="mt-4 space-y-4">
          {rec.type === "DEVIATION" ? (
            <DeviationForm record={rec} onChanged={() => load()} />
          ) : (
            <div data-testid={`framework-form-${rec.type}`}>
              <div className="text-sm font-semibold text-slate-900 mb-2">{TYPE_LABEL[rec.type] || rec.type} — Form</div>
              <MultiPartFrameworkForm
                record={rec}
                template={activeTpl}
                readOnly={["CLOSED"].includes(rec.status) || !hasPermission(user, "edit_draft")}
              />
            </div>
          )}
          <RiskScoreCard
            recordId={rec.id}
            current={rec.risk}
            onUpdated={() => load()}
            locked={["CLOSED", "REJECTED"].includes(rec.status)}
          />
          <Attachments recordId={rec.id} locked={rec.status === "CLOSED"} />
        </TabsContent>

        <TabsContent value="workflow" className="mt-4">
          <div className="border border-slate-200 bg-white rounded-sm">
            {workflow.length === 0 ? (
              <div className="p-6 text-sm text-slate-500" data-testid="workflow-empty">No workflow events yet.</div>
            ) : (
              <ol className="divide-y divide-slate-100">
                {workflow.map((w, i) => (
                  <li key={w.id} className="p-4 flex gap-4 items-start" data-testid={`workflow-${i}`}>
                    <div className="w-2 h-2 rounded-full bg-slate-900 mt-2" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 text-sm">
                        <span className="font-semibold text-slate-900">{w.action}</span>
                        <span className="text-slate-400">·</span>
                        <span className="text-slate-700">{w.actor_name}</span>
                      </div>
                      <div className="text-[11px] text-slate-500 mono mt-0.5">{new Date(w.timestamp).toLocaleString()} · {w.from_status} → {w.to_status}</div>
                      {w.reason && <div className="text-sm text-slate-700 mt-1">Reason: {w.reason}</div>}
                      {w.comment && <div className="text-sm text-slate-600 mt-0.5">Comment: {w.comment}</div>}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </TabsContent>

        <TabsContent value="comments" className="mt-4 space-y-3">
          <div className="border border-slate-200 bg-white rounded-sm p-3 space-y-2">
            <Textarea data-testid="comment-input" rows={2} value={commentText} onChange={(e) => setCommentText(e.target.value)} placeholder="Add a comment to this record…" />
            <div className="flex justify-end">
              <Button data-testid="comment-submit" onClick={addComment} disabled={!commentText.trim()} className="bg-slate-900 hover:bg-slate-800 text-white">Post comment</Button>
            </div>
          </div>
          <div className="border border-slate-200 bg-white rounded-sm divide-y divide-slate-100">
            {comments.length === 0 ? (
              <div className="p-6 text-sm text-slate-500" data-testid="comments-empty">No comments.</div>
            ) : (
              comments.map((c) => (
                <div key={c.id} className="p-4">
                  <div className="text-sm font-medium text-slate-900">{c.user_name} <span className="text-[11px] text-slate-500 mono ml-2">{new Date(c.timestamp).toLocaleString()}</span></div>
                  <div className="text-sm text-slate-700 mt-1 whitespace-pre-wrap">{c.body}</div>
                </div>
              ))
            )}
          </div>
        </TabsContent>

        <TabsContent value="audit" className="mt-4">
          <div className="border border-slate-200 bg-white rounded-sm overflow-hidden">
            <div className="px-3 py-2 border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500 mono flex items-center justify-between">
              <span>Audit Trail · 21 CFR Part 11 · Immutable</span>
              <span>{audit.length} entries</span>
            </div>
            <div className="max-h-[600px] overflow-y-auto">
              <table className="w-full table-dense text-[12px]">
                <thead className="bg-slate-50 text-[10px] uppercase text-slate-500">
                  <tr>
                    <th className="text-left">Timestamp (UTC)</th><th className="text-left">User</th><th className="text-left">Action</th><th className="text-left">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.map((a) => {
                    const h = humanizeAuditEntry(a);
                    return (
                      <tr key={a.id} className="border-t border-slate-100" data-testid={`audit-row-${a.id}`}>
                        <td className="align-top whitespace-nowrap mono">{new Date(a.timestamp).toLocaleString()}</td>
                        <td className="align-top mono">{a.user_email}</td>
                        <td className="align-top font-semibold text-slate-900">{a.action}</td>
                        <td className="align-top max-w-md break-words text-slate-700">
                          <div>{h.sentence}</div>
                          {h.diff && <div className="text-[11px] text-slate-500 mt-0.5">{h.diff}</div>}
                          {h.reason && <div className="text-[11px] text-slate-500 mt-0.5">Reason: {h.reason}</div>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      <ESignDialog
        open={esign.open}
        onOpenChange={(o) => setEsign({ open: o, action: o ? esign.action : null })}
        action={esign.action}
        onConfirm={submitAction}
        busy={busy}
        user={user}
      />
    </div>
  );
}

const Meta = ({ label, value, mono }) => (
  <div>
    <div className="text-[10px] uppercase tracking-wide text-slate-400">{label}</div>
    <div className={`text-slate-900 ${mono ? "mono" : ""}`}>{value || "—"}</div>
  </div>
);

const DetailBlock = ({ label, value }) => (
  <div className="border border-slate-200 bg-white rounded-sm">
    <div className="px-4 py-2 border-b border-slate-200 text-sm font-semibold text-slate-900">{label}</div>
    <div className="p-4 text-sm text-slate-700 whitespace-pre-wrap min-h-[40px]">{value || <span className="text-slate-400 italic">— not provided —</span>}</div>
  </div>
);
