"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input, Textarea } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { ApiError, api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { today } from "@/lib/utils";
import type { FixedEvent } from "@/types";

export function CheckinForm() {
  const router = useRouter();
  const t = useT();

  const [step, setStep] = useState<"checkin" | "generating">("checkin");
  const [error, setError] = useState<string | null>(null);
  // Preserved across retries so we don't create a second checkin if plan generation fails.
  const [pendingCheckinId, setPendingCheckinId] = useState<string | null>(null);

  const [form, setForm] = useState({
    wake_time: "",
    sleep_quality: 7,
    energy_level: 7,
    body_status: "",
    mood: "",
    available_hours: "",
    day_constraints: "",
    raw_input: "",
    important_tasks_raw: "",  // newline-separated
    fixed_events_raw: "",     // newline-separated "title at HH:MM"
  });

  function updateField(field: string, value: string | number) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function parseFixedEvents(raw: string): FixedEvent[] {
    return raw
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const timeMatch = line.match(/(\d{1,2}:\d{2})/);
        return {
          title: line.replace(/(\d{1,2}:\d{2})/, "").replace(/\bat\b/i, "").trim(),
          time: timeMatch?.[1],
        };
      });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setStep("generating");

    try {
      // If a previous attempt already created the checkin but plan generation
      // failed, reuse that checkin instead of creating a duplicate.
      let checkinId = pendingCheckinId;

      if (!checkinId) {
        const checkin = await api.checkins.create({
          checkin_date: today(),
          wake_time: form.wake_time || undefined,
          sleep_quality: form.sleep_quality,
          energy_level: form.energy_level,
          body_status: form.body_status || undefined,
          mood: form.mood || undefined,
          available_hours: form.available_hours ? parseFloat(form.available_hours) : undefined,
          day_constraints: form.day_constraints || undefined,
          raw_input: form.raw_input || undefined,
          important_tasks: form.important_tasks_raw
            .split("\n")
            .map((t) => t.trim())
            .filter(Boolean),
          fixed_events: parseFixedEvents(form.fixed_events_raw),
        });
        checkinId = checkin.id;
        setPendingCheckinId(checkinId);
      }

      const plan = await api.plans.generate({
        checkin_id: checkinId,
      });

      router.push(`/plans/${plan.id}`);
    } catch (err: unknown) {
      if (
        err instanceof ApiError &&
        err.code === "PLAN_ALREADY_EXISTS" &&
        err.planId
      ) {
        router.push(`/plans/${err.planId}`);
        return;
      }
      setError(err instanceof Error ? err.message : t("common.error"));
      setStep("checkin");
    }
  }

  if (step === "generating") {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <div className="h-10 w-10 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
        <p className="text-slate-300 text-sm">{t("morning.generating")}</p>
        <p className="text-slate-500 text-xs">{t("morning.generating_sub")}</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="rounded-lg bg-red-950 border border-red-800 px-4 py-3 text-red-300 text-sm">
          <p>{error}</p>
          {pendingCheckinId && (
            <p className="text-red-400 text-xs mt-1">{t("morning.checkin_hint")}</p>
          )}
        </div>
      )}

      {/* Quick raw input */}
      <Card variant="elevated">
        <CardHeader>
          <CardTitle>{t("morning.quick_input")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            label={t("morning.quick_label")}
            placeholder={t("morning.quick_ph")}
            rows={5}
            value={form.raw_input}
            onChange={(e) => updateField("raw_input", e.target.value)}
          />
        </CardContent>
      </Card>

      {/* Vitals */}
      <Card>
        <CardHeader>
          <CardTitle>{t("morning.vitals")}</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Input
            label={t("morning.wake_time")}
            type="time"
            value={form.wake_time}
            onChange={(e) => updateField("wake_time", e.target.value)}
          />

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">
              {t("morning.sleep_quality")} — {form.sleep_quality}/10
            </label>
            <input
              type="range" min={1} max={10}
              value={form.sleep_quality}
              onChange={(e) => updateField("sleep_quality", parseInt(e.target.value))}
              className="accent-brand-500"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">
              {t("morning.energy_level")} — {form.energy_level}/10
            </label>
            <input
              type="range" min={1} max={10}
              value={form.energy_level}
              onChange={(e) => updateField("energy_level", parseInt(e.target.value))}
              className="accent-brand-500"
            />
          </div>

          <Input
            label={t("morning.avail_hours")}
            type="number"
            min={1} max={16} step={0.5}
            placeholder="e.g. 8"
            value={form.available_hours}
            onChange={(e) => updateField("available_hours", e.target.value)}
          />

          <Input
            label={t("morning.body_status")}
            placeholder={t("morning.body_ph")}
            value={form.body_status}
            onChange={(e) => updateField("body_status", e.target.value)}
          />

          <Input
            label={t("morning.mood")}
            placeholder={t("morning.mood_ph")}
            value={form.mood}
            onChange={(e) => updateField("mood", e.target.value)}
          />
        </CardContent>
      </Card>

      {/* Tasks & Events */}
      <Card>
        <CardHeader>
          <CardTitle>{t("morning.agenda")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            label={t("morning.fixed_events")}
            placeholder={t("morning.fixed_ph")}
            rows={3}
            value={form.fixed_events_raw}
            onChange={(e) => updateField("fixed_events_raw", e.target.value)}
          />
          <Textarea
            label={t("morning.tasks")}
            placeholder={t("morning.tasks_ph")}
            rows={4}
            value={form.important_tasks_raw}
            onChange={(e) => updateField("important_tasks_raw", e.target.value)}
          />
          <Textarea
            label={t("morning.constraints")}
            placeholder={t("morning.constraints_ph")}
            rows={2}
            value={form.day_constraints}
            onChange={(e) => updateField("day_constraints", e.target.value)}
          />
        </CardContent>
      </Card>

      <Button type="submit" size="lg" className="w-full">
        {pendingCheckinId && error ? t("morning.retry") : t("morning.generate")}
      </Button>
    </form>
  );
}
