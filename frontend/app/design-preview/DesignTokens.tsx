"use client";

import { useT } from "@/lib/i18n";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { cn } from "@/lib/utils";

const ACCENT_SCALE: { step: string; hex: string }[] = [
  { step: "50", hex: "#eef3f8" },
  { step: "100", hex: "#dce7f0" },
  { step: "200", hex: "#b9cee0" },
  { step: "300", hex: "#93b1cb" },
  { step: "400", hex: "#6f96b4" },
  { step: "500", hex: "#4f7a9c" },
  { step: "600", hex: "#3f6483" },
  { step: "700", hex: "#33506a" },
  { step: "800", hex: "#293f52" },
  { step: "900", hex: "#212f3b" },
];

const STATUS_SWATCHES: { key: string; label: string; className: string }[] = [
  { key: "success", label: "success", className: "bg-status-success" },
  { key: "warning", label: "warning", className: "bg-status-warning" },
  { key: "danger", label: "danger", className: "bg-status-danger" },
  { key: "neutral", label: "neutral", className: "bg-status-neutral" },
];

const TYPE_SCALE: { name: string; className: string; sample: string }[] = [
  { name: "display · 28/36 semibold", className: "text-[28px] leading-9 font-semibold", sample: "Tagesplan" },
  { name: "title · 20/28 semibold", className: "text-xl leading-7 font-semibold", sample: "Quellen" },
  { name: "body · 14/20 regular", className: "text-sm leading-5", sample: "Second-Brain-Kontext, der die Antwort trägt." },
  { name: "small · 13/18 regular", className: "text-[13px] leading-[18px]", sample: "00-Index.md — zuletzt aktualisiert" },
  { name: "micro · 11/16 uppercase", className: "text-[11px] leading-4 font-medium uppercase tracking-wide", sample: "Basiskontext" },
];

export function DesignTokens() {
  const t = useT();

  return (
    <Card variant="bordered" className="mb-8">
      <CardHeader>
        <CardTitle>{t("design_preview.tokens_title")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-8">
        {/* Accent contrast fix — before/after, side by side */}
        <div>
          <p className="text-xs text-slate-500 mb-3">
            Kontrastkorrektur: Buttons, aktive Navigation und Fokusringe auf brand-400/500 statt brand-600 — brand-600 und dunkler bleiben Rändern, Flächen und Füllungen vorbehalten.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="rounded-lg border border-slate-700/50 p-3">
              <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-2">
                {t("design_preview.tokens_accent_before")}
              </p>
              <button
                type="button"
                disabled
                className="inline-flex items-center rounded-lg px-4 py-2 text-sm font-medium text-white"
                style={{ backgroundColor: "#3f6483" }}
              >
                Primäraktion
              </button>
              <p className="text-[11px] font-mono text-slate-500 mt-2">#3f6483 · ~3.2:1 gegen slate-950</p>
            </div>
            <div className="rounded-lg border border-brand-500/40 p-3">
              <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-2">
                {t("design_preview.tokens_accent_after")}
              </p>
              <button
                type="button"
                disabled
                className="inline-flex items-center rounded-lg px-4 py-2 text-sm font-medium text-white bg-brand-500"
              >
                Primäraktion
              </button>
              <p className="text-[11px] font-mono text-slate-500 mt-2">#4f7a9c · ~4.4:1 gegen slate-950</p>
            </div>
          </div>
        </div>

        {/* Full accent scale */}
        <div>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-2">brand-50 … 900</p>
          <div className="flex rounded-lg overflow-hidden border border-slate-700/50">
            {ACCENT_SCALE.map(({ step, hex }) => (
              <div key={step} className="flex-1 min-w-0">
                <div className="h-12" style={{ backgroundColor: hex }} />
                <p className="text-[10px] font-mono text-slate-500 text-center py-1 truncate">{step}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Status colors — deliberately separate from the accent */}
        <div>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-2">status — getrennt vom Akzent, feste Bedeutung</p>
          <div className="flex flex-wrap gap-3">
            {STATUS_SWATCHES.map(({ key, label, className }) => (
              <div key={key} className="flex items-center gap-2 rounded-lg border border-slate-700/50 px-3 py-2">
                <span className={cn("h-3 w-3 rounded-full shrink-0", className)} />
                <span className="text-xs font-mono text-slate-400">status-{label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Typography scale */}
        <div>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-2">Typografie</p>
          <div className="space-y-2">
            {TYPE_SCALE.map(({ name, className, sample }) => (
              <div key={name} className="flex items-baseline gap-4">
                <span className="text-[10px] font-mono text-slate-600 w-40 shrink-0">{name}</span>
                <span className={cn(className, "text-slate-200 truncate")}>{sample}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Mono font check — used for source citations */}
        <div>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-2">JetBrains Mono (Quellenangaben)</p>
          <p className="font-mono text-xs text-slate-400">00-Index.md — Second Brain · Projekte/CommandPilot.md — Status: aktiv</p>
        </div>

        {/* Radii convention */}
        <div>
          <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-2">Radien</p>
          <div className="flex gap-4 items-end">
            <div className="flex flex-col items-center gap-1">
              <div className="h-10 w-10 bg-slate-700 rounded-md" />
              <span className="text-[10px] font-mono text-slate-500">md · 6px · Chips</span>
            </div>
            <div className="flex flex-col items-center gap-1">
              <div className="h-10 w-10 bg-slate-700 rounded-lg" />
              <span className="text-[10px] font-mono text-slate-500">lg · 8px · Inputs</span>
            </div>
            <div className="flex flex-col items-center gap-1">
              <div className="h-10 w-10 bg-slate-700 rounded-xl" />
              <span className="text-[10px] font-mono text-slate-500">xl · 12px · Cards</span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
