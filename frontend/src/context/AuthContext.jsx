import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import api, { formatApiError } from "../lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [error, setError] = useState("");

  const fetchMe = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch {
      setUser(false);
    }
  }, []);

  useEffect(() => { fetchMe(); }, [fetchMe]);

  const login = async (email, password) => {
    setError("");
    try {
      const { data } = await api.post("/auth/login", { email, password });
      if (data?.access_token) localStorage.setItem("izqms_token", data.access_token);
      // Carry must_change_password from login response into user object
      const enriched = { ...data.user, must_change_password: !!data.must_change_password };
      setUser(enriched);
      return { ok: true, must_change_password: !!data.must_change_password };
    } catch (e) {
      setError(formatApiError(e.response?.data?.detail) || e.message);
      return { ok: false };
    }
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch (e) { /* ignore */ }
    localStorage.removeItem("izqms_token");
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, error, login, logout, refreshMe: fetchMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
