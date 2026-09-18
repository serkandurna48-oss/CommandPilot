"use client";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/Spinner";
import { ApiError, api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { JarvisChatMessage, JarvisSourceRef } from "@/types";
import { Send } from "lucide-react";

interface DisplayMessage extends JarvisChatMessage {
  sources?: JarvisSourceRef[];
}

export function JarvisChat() {
  const t = useT();
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
      setMessages((prev) => [...prev, { role: "assistant", content: res.reply, sources: res.sources }]);
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
