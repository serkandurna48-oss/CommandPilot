import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const LANGUAGE_KEY = "commandpilot_language";

export function getUserLanguage(): "de" | "en" {
  if (typeof window === "undefined") return "en";
  const stored = localStorage.getItem(LANGUAGE_KEY);
  return stored === "de" || stored === "en" ? stored : "en";
}

export function setUserLanguage(lang: "de" | "en") {
  localStorage.setItem(LANGUAGE_KEY, lang);
}

export function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const locale = getUserLanguage() === "de" ? "de-DE" : "en-US";
  return date.toLocaleDateString(locale, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function formatDateShort(dateStr: string): string {
  const date = new Date(dateStr);
  const locale = getUserLanguage() === "de" ? "de-DE" : "en-US";
  return date.toLocaleDateString(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

// Whole days between dateStr and now, floored — used by ProjectCards.tsx's
// "Stand: vor X Tagen" and its stale-after-3-days marker. Floor (not round)
// so "updated 20 hours ago" reads as 0 (today), not 1.
export function daysSince(dateStr: string): number {
  const then = new Date(dateStr).getTime();
  const now = Date.now();
  return Math.max(0, Math.floor((now - then) / (1000 * 60 * 60 * 24)));
}

export function today(): string {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

export const BLOCK_TYPE_LABELS: Record<string, string> = {
  deep_work: "Deep Work",
  admin: "Admin",
  sport: "Sport",
  break: "Break",
  social: "Social",
  learning: "Learning",
  personal: "Personal",
  other: "Other",
};

// Category colors, not status colors — deep_work is the one brand-tinted
// entry, sport/social/learning/personal keep their own deliberate hues
// (a Google-Calendar-style category palette, not the status family). Neutral
// entries (admin/break/other, no strong category identity) use Focus Deck
// tokens instead of raw slate (23.09.2026 — same debt as operatorStyles.ts).
export const BLOCK_TYPE_COLORS: Record<string, string> = {
  deep_work: "bg-brand-600 text-white",
  admin: "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-secondary)]",
  sport: "bg-amber-500 text-slate-900",
  break: "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-tertiary)]",
  social: "bg-pink-600 text-white",
  learning: "bg-violet-600 text-white",
  personal: "bg-indigo-500 text-white",
  other: "bg-[var(--bg-elevated)] border border-[var(--border-default)] text-[var(--text-secondary)]",
};
