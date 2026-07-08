"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { useT } from "@/lib/i18n";
import { generateRunnerPrompt } from "@/lib/generateRunnerPrompt";
import type { WorkOrder, ApprovalScope, WorkOrderStep } from "@/types";
import { Terminal, Copy, Check } from "lucide-react";

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
    <Card variant="bordered">
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle>{t("operator.prompt.title")}</CardTitle>
        <Button size="sm" variant="secondary" onClick={handleGenerate}>
          <Terminal className="h-4 w-4" />
          {t("operator.prompt.generate")}
        </Button>
      </CardHeader>
      {prompt && (
        <CardContent className="space-y-2">
          <p className="text-slate-500 text-xs">{t("operator.prompt.hint")}</p>
          <textarea
            readOnly
            value={prompt}
            rows={14}
            className="w-full rounded-lg bg-slate-950 border border-slate-700 text-slate-300 text-xs font-mono p-3 resize-y"
            onFocus={(e) => e.currentTarget.select()}
          />
          <Button size="sm" variant="secondary" onClick={handleCopy}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? t("operator.prompt.copied") : t("operator.prompt.copy")}
          </Button>
        </CardContent>
      )}
    </Card>
  );
}
