"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/Spinner";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { JarvisSourceRef } from "@/types";
import { Send, ChevronDown } from "lucide-react";

type DemoState = "empty" | "short" | "long" | "loading" | "error";

interface PreviewMessage {
  role: "user" | "assistant";
  content: React.ReactNode;
  hitSources?: JarvisSourceRef[];
  baseSources?: JarvisSourceRef[];
}

const FOCUS_RING =
  "focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-[2.5px] focus-visible:outline-[var(--interactive-border-focus)]";

const BASE_SOURCES: JarvisSourceRef[] = [
  { source_file: "00-Index.md", source_heading: "" },
  { source_file: "Projekte/CommandPilot.md", source_heading: "" },
  { source_file: "Projekte/CampPilot.md", source_heading: "" },
  { source_file: "Regeln/Fokuszeiten.md", source_heading: "" },
];

const SHORT_THREAD: PreviewMessage[] = [
  { role: "user", content: "Was war mein letzter Stand zum Q3-Report?" },
  {
    role: "assistant",
    content: (
      <>
        <p>Laut deinen Notizen hast du den Entwurf am 12. September abgeschlossen — offen ist noch die Abstimmung mit Finance.</p>
        <ul className="list-disc pl-5 mt-2 space-y-1">
          <li>Entwurf fertig, wartet auf Review</li>
          <li>Rückmeldung von Finance noch offen</li>
        </ul>
      </>
    ),
    hitSources: [
      { source_file: "Projekte/Q3-Report.md", source_heading: "Status" },
      { source_file: "Projekte/Q3-Report.md", source_heading: "Nächste Schritte" },
    ],
    baseSources: BASE_SOURCES,
  },
];

const LONG_THREAD: PreviewMessage[] = [
  ...SHORT_THREAD,
  { role: "user", content: "Und wie sieht's beim CampPilot-Onboarding aus?" },
  {
    role: "assistant",
    content: (
      <>
        <p>
          Beim CampPilot-Onboarding sind laut deinen Notizen drei von fünf Schritten abgeschlossen. Der offene Teil betrifft
          die Zahlungsanbindung — dort wartest du seit dem 3. September auf eine Rückmeldung vom Anbieter.
        </p>
        <p className="mt-2">Zusammengefasst:</p>
        <ul className="list-disc pl-5 mt-2 space-y-1">
          <li><strong>Erledigt:</strong> Grundstruktur, Rollenmodell, erste Testkonten</li>
          <li><strong>Offen:</strong> Zahlungsanbindung, Abschlussreview mit dem Team</li>
          <li><strong>Risiko:</strong> Der Anbieter hat auf zwei Nachfragen nicht reagiert — falls das bis Ende der Woche so bleibt, notierst du, dass ein Alternativanbieter geprüft werden soll.</li>
        </ul>
        <p className="mt-2">Dazu findet sich in deinem Second Brain nichts zu einem konkreten Zieldatum — falls du eins gesetzt hast, steht es nicht im Vault.</p>
      </>
    ),
    hitSources: [
      { source_file: "Projekte/CampPilot.md", source_heading: "Onboarding" },
      { source_file: "Projekte/CampPilot.md", source_heading: "Zahlungsanbindung" },
      { source_file: "Regeln/Risikoeinschätzung.md", source_heading: "" },
    ],
    baseSources: BASE_SOURCES,
  },
  { role: "user", content: "Danke. Notier mal kurz, worauf ich beim Fokusblock morgen achten soll." },
  {
    role: "assistant",
    content: (
      <p>
        Deine Regel dazu: keine Tiefarbeit direkt nach intensivem Sport, und Fokusblöcke bevorzugt vor 11 Uhr, wenn deine
        Energie laut den letzten Check-ins am höchsten ist.
      </p>
    ),
    hitSources: [{ source_file: "Regeln/Fokuszeiten.md", source_heading: "Zeitfenster" }],
    baseSources: BASE_SOURCES,
  },
];

function SourceList({
  title,
  sources,
  onSelect,
  tone,
}: {
  title: string;
  sources: JarvisSourceRef[];
  onSelect: (s: JarvisSourceRef) => void;
  tone: "hit" | "base";
}) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-[var(--text-tertiary)] mb-1">{title}</p>
      <ul className="space-y-1">
        {sources.map((s, i) => (
          <li key={i}>
            <button
              type="button"
              onClick={() => onSelect(s)}
              className={cn(
                "w-full text-left text-xs font-mono px-2 py-1 rounded-md motion-safe:transition-colors truncate",
                FOCUS_RING,
                tone === "hit"
                  ? "text-brand-300 bg-brand-600/10 hover:bg-brand-600/20"
                  : "text-[var(--text-tertiary)] hover:bg-[var(--interactive-bg-tertiary-hover)]"
              )}
              title={`${s.source_file}${s.source_heading ? " — " + s.source_heading : ""}`}
            >
              {s.source_file}
              {s.source_heading ? ` — ${s.source_heading}` : ""}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function PreviewJarvisPanel({
  onSelectSource,
}: {
  onSelectSource: (source: JarvisSourceRef) => void;
}) {
  const t = useT();
  const [demoState, setDemoState] = useState<DemoState>("short");
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const isFirstRender = useRef(true);

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    bottomRef.current?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
  }, [demoState]);

  const messages = demoState === "long" ? LONG_THREAD : demoState === "short" ? SHORT_THREAD : [];

  function handleSend() {
    if (!input.trim() || demoState === "loading") return;
    setDemoState("loading");
    setTimeout(() => setDemoState("short"), 900);
    setInput("");
  }

  const stateOptions: { key: DemoState; label: string }[] = [
    { key: "empty", label: t("design_preview.state.empty") },
    { key: "short", label: t("design_preview.state.short") },
    { key: "long", label: t("design_preview.state.long") },
    { key: "loading", label: t("design_preview.state.loading") },
    { key: "error", label: t("design_preview.state.error") },
  ];

  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-1.5 mb-3 overflow-x-auto pb-1">
        <span className="text-[11px] uppercase tracking-wide text-[var(--text-tertiary)] shrink-0 mr-1">
          {t("design_preview.state_label")}
        </span>
        {stateOptions.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            onClick={() => setDemoState(key)}
            className={cn(
              "shrink-0 rounded-md px-2.5 py-1 text-xs font-medium motion-safe:transition-colors",
              FOCUS_RING,
              demoState === key
                ? "bg-brand-500 text-white"
                : "bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex flex-col h-[60vh] min-h-[420px]">
        <div className="flex-1 min-h-0 overflow-y-auto space-y-4 pb-4">
          {demoState === "empty" && <EmptyState title={t("jarvis.empty_state")} />}

          {(demoState === "short" || demoState === "long") &&
            messages.map((msg, i) => (
              <div key={i} className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
                <div className={cn("max-w-[85%] md:max-w-[70%]", msg.role === "user" ? "" : "w-full")}>
                  <Card
                    variant={msg.role === "user" ? "elevated" : "default"}
                    className={cn(msg.role === "user" ? "bg-brand-500/15 border-brand-500/30" : undefined)}
                  >
                    {/* Fließtext-Rolle: 16px, nicht der 14px UI-Standard (docs/referenzen/) */}
                    <CardContent className="py-3 text-base leading-[26px] text-[var(--text-primary)]">
                      {msg.content}
                    </CardContent>
                  </Card>

                  {msg.role === "assistant" && msg.hitSources && msg.hitSources.length > 0 && (
                    <div className="mt-1.5 px-1 space-y-2">
                      <SourceList
                        title={t("design_preview.sources_hit")}
                        sources={msg.hitSources}
                        onSelect={onSelectSource}
                        tone="hit"
                      />
                      {msg.baseSources && msg.baseSources.length > 0 && (
                        <details className="group">
                          <summary
                            className={cn(
                              "flex items-center gap-1 text-[11px] uppercase tracking-wide text-[var(--text-tertiary)] cursor-pointer select-none rounded",
                              FOCUS_RING
                            )}
                          >
                            <ChevronDown className="h-3 w-3 motion-safe:transition-transform group-open:rotate-180" />
                            {t("design_preview.sources_base")} ({msg.baseSources.length})
                          </summary>
                          <p className="text-[11px] text-[var(--text-tertiary)] mt-1 mb-1">{t("design_preview.sources_base_hint")}</p>
                          <SourceList title="" sources={msg.baseSources} onSelect={onSelectSource} tone="base" />
                        </details>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}

          {demoState === "loading" && (
            <div className="flex justify-start">
              <Card>
                <CardContent className="py-3 flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                  <div className="h-4 w-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
                  {t("jarvis.thinking")}
                </CardContent>
              </Card>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {demoState === "error" && (
          <div className="mb-3 rounded-lg bg-status-danger/10 border border-status-danger/30 px-4 py-3 text-status-danger text-sm flex items-center justify-between gap-3">
            <p>
              <span className="font-medium">{t("jarvis.error_banner")}</span> Second Brain nicht erreichbar (503).
            </p>
            <Button type="button" variant="secondary" size="sm" onClick={() => setDemoState("short")}>
              {t("jarvis.retry")}
            </Button>
          </div>
        )}

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-end gap-2"
        >
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder={t("jarvis.placeholder")}
            rows={2}
            className="flex-1 resize-none"
            disabled={demoState === "loading"}
          />
          <Button type="submit" disabled={demoState === "loading" || !input.trim()} loading={demoState === "loading"}>
            <Send className="h-4 w-4" />
            {t("jarvis.send")}
          </Button>
        </form>
      </div>
    </div>
  );
}
