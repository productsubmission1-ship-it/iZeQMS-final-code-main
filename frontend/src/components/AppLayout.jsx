import React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  FileText,
  AlertTriangle,
  Wrench,
  AlertOctagon,
  Calendar,
  Shield,
  Users,
  LogOut,
  Search,
  FileStack,
  Settings as SettingsIcon,
  User as UserIcon,
  Sliders,
  KeyRound,
  Boxes,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { Input } from "./ui/input";
import NotificationBell from "./NotificationBell";
import { hasPermission, isAuditor, ROLE_LABELS, canonicalize } from "../lib/roles";

const MODULES = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard", testid: "nav-dashboard", perm: null },
  { to: "/records/CHANGE_CONTROL", icon: FileText, label: "Change Control", testid: "nav-change-control", perm: null },
  { to: "/records/DEVIATION", icon: AlertTriangle, label: "Deviation", testid: "nav-deviation", perm: null },
  { to: "/records/CAPA", icon: Wrench, label: "CAPA", testid: "nav-capa", perm: null },
  { to: "/records/INCIDENT", icon: AlertOctagon, label: "Incident", testid: "nav-incident", perm: null },
  { to: "/records/EVENT", icon: Calendar, label: "Event", testid: "nav-event", perm: null },
  { to: "/audit", icon: Shield, label: "Audit Trail", testid: "nav-audit", perm: "audit_trail_view" },
  { to: "/reports", icon: FileStack, label: "Reports", testid: "nav-reports", perm: "view_reports" },
  { to: "/users", icon: Users, label: "Users", testid: "nav-users", perm: "user_management" },
  { to: "/roles", icon: KeyRound, label: "Role Matrix", testid: "nav-roles", perm: "role_management" },
  { to: "/module-framework", icon: Boxes, label: "Module Framework", testid: "nav-module-framework", perm: "view_module_framework" },
  { to: "/form-builder", icon: Sliders, label: "Form Builder", testid: "nav-form-builder", perm: "workflow_config" },
  { to: "/settings", icon: SettingsIcon, label: "Settings", testid: "nav-settings", perm: "role_management" },
];

export default function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const auditorMode = isAuditor(user);
  const visibleModules = MODULES.filter((m) => !m.perm || hasPermission(user, m.perm));

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-200 bg-white flex flex-col" data-testid="sidebar">
        <div className="px-5 py-5 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-slate-900 text-white flex items-center justify-center rounded-sm font-bold tracking-tighter">iz</div>
            <div>
              <div className="font-bold text-slate-900 leading-none" style={{ fontFamily: "Work Sans" }}>izQMS</div>
              <div className="text-[10px] text-slate-500 mt-0.5 mono">eQMS · 21 CFR Part 11</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
          {visibleModules.map((m) => (
            <NavLink
              key={m.to}
              to={m.to}
              end={m.to === "/"}
              data-testid={m.testid}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 text-sm rounded-sm transition-colors duration-150 ${
                  isActive
                    ? "bg-slate-900 text-white font-medium"
                    : "text-slate-700 hover:bg-slate-100"
                }`
              }
            >
              <m.icon size={16} strokeWidth={2} />
              <span>{m.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="px-3 py-3 border-t border-slate-200">
          <div className="px-3 py-2">
            <div className="text-sm font-medium text-slate-900 truncate" data-testid="sidebar-user-name">{user?.name}</div>
            <div className="text-[11px] text-slate-500 mono truncate">{user?.email}</div>
            <div className="text-[10px] text-slate-400 mt-1 uppercase tracking-wide" data-testid="sidebar-user-roles">
              {(user?.roles || []).map((r) => ROLE_LABELS[canonicalize(r)] || r).join(" · ")}
            </div>
            {auditorMode && (
              <div className="mt-2 inline-block px-2 py-0.5 text-[10px] mono font-semibold uppercase rounded-sm bg-amber-50 text-amber-800 border border-amber-300" data-testid="readonly-badge">Read-only</div>
            )}
          </div>
          <button
            onClick={async () => { await logout(); navigate("/login"); }}
            data-testid="logout-btn"
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 rounded-sm transition-colors"
          >
            <LogOut size={15} /> <span>Sign out</span>
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 bg-white border-b border-slate-200 flex items-center px-6 gap-4 sticky top-0 z-10">
          <div className="flex-1 max-w-xl relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input
              data-testid="global-search-input"
              placeholder="Search records by ID, title, or keyword…"
              className="pl-9 h-9 bg-slate-50 border-slate-200"
              onKeyDown={(e) => {
                if (e.key === "Enter" && e.currentTarget.value.trim()) {
                  navigate(`/records/ALL?q=${encodeURIComponent(e.currentTarget.value.trim())}`);
                }
              }}
            />
          </div>
          <div className="text-[11px] text-slate-500 mono" data-testid="header-timestamp">
            {new Date().toUTCString()}
          </div>
          <NotificationBell />
          <NavLink to="/profile" data-testid="nav-profile" className="p-2 hover:bg-slate-100 rounded-sm">
            <UserIcon size={16} className="text-slate-700" />
          </NavLink>
        </header>

        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
