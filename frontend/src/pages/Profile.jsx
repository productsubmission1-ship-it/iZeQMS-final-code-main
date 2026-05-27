import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { Link } from "react-router-dom";

export default function Profile() {
  const { user } = useAuth();
  const [audit, setAudit] = useState([]);

  useEffect(() => {
    if (!user?.id) return;
    api.get(`/users/${user.id}/audit`).then(({ data }) => setAudit(data.slice(0, 30))).catch(() => {});
  }, [user?.id]);

  if (!user) return null;

  return (
    <div className="space-y-5" data-testid="profile-page">
      <div>
        <div className="text-[11px] uppercase tracking-wide text-slate-500 mono">My account</div>
        <h1 className="text-3xl font-semibold text-slate-950 tracking-tight mt-1" style={{ fontFamily: "Work Sans" }}>{user.name}</h1>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card title="Identity">
          <Row k="Employee ID" v={user.employee_id} />
          <Row k="Username" v={user.username} />
          <Row k="Email" v={user.email} mono />
          <Row k="User type" v={user.user_type} />
          <Row k="Access level" v={user.access_level} />
        </Card>
        <Card title="Assignment & status">
          <Row k="Department" v={user.department} />
          <Row k="Location" v={user.location} />
          <Row k="Roles" v={(user.roles || []).join(", ")} />
          <Row k="Status" v={user.locked ? "LOCKED" : user.active ? "ACTIVE" : "INACTIVE"} />
          <Row k="Approval status" v={user.approval_status} />
          <Row k="Expiry" v={user.expiry_date ? new Date(user.expiry_date).toLocaleDateString() : "—"} mono />
        </Card>
        <Card title="Security">
          <Row k="Last login" v={user.last_login ? new Date(user.last_login).toLocaleString() : "—"} mono />
          <Row k="Failed login count" v={user.failed_login_count || 0} mono />
          <Row k="Password changed" v={user.password_changed_at ? new Date(user.password_changed_at).toLocaleDateString() : "—"} mono />
          <div className="pt-2"><Link to="/change-password" data-testid="profile-change-pw" className="text-sm text-slate-900 underline-offset-2 hover:underline">Change password →</Link></div>
        </Card>
        <Card title="Activity (recent)">
          {audit.length === 0 ? <div className="text-sm text-slate-500">No activity yet.</div> : (
            <ul className="space-y-1.5 text-xs" data-testid="profile-activity">
              {audit.map((a) => (
                <li key={a.id} className="flex justify-between gap-2 border-b border-slate-100 pb-1">
                  <span className="text-slate-700 truncate"><span className="font-semibold">{a.action}</span> {a.reason}</span>
                  <span className="mono text-slate-500 shrink-0">{new Date(a.timestamp).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

const Card = ({ title, children }) => (
  <div className="border border-slate-200 bg-white rounded-sm">
    <div className="px-4 py-2 border-b border-slate-200 text-sm font-semibold text-slate-900">{title}</div>
    <div className="p-4 space-y-2">{children}</div>
  </div>
);
const Row = ({ k, v, mono }) => (
  <div className="flex justify-between items-baseline gap-3">
    <span className="text-xs uppercase tracking-wide text-slate-500">{k}</span>
    <span className={`text-sm text-slate-900 ${mono ? "mono" : ""}`}>{v || "—"}</span>
  </div>
);
