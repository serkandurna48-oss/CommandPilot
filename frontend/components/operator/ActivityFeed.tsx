"use client";

import { useT } from "@/lib/i18n";
import type { ActivityLogEntry } from "@/types";
import { cn } from "@/lib/utils";
import { LOG_LEVEL_COLORS } from "@/lib/operatorStyles";
import { Terminal } from "lucide-react";

/**
 * Activity stream — the persistent, default view of a work order's activity
 * log (Mission Control redesign). Generalized from the running-only stream
 * in the earlier LiveExecutionView: shows exactly the same real
 * activity_logs rows regardless of order status, so a completed or blocked
 * work order's history reads the same way a live one does, not a different
 * (calmer) component. Newest entry on top, scrollable — nothing is
 * truncated beyond the scroll, unlike the old fixed max-56 excerpt this
 * replaces (that was only ever a "recent" preview inside the live view;
 * this is the actual persistent log view).
 *
 * Focus Deck tokens (23.09.2026) — the log lines keep the monospace
 * treatment (timestamps/levels are exactly the "technical metadata" the
 * design system reserves mono for), but the terminal-green/black chrome is
 * gone; this now reads as a surface in the same system as everything else.
 */
export function ActivityFeed({ activityLog }: { activityLog: ActivityLogEntry[] }) {
  const t = useT();
  const ordered = [...activityLog].reverse();

  return (
    <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-app)] overflow-hidden">
      <div className="flex items-center gap-1.5 px-3 py-1.5 border-b border-[var(--border-light)] text-[var(--text-tertiary)] text-[10px] font-mono uppercase tracking-widest">
        <Terminal className="h-3 w-3" /> {t("operator.live.stream_title")}
      </div>
      <div className="px-3 py-2 max-h-80 overflow-y-auto space-y-1">
        {ordered.length === 0 ? (
          <p className="text-[var(--text-placeholder)] text-xs font-mono">{t("operator.section.no_activity")}</p>
        ) : (
          ordered.map((entry) => (
            <div key={entry.id} className="text-xs font-mono flex items-start gap-2">
              <span className="text-[var(--text-placeholder)] shrink-0">{new Date(entry.createdAt).toLocaleTimeString()}</span>
              <span className={cn("shrink-0 uppercase", LOG_LEVEL_COLORS[entry.level])}>{t(`operator.log.${entry.level}`)}</span>
              <span className="text-[var(--text-secondary)]">{entry.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
