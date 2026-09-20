import { cn } from "@/lib/utils";
import { HTMLAttributes } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "elevated" | "bordered";
}

export function Card({ className, variant = "default", ...props }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-xl",
        // Tiefe über Flächenhelligkeit + Rahmen, nicht über Schatten —
        // "elevated" nutzt einen 1px-Innenring statt box-shadow.
        variant === "default" && "bg-[var(--bg-surface)]/60 border border-[var(--border-light)]",
        variant === "elevated" && "bg-[var(--bg-surface)] shadow-[inset_0_0_0_1px_var(--border-heavy)]",
        variant === "bordered" && "bg-transparent border border-[var(--border-medium)]",
        className
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 py-4 border-b border-[var(--border-light)]", className)} {...props} />;
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 py-4", className)} {...props} />;
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider", className)}
      {...props}
    />
  );
}
