import React, { useEffect, useMemo, useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Copy, GitBranch } from "lucide-react";
import { toast } from "sonner";
import api, { formatApiError } from "../lib/api";

/**
 * Clone & Edit dialog — spawns a plant-specific DRAFT copy of a GLOBAL template
 * and immediately opens the Template Designer on the new copy.
 *
 * Backend: POST /api/module-framework/templates/{id}/copy
 * Body: { new_code, new_name, target_plant_id, reason }
 */
export default function CloneToPlantDialog({ open, onOpenChange, sourceTemplate, plants, onCloned }) {
  const [plantId, setPlantId] = useState("");
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [reason, setReason] = useState("New plant rollout");
  const [busy, setBusy] = useState(false);

  const plantOptions = useMemo(
    () => (plants || []).filter((p) => p.is_active !== false),
    [plants],
  );

  // Pre-populate sensible defaults whenever a new source template is opened.
  useEffect(() => {
    if (!open || !sourceTemplate) return;
    const slug = (s) => (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    const firstPlant = plantOptions[0];
    const plantSlug = firstPlant ? slug(firstPlant.code || firstPlant.name) : "plant";
    setPlantId(firstPlant?.id || "");
    setCode(`${sourceTemplate.code}__${plantSlug}`);
    setName(`${sourceTemplate.name} — ${firstPlant?.name || "Plant"}`);
    setReason("New plant rollout");
  }, [open, sourceTemplate, plantOptions]);

  // When the plant changes, refresh the suggested code/name suffix.
  const onPickPlant = (id) => {
    setPlantId(id);
    const p = plantOptions.find((x) => x.id === id);
    if (!p || !sourceTemplate) return;
    const slug = (s) => (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
    const plantSlug = slug(p.code || p.name);
    setCode(`${sourceTemplate.code}__${plantSlug}`);
    setName(`${sourceTemplate.name} — ${p.name}`);
  };

  const submit = async () => {
    if (!sourceTemplate) return;
    if (!plantId) { toast.error("Select a target plant"); return; }
    if (!code || code.length < 2) { toast.error("Enter a unique code"); return; }
    if (!name || name.length < 2) { toast.error("Enter a name"); return; }
    if (!reason || reason.length < 3) { toast.error("Reason is required (audit trail)"); return; }
    setBusy(true);
    try {
      const res = await api.post(`/module-framework/templates/${sourceTemplate.id}/copy`, {
        new_code: code, new_name: name, target_plant_id: plantId, reason,
      });
      toast.success(`Clone created as DRAFT v${res.data?.version || 1}`);
      onOpenChange(false);
      onCloned?.(res.data);
    } catch (e) {
      toast.error(formatApiError(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(false);
    }
  };

  if (!sourceTemplate) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg" data-testid="clone-template-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GitBranch size={16} className="text-slate-600" /> Clone &amp; Edit — Plant-specific copy
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="border border-slate-200 bg-slate-50 rounded-sm p-3 text-xs">
            <div className="text-[10px] mono uppercase tracking-wide text-slate-500">Source template</div>
            <div className="font-medium text-slate-900 mt-0.5">{sourceTemplate.name}</div>
            <div className="mono text-[11px] text-slate-600">
              {sourceTemplate.code} · v{sourceTemplate.version} · {sourceTemplate.status} · {sourceTemplate.plant_id === "GLOBAL" ? "Global" : sourceTemplate.plant_id}
            </div>
            <p className="text-[11px] text-slate-500 mt-2 leading-relaxed">
              A new <b>DRAFT</b> copy will be created against the selected plant. Workflow, form, PDF layout, approvals, and role mapping are duplicated and remain fully editable until you publish.
            </p>
          </div>

          <div>
            <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Target plant</label>
            <Select value={plantId} onValueChange={onPickPlant}>
              <SelectTrigger data-testid="clone-target-plant"><SelectValue placeholder="Select plant…" /></SelectTrigger>
              <SelectContent>
                {plantOptions.length === 0 && <SelectItem value="__none" disabled>No plants configured</SelectItem>}
                {plantOptions.map((p) => (
                  <SelectItem key={p.id} value={p.id}>{p.name} ({p.code})</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">New code</label>
              <Input value={code} onChange={(e) => setCode(e.target.value)} data-testid="clone-new-code" />
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">New name</label>
              <Input value={name} onChange={(e) => setName(e.target.value)} data-testid="clone-new-name" />
            </div>
          </div>

          <div>
            <label className="text-[11px] uppercase tracking-wide text-slate-500 mono">Reason (audit trail)</label>
            <Input value={reason} onChange={(e) => setReason(e.target.value)} data-testid="clone-reason" />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} data-testid="clone-cancel-btn">Cancel</Button>
          <Button onClick={submit} disabled={busy} className="bg-slate-900 hover:bg-slate-800 text-white" data-testid="clone-submit-btn">
            <Copy size={14} className="mr-1.5" /> {busy ? "Cloning…" : "Clone & Edit"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
