"use client";

import { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/Button";
import { Input, Textarea, Select } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/Spinner";
import { api } from "@/lib/api";
import type { UserRule } from "@/types";
import { Trash2, ToggleLeft, ToggleRight, Plus } from "lucide-react";

const CATEGORIES = ["scheduling", "energy", "focus", "sport", "study", "business", "social", "general"];

export function RulesManager() {
  const [rules, setRules] = useState<UserRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ title: "", rule_text: "", category: "general", priority: 5 });

  const loadRules = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.rules.listMine();
      setRules(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadRules(); }, [loadRules]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!form.title.trim() || !form.rule_text.trim()) return;
    setSaving(true);
    try {
      await api.rules.create({
        title: form.title,
        rule_text: form.rule_text,
        category: form.category,
        priority: form.priority,
        is_active: true,
      });
      setForm({ title: "", rule_text: "", category: "general", priority: 5 });
      setShowForm(false);
      await loadRules();
    } finally {
      setSaving(false);
    }
  }

  async function toggleRule(rule: UserRule) {
    await api.rules.update(rule.id, { is_active: !rule.is_active });
    setRules((prev) => prev.map((r) => (r.id === rule.id ? { ...r, is_active: !r.is_active } : r)));
  }

  async function deleteRule(id: string) {
    if (!confirm("Delete this rule?")) return;
    await api.rules.delete(id);
    setRules((prev) => prev.filter((r) => r.id !== id));
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-slate-400 text-sm">
          {rules.length} rule{rules.length !== 1 ? "s" : ""} — active rules are injected into every AI plan.
        </p>
        <Button size="sm" onClick={() => setShowForm((v) => !v)}>
          <Plus className="h-4 w-4" />
          {showForm ? "Cancel" : "Add Rule"}
        </Button>
      </div>

      {showForm && (
        <Card variant="elevated">
          <CardContent className="pt-4">
            <form onSubmit={handleCreate} className="space-y-3">
              <Input
                label="Title"
                placeholder="e.g. No heavy tasks after sport"
                value={form.title}
                onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
              />
              <Textarea
                label="Rule"
                placeholder="Do not schedule deep work within 2 hours after an intense workout."
                rows={3}
                value={form.rule_text}
                onChange={(e) => setForm((f) => ({ ...f, rule_text: e.target.value }))}
              />
              <div className="grid grid-cols-2 gap-3">
                <Select
                  label="Category"
                  value={form.category}
                  onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}
                >
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>{c}</option>
                  ))}
                </Select>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">
                    Priority — {form.priority}
                  </label>
                  <input
                    type="range" min={1} max={10}
                    value={form.priority}
                    onChange={(e) => setForm((f) => ({ ...f, priority: parseInt(e.target.value) }))}
                    className="accent-brand-500 mt-1"
                  />
                </div>
              </div>
              <Button type="submit" loading={saving} size="sm">Save Rule</Button>
            </form>
          </CardContent>
        </Card>
      )}

      {loading ? (
        <div className="py-8 flex justify-center">
          <div className="h-6 w-6 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
        </div>
      ) : rules.length === 0 ? (
        <EmptyState
          title="No rules yet"
          description="Rules are used as context by the AI to personalize every plan. Add your operating principles."
        />
      ) : (
        <div className="space-y-2">
          {rules.map((rule) => (
            <Card
              key={rule.id}
              className={!rule.is_active ? "opacity-50" : undefined}
            >
              <CardContent className="py-3 flex gap-3 items-start">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-0.5">
                    <p className="text-slate-200 text-sm font-medium">{rule.title}</p>
                    {rule.category && (
                      <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded">
                        {rule.category}
                      </span>
                    )}
                    <span className="text-xs text-slate-600">p{rule.priority}</span>
                  </div>
                  <p className="text-slate-400 text-xs">{rule.rule_text}</p>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button
                    onClick={() => toggleRule(rule)}
                    className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
                    title={rule.is_active ? "Disable" : "Enable"}
                  >
                    {rule.is_active
                      ? <ToggleRight className="h-4 w-4 text-brand-400" />
                      : <ToggleLeft className="h-4 w-4" />
                    }
                  </button>
                  <button
                    onClick={() => deleteRule(rule.id)}
                    className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-red-400 transition-colors"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
