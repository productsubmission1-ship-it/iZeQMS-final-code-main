import React, { useCallback, useEffect, useRef, useState } from "react";
import api, { formatApiError, API_BASE } from "../lib/api";
import { Button } from "./ui/button";
import { Paperclip, Download, Trash2, FileText, X } from "lucide-react";
import { toast } from "sonner";

const formatBytes = (b) => {
  if (!b) return "0 B";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0; let n = b;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n < 10 ? 1 : 0)} ${u[i]}`;
};

export const Attachments = ({ recordId, locked = false }) => {
  const [rows, setRows] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [confirmDel, setConfirmDel] = useState(null);
  const [reason, setReason] = useState("");
  const inputRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/records/${recordId}/attachments`);
      setRows(data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  }, [recordId]);

  useEffect(() => { load(); }, [load]);

  const onUpload = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", f);
      await api.post(`/records/${recordId}/attachments`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`Uploaded ${f.name}`);
      await load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  const onDownload = async (a) => {
    try {
      const token = localStorage.getItem("izqms_token");
      const res = await fetch(`${API_BASE}/attachments/${a.id}/download`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        credentials: "include",
      });
      if (!res.ok) throw new Error(`Download failed (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url; link.download = a.filename; link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(err.message);
    }
  };

  const onDelete = async () => {
    if (!confirmDel || !reason.trim() || reason.trim().length < 3) {
      toast.error("Reason (min 3 chars) is required");
      return;
    }
    try {
      await api.delete(`/attachments/${confirmDel.id}`, { data: { reason: reason.trim() } });
      toast.success("Attachment removed");
      setConfirmDel(null); setReason("");
      await load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    }
  };

  return (
    <div className="border border-slate-200 bg-white rounded-sm" data-testid="attachments-panel">
      <div className="px-4 py-2 border-b border-slate-200 text-sm font-semibold text-slate-900 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Paperclip size={14} /> Attachments
          <span className="text-xs text-slate-500 mono">({rows.length})</span>
        </div>
        {!locked && (
          <div>
            <input ref={inputRef} type="file" className="hidden" onChange={onUpload} data-testid="attachment-input" />
            <Button
              size="sm"
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
              className="bg-slate-900 hover:bg-slate-800 text-white h-7 text-xs"
              data-testid="attachment-upload-btn"
            >
              {uploading ? "Uploading…" : "Add file"}
            </Button>
          </div>
        )}
      </div>
      {rows.length === 0 ? (
        <div className="p-6 text-sm text-slate-500" data-testid="attachments-empty">No attachments yet.</div>
      ) : (
        <ul className="divide-y divide-slate-100">
          {rows.map((a) => (
            <li key={a.id} className="px-4 py-3 flex items-center gap-3" data-testid={`attachment-row-${a.id}`}>
              <FileText size={16} className="text-slate-500 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm text-slate-900 truncate">{a.filename}</div>
                <div className="text-[11px] text-slate-500 mono">
                  {formatBytes(a.size_bytes)} · {a.uploaded_by_name} · {new Date(a.uploaded_at).toLocaleString()}
                </div>
              </div>
              <Button size="icon" variant="ghost" onClick={() => onDownload(a)} data-testid={`attachment-download-${a.id}`}>
                <Download size={14} />
              </Button>
              {!locked && (
                <Button size="icon" variant="ghost" onClick={() => setConfirmDel(a)} data-testid={`attachment-delete-${a.id}`}>
                  <Trash2 size={14} className="text-red-600" />
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {confirmDel && (
        <div className="fixed inset-0 bg-slate-900/40 z-40 flex items-center justify-center p-4" onClick={() => { setConfirmDel(null); setReason(""); }}>
          <div className="bg-white border border-slate-200 rounded-sm shadow-2xl w-full max-w-md p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <div className="font-semibold text-slate-900">Remove attachment</div>
              <button onClick={() => { setConfirmDel(null); setReason(""); }} className="text-slate-500 hover:text-slate-900"><X size={16} /></button>
            </div>
            <div className="text-sm text-slate-700 mb-3">
              Removing <span className="font-medium">{confirmDel.filename}</span>. This is audit-trailed and cannot be undone.
            </div>
            <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Reason</label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              data-testid="attachment-delete-reason"
              className="w-full border border-slate-300 rounded-sm p-2 text-sm mt-1"
              placeholder="Why is this file being removed?"
            />
            <div className="flex justify-end gap-2 mt-3">
              <Button variant="outline" onClick={() => { setConfirmDel(null); setReason(""); }}>Cancel</Button>
              <Button onClick={onDelete} className="bg-red-600 hover:bg-red-700 text-white" data-testid="attachment-delete-confirm">Remove</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Attachments;
