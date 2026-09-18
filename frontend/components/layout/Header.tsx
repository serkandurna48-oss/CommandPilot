"use client";

import { useState, useEffect } from "react";
import { formatDate, today } from "@/lib/utils";

interface HeaderProps {
  title: string;
  subtitle?: string;
}

export function Header({ title, subtitle }: HeaderProps) {
  const [dateLabel, setDateLabel] = useState("");

  useEffect(() => {
    setDateLabel(formatDate(today()));
  }, []);

  return (
    <div className="mb-8">
      <p className="text-xs text-[var(--text-tertiary)] uppercase tracking-widest mb-1">
        {dateLabel}
      </p>
      {/* Seitentitel 28px — Hierarchie über Gewicht/Farbe, nicht Schriftgröße
          (JARVIS-D1, docs/referenzen/chatgpt-design-reference.md) */}
      <h1 className="text-[28px] leading-[34px] font-semibold text-[var(--text-primary)]">{title}</h1>
      {subtitle && <p className="text-[var(--text-secondary)] text-sm mt-1">{subtitle}</p>}
    </div>
  );
}
