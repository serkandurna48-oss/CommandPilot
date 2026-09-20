import { cn } from "@/lib/utils";
import { InputHTMLAttributes, TextareaHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const inputBase =
  "w-full rounded-lg bg-[var(--bg-surface)] border border-[var(--border-default)] text-[var(--text-primary)] placeholder-[var(--text-placeholder)] px-3 py-2.5 text-base min-h-11 motion-safe:transition-colors focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-[2.5px] focus-visible:outline-[var(--interactive-border-focus)] disabled:opacity-50";

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, ...props }, ref) => (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide">{label}</label>}
      <input ref={ref} className={cn(inputBase, error && "border-status-danger", className)} {...props} />
      {error && <p className="text-xs text-status-danger">{error}</p>}
    </div>
  )
);
Input.displayName = "Input";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, label, error, ...props }, ref) => (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide">{label}</label>}
      <textarea ref={ref} className={cn(inputBase, "resize-none", error && "border-status-danger", className)} {...props} />
      {error && <p className="text-xs text-status-danger">{error}</p>}
    </div>
  )
);
Textarea.displayName = "Textarea";

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, children, ...props }, ref) => (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wide">{label}</label>}
      <select ref={ref} className={cn(inputBase, "cursor-pointer", error && "border-status-danger", className)} {...props}>
        {children}
      </select>
      {error && <p className="text-xs text-status-danger">{error}</p>}
    </div>
  )
);
Select.displayName = "Select";
