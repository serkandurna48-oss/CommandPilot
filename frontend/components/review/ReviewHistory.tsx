"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatDateShort } from "@/lib/utils";
import type { EveningReview } from "@/types";

// Same fix as CheckinHistory.tsx: GET /api/reviews/me already existed and
// worked, just was never called from the frontend. No new backend work.
// Renders nothing while loading or once confirmed empty.
//
// Found live in production (24.09.2026), same bug as CheckinHistory.tsx: a
// failed fetch was treated as "confirmed empty" and rendered nothing.
export function ReviewHistory() {
  const t = useT();
  const [reviews, setReviews] = useState<EveningReview[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(() => {
    const currentRequest = ++requestId.current;
    setError(null);
    api.reviews
      .listMine()
      .then((data) => {
        if (currentRequest === requestId.current) setReviews(data);
      })
      .catch((e: unknown) => {
        if (currentRequest === requestId.current) {
          setError(e instanceof Error ? e.message : String(e));
        }
      });
  }, []);

  useEffect(() => {
    load();
    // Ignore responses from an earlier request or a cleaned-up effect.
    return () => { requestId.current += 1; };
  }, [load]);

  if (error !== null) {
    return (
      <div className="mt-8 flex items-center justify-between gap-3 rounded-2xl border border-status-danger/30 bg-status-danger/10 px-4 py-3">
        <p className="text-status-danger text-sm">{t("error.load_failed")} {error}</p>
        <Button size="sm" variant="outline-accent" onClick={load}>
          {t("button.retry")}
        </Button>
      </div>
    );
  }

  if (!reviews || reviews.length === 0) return null;

  return (
    <div className="mt-8">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)] mb-3">
        {t("review.history.title")}
      </h2>
      <div className="rounded-2xl border border-white/[0.06] bg-[var(--bg-surface)] shadow-[var(--shadow-card)] divide-y divide-white/[0.05] overflow-hidden">
        {reviews.slice(0, 14).map((r) => (
          <div key={r.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
            <span className="text-[var(--text-tertiary)] text-xs font-mono w-20 shrink-0">
              {formatDateShort(r.review_date ?? r.created_at)}
            </span>
            <span className="text-[var(--text-secondary)] flex-1 truncate">{r.biggest_win || "—"}</span>
            {typeof r.overall_day_rating === "number" && (
              <span className="text-[10px] font-mono text-[var(--text-tertiary)] shrink-0">
                {r.overall_day_rating}/10
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
