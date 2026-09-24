"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { ApiError, api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { RISK_COLORS } from "@/lib/operatorStyles";
import { useJarvisContext } from "@/lib/jarvisContext";
import { deriveJarvisIntelligenceMode } from "@/lib/jarvisIntelligenceState";
import { JarvisContextSnapshot } from "@/components/jarvis/JarvisContextSnapshot";
import { JarvisQuickAction } from "@/components/jarvis/JarvisQuickAction";
import { JarvisDecisionHistory } from "@/components/jarvis/JarvisDecisionHistory";
import type {
  JarvisChatMessage,
  JarvisSourceRef,
  JarvisSuggestedAction,
  JarvisSuggestedActionDecisionRequest,
} from "@/types";
import { ArrowRight, Check, X, ChevronRight, FileText, FolderOpen, Sparkles, Calendar, ListChecks, ClipboardList, Briefcase } from "lucide-react";

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
  baseSources?: JarvisSourceRef[];
  calendarSources?: JarvisSourceRef[];
  taskSources?: JarvisSourceRef[];
  workOrderSources?: JarvisSourceRef[];
  projectSources?: JarvisSourceRef[];
  suggestedActions?: DisplaySuggestedAction[];
  // Set only when this reply came from a quick-intelligence action that
  // defines a resultLabel (e.g. "Risk analysis") — replaces the generic
  // "Jarvis" role label above the answer. Free-typed follow-ups have none,
  // and keep the plain role label; never fabricated per message.
  modeLabel?: string;
}

// Higgsfield reference (05-pages/02-jarvis-expanded-desktop.png): a real,
// bordered, collapsible "SOURCES USED" disclosure — not an inline plain-text
// list. base_sources is real data the backend already returns (CLAUDE.md's
// Jarvis contract: "separat verfügbar, aber nicht Default-sichtbar") — this
// surfaces it honestly, collapsed by default, never fabricated.
function SourcesDisclosure({
  title,
  icon: Icon,
  sources,
  defaultOpen,
}: {
  title: string;
  icon: typeof FileText;
  sources: JarvisSourceRef[];
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(!!defaultOpen);
  return (
    <div className="rounded-lg border border-[var(--border-light)] overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-[var(--interactive-bg-secondary-hover)] motion-safe:transition-colors"
      >
        <Icon className="h-3.5 w-3.5 text-[var(--text-tertiary)] shrink-0" />
        <span className="text-xs font-medium text-[var(--text-secondary)] flex-1">
          {title} ({sources.length})
        </span>
        <ChevronRight className={cn("h-3.5 w-3.5 text-[var(--text-tertiary)] motion-safe:transition-transform", open && "rotate-90")} />
      </button>
      {open && (
        <ol className="px-3 pb-3 space-y-1">
          {sources.map((s, si) => (
            <li key={si} className="text-[11px] font-mono text-[var(--text-tertiary)] flex gap-2">
              <span className="text-[var(--text-placeholder)]">{si + 1}.</span>
              <span>{s.source_file}{s.source_heading ? ` — ${s.source_heading}` : ""}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
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
            <p className="text-[10px] uppercase tracking-wide text-[var(--text-tertiary)] mb-0.5">{t("jarvis.sources")}</p>
            <ul className="space-y-0.5">
              {action.sources.map((s, si) => (
                <li key={si} className="text-[11px] text-[var(--text-tertiary)] font-mono">
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
              status === "confirmed" ? "text-status-success" : "text-[var(--text-tertiary)]"
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
              <p className="text-[11px] text-status-danger">
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
  const jarvisContext = useJarvisContext();
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<string, DecisionState>>({});
  // Set only while a quick-intelligence action's request is in flight — the
  // working-state label shown instead of the generic "Thinking..." (e.g.
  // "Analyzing risks…"). Cleared once the request settles either way.
  const [pendingLabel, setPendingLabel] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const lastMessage = messages[messages.length - 1];
  const mode = deriveJarvisIntelligenceMode({
    hasMessages: messages.length > 0,
    loading,
    lastAssistantHasActions:
      !!lastMessage && lastMessage.role === "assistant" && (lastMessage.suggestedActions?.length ?? 0) > 0,
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Composer grows with content (comfortable one-liner up to ~4 lines), then
  // scrolls internally rather than growing indefinitely — also what snaps it
  // back to baseline height once `send()` clears the input.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    const maxHeight = 136;
    el.style.height = "auto";
    const next = Math.min(el.scrollHeight, maxHeight);
    el.style.height = `${next}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [input]);

  async function send(text: string, opts?: { workingLabel?: string; resultLabel?: string }) {
    const question = text.trim();
    if (!question || loading) return;

    setError(null);
    setInput("");
    setPendingLabel(opts?.workingLabel ?? null);

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
        {
          role: "assistant",
          content: res.reply,
          sources: res.sources,
          baseSources: res.base_sources,
          calendarSources: res.calendar_sources,
          taskSources: res.task_sources,
          workOrderSources: res.work_order_sources,
          projectSources: res.project_sources,
          suggestedActions,
          modeLabel: opts?.resultLabel,
        },
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
      setPendingLabel(null);
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
    // Fills whatever real height its ancestor chain resolves to — the panel,
    // the mobile overlay, and the dedicated /jarvis page each establish that
    // height differently, so the "how tall is the viewport chrome around
    // this" concern belongs to them, not to this shared component.
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {mode === "context" && (
          // Contextual Intelligence Workspace pass: this is the "the user
          // should not need to type first" surface — real structured fields
          // about what's currently in view (JarvisContextSnapshot), then
          // real quick-intelligence rows that send real prompts through the
          // unchanged /api/jarvis/chat endpoint. The entity title itself
          // lives in the surrounding chrome (JarvisIntelligenceHeader in
          // JarvisRail/JarvisPage/MobileJarvisOverlay), not duplicated here.
          <div className="py-2 space-y-6">
            {jarvisContext.snapshot && jarvisContext.snapshot.length > 0 && (
              <JarvisContextSnapshot fields={jarvisContext.snapshot} />
            )}
            {jarvisContext.quickActions.length > 0 && (
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-2">
                  {t("jarvis.panel.quick_intelligence_label")}
                </p>
                <div className="space-y-2">
                  {jarvisContext.quickActions.map((qa) => (
                    <JarvisQuickAction
                      key={qa.label}
                      label={qa.label}
                      description={qa.description}
                      icon={qa.icon}
                      onClick={() => send(qa.prompt, { workingLabel: qa.workingLabel, resultLabel: qa.resultLabel })}
                    />
                  ))}
                </div>
              </div>
            )}
            {/* Fallback for routes without real structured data or quick
                actions yet (e.g. Settings) — the plain route summary, never
                a blank panel. */}
            {(!jarvisContext.snapshot || jarvisContext.snapshot.length === 0) &&
              jarvisContext.quickActions.length === 0 && (
                <div className="flex items-start gap-3">
                  <Sparkles className="h-5 w-5 text-[var(--text-accent)] shrink-0 mt-0.5" />
                  <p className="font-serif text-lg text-[var(--text-primary)]">{jarvisContext.summary}</p>
                </div>
              )}
            {/* Command Layer audit trail (JARVIS-C1) — every proposal ever
                confirmed/rejected, route-agnostic so it renders once per
                panel/page regardless of what's currently in context. Renders
                nothing until real decisions exist. */}
            <JarvisDecisionHistory />
          </div>
        )}

        {/* Higgsfield reference (05-pages/02-jarvis-expanded-desktop.png):
            a briefing/document read, not a two-sided chat UI — plain
            YOU/JARVIS label + text, hairline-divided, no bubbles. */}
        {messages.map((msg, i) => (
          <div key={i} className="pb-4 border-b border-[var(--border-light)] last:border-0">
            <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-2">
              {msg.role === "user" ? t("jarvis.you_label") : msg.modeLabel ?? t("jarvis.title")}
            </p>
            <p
              className={cn(
                "whitespace-pre-wrap",
                msg.role === "user"
                  ? "text-sm text-[var(--text-secondary)]"
                  : "font-serif text-[17px] leading-relaxed text-[var(--text-primary)]"
              )}
            >
              {msg.content}
            </p>

            {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
              <div className="mt-3">
                <SourcesDisclosure title={t("jarvis.sources")} icon={FileText} sources={msg.sources} />
              </div>
            )}
            {msg.role === "assistant" && msg.baseSources && msg.baseSources.length > 0 && (
              <div className="mt-2">
                <SourcesDisclosure title={t("jarvis.base_context")} icon={FolderOpen} sources={msg.baseSources} />
              </div>
            )}
            {msg.role === "assistant" && msg.calendarSources && msg.calendarSources.length > 0 && (
              <div className="mt-2">
                <SourcesDisclosure title={t("jarvis.calendar_sources")} icon={Calendar} sources={msg.calendarSources} />
              </div>
            )}
            {msg.role === "assistant" && msg.taskSources && msg.taskSources.length > 0 && (
              <div className="mt-2">
                <SourcesDisclosure title={t("jarvis.task_sources")} icon={ListChecks} sources={msg.taskSources} />
              </div>
            )}
            {msg.role === "assistant" && msg.workOrderSources && msg.workOrderSources.length > 0 && (
              <div className="mt-2">
                <SourcesDisclosure title={t("jarvis.work_order_sources")} icon={ClipboardList} sources={msg.workOrderSources} />
              </div>
            )}
            {msg.role === "assistant" && msg.projectSources && msg.projectSources.length > 0 && (
              <div className="mt-2">
                <SourcesDisclosure title={t("jarvis.project_sources")} icon={Briefcase} sources={msg.projectSources} />
              </div>
            )}

            {msg.role === "assistant" && msg.suggestedActions && msg.suggestedActions.length > 0 && (
              <div className="mt-3">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)] mb-2">
                  {t("jarvis.panel.next_steps_label")}
                </p>
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
              </div>
            )}
          </div>
        ))}

        {mode === "thinking" && (
          <div className="flex items-center gap-2 pb-4">
            <div className="h-4 w-4 rounded-full border-2 border-brand-500 border-t-transparent animate-spin shrink-0" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
              {pendingLabel ?? t("jarvis.thinking")}
            </span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Composer-Footer (Focus-Deck-Kompositions-Pass): eigene, oben
          abgegrenzte Zone statt einer frei schwebenden Pille im leeren Raum
          — dieselbe horizontale Einfassung wie der Rest der Rail (kommt von
          JarvisRail/MobileJarvisOverlay's Padding), ein Top-Border als
          eindeutige visuelle Verbindung zur Rail, kein zusätzlicher
          Kartenrahmen um den Composer selbst. */}
      <div className="pt-3 border-t border-[var(--border-light)] shrink-0">
        {error && (
          <div className="mb-3 rounded-lg bg-status-danger/10 border border-status-danger/30 px-4 py-3 text-status-danger text-sm flex items-center justify-between gap-3">
            <p>
              <span className="font-medium">{t("jarvis.error_banner")}</span> {error}
            </p>
            <Button type="button" variant="secondary" size="sm" onClick={() => send(input)}>
              {t("jarvis.retry")}
            </Button>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Deterministic composer: outer is `relative`, the icon and the
              send button are `absolute` at fixed edges, and the textarea is
              a single full-width block with padding carved out for both —
              not a flex row. A flex row lets an intrinsically-wide child
              (or browser flex quirks) shove the button around; absolute
              positioning makes the button's position a constant, full stop,
              regardless of placeholder/typed-text/textarea/viewport width. */}
          <div
            className={cn(
              // Full intelligence input, not the closed command bar's compact
              // pill: rounded-2xl (card-family radius) rather than
              // rounded-full, and a taller comfortable baseline — grows
              // further as content wraps (see the resize effect above).
              "relative w-full rounded-2xl border bg-[var(--bg-surface)]",
              "motion-safe:transition-[border-color,box-shadow]",
              // Calm by default, glow only on focus (Higgsfield reference:
              // the composer is a plain neutral surface until active).
              "border-[var(--border-default)]",
              "focus-within:border-[var(--interactive-bg-primary-default)] focus-within:shadow-[0_0_0_3px_rgba(181,115,63,0.18)]"
            )}
          >
            <Sparkles className="absolute left-4 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--text-accent)] pointer-events-none" />
            <Textarea
              ref={textareaRef}
              bare
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t("jarvis.placeholder")}
              rows={1}
              className="block w-full min-w-0 py-5 pl-10 pr-12 text-sm min-h-0 resize-none"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              aria-label={t("jarvis.send")}
              className="absolute right-2 top-1/2 -translate-y-1/2 z-10 flex items-center justify-center h-10 w-10 rounded-full shrink-0 bg-[var(--interactive-bg-primary-default)] hover:bg-[var(--interactive-bg-primary-hover)] text-white disabled:opacity-50 motion-safe:transition-colors focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-offset-2 focus-visible:outline-[var(--interactive-border-focus)]"
            >
              {loading ? (
                <div className="h-4 w-4 rounded-full border-2 border-white border-t-transparent animate-spin" />
              ) : (
                <ArrowRight className="h-4 w-4" />
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
