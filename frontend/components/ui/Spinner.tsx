import { cn } from "@/lib/utils";

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("animate-spin h-5 w-5 text-brand-500", className)}
      fill="none"
      viewBox="0 0 24 24"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

export function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <Spinner className="h-8 w-8" />
    </div>
  );
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="h-12 w-12 rounded-full bg-slate-800 flex items-center justify-center mb-4">
        <span className="text-2xl">—</span>
      </div>
      <p className="text-slate-300 font-medium">{title}</p>
      {description && <p className="text-slate-500 text-sm mt-1 max-w-xs">{description}</p>}
    </div>
  );
}
