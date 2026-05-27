import React, { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import api from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "./ui/dialog";
import { Button } from "./ui/button";
import { Clock } from "lucide-react";

/**
 * Tracks user inactivity. Shows a warning dialog 2 minutes before the configured
 * session timeout. If the user doesn't extend, signs them out.
 */
export default function SessionTimer() {
  const { user, logout, refreshMe } = useAuth();
  const [policy, setPolicy] = useState({ session_timeout_minutes: 60 });
  const [warning, setWarning] = useState(false);
  const [remaining, setRemaining] = useState(120);
  const lastActivityRef = useRef(Date.now());

  useEffect(() => {
    if (!user) return;
    api.get("/settings/password-policy").then(({ data }) => setPolicy(data)).catch(() => {});
  }, [user]);

  useEffect(() => {
    if (!user) return;
    const reset = () => { lastActivityRef.current = Date.now(); };
    const events = ["mousedown", "keydown", "touchstart", "scroll"];
    events.forEach((e) => window.addEventListener(e, reset, { passive: true }));
    return () => events.forEach((e) => window.removeEventListener(e, reset));
  }, [user]);

  useEffect(() => {
    if (!user) return;
    const interval = setInterval(async () => {
      const timeoutMs = (policy.session_timeout_minutes || 60) * 60_000;
      const idleMs = Date.now() - lastActivityRef.current;
      const remainingMs = timeoutMs - idleMs;
      if (remainingMs <= 0) {
        await logout();
        return;
      }
      if (remainingMs <= 120_000 && !warning) {
        setWarning(true);
      }
      if (warning) {
        setRemaining(Math.max(0, Math.floor(remainingMs / 1000)));
      }
    }, 5_000);
    return () => clearInterval(interval);
  }, [user, policy, warning, logout]);

  const extend = async () => {
    lastActivityRef.current = Date.now();
    try { await refreshMe(); } catch { /* ignore */ }
    setWarning(false);
  };

  if (!user) return null;

  return (
    <Dialog open={warning} onOpenChange={(o) => !o && setWarning(false)}>
      <DialogContent data-testid="session-timeout-dialog" className="sm:max-w-md">
        <DialogHeader>
          <div className="flex items-center gap-2 mb-1">
            <Clock size={18} className="text-amber-700" />
            <DialogTitle>Session timing out</DialogTitle>
          </div>
          <DialogDescription>
            Your session will expire in <span className="mono font-semibold text-slate-900">{Math.floor(remaining / 60)}m {remaining % 60}s</span> due to inactivity.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={async () => { await logout(); }} data-testid="session-signout">Sign out now</Button>
          <Button onClick={extend} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="session-extend">Stay signed in</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
