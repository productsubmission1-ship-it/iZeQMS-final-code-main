import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { hasPermission } from "../lib/roles";

/**
 * Wrap a route element to require a specific role-matrix permission.
 * If the user lacks it, redirect to /dashboard with a flash.
 */
export default function RequirePermission({ permission, children }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  if (!hasPermission(user, permission)) {
    return (
      <div className="border border-rose-200 bg-rose-50 rounded-sm p-6 text-center" data-testid="forbidden-page">
        <div className="text-rose-800 font-medium">Access denied</div>
        <div className="text-xs text-rose-600 mt-1 mono">{permission}</div>
        <div className="text-xs text-slate-600 mt-3">
          Your role does not grant access to this section. Contact a system administrator if you need this permission.
        </div>
      </div>
    );
  }
  return children;
}
