import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import api, { formatApiError } from "../lib/api";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { Lock } from "lucide-react";
import { toast } from "sonner";

export default function ChangePassword() {
  const { user, refreshMe, logout } = useAuth();
  const navigate = useNavigate();
  const [cur, setCur] = useState("");
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);
  const [policy, setPolicy] = useState({});

  useEffect(() => {
    api.get("/settings/password-policy").then(({ data }) => setPolicy(data)).catch(() => {});
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (pw !== pw2) { toast.error("Passwords do not match"); return; }
    setBusy(true);
    try {
      await api.post("/auth/change-password", { current_password: cur, new_password: pw });
      toast.success("Password updated. Please sign in again.");
      await logout();
      navigate("/login");
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="max-w-md mx-auto" data-testid="change-password-page">
      <div className="mb-4 flex items-center gap-2"><Lock size={18} /><h1 className="text-2xl font-semibold tracking-tight" style={{ fontFamily: "Work Sans" }}>Change Password</h1></div>
      {user?.must_change_password && (
        <div className="border border-amber-300 bg-amber-50 p-3 rounded-sm text-sm text-amber-900 mb-4" data-testid="must-change-banner">
          You must set a new password before continuing.
        </div>
      )}
      <div className="border border-slate-200 bg-white rounded-sm p-5">
        <form onSubmit={submit} className="space-y-3">
          <div>
            <Label className="text-xs uppercase tracking-wide text-slate-500">Current password</Label>
            <Input required type="password" value={cur} onChange={(e) => setCur(e.target.value)} data-testid="cp-current" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wide text-slate-500">New password</Label>
            <Input required type="password" value={pw} onChange={(e) => setPw(e.target.value)} data-testid="cp-new" />
          </div>
          <div>
            <Label className="text-xs uppercase tracking-wide text-slate-500">Confirm new password</Label>
            <Input required type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} data-testid="cp-confirm" />
          </div>
          <div className="text-[11px] mono text-slate-500 bg-slate-50 p-2 rounded-sm">
            Policy: min {policy.min_length} chars
            {policy.require_upper && " · uppercase"}
            {policy.require_lower && " · lowercase"}
            {policy.require_digit && " · digit"}
            {policy.require_special && " · special"}
          </div>
          <Button type="submit" disabled={busy || !pw} className="w-full bg-slate-900 hover:bg-slate-800 text-white" data-testid="cp-submit">
            {busy ? "Updating…" : "Update password"}
          </Button>
        </form>
      </div>
    </div>
  );
}
