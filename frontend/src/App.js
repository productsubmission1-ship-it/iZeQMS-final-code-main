import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import AppLayout from "./components/AppLayout";
import SessionTimer from "./components/SessionTimer";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import RecordsList from "./pages/RecordsList";
import RecordDetail from "./pages/RecordDetail";
import NewRecord from "./pages/NewRecord";
import AuditPage from "./pages/AuditPage";
import Users from "./pages/Users";
import Reports from "./pages/Reports";
import Profile from "./pages/Profile";
import Settings from "./pages/Settings";
import ChangePassword from "./pages/ChangePassword";
import ResetPassword from "./pages/ResetPassword";
import FormBuilder from "./pages/FormBuilder";
import RoleMgmt from "./pages/RoleMgmt";
import UserPermissions from "./pages/UserPermissions";
import ModuleFramework from "./pages/ModuleFramework";
import DynamicRecords from "./pages/DynamicRecords";
import RequirePermission from "./components/RequirePermission";
import { Toaster } from "./components/ui/sonner";

function Protected({ children }) {
  const { user } = useAuth();
  if (user === null) return (
    <div className="min-h-screen flex items-center justify-center text-slate-500 text-sm" data-testid="auth-loading">Verifying session…</div>
  );
  if (!user) return <Navigate to="/login" replace />;
  if (user.must_change_password && window.location.pathname !== "/change-password") {
    return <Navigate to="/change-password" replace />;
  }
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <SessionTimer />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/change-password" element={<Protected><ChangePassword /></Protected>} />
          <Route path="/" element={<Protected><AppLayout /></Protected>}>
            <Route index element={<Dashboard />} />
            <Route path="records/:type" element={<RecordsList />} />
            <Route path="record/:id" element={<RecordDetail />} />
            <Route path="new/:type" element={<NewRecord />} />
            <Route path="audit" element={<AuditPage />} />
            <Route path="users" element={<Users />} />
            <Route path="users/:user_id/permissions" element={<RequirePermission permission="role_management"><UserPermissions /></RequirePermission>} />
            <Route path="roles" element={<RequirePermission permission="role_management"><RoleMgmt /></RequirePermission>} />
            <Route path="module-framework" element={<RequirePermission permission="role_management"><ModuleFramework /></RequirePermission>} />
            <Route path="dynamic-records/:template_id" element={<DynamicRecords />} />
            <Route path="reports" element={<Reports />} />
            <Route path="form-builder" element={<FormBuilder />} />
            <Route path="profile" element={<Profile />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-right" />
    </AuthProvider>
  );
}
