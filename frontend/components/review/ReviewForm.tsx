"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { today } from "@/lib/utils";

interface ReviewFormProps {
  planId?: string;
  reviewQuestions?: string[];
}

export function ReviewForm({ planId, reviewQuestions = [] }: ReviewFormProps) {
  const router = useRouter();
  const t = useT();
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState({
    energy_end: 7,
    overall_day_rating: 7,
    biggest_win: "",
    lessons: "",
    raw_reflection: "",
    completed_raw: "",
    missed_raw: "",
    carry_over_raw: "",
  });

  function update(field: string, value: string | number) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await api.reviews.create({
        plan_id: planId,
        review_date: today(),
        completed_items: form.completed_raw.split("\n").map((t) => t.trim()).filter(Boolean),
        missed_items: form.missed_raw.split("\n").map((t) => t.trim()).filter(Boolean),
        carry_over_to_tomorrow: form.carry_over_raw.split("\n").map((t) => t.trim()).filter(Boolean),
        energy_end: form.energy_end,
        overall_day_rating: form.overall_day_rating,
        biggest_win: form.biggest_win || undefined,
        lessons: form.lessons || undefined,
        raw_reflection: form.raw_reflection || undefined,
      });
      setDone(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center gap-4">
        <div className="h-12 w-12 rounded-full bg-brand-600/20 border border-brand-500/30 flex items-center justify-center text-2xl">
          ✓
        </div>
        <p className="text-slate-200 font-medium">{t("review.saved")}</p>
        <p className="text-slate-500 text-sm">{t("review.saved_sub")}</p>
        <Button variant="ghost" onClick={() => router.push("/dashboard")}>
          {t("review.back")}
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error && (
        <div className="rounded-lg bg-red-950 border border-red-800 px-4 py-3 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Review questions from today's plan */}
      {reviewQuestions.length > 0 && (
        <Card variant="bordered">
          <CardHeader>
            <CardTitle>{t("review.today_questions")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-2">
              {reviewQuestions.map((q, i) => (
                <li key={i} className="text-slate-300 text-sm flex gap-3">
                  <span className="text-slate-600 font-mono text-xs mt-0.5">{i + 1}.</span>
                  {q}
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      )}

      {/* Ratings */}
      <Card>
        <CardHeader><CardTitle>{t("review.eod_vitals")}</CardTitle></CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">
              {t("review.energy_end")} — {form.energy_end}/10
            </label>
            <input
              type="range" min={1} max={10}
              value={form.energy_end}
              onChange={(e) => update("energy_end", parseInt(e.target.value))}
              className="accent-brand-500"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">
              {t("review.overall_day")} — {form.overall_day_rating}/10
            </label>
            <input
              type="range" min={1} max={10}
              value={form.overall_day_rating}
              onChange={(e) => update("overall_day_rating", parseInt(e.target.value))}
              className="accent-brand-500"
            />
          </div>
        </CardContent>
      </Card>

      {/* Execution */}
      <Card>
        <CardHeader><CardTitle>{t("review.execution")}</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            label={t("review.completed")}
            placeholder={t("review.completed_ph")}
            rows={3}
            value={form.completed_raw}
            onChange={(e) => update("completed_raw", e.target.value)}
          />
          <Textarea
            label={t("review.missed")}
            placeholder={t("review.missed_ph")}
            rows={2}
            value={form.missed_raw}
            onChange={(e) => update("missed_raw", e.target.value)}
          />
          <Textarea
            label={t("review.carry_over")}
            placeholder={t("review.carry_over_ph")}
            rows={2}
            value={form.carry_over_raw}
            onChange={(e) => update("carry_over_raw", e.target.value)}
          />
        </CardContent>
      </Card>

      {/* Reflection */}
      <Card>
        <CardHeader><CardTitle>{t("review.reflection")}</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <Textarea
            label={t("review.biggest_win")}
            placeholder={t("review.biggest_win_ph")}
            rows={2}
            value={form.biggest_win}
            onChange={(e) => update("biggest_win", e.target.value)}
          />
          <Textarea
            label={t("review.lesson")}
            placeholder={t("review.lesson_ph")}
            rows={2}
            value={form.lessons}
            onChange={(e) => update("lessons", e.target.value)}
          />
          <Textarea
            label={t("review.raw")}
            placeholder={t("review.raw_ph")}
            rows={3}
            value={form.raw_reflection}
            onChange={(e) => update("raw_reflection", e.target.value)}
          />
        </CardContent>
      </Card>

      <Button type="submit" size="lg" loading={submitting} className="w-full">
        {t("review.save")}
      </Button>
    </form>
  );
}
