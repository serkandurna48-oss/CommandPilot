"use client";

import { ExternalLink, Globe } from "lucide-react";
import { useT } from "@/lib/i18n";
import type { Project } from "@/types";

// Product Websites — a card grid of real, user-attached links
// (Project.website_url, supabase/migrations/014_projects_website_url.sql).
// Only a project with a real URL ever renders a card here; nothing
// fabricated, nothing inferred from repo names or descriptions. Renders
// nothing at all when no project has a website_url set — same "absent, not
// fake" rule as every other empty state in this codebase.
export function ProductWebsites({ projects }: { projects: Project[] }) {
  const t = useT();
  const withWebsite = projects.filter((p) => !!p.website_url && p.status !== "archived");

  if (withWebsite.length === 0) return null;

  return (
    <div className="rounded-2xl border border-white/[0.06] bg-[var(--bg-surface)] shadow-[var(--shadow-card)] mb-4">
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-white/[0.06]">
        <h2 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wide">
          {t("dashboard.section.product_websites")}
        </h2>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 p-4">
        {withWebsite.map((p) => (
          <a
            key={p.id}
            href={p.website_url}
            target="_blank"
            rel="noopener noreferrer"
            className="group rounded-xl border border-[var(--border-light)] px-4 py-3.5 hover:border-[var(--interactive-bg-primary-default)] hover:bg-[var(--interactive-bg-secondary-hover)] motion-safe:transition-colors duration-150"
          >
            <div className="flex items-start justify-between gap-2">
              <span className="flex items-center justify-center h-8 w-8 rounded-full bg-[var(--interactive-bg-primary-default)]/15 text-[var(--text-accent)] shrink-0">
                <Globe className="h-4 w-4" />
              </span>
              <ExternalLink className="h-3.5 w-3.5 text-[var(--text-tertiary)] group-hover:text-[var(--text-accent)] motion-safe:transition-colors duration-150 shrink-0 mt-1" />
            </div>
            <p className="mt-3 text-sm font-medium text-[var(--text-primary)] truncate">{p.name}</p>
            <p className="text-[11px] text-[var(--text-tertiary)] truncate mt-0.5">
              {p.website_url!.replace(/^https?:\/\//, "")}
            </p>
          </a>
        ))}
      </div>
    </div>
  );
}
