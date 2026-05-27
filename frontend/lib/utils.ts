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

export const BLOCK_TYPE_COLORS: Record<string, string> = {
  deep_work: "bg-brand-600 text-white",
  admin: "bg-slate-600 text-slate-100",
  sport: "bg-amber-500 text-slate-900",
  break: "bg-slate-700 text-slate-300",
  social: "bg-pink-600 text-white",
  learning: "bg-violet-600 text-white",
  personal: "bg-indigo-500 text-white",
  other: "bg-slate-600 text-slate-100",
};
