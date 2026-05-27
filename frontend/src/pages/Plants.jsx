import React, { useEffect, useState } from "react";
import api, { formatApiError } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "../components/ui/dialog";
import { toast } from "sonner";
import { Plus, Edit3, PowerOff, Power, Building2 } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { hasPermission } from "../lib/roles";

export default function Plants() {
  const { user: me } = useAuth();
  const canManage = hasPermission(me, "role_management"); // re-use role mgmt gate
  const [plants, setPlants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [open, setOpen] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/module-framework/plants");
      setPlants(data || []);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const openCreate = () => {
    setEditing({ code: "", name: "", location: "", address: "", gmp_zone: "", time_zone: "UTC", description: "" });
    setOpen(true);
  };
  const openEdit = (p) => {
    setEditing({ ...p, reason: "" });
    setOpen(true);
  };

  const save = async () => {
    if (!editing.code || !editing.name) return toast.error("Code and name required");
    try {
      if (editing.id) {
        if (!editing.reason || editing.reason.length < 3) return toast.error("Reason required");
        await api.patch(`/module-framework/plants/${editing.id}`, {
          name: editing.name, location: editing.location, address: editing.address,
          gmp_zone: editing.gmp_zone, time_zone: editing.time_zone, description: editing.description,
          reason: editing.reason,
        });
        toast.success("Plant updated");
      } else {
        await api.post("/module-framework/plants", {
          code: editing.code.toUpperCase(),
          name: editing.name, location: editing.location, address: editing.address,
          gmp_zone: editing.gmp_zone, time_zone: editing.time_zone, description: editing.description,
        });
        toast.success("Plant created");
      }
      setOpen(false); setEditing(null); load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  const toggle = async (p) => {
    const reason = window.prompt(`Reason for ${p.active ? "deactivating" : "activating"} ${p.name}:`, p.active ? "Decommissioning" : "Re-activate");
    if (!reason || reason.length < 3) return;
    try {
      await api.patch(`/module-framework/plants/${p.id}`, { active: !p.active, reason });
      toast.success(`Plant ${p.active ? "deactivated" : "activated"}`);
      load();
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    }
  };

  return (
    <div className="space-y-5" data-testid="plants-page">
      <div className="flex items-end justify-between">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500 mono">Plant/Site Framework</div>
          <h1 className="text-3xl font-semibold text-slate-950 tracking-tight mt-1" style={{ fontFamily: "Work Sans" }}>Plants & Sites</h1>
          <div className="text-xs text-slate-500 mt-1">Multi-plant deployment. Module templates can target a specific plant or be GLOBAL.</div>
        </div>
        {canManage && (
          <Button onClick={openCreate} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="new-plant-btn">
            <Plus size={16} className="mr-1" /> New Plant
          </Button>
        )}
      </div>

      <div className="border border-slate-200 bg-white rounded-sm overflow-x-auto">
        <table className="w-full table-dense">
          <thead className="bg-slate-50 text-[11px] uppercase tracking-wide text-slate-500">
            <tr>
              <th className="text-left">Code</th>
              <th className="text-left">Name</th>
              <th className="text-left">Location</th>
              <th className="text-left">GMP Zone</th>
              <th className="text-left">Time Zone</th>
              <th className="text-left">Status</th>
              <th className="text-left">Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={8} className="text-center text-xs text-slate-500 py-6">Loading…</td></tr>}
            {!loading && plants.length === 0 && <tr><td colSpan={8} className="text-center text-xs text-slate-500 py-6">No plants. Click "New Plant" to add one.</td></tr>}
            {plants.map((p) => (
              <tr key={p.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`plant-row-${p.code}`}>
                <td className="mono text-xs font-semibold">{p.code}</td>
                <td><div className="font-medium text-slate-900 flex items-center gap-2"><Building2 size={14} className="text-slate-400" />{p.name}</div></td>
                <td className="text-xs">{p.location || "—"}</td>
                <td className="text-xs">{p.gmp_zone || "—"}</td>
                <td className="text-xs mono">{p.time_zone || "UTC"}</td>
                <td>
                  <span
                    className="inline-block px-2 py-0.5 text-[10px] mono font-semibold uppercase rounded-sm"
                    style={p.active
                      ? { color: "#047857", background: "#ECFDF5", border: "1px solid #A7F3D0" }
                      : { color: "#B91C1C", background: "#FEF2F2", border: "1px solid #FECACA" }}
                  >{p.active ? "ACTIVE" : "INACTIVE"}</span>
                </td>
                <td className="mono text-[11px]">{p.created_at ? new Date(p.created_at).toLocaleDateString() : "—"}</td>
                <td className="text-right">
                  <div className="flex gap-1 justify-end">
                    {canManage && (
                      <>
                        <button onClick={() => openEdit(p)} title="Edit" className="p-1.5 hover:bg-slate-200 rounded-sm" data-testid={`edit-plant-${p.code}`}><Edit3 size={14} /></button>
                        <button onClick={() => toggle(p)} title={p.active ? "Deactivate" : "Activate"} className="p-1.5 hover:bg-slate-200 rounded-sm" data-testid={`toggle-plant-${p.code}`}>
                          {p.active ? <PowerOff size={14} className="text-rose-600" /> : <Power size={14} className="text-emerald-600" />}
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg" data-testid="plant-dialog">
          <DialogHeader>
            <DialogTitle>{editing?.id ? `Edit plant: ${editing.code}` : "Create new plant"}</DialogTitle>
            <DialogDescription>Multi-plant identity. Module templates can target a specific plant or apply globally.</DialogDescription>
          </DialogHeader>
          {editing && (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-600">Code *</label>
                  <Input value={editing.code} disabled={!!editing.id} onChange={(e) => setEditing((p) => ({ ...p, code: e.target.value.toUpperCase() }))} placeholder="e.g. PLANT-3" data-testid="plant-code" />
                </div>
                <div>
                  <label className="text-xs text-slate-600">Name *</label>
                  <Input value={editing.name} onChange={(e) => setEditing((p) => ({ ...p, name: e.target.value }))} data-testid="plant-name" />
                </div>
                <div>
                  <label className="text-xs text-slate-600">Location</label>
                  <Input value={editing.location} onChange={(e) => setEditing((p) => ({ ...p, location: e.target.value }))} data-testid="plant-location" />
                </div>
                <div>
                  <label className="text-xs text-slate-600">GMP Zone</label>
                  <Input value={editing.gmp_zone} onChange={(e) => setEditing((p) => ({ ...p, gmp_zone: e.target.value }))} placeholder="e.g. GMP Grade A" data-testid="plant-gmp" />
                </div>
                <div className="col-span-2">
                  <label className="text-xs text-slate-600">Address</label>
                  <Input value={editing.address} onChange={(e) => setEditing((p) => ({ ...p, address: e.target.value }))} data-testid="plant-address" />
                </div>
                <div>
                  <label className="text-xs text-slate-600">Time zone</label>
                  <Input value={editing.time_zone} onChange={(e) => setEditing((p) => ({ ...p, time_zone: e.target.value }))} placeholder="UTC / Asia/Kolkata" data-testid="plant-tz" />
                </div>
              </div>
              <div>
                <label className="text-xs text-slate-600">Description</label>
                <Textarea rows={2} value={editing.description} onChange={(e) => setEditing((p) => ({ ...p, description: e.target.value }))} data-testid="plant-desc" />
              </div>
              {editing.id && (
                <div>
                  <label className="text-xs text-slate-600">Reason for change *</label>
                  <Input value={editing.reason || ""} onChange={(e) => setEditing((p) => ({ ...p, reason: e.target.value }))} data-testid="plant-reason" />
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} className="bg-slate-900 text-white" data-testid="plant-save">{editing?.id ? "Save" : "Create plant"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
