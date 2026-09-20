"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/Spinner";
import { ApiError, api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { RISK_COLORS } from "@/lib/operatorStyles";
import type {
  JarvisChatMessage,
  JarvisSourceRef,
  JarvisSuggestedAction,
  JarvisSuggestedActionDecisionRequest,
} from "@/types";
import { Send, Check, X } from "lucide-react";

// One suggested_action as shown in the UI, tagged with a stable client-side
// idempotency token (JARVIS-C1, Phase 6) generated once when the proposal
// arrives — never by the backend, since a proposal is never persisted at
// chat time. The SAME token is reused for retries of the same card's
// confirm/reject click, which is what actually makes a double-click safe
// (see supabase/migrations/013_suggested_action_decisions.sql).
interface DisplaySuggestedAction extends JarvisSuggestedAction {
  requestId: string;
}

interface DisplayMessage extends JarvisChatMessage {
  sources?: JarvisSourceRef[];
  suggestedActions?: DisplaySuggestedAction[];
}

type DecisionStatus = "idle" | "confirming" | "rejecting" | "confirmed" | "rejected";

interface DecisionState {
  status: DecisionStatus;
  workOrderId?: string;
  error?: string;
}

function SuggestedActionCard({
  action,
  decision,
  onConfirm,
  onReject,
}: {
  action: DisplaySuggestedAction;
  decision?: DecisionState;
  onConfirm: () => void;
  onReject: () => void;
}) {
  const t = useT();
  const status = decision?.status ?? "idle";
  const busy = status === "confirming" || status === "rejecting";
  const decided = status === "confirmed" || status === "rejected";

  return (
    <Card variant="bordered" className="mt-2">
      <CardContent className="py-3 space-y-2">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium text-[var(--text-primary)]">{action.title}</p>
          <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-mono shrink-0", RISK_COLORS[action.risk])}>
            {t(`jarvis.suggested_action.risk.${action.risk}`)}
          </span>
        </div>

        <p className="text-xs text-[var(--text-secondary)]">{action.description}</p>

        <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-[var(--text-tertiary)]">
          <span>{t("jarvis.suggested_action.team_type")}: {action.team_type}</span>
          {action.target_repo_name && (
            <span>{t("jarvis.suggested_action.target_repo")}: {action.target_repo_name}</span>
          )}
        </div>

        <p className="text-[11px] text-[var(--text-tertiary)]">
          {action.requires_approval
            ? t("jarvis.suggested_action.requires_approval_yes")
            : t("jarvis.suggested_action.requires_approval_no")}
        </p>

        {action.sources.length > 0 && (
          <div>
            <p className="text-[10px] uppercase tracking-wide text-slate-500 mb-0.5">{t("jarvis.sources")}</p>
            <ul className="space-y-0.5">
              {action.sources.map((s, si) => (
                <li key={si} className="text-[11px] text-slate-500 font-mono">
                  {s.source_file}
                  {s.source_heading ? ` — ${s.source_heading}` : ""}
                </li>
              ))}
            </ul>
          </div>
        )}

        {decided ? (
          <div
            className={cn(
              "flex items-center gap-1.5 pt-1 text-xs",
              status === "confirmed" ? "text-green-400/80" : "text-slate-500"
            )}
          >
            {status === "confirmed" ? <Check className="h-3.5 w-3.5" /> : <X className="h-3.5 w-3.5" />}
            {status === "confirmed" ? t("jarvis.suggested_action.confirmed") : t("jarvis.suggested_action.rejected")}
            {status === "confirmed" && decision?.workOrderId && (
              <Link href={`/operator/${decision.workOrderId}`} className="underline hover:no-underline">
                {t("jarvis.suggested_action.view_work_order")}
              </Link>
            )}
          </div>
        ) : (
          <>
            <div className="flex gap-2 pt-1">
              <Button size="sm" variant="primary" disabled={busy} loading={status === "confirming"} onClick={onConfirm}>
                <Check className="h-3.5 w-3.5" />
                {t("jarvis.suggested_action.confirm")}
              </Button>
              <Button size="sm" variant="secondary" disabled={busy} loading={status === "rejecting"} onClick={onReject}>
                <X className="h-3.5 w-3.5" />
                {t("jarvis.suggested_action.reject")}
              </Button>
            </div>
            {decision?.error && (
              <p className="text-[11px] text-rose-400/80">
                {t("jarvis.suggested_action.error_retry")} {decision.error}
              </p>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

export function JarvisChat() {
  const t = useT();
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<string, DecisionState>>({});
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function send(text: string) {
    const question = text.trim();
    if (!question || loading) return;

    setError(null);
    setInput("");

    // History sent to the backend is the conversation as it stood before this
    // question — the backend appends the current message separately.
    const historyForRequest: JarvisChatMessage[] = messages.map(({ role, content }) => ({ role, content }));

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);

    try {
      const res = await api.jarvis.chat({ message: question, history: historyForRequest });
      const suggestedActions: DisplaySuggestedAction[] = res.suggested_actions.map((a) => ({
        ...a,
        requestId: crypto.randomUUID(),
      }));
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.reply, sources: res.sources, suggestedActions },
      ]);
    } catch (err: unknown) {
      // Never fall back to mock/placeholder content on failure — a visible
      // error is required so a real outage is never mistaken for silence.
      const message = err instanceof ApiError ? err.message : err instanceof Error ? err.message : t("common.error");
      setError(message);
      // Roll back the optimistic user message so retry doesn't duplicate it.
      setMessages((prev) => prev.slice(0, -1));
      setInput(question);
    } finally {
      setLoading(false);
    }
  }

  async function decideSuggestedAction(action: DisplaySuggestedAction, decision: "confirm" | "reject") {
    setDecisions((prev) => ({
      ...prev,
      [action.requestId]: { status: decision === "confirm" ? "confirming" : "rejecting" },
    }));

    const payload: JarvisSuggestedActionDecisionRequest = {
      action: {
        title: action.title,
        description: action.description,
        team_type: action.team_type,
        target_repo_name: action.target_repo_name,
        risk: action.risk,
        requires_approval: action.requires_approval,
        sources: action.sources,
      },
      request_id: action.requestId,
    };

    try {
      const res =
        decision === "confirm"
          ? await api.jarvis.confirmSuggestedAction(payload)
          : await api.jarvis.rejectSuggestedAction(payload);
      setDecisions((prev) => ({
        ...prev,
        [action.requestId]: {
          status: res.decision === "confirmed" ? "confirmed" : "rejected",
          workOrderId: res.work_order_id ?? undefined,
        },
      }));
    } catch (err: unknown) {
      // Same rule as the chat error path: a visible, retryable error, never
      // a silent no-op that could be mistaken for "nothing happened yet."
      const message = err instanceof ApiError ? err.message : err instanceof Error ? err.message : t("common.error");
      setDecisions((prev) => ({ ...prev, [action.requestId]: { status: "idle", error: message } }));
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    send(input);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-14rem)] md:h-[calc(100vh-12rem)]">
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.length === 0 && !loading && (
          <EmptyState title={t("jarvis.empty_state")} />
        )}

        {messages.map((msg, i) => (
          <div key={i} className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
            <div className={cn("max-w-[85%] md:max-w-[70%]", msg.role === "user" ? "" : "w-full")}>
              <Card
                variant={msg.role === "user" ? "elevated" : "default"}
                className={cn(msg.role === "user" ? "bg-brand-600/15 border-brand-600/30" : undefined)}
              >
                <CardContent className="py-3 text-sm text-slate-100 whitespace-pre-wrap">
                  {msg.content}
                </CardContent>
              </Card>
              {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                <div className="mt-1.5 px-1">
                  <p className="text-[11px] uppercase tracking-wide text-slate-500 mb-1">
                    {t("jarvis.sources")}
                  </p>
                  <ul className="space-y-0.5">
                    {msg.sources.map((s, si) => (
                      <li key={si} className="text-xs text-slate-400 font-mono">
                        {s.source_file}
                        {s.source_heading ? ` — ${s.source_heading}` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {msg.role === "assistant" && msg.suggestedActions && msg.suggestedActions.length > 0 && (
                <div className="space-y-2">
                  {msg.suggestedActions.map((action) => (
                    <SuggestedActionCard
                      key={action.requestId}
                      action={action}
                      decision={decisions[action.requestId]}
                      onConfirm={() => decideSuggestedAction(action, "confirm")}
                      onReject={() => decideSuggestedAction(action, "reject")}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <Card>
              <CardContent className="py-3 flex items-center gap-2 text-sm text-slate-400">
                <div className="h-4 w-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin" />
                {t("jarvis.thinking")}
              </CardContent>
            </Card>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {error && (
        <div className="mb-3 rounded-lg bg-red-950 border border-red-800 px-4 py-3 text-red-300 text-sm flex items-center justify-between gap-3">
          <p>
            <span className="font-medium">{t("jarvis.error_banner")}</span> {error}
          </p>
          <Button type="button" variant="secondary" size="sm" onClick={() => send(input)}>
            {t("jarvis.retry")}
          </Button>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex items-end gap-2">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("jarvis.placeholder")}
          rows={2}
          className="flex-1 resize-none"
          disabled={loading}
        />
        <Button type="submit" disabled={loading || !input.trim()} loading={loading}>
          <Send className="h-4 w-4" />
          {t("jarvis.send")}
        </Button>
      </form>
    </div>
  );
}
