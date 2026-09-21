"use client";

import type { JarvisSnapshotField } from "@/lib/jarvisContext";

// Compact "what matters about this right now" block, shown before
// conversation starts. Every field here is real record data the calling
// page already has (see ProjectsManager.tsx, dashboard/page.tsx) — this
// component never invents a label/value pair, and simply renders nothing
// when there's nothing real to show.
export function JarvisContextSnapshot({ fields }: { fields: JarvisSnapshotField[] }) {
  if (fields.length === 0) return null;

  return (
    <dl className="space-y-4">
      {fields.map((f) => (
        <div key={f.label}>
          <dt className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-1">
            {f.label}
          </dt>
          <dd className="text-sm text-[var(--text-secondary)] leading-relaxed">{f.value}</dd>
        </div>
      ))}
    </dl>
  );
}
