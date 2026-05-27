import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "./ui/dialog";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Button } from "./ui/button";
import { ShieldCheck } from "lucide-react";

export default function ESignDialog({ open, onOpenChange, action, onConfirm, busy, user }) {
  const [password, setPassword] = useState("");
  const [reason, setReason] = useState("");
  const [comment, setComment] = useState("");

  const reset = () => { setPassword(""); setReason(""); setComment(""); };

  const submit = async () => {
    await onConfirm({ password, reason, comment });
    reset();
  };

  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) reset(); }}>
      <DialogContent data-testid="esign-dialog" className="sm:max-w-md border-slate-200 rounded-sm">
        <DialogHeader>
          <div className="flex items-center gap-2 mb-1">
            <ShieldCheck size={18} className="text-slate-900" />
            <DialogTitle className="text-slate-900" style={{ fontFamily: "Work Sans" }}>Electronic Signature Required</DialogTitle>
          </div>
          <DialogDescription className="text-slate-600">
            21 CFR Part 11 · Action: <span className="mono font-semibold text-slate-900">{action}</span>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2">
          <div>
            <Label className="text-xs uppercase tracking-wide text-slate-500">Signing as</Label>
            <div className="mono text-sm text-slate-900" data-testid="esign-user">{user?.email}</div>
          </div>
          <div>
            <Label htmlFor="esign-password" className="text-xs uppercase tracking-wide text-slate-500">Password</Label>
            <Input id="esign-password" data-testid="esign-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </div>
          <div>
            <Label htmlFor="esign-reason" className="text-xs uppercase tracking-wide text-slate-500">Reason for action *</Label>
            <Input id="esign-reason" data-testid="esign-reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Reviewed investigation, root cause documented" />
          </div>
          <div>
            <Label htmlFor="esign-comment" className="text-xs uppercase tracking-wide text-slate-500">Comment (optional)</Label>
            <Textarea id="esign-comment" data-testid="esign-comment" value={comment} onChange={(e) => setComment(e.target.value)} rows={2} />
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="esign-cancel">Cancel</Button>
          <Button
            data-testid="esign-confirm"
            disabled={!password || !reason || busy}
            onClick={submit}
            className="bg-slate-900 hover:bg-slate-800 text-white"
          >
            {busy ? "Signing…" : "Sign & Confirm"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
