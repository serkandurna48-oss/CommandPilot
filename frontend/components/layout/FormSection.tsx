interface FormSectionProps {
  title: string;
  description?: string;
  children: React.ReactNode;
}

// The form-oriented sibling of SurfaceSection/Settings' Section — same
// contract (title + optional description + content, sharing one outer
// divided surface with the sections around it), used for the previously
// stacked-independent-Card forms (Morning, Evening Review, New Work Order).
// Section labels keep the small-caps treatment; field labels do not — see
// components/ui/Input.tsx, which no longer force-uppercases them.
export function FormSection({ title, description, children }: FormSectionProps) {
  return (
    <div className="px-6 py-6">
      <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider">{title}</h2>
      {description && <p className="text-[var(--text-tertiary)] text-xs mt-0.5">{description}</p>}
      <div className="mt-4 space-y-4">{children}</div>
    </div>
  );
}
