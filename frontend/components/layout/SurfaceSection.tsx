import { cn } from "@/lib/utils";

interface SurfaceSectionProps {
  title: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

// One shared "labeled block inside a divided surface" — the pattern Home's
// Panel and Settings' Section each implemented locally. New adoptions (like
// WorkOrderDetail) use this directly; Home/Settings keep their local copies
// for now (visually identical, functionally unchanged) rather than risking
// a touch to two already-locked routes in the same pass that introduces
// this component.
export function SurfaceSection({ title, action, className, children }: SurfaceSectionProps) {
  return (
    <div className={cn("px-5 py-4", className)}>
      <div className="flex items-center justify-between gap-3 mb-3">
        <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider">{title}</h2>
        {action}
      </div>
      {children}
    </div>
  );
}
