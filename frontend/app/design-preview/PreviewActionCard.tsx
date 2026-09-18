"use client";

import { useT } from "@/lib/i18n";
import { Card, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import type { JarvisSuggestedAction } from "@/types";
import { ShieldAlert, ShieldCheck } from "lucide-react";

const RISK_STYLES: Record<JarvisSuggestedAction["risk"], { dot: string; textKey: string }> = {
  low: { dot: "bg-status-success", textKey: "design_preview.risk_low" },
  medium: { dot: "bg-status-warning", textKey: "design_preview.risk_medium" },
  high: { dot: "bg-status-danger", textKey: "design_preview.risk_high" },
};

export function PreviewActionCard({
  action,
  selected,
  onSelect,
}: {
  action: JarvisSuggestedAction;
  selected: boolean;
  onSelect: () => void;
}) {
  const t = useT();
  const risk = RISK_STYLES[action.risk];

  return (
    <Card
      variant="default"
      className={cn(
        "cursor-pointer motion-safe:transition-colors",
        "focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-[2.5px] focus-visible:outline-[var(--interactive-border-focus)]",
        selected ? "border-brand-500/60 bg-[var(--bg-secondary)]" : "hover:border-[var(--border-medium)]"
      )}
      onClick={onSelect}
      role="button"
      tabIndex={0}
      aria-pressed={selected}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
    >
      <CardContent className="py-3.5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-sm font-medium text-[var(--text-primary)] truncate">{action.title}</p>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5 line-clamp-2">{action.description}</p>
          </div>
          <span className="shrink-0 inline-flex items-center gap-1.5 text-[11px] text-[var(--text-secondary)]">
            <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", risk.dot)} />
            {t(risk.textKey)}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 mt-3 text-[11px] text-[var(--text-tertiary)]">
          <span className="inline-flex items-center gap-1">
            {action.requires_approval ? (
              <ShieldAlert className="h-3.5 w-3.5 text-status-warning" />
            ) : (
              <ShieldCheck className="h-3.5 w-3.5 text-status-success" />
            )}
            {t(action.requires_approval ? "design_preview.requires_approval" : "design_preview.no_approval")}
          </span>
          {action.target_repo_name && (
            <span className="font-mono truncate">{action.target_repo_name}</span>
          )}
          <span>{action.sources.length} {action.sources.length === 1 ? "Quelle" : "Quellen"}</span>
        </div>

        <div className="mt-3 pt-3 border-t border-[var(--border-default)] flex items-center justify-between gap-3">
          <span className="text-[10px] uppercase tracking-wide text-[var(--text-tertiary)]">{t("design_preview.badge")}</span>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled
            onClick={(e) => e.stopPropagation()}
            title={t("design_preview.actions_hint")}
          >
            {t("design_preview.actions_unavailable")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
