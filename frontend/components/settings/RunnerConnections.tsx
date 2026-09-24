"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { api, type RunnerConnection } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { formatDate } from "@/lib/utils";

// Guided pairing (23.09.2026) — replaces "copy a Supabase session token out
// of browser DevTools" for scripts/run_work_order_daemon.py. This panel is
// the ONLY place a runner ever gets approved or revoked; the runner itself
// only ever sees a short user_code, never anything typed here. See
// supabase/migrations/017_runner_connections.sql for the full flow.
export function RunnerConnections() {
  const t = useT();
  const [connections, setConnections] = useState<RunnerConnection[] | null>(null);
  // Found live 23.09.2026: the first version of this component caught a
  // failed listMine() and set connections to [] — exactly the silent
  // "fetch failed looks identical to genuinely empty" anti-pattern CLAUDE.md
  // already warns about for frontend/lib/mockWorkOrders.ts. A real 503
  // (schema not migrated yet, expired session, backend down) must never
  // render as "Noch kein Runner verbunden" — loadError is what makes that
  // distinguishable and visible instead.
  const [loadError, setLoadError] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [label, setLabel] = useState("");
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  // Stable — no `t` dependency, matching ProjectsManager.tsx's loadProjects
  // precedent: useT() returns a fresh function every render, so depending
  // on it here would re-run this effect every render instead of once.
  const loadConnections = useCallback(() => {
    setLoadError(null);
    api.runnerConnections
      .listMine()
      .then(setConnections)
      .catch((err) => {
        setConnections(null);
        setLoadError(err instanceof Error ? err.message : "error");
      });
  }, []);

  useEffect(() => {
    loadConnections();
  }, [loadConnections]);

  async function handleApprove(e: React.FormEvent) {
    e.preventDefault();
    if (!code.trim()) return;
    setApproving(true);
    setError(null);
    setSuccess(null);
    try {
      const connection = await api.runnerConnections.approve({
        user_code: code.trim(),
        label: label.trim() || undefined,
      });
      setSuccess(t("settings.runner.connected_as").replace("{label}", connection.label));
      setCode("");
      setLabel("");
      loadConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setApproving(false);
    }
  }

  async function handleRevoke(id: string) {
    setRevokingId(id);
    try {
      await api.runnerConnections.revoke(id);
      loadConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally {
      setRevokingId(null);
    }
  }

  const active = (connections ?? []).filter((c) => !c.revoked_at);

  return (
    <div className="space-y-4">
      <form onSubmit={handleApprove} className="flex flex-wrap items-end gap-2">
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wide">
            {t("settings.runner.code_label")}
          </label>
          <input
            type="text"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            placeholder="ABCD-1234"
            className="w-36 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-default)] px-3 py-2 text-sm font-mono uppercase text-[var(--text-primary)] placeholder:text-[var(--text-placeholder)] placeholder:normal-case focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-[var(--interactive-border-focus)]"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-[var(--text-tertiary)] uppercase tracking-wide">
            {t("settings.runner.label_label")}
          </label>
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder={t("settings.runner.label_placeholder")}
            className="w-48 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-default)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-placeholder)] focus:outline-none focus-visible:outline focus-visible:outline-[1.5px] focus-visible:outline-[var(--interactive-border-focus)]"
          />
        </div>
        <Button type="submit" size="sm" loading={approving} disabled={!code.trim()} className="rounded-xl">
          {t("settings.runner.connect")}
        </Button>
      </form>

      {error && <p className="text-status-danger text-xs">{error}</p>}
      {success && <p className="text-status-success text-xs">{success}</p>}

      <p className="text-[var(--text-tertiary)] text-xs">{t("settings.runner.hint")}</p>

      {loadError && (
        <div className="rounded-lg bg-status-danger/10 border border-status-danger/30 px-3 py-2 flex items-center justify-between gap-2">
          <p className="text-status-danger text-xs">{t("settings.runner.load_error")} {loadError}</p>
          <Button size="sm" variant="outline-accent" onClick={loadConnections} className="rounded-xl shrink-0">
            {t("button.retry")}
          </Button>
        </div>
      )}

      {loadError ? null : connections === null ? null : active.length === 0 ? (
        <p className="text-[var(--text-tertiary)] text-sm">{t("settings.runner.empty")}</p>
      ) : (
        <div className="rounded-lg border border-[var(--border-light)] divide-y divide-[var(--border-light)] overflow-hidden">
          {active.map((c) => (
            <div key={c.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
              <div className="min-w-0">
                <p className="text-sm font-medium text-[var(--text-primary)] truncate">{c.label}</p>
                <p className="text-[var(--text-tertiary)] text-xs mt-0.5">
                  {t("settings.runner.connected_since")} {formatDate(c.created_at)}
                  {c.last_used_at && ` · ${t("settings.runner.last_used")} ${formatDate(c.last_used_at)}`}
                  {!c.last_used_at && ` · ${t("settings.runner.never_used")}`}
                </p>
              </div>
              <Button
                size="sm"
                variant="outline-accent"
                loading={revokingId === c.id}
                onClick={() => handleRevoke(c.id)}
                className="rounded-xl shrink-0"
              >
                {t("settings.runner.revoke")}
              </Button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
