import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "./ui/dialog";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Button } from "./ui/button";

export default function UserActionDialog({ open, onOpenChange, title, description, busy, onConfirm, requireExtra, extraLabel, defaultExtra }) {
  const [password, setPassword] = useState("");
  const [reason, setReason] = useState("");
  const [extra, setExtra] = useState(defaultExtra || "");

  const reset = () => { setPassword(""); setReason(""); setExtra(defaultExtra || ""); };

  const submit = async () => {
    await onConfirm({ esign_password: password, esign_reason: reason, extra: requireExtra ? { expiry_date: extra ? new Date(extra).toISOString() : null } : undefined });
    reset();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) reset(); }}>
      <DialogContent data-testid="user-action-dialog" className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}. Electronic signature required.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          {requireExtra && (
            <div>
              <Label className="text-xs uppercase tracking-wide text-slate-500">{extraLabel}</Label>
              <Input type="date" value={extra} onChange={(e) => setExtra(e.target.value)} data-testid="action-extra" />
            </div>
          )}
          <div>
            <Label className="text-xs uppercase tracking-wide text-slate-500">Your password</Label>
            <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} data-testid="action-password" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wide text-slate-500">Reason *</Label>
            <Input value={reason} onChange={(e) => setReason(e.target.value)} data-testid="action-reason" />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="action-cancel">Cancel</Button>
          <Button disabled={!password || !reason || busy} onClick={submit} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="action-confirm">{busy ? "Signing…" : "Sign & Confirm"}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
