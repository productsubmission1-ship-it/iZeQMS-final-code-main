import React, { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import api, { formatApiError } from "../lib/api";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { toast } from "sonner";

export default function ResetPassword() {
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const [token, setToken] = useState(sp.get("token") || "");
  const [pw1, setPw1] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) toast.error("Missing reset token");
  }, [token]);

  const submit = async (e) => {
    e.preventDefault();
    if (pw1.length < 8) return toast.error("Password must be at least 8 characters");
    if (pw1 !== pw2) return toast.error("Passwords do not match");
    setBusy(true);
    try {
      await api.post("/auth/reset-password", { token, new_password: pw1 });
      toast.success("Password reset. You can sign in now.");
      navigate("/login");
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6" data-testid="reset-password-page">
      <form onSubmit={submit} className="w-full max-w-md bg-white border border-slate-200 rounded-sm p-6 space-y-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-7 h-7 bg-slate-900 text-white flex items-center justify-center rounded-sm font-bold mono">iz</div>
            <span className="font-bold text-slate-900">izQMS</span>
          </div>
          <h1 className="text-2xl font-semibold text-slate-950 tracking-tight" style={{ fontFamily: "Work Sans" }}>Reset password</h1>
          <p className="text-xs text-slate-500 mt-1">Set a new password to regain access. Must meet your organization's policy.</p>
        </div>
        <div>
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Token</label>
          <Input value={token} onChange={(e) => setToken(e.target.value)} required data-testid="reset-token" className="mono" />
        </div>
        <div>
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">New password</label>
          <Input type="password" value={pw1} onChange={(e) => setPw1(e.target.value)} required data-testid="reset-pw1" />
        </div>
        <div>
          <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Confirm</label>
          <Input type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} required data-testid="reset-pw2" />
        </div>
        <Button type="submit" disabled={busy} className="w-full bg-slate-900 hover:bg-slate-800 text-white" data-testid="reset-submit">
          {busy ? "Resetting…" : "Reset password"}
        </Button>
        <div className="text-center">
          <button type="button" onClick={() => navigate("/login")} className="text-xs text-slate-500 hover:text-slate-900" data-testid="back-to-login">Back to login</button>
        </div>
      </form>
    </div>
  );
}
