"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatDateShort } from "@/lib/utils";
import type { EveningReview } from "@/types";

// Same fix as CheckinHistory.tsx: GET /api/reviews/me already existed and
// worked, just was never called from the frontend. No new backend work.
// Renders nothing until at least one real review exists.
export function ReviewHistory() {
  const t = useT();
  const [reviews, setReviews] = useState<EveningReview[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.reviews
      .listMine()
      .then((res) => {
        if (!cancelled) setReviews(res);
      })
      .catch(() => {
        if (!cancelled) setReviews([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

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
