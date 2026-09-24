"use client";

import { useEffect, useState } from "react";
import { BookOpen, AlertTriangle } from "lucide-react";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { api, type VaultStatus } from "@/lib/api";

// One data source, visibly connected (24.09.2026) — Vault chosen over
// Calendar/Notion: it already has a real per-project association (file
// naming convention under Projekte/), zero external API/auth surface
// (local filesystem only), and reuses existing, already-tested retrieval
// code (vault_service.get_vault_status). Calendar/Notion have no project
// linkage at all — surfacing one of those here would invite exactly the
// kind of invented project association this pass is explicitly avoiding
// elsewhere (see ProjectCards.tsx, work_orders_context_service.py).
//
// Client-side "last known good" cache (localStorage, not a new DB column):
// a live check failing must still show when the source last actually
// worked, not just go blank — same "veraltet/fehlgeschlagen sichtbar
// machen" requirement ProjectCards already applies to project data.
const LAST_OK_KEY = "cp_vault_status_last_ok";

interface LastOk {
  checked_at: string;
  notes_found: number;
}

function readLastOk(): LastOk | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(LAST_OK_KEY);
    return raw ? (JSON.parse(raw) as LastOk) : null;
  } catch {
    return null;
  }
}

function writeLastOk(value: LastOk) {
  try {
    localStorage.setItem(LAST_OK_KEY, JSON.stringify(value));
  } catch {
    // best-effort cache only — a write failure (private browsing, full
    // storage) must never block rendering the live status itself.
  }
}

export function DataSourceStatus() {
  const t = useT();
  const [status, setStatus] = useState<VaultStatus | null>(null);
  const [fetchFailed, setFetchFailed] = useState(false);
  const [lastOk, setLastOk] = useState<LastOk | null>(null);

  useEffect(() => {
    setLastOk(readLastOk());
    api.integrations
      .vaultStatus()
      .then((res) => {
        setStatus(res);
        if (res.ok) {
          const value = { checked_at: res.checked_at, notes_found: res.notes_found };
          writeLastOk(value);
          setLastOk(value);
        }
      })
      .catch(() => setFetchFailed(true));
  }, []);

  // Not the configured owner: this feature is single-tenant by design
  // (CLAUDE.md § Jarvis) — showing anything here to another authenticated
  // user would just be noise about a feature that was never meant for them.
  if (status?.reason === "not_owner") return null;

  const isLive = !!status?.ok;
  const isError = fetchFailed || (!!status && !status.ok);

  // A specific reason the backend actually reported (not_configured,
  // read_error) takes priority over the generic client-side "stale"
  // fallback below — that fallback exists for "couldn't reach the backend
  // at all," not for masking a real, current read error behind an old
  // cached success (confirmed against e8c2b02: a read_error would have
  // rendered as "last synced HH:MM" if a prior successful check existed
  // in localStorage, which reads as "basically fine" — it is not).
  let text: string;
  if (isLive && status) {
    text = t("dashboard.data_source.connected").replace("{n}", String(status.notes_found));
  } else if (status?.reason === "not_configured") {
    text = t("dashboard.data_source.not_configured");
  } else if (status?.reason === "read_error") {
    text = t("dashboard.data_source.read_error").replace("{n}", String(status.notes_found));
  } else if (lastOk) {
    text = t("dashboard.data_source.stale").replace("{time}", new Date(lastOk.checked_at).toLocaleTimeString());
  } else if (fetchFailed) {
    text = t("dashboard.data_source.fetch_failed");
  } else {
    return null; // still loading, nothing confirmed yet — no flash of a wrong state
  }

  return (
    <div className="flex items-center gap-1.5 text-[11px] font-mono text-[var(--text-tertiary)] mb-3">
      {isError ? (
        <AlertTriangle className="h-3 w-3 text-status-warning shrink-0" />
      ) : (
        <BookOpen className={cn("h-3 w-3 shrink-0", isLive ? "text-status-success" : "text-status-warning")} />
      )}
      <span className={cn(isError && "text-status-warning")}>{text}</span>
    </div>
  );
}
