"use client";

import { formatDate } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
}

// The one shared page header for the Focus Deck system — promoted from the
// pattern Home/Settings each implemented locally (serif headline + accent
// underline + mono date, date hidden on mobile so it doesn't compete with
// the headline). Replaces the legacy Header.tsx (ALL-CAPS eyebrow date +
// sans title + raw slate-* colors), which predates the Focus Deck tokens.
export function PageHeader({ title, subtitle }: PageHeaderProps) {
  return (
    <div className="mb-8">
      <div className="flex items-start justify-between gap-4">
        <h1 className="relative inline-block font-serif text-[32px] md:text-[40px] leading-[1.15] font-semibold text-[var(--text-primary)] pb-2.5">
          {title}
          <span className="absolute left-0 bottom-0 h-[2px] w-10 bg-[var(--interactive-bg-primary-default)]" />
        </h1>
        <p className="hidden md:block text-xs font-mono text-[var(--text-tertiary)] whitespace-nowrap mt-2">
          {formatDate(new Date().toISOString())}
        </p>
      </div>
      {subtitle && <p className="text-[var(--text-secondary)] text-sm mt-3">{subtitle}</p>}
    </div>
  );
}
