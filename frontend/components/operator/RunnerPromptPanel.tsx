"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { useT } from "@/lib/i18n";
import { generateRunnerPrompt } from "@/lib/generateRunnerPrompt";
import type { WorkOrder, ApprovalScope, WorkOrderStep } from "@/types";
import { Terminal, Copy, Check } from "lucide-react";

// Renders its own header row (title + Generate action) rather than going
// through SurfaceSection — the action button owns state that lives inside
// this component (the generated prompt), so it can't be lifted into a
// caller-supplied `action` slot. Header markup intentionally mirrors
// SurfaceSection's exactly, so this still reads as one section in the
// same divided surface as its siblings in WorkOrderDetail.
export function RunnerPromptPanel({ order, scope, steps }: { order: WorkOrder; scope: ApprovalScope; steps: WorkOrderStep[] }) {
  const t = useT();
  const [prompt, setPrompt] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  function handleGenerate() {
    setPrompt(generateRunnerPrompt(order, scope, steps));
    setCopied(false);
  }

  async function handleCopy() {
    if (!prompt) return;
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API unavailable (e.g. insecure context) — the textarea
      // below still lets the user select-all/copy manually.
    }
  }

  return (
    <div className="px-5 py-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-[var(--text-secondary)] uppercase tracking-wider">{t("operator.prompt.title")}</h2>
        <Button size="sm" variant="secondary" onClick={handleGenerate}>
          <Terminal className="h-4 w-4" />
          {t("operator.prompt.generate")}
        </Button>
      </div>
      {prompt && (
        <div className="space-y-2 mt-3">
          <p className="text-[var(--text-tertiary)] text-xs">{t("operator.prompt.hint")}</p>
          <textarea
            readOnly
            value={prompt}
            rows={14}
            className="w-full rounded-lg bg-[var(--bg-app)] border border-[var(--border-default)] text-[var(--text-secondary)] text-xs font-mono p-3 resize-y"
            onFocus={(e) => e.currentTarget.select()}
          />
          <Button size="sm" variant="secondary" onClick={handleCopy}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? t("operator.prompt.copied") : t("operator.prompt.copy")}
          </Button>
        </div>
      )}
    </div>
  );
}
