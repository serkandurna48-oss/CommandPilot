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
        variant === "default"   && "bg-slate-800/60 border border-slate-700/50",
        variant === "elevated"  && "bg-slate-800 border border-slate-700 shadow-lg",
        variant === "bordered"  && "bg-transparent border border-slate-600",
        className
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 py-4 border-b border-slate-700/50", className)} {...props} />;
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 py-4", className)} {...props} />;
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-sm font-semibold text-slate-200 uppercase tracking-wider", className)} {...props} />;
}
