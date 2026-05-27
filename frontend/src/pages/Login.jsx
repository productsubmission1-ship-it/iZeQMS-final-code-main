import React, { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Button } from "../components/ui/button";
import { Lock, ShieldCheck, Activity } from "lucide-react";
import api, { formatApiError } from "../lib/api";
import { toast } from "sonner";

function ForgotPasswordLink() {
  const [busy, setBusy] = useState(false);
  const onClick = async () => {
    const email = window.prompt("Enter the email on your izQMS account:");
    if (!email) return;
    setBusy(true);
    try {
      await api.post("/auth/forgot-password", { email });
      toast.success("If an account exists, a reset link has been sent. Check your inbox or system logs.");
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally { setBusy(false); }
  };
  return (
    <button type="button" onClick={onClick} disabled={busy} className="text-xs text-slate-500 hover:text-slate-900 mono" data-testid="forgot-password-link">
      {busy ? "Sending…" : "Forgot password?"}
    </button>
  );
}

export default function Login() {
  const { user, login, error } = useAuth();
  const [email, setEmail] = useState("admin@izqms.com");
  const [password, setPassword] = useState("Admin@izQMS2026");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  if (user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const ok = await login(email, password);
    setBusy(false);
    if (ok.ok) navigate(ok.must_change_password ? "/change-password" : "/");
  };

  return (
    <div className="min-h-screen auth-bg flex">
      {/* Left informational panel */}
      <div className="hidden lg:flex w-1/2 flex-col justify-between p-12 relative">
        <div className="flex items-center gap-2">
          <div className="w-9 h-9 bg-slate-900 text-white flex items-center justify-center rounded-sm font-bold">iz</div>
          <div>
            <div className="font-bold text-slate-900 text-lg" style={{ fontFamily: "Work Sans" }}>izQMS</div>
            <div className="text-[11px] text-slate-500 mono">Electronic Quality Management System</div>
          </div>
        </div>

        <div>
          <h1 className="text-5xl font-semibold text-slate-950 leading-[1.05]" style={{ fontFamily: "Work Sans" }}>
            Compliance-grade<br />Quality Management,<br />engineered for pharma.
          </h1>
          <p className="text-slate-600 mt-6 text-base max-w-md">
            A centralized, audited platform for Change Control, Deviation, CAPA, Incident & Event lifecycles — built around 21 CFR Part 11, EU Annex 11 and ALCOA++ principles.
          </p>

          <div className="grid grid-cols-3 gap-4 mt-10 max-w-lg">
            {[
              { icon: ShieldCheck, label: "21 CFR Part 11" },
              { icon: Lock, label: "ALCOA++" },
              { icon: Activity, label: "Audit Trail" },
            ].map((b) => (
              <div key={b.label} className="border border-slate-200 bg-white/70 backdrop-blur p-3 rounded-sm">
                <b.icon size={16} className="text-slate-900" />
                <div className="text-xs mt-2 text-slate-700 font-medium">{b.label}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="text-[11px] text-slate-500 mono">
          © 2026 izQMS · Secure HTTPS · Role-based · Audit-traced
        </div>
      </div>

      {/* Right form */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-md bg-white border border-slate-200 rounded-sm shadow-2xl p-8" data-testid="login-card">
          <div className="lg:hidden mb-6 flex items-center gap-2">
            <div className="w-8 h-8 bg-slate-900 text-white flex items-center justify-center rounded-sm font-bold">iz</div>
            <div className="font-bold text-slate-900">izQMS</div>
          </div>

          <h2 className="text-2xl font-semibold text-slate-950" style={{ fontFamily: "Work Sans" }}>Sign in</h2>
          <p className="text-sm text-slate-500 mt-1">Authorized personnel only. All actions are audited.</p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            <div>
              <Label htmlFor="login-email" className="text-xs uppercase tracking-wide text-slate-500">User ID / Email</Label>
              <Input id="login-email" data-testid="login-email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" />
            </div>
            <div>
              <Label htmlFor="login-password" className="text-xs uppercase tracking-wide text-slate-500">Password</Label>
              <Input id="login-password" data-testid="login-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
            </div>

            {error && <div className="text-sm text-red-700 bg-red-50 border border-red-200 px-3 py-2 rounded-sm" data-testid="login-error">{error}</div>}

            <Button type="submit" data-testid="login-submit" disabled={busy} className="w-full bg-slate-900 hover:bg-slate-800 text-white">
              {busy ? "Authenticating…" : "Sign in securely"}
            </Button>

            <div className="text-center">
              <ForgotPasswordLink />
            </div>
          </form>

          <div className="mt-6 text-[11px] text-slate-500 mono leading-relaxed border-t border-slate-100 pt-4">
            By signing in, you certify that you are the authorized owner of these credentials. Unauthorized access is prohibited and audited per 21 CFR Part 11.
          </div>
        </div>
      </div>
    </div>
  );
}
