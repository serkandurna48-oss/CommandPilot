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
      <p className="text-xs text-slate-500 uppercase tracking-widest mb-1">
        {dateLabel}
      </p>
      <h1 className="text-2xl font-semibold text-slate-100">{title}</h1>
      {subtitle && <p className="text-slate-400 text-sm mt-1">{subtitle}</p>}
    </div>
  );
}
