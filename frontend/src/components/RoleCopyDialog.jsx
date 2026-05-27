import React, { useEffect, useState } from "react";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { toast } from "sonner";
import api, { formatApiError } from "../lib/api";

export default function RoleCopyDialog({ open, onOpenChange, role, onCopied }) {
  const [form, setForm] = useState({ new_code: "", new_name: "", reason: "" });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open || !role) return;
    setForm({
      new_code: `${role.code}_copy`,
      new_name: `${role.name} (copy)`,
      reason: "",
    });
  }, [open, role]);

  if (!open || !role) return null;

  const submit = async () => {
    if (!form.new_code || !form.new_name) return toast.error("Code and name are required");
    if (!form.reason || form.reason.trim().length < 3) return toast.error("Reason is required");
    setBusy(true);
    try {
      await api.post(`/role-mgmt/roles/${role.id}/copy`, form);
      toast.success(`Copied role "${role.name}"`);
      onOpenChange(false);
      onCopied?.();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid="role-copy-dialog">
        <DialogHeader>
          <DialogTitle>Copy role: {role.name}</DialogTitle>
          <DialogDescription>
            A new role with identical permissions will be created. You can then edit it independently.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-slate-600">New role code *</label>
            <Input
              value={form.new_code}
              onChange={(e) => setForm((p) => ({ ...p, new_code: e.target.value.toLowerCase().replace(/\s+/g, "_") }))}
              data-testid="copy-code"
            />
          </div>
          <div>
            <label className="text-xs text-slate-600">New role name *</label>
            <Input
              value={form.new_name}
              onChange={(e) => setForm((p) => ({ ...p, new_name: e.target.value }))}
              data-testid="copy-name"
            />
          </div>
          <div>
            <label className="text-xs text-slate-600">Reason *</label>
            <Textarea
              rows={2}
              value={form.reason}
              onChange={(e) => setForm((p) => ({ ...p, reason: e.target.value }))}
              data-testid="copy-reason"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button
            onClick={submit}
            disabled={busy}
            className="bg-slate-900 text-white hover:bg-slate-800"
            data-testid="copy-confirm"
          >
            {busy ? "Copying…" : "Copy role"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
