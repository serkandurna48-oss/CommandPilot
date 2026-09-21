import { useT } from "@/lib/i18n";
import { AUTONOMOUS_ALLOWED, NEEDS_APPROVAL, BLOCKED_ALWAYS } from "@/lib/safetyRules";
import { Check, AlertTriangle, Ban } from "lucide-react";

function RuleList({ items, icon: Icon, tone }: { items: string[]; icon: typeof Check; tone: string }) {
  return (
    <ul className="space-y-1">
      {items.map((item, i) => (
        <li key={i} className="text-xs flex items-start gap-1.5">
          <Icon className={`h-3.5 w-3.5 shrink-0 mt-0.5 ${tone}`} />
          <span className="text-[var(--text-secondary)]">{item}</span>
        </li>
      ))}
    </ul>
  );
}

/**
 * Repo-wide safety rules — always visible, never mock. These are the same
 * defaults baked into generateRunnerPrompt() so the UI and the generated
 * prompt can never silently drift apart. Rendered as bare content — the
 * caller (WorkOrderDetail) supplies the section title/surface via
 * SurfaceSection, keeping this in the same divided surface as everything
 * else on the page rather than its own bordered card.
 */
export function SafetyRulesPanel() {
  const t = useT();

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <div>
        <p className="text-[10px] font-mono uppercase tracking-wider text-status-success/80 mb-2">
          {t("operator.section.autonomous_allowed")}
        </p>
        <RuleList items={AUTONOMOUS_ALLOWED} icon={Check} tone="text-status-success/80" />
      </div>
      <div>
        <p className="text-[10px] font-mono uppercase tracking-wider text-status-warning/80 mb-2">
          {t("operator.section.needs_approval_list")}
        </p>
        <RuleList items={NEEDS_APPROVAL} icon={AlertTriangle} tone="text-status-warning/80" />
      </div>
      <div>
        <p className="text-[10px] font-mono uppercase tracking-wider text-status-danger/80 mb-2">
          {t("operator.section.blocked_list")}
        </p>
        <RuleList items={BLOCKED_ALWAYS} icon={Ban} tone="text-status-danger/80" />
      </div>
    </div>
  );
}
