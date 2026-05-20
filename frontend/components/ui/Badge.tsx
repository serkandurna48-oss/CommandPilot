import { cn } from "@/lib/utils";
import { LIFE_AREA_COLORS } from "@/types";

interface BadgeProps {
  label: string;
  lifeArea?: string;
  className?: string;
}

export function Badge({ label, lifeArea, className }: BadgeProps) {
  const color = lifeArea ? LIFE_AREA_COLORS[lifeArea.toLowerCase()] : undefined;

  return (
    <span
      className={cn("inline-flex items-center px-2 py-0.5 rounded text-xs font-medium", className)}
      style={
        color
          ? { backgroundColor: `${color}25`, color, borderColor: `${color}40`, border: "1px solid" }
          : { backgroundColor: "#334155", color: "#94a3b8" }
      }
    >
      {label}
    </span>
  );
}

interface RatingDotProps {
  value: number;
  max?: number;
}

export function RatingDots({ value, max = 10 }: RatingDotProps) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: max }).map((_, i) => (
        <div
          key={i}
          className={cn(
            "h-1.5 w-1.5 rounded-full",
            i < value ? "bg-brand-500" : "bg-slate-600"
          )}
        />
      ))}
    </div>
  );
}
