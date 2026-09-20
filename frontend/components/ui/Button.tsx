import { cn } from "@/lib/utils";
import { ButtonHTMLAttributes, forwardRef } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

const variants = {
  primary:
    "bg-[var(--interactive-bg-primary-default)] hover:bg-[var(--interactive-bg-primary-hover)] active:bg-[var(--interactive-bg-primary-press)] text-white border-transparent",
  secondary:
    "bg-[var(--bg-elevated)] hover:bg-[var(--interactive-bg-secondary-hover)] text-[var(--text-primary)] border-[var(--border-default)]",
  ghost:
    "bg-transparent hover:bg-[var(--interactive-bg-secondary-hover)] text-[var(--text-secondary)] border-transparent",
  danger: "bg-status-danger hover:brightness-110 active:brightness-90 text-white border-transparent",
};

const sizes = {
  sm: "min-h-11 px-3 py-2 text-sm",
  md: "min-h-11 px-4 py-2 text-sm",
  lg: "min-h-11 px-6 py-3 text-base",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", loading, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-lg border font-medium motion-safe:transition-colors focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-[2.5px] focus-visible:outline-[var(--interactive-border-focus)] disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]",
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      >
        {loading && (
          <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
