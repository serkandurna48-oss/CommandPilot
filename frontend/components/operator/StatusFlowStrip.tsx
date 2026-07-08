import { useT } from "@/lib/i18n";
import { WORK_ORDER_STATUS_FLOW, WORK_ORDER_STATUS_COLORS } from "@/lib/operatorStyles";
import type { WorkOrderStatus } from "@/types";
import { cn } from "@/lib/utils";

/**
 * Renders every possible WorkOrderStatus so the full lifecycle is always
 * visible, with the work order's current status highlighted. Makes the
 * status flow legible in the UI without needing a separate diagram.
 */
export function StatusFlowStrip({ current }: { current: WorkOrderStatus }) {
  const t = useT();

  return (
    <div className="flex flex-wrap gap-1.5">
      {WORK_ORDER_STATUS_FLOW.map((status) => (
        <span
          key={status}
          className={cn(
            "text-[10px] px-1.5 py-0.5 rounded font-mono transition-opacity",
            WORK_ORDER_STATUS_COLORS[status],
            status === current ? "opacity-100 ring-1 ring-slate-400/40" : "opacity-40"
          )}
        >
          {t(`operator.status.${status}`)}
        </span>
      ))}
    </div>
  );
}
