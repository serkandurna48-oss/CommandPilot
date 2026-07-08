/**
 * Canonical safety rules for the Background Dev Team control plane.
 * These are repo-wide defaults, not per-work-order — a work order's
 * ApprovalScope narrows these further, it never widens them.
 * Used by the operator UI (safety rules panel) and by generateRunnerPrompt().
 */

export const AUTONOMOUS_ALLOWED = [
  "Repo lesen",
  "Plan erstellen",
  "Code ändern innerhalb Scope",
  "Tests / Lint / Typecheck ausführen",
  "Lokale Artifacts erzeugen",
  "Review Package schreiben",
];

export const NEEDS_APPROVAL = [
  "Dependencies installieren",
  "Externe Services anbinden",
  "Migrationen ausführen",
  "Push / PR erstellen",
  "Laufzeit- oder Kostenlimit erhöhen",
  "Große Architekturänderungen",
];

export const BLOCKED_ALWAYS = [
  "Deployments",
  "Production-Daten ändern",
  "Secrets anzeigen oder loggen",
  "E-Mails senden",
  "Zahlungen auslösen",
  "Destructive Git-Kommandos (reset --hard, force push, clean -f)",
  "Direkte Änderungen auf main",
  "Userdaten exportieren",
];
