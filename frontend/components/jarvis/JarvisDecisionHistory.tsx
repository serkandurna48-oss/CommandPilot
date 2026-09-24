"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Check, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn, formatDateShort } from "@/lib/utils";
import type { JarvisSuggestedActionDecisionListItem } from "@/types";

// Closes the loop on the Command Layer (JARVIS-C1): every proposal a human
// has confirmed or rejected is recorded in suggested_action_decisions, but
// until now that audit trail was never surfaced anywhere — a decision
// vanished from view the moment you left the chat turn that produced it.
// Renders nothing while loading or once confirmed empty.
//
// Found live in production (24.09.2026), same bug as CheckinHistory.tsx: a
// failed fetch was treated as "confirmed empty" and rendered nothing.
export function JarvisDecisionHistory() {
  const t = useT();
  const [decisions, setDecisions] = useState<JarvisSuggestedActionDecisionListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);

  const load = useCallback(() => {
    const currentRequest = ++requestId.current;
    setError(null);
    api.jarvis
      .listDecisions()
      .then((data) => {
        if (currentRequest === requestId.current) setDecisions(data.decisions);
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
      <div className="flex items-center justify-between gap-3 rounded-lg border border-status-danger/30 bg-status-danger/10 px-3 py-2">
        <p className="text-status-danger text-xs">{t("error.load_failed")}</p>
        <Button size="sm" variant="outline-accent" onClick={load}>
          {t("button.retry")}
        </Button>
      </div>
    );
  }

  if (!decisions || decisions.length === 0) return null;

  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-2">
        {t("jarvis.panel.decisions_label")}
      </p>
      <div className="space-y-0.5">
        {decisions.slice(0, 6).map((d) => {
          const confirmed = d.decision === "confirmed";
          const content = (
            <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg hover:bg-[var(--interactive-bg-secondary-hover)] motion-safe:transition-colors duration-150">
              <span
                className={cn(
                  "flex items-center justify-center h-5 w-5 rounded-full shrink-0",
                  confirmed ? "bg-status-success/15 text-status-success" : "bg-[var(--bg-hover-surface)] text-[var(--text-tertiary)]"
                )}
              >
                {confirmed ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
              </span>
              <span className="min-w-0 flex-1 text-xs text-[var(--text-secondary)] truncate">{d.title}</span>
              <span className="text-[10px] text-[var(--text-placeholder)] shrink-0">{formatDateShort(d.created_at)}</span>
            </div>
          );
          return confirmed && d.work_order_id ? (
            <Link key={d.id} href={`/operator/${d.work_order_id}`}>
              {content}
            </Link>
          ) : (
            <div key={d.id}>{content}</div>
          );
        })}
      </div>
    </div>
  );
}
