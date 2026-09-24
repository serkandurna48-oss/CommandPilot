"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatDateShort } from "@/lib/utils";
import type { Checkin } from "@/types";

// GET /api/checkins/me has existed since the backend's first cut but was
// never called from the frontend — every morning check-in a user has ever
// submitted (energy, sleep, mood) was captured and then permanently
// invisible again. No new backend work; this is a pure read-surface fix.
// Renders nothing while loading or once confirmed empty — a "no check-ins
// yet" first-day state should stay unobtrusive.
//
// Found live in production (24.09.2026): a failed fetch (cold backend,
// expired token, network blip) was caught and treated as "confirmed
// empty," rendering nothing — a real check-in history could silently
// vanish with zero indication anything went wrong. Failure now gets its
// own visible state instead of being folded into "no history."
export function CheckinHistory() {
  const t = useT();
  const [checkins, setCheckins] = useState<Checkin[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(() => {
    const currentRequest = ++requestId.current;
    setError(null);
    api.checkins
      .listMine()
      .then((data) => {
        if (currentRequest === requestId.current) setCheckins(data);
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

  if (!checkins || checkins.length === 0) return null;

  return (
    <div className="mt-8">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)] mb-3">
        {t("morning.history.title")}
      </h2>
      <div className="rounded-2xl border border-white/[0.06] bg-[var(--bg-surface)] shadow-[var(--shadow-card)] divide-y divide-white/[0.05] overflow-hidden">
        {checkins.slice(0, 14).map((c) => (
          <div key={c.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
            <span className="text-[var(--text-tertiary)] text-xs font-mono w-20 shrink-0">
              {formatDateShort(c.checkin_date ?? c.created_at)}
            </span>
            <span className="text-[var(--text-secondary)] flex-1 truncate">{c.mood || "—"}</span>
            {typeof c.energy_level === "number" && (
              <span className="text-[10px] font-mono text-[var(--text-tertiary)] shrink-0">
                {t("morning.history.energy")} {c.energy_level}/10
              </span>
            )}
            {typeof c.sleep_quality === "number" && (
              <span className="text-[10px] font-mono text-[var(--text-tertiary)] shrink-0">
                {t("morning.history.sleep")} {c.sleep_quality}/10
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
