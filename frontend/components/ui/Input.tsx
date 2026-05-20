import { cn } from "@/lib/utils";
import { InputHTMLAttributes, TextareaHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

const inputBase =
  "w-full rounded-lg bg-slate-800 border border-slate-600 text-slate-100 placeholder-slate-500 px-3 py-2 text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent disabled:opacity-50";

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, ...props }, ref) => (
    <div className="flex flex-col gap-1.5">
      {label && <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">{label}</label>}
      <input ref={ref} className={cn(inputBase, error && "border-red-500", className)} {...props} />
      {error && <p className="text-xs text-red-400">{error}</p>}
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
      {label && <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">{label}</label>}
      <textarea ref={ref} className={cn(inputBase, "resize-none", error && "border-red-500", className)} {...props} />
      {error && <p className="text-xs text-red-400">{error}</p>}
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
      {label && <label className="text-xs font-medium text-slate-400 uppercase tracking-wide">{label}</label>}
      <select ref={ref} className={cn(inputBase, "cursor-pointer", error && "border-red-500", className)} {...props}>
        {children}
      </select>
      {error && <p className="text-xs text-red-400">{error}</p>}
    </div>
  )
);
Select.displayName = "Select";
