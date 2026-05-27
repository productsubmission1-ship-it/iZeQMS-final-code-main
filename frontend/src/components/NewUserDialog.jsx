import React, { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import api, { formatApiError } from "../lib/api";
import { CANONICAL_ROLES, ROLE_LABELS, ROLE_DESCRIPTIONS, ROLES } from "../lib/roles";

export default function NewUserDialog({ open, onOpenChange, onCreated, currentUser }) {
  const [form, setForm] = useState({
    name: "", email: "", employee_id: "", username: "", department: "Quality Assurance",
    location: "Plant-1", roles: [ROLES.EMPLOYEE], user_type: "Employee", access_level: "Full",
    manager_id: "", expiry_date: "", notes: "", password: "", requires_approval: true,
    esign_password: "", esign_reason: "",
  });
  const [busy, setBusy] = useState(false);
  const [tempPw, setTempPw] = useState(null);
  const [dynamicRoles, setDynamicRoles] = useState([]); // [{code, name}]

  useEffect(() => {
    if (!open) return;
    api.get("/role-mgmt/roles?active=true")
      .then((res) => setDynamicRoles((res.data || []).map((r) => ({ code: r.code, name: r.name }))))
      .catch(() => setDynamicRoles([]));
  }, [open]);

  // Build combined role list: canonical + custom roles created in Role Matrix
  const ALL_ROLES = (() => {
    const out = [];
    const seen = new Set();
    for (const r of CANONICAL_ROLES) { out.push({ code: r, label: ROLE_LABELS[r] || r, custom: false }); seen.add(r); }
    for (const dr of dynamicRoles) {
      if (!seen.has(dr.code)) { out.push({ code: dr.code, label: dr.name || dr.code, custom: true }); seen.add(dr.code); }
    }
    return out;
  })();

  const set = (k, v) => setForm((p) => ({ ...p, [k]: v }));
  const toggleRole = (r) => setForm((p) => ({ ...p, roles: p.roles.includes(r) ? p.roles.filter((x) => x !== r) : [...p.roles, r] }));

  const submit = async (e) => {
    e?.preventDefault();
    setBusy(true);
    try {
      const payload = { ...form };
      if (!payload.password) delete payload.password;
      if (!payload.expiry_date) delete payload.expiry_date;
      else payload.expiry_date = new Date(payload.expiry_date).toISOString();
      if (!payload.manager_id) delete payload.manager_id;
      const { data } = await api.post("/users", payload);
      toast.success(`User ${data.user.email} created`);
      if (data.temp_password) setTempPw(data.temp_password);
      onCreated?.(data.user);
      if (!data.temp_password) {
        onOpenChange(false);
      }
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="new-user-dialog" className="sm:max-w-2xl max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Add New User</DialogTitle>
          <DialogDescription>All required fields are audit-tracked. Electronic signature required.</DialogDescription>
        </DialogHeader>
        {tempPw ? (
          <div className="space-y-3 py-2">
            <div className="border border-amber-300 bg-amber-50 p-4 rounded-sm">
              <div className="text-sm font-semibold text-amber-900">Temporary password generated</div>
              <div className="mono text-xl font-bold text-slate-900 mt-2 select-all" data-testid="temp-password-display">{tempPw}</div>
              <div className="text-xs text-amber-800 mt-2">Share this with the user securely. They will be required to change it at first login.</div>
            </div>
            <div className="flex justify-end">
              <Button onClick={() => { setTempPw(null); onOpenChange(false); }} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="temp-password-close">Done</Button>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <Section title="Identity">
              <Grid>
                <Field label="Full name *"><Input required value={form.name} onChange={(e) => set("name", e.target.value)} data-testid="newuser-name" /></Field>
                <Field label="Employee ID *"><Input required value={form.employee_id} onChange={(e) => set("employee_id", e.target.value)} data-testid="newuser-emp" placeholder="EMP-1234" /></Field>
                <Field label="Username *"><Input required value={form.username} onChange={(e) => set("username", e.target.value)} data-testid="newuser-username" /></Field>
                <Field label="Email *"><Input required type="email" value={form.email} onChange={(e) => set("email", e.target.value)} data-testid="newuser-email" /></Field>
              </Grid>
            </Section>
            <Section title="Assignment">
              <Grid>
                <Field label="Department"><Input value={form.department} onChange={(e) => set("department", e.target.value)} data-testid="newuser-dept" /></Field>
                <Field label="Location"><Input value={form.location} onChange={(e) => set("location", e.target.value)} data-testid="newuser-location" /></Field>
                <Field label="User type">
                  <Select value={form.user_type} onValueChange={(v) => set("user_type", v)}>
                    <SelectTrigger data-testid="newuser-type"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Employee">Employee</SelectItem>
                      <SelectItem value="Contractor">Contractor</SelectItem>
                      <SelectItem value="Auditor">External Auditor</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Access level">
                  <Select value={form.access_level} onValueChange={(v) => set("access_level", v)}>
                    <SelectTrigger data-testid="newuser-access"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="Full">Full</SelectItem>
                      <SelectItem value="ReadOnly">Read Only</SelectItem>
                      <SelectItem value="Limited">Limited</SelectItem>
                    </SelectContent>
                  </Select>
                </Field>
                <Field label="Expiry date (optional)"><Input type="date" value={form.expiry_date} onChange={(e) => set("expiry_date", e.target.value)} data-testid="newuser-expiry" /></Field>
                <Field label="Notes / justification"><Input value={form.notes} onChange={(e) => set("notes", e.target.value)} placeholder="Reason for access" data-testid="newuser-notes" /></Field>
              </Grid>
            </Section>
            <Section title="Roles (multi-select)">
              <div className="flex flex-wrap gap-2" data-testid="newuser-roles">
                {ALL_ROLES.map((r) => (
                  <button
                    key={r.code}
                    type="button"
                    data-testid={`newuser-role-${r.code}`}
                    onClick={() => toggleRole(r.code)}
                    className={`px-3 py-1 text-xs border rounded-sm ${form.roles.includes(r.code) ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-700 border-slate-300"}`}
                    title={r.custom ? "Custom role (created in Role Matrix)" : r.label}
                  >
                    {r.label}{r.custom && <span className="ml-1 text-[9px] opacity-70">●</span>}
                  </button>
                ))}
              </div>
            </Section>
            <Section title="Electronic Signature (21 CFR Part 11)">
              <Grid>
                <Field label="Your password *"><Input required type="password" value={form.esign_password} onChange={(e) => set("esign_password", e.target.value)} data-testid="newuser-esign-pw" /></Field>
                <Field label="Reason for creation *"><Input required value={form.esign_reason} onChange={(e) => set("esign_reason", e.target.value)} data-testid="newuser-esign-reason" placeholder="New hire for QA team" /></Field>
              </Grid>
            </Section>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)} data-testid="newuser-cancel">Cancel</Button>
              <Button type="submit" disabled={busy || form.roles.length === 0} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="newuser-submit">{busy ? "Creating…" : "Sign & Create User"}</Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}

const Section = ({ title, children }) => (
  <div className="border border-slate-200 rounded-sm">
    <div className="px-3 py-1.5 border-b border-slate-200 bg-slate-50 text-xs font-semibold text-slate-700 uppercase tracking-wide">{title}</div>
    <div className="p-3 space-y-3">{children}</div>
  </div>
);
const Grid = ({ children }) => <div className="grid grid-cols-1 md:grid-cols-2 gap-3">{children}</div>;
const Field = ({ label, children }) => (
  <div><Label className="text-xs uppercase tracking-wide text-slate-500">{label}</Label>{children}</div>
);
