"use client";

import { useAuth } from "@/lib/auth";

export type Lang = "en" | "de";

export const SUPPORTED_LANGS: { value: Lang; label: string }[] = [
  { value: "en", label: "English" },
  { value: "de", label: "Deutsch" },
];

// All UI strings. Keys are dot-namespaced. Always add both "en" and "de".
// JSON keys in AI output must stay English — only user-visible UI text is here.
const dict: Record<string, Record<Lang, string>> = {
  // ── Page titles & subtitles ────────────────────────────────────────────────
  "cockpit":                  { en: "Cockpit",            de: "Cockpit" },
  "cockpit.subtitle":         { en: "Your overview for today.", de: "Behalte deine Tagespläne, offenen Schritte und letzten Entscheidungen im Blick." },
  "morning_checkin":          { en: "Morning Check-in",   de: "Tagesstart" },
  "morning_checkin.subtitle": { en: "A few quick questions before your plan is created.", de: "Sag CommandPilot kurz, wie dein Tag aussieht. Daraus entsteht ein klarer Tagesplan." },
  "plan.today":               { en: "Today's Plan",       de: "Heutiger Tagesplan" },
  "plan.today.subtitle":      { en: "Your day in structure.", de: "Dein Tagesplan auf einen Blick." },
  "evening_review":           { en: "Evening Review",     de: "Abend-Reflexion" },
  "evening_review.subtitle":  { en: "A brief look back before the day ends.", de: "Kurz zurückblicken, bevor der Tag endet." },
  "rules":                    { en: "Rules",              de: "Regeln" },
  "settings":                 { en: "Settings",           de: "Einstellungen" },

  // ── Greeting (time-aware, used in HomeBriefing + JarvisChat) ─────────────────
  "greeting.morning":          { en: "Good morning.",        de: "Guten Morgen." },
  "greeting.afternoon":        { en: "Good afternoon.",      de: "Guten Nachmittag." },
  "greeting.evening":          { en: "Good evening.",        de: "Guten Abend." },
  "greeting.night":            { en: "Late hours.",          de: "Späte Stunde." },

  // ── Navigation ─────────────────────────────────────────────────────────────
  "nav.dashboard":            { en: "Dashboard",          de: "Cockpit" },
  "nav.morning":              { en: "Morning",            de: "Start" },
  "nav.review":               { en: "Review",             de: "Review" },
  "nav.rules":                { en: "Rules",              de: "Regeln" },
  "nav.projects":             { en: "Projects",           de: "Projekte" },
  "nav.operator":             { en: "Operator",           de: "Operator" },
  "nav.jarvis":               { en: "Jarvis",             de: "Jarvis" },
  "nav.settings":             { en: "Settings",           de: "Einstellungen" },
  // Focus-Deck-Icon-Rail (Slice 1): fünf globale Ziele, bündeln die acht
  // Routen oben. "Home" bündelt Dashboard/Morning/Plan/Review, "Activity"
  // bündelt Operator/Work Orders/Agent Runs/Review Packages.
  "nav.home":                 { en: "Home",               de: "Home" },
  "nav.activity":             { en: "Activity",           de: "Aktivität" },

  // ── Dashboard / Home briefing (Focus Deck Home Fidelity Sprint) ─────────────
  // Replaces the earlier "Command Hero / Signal-Noise / Project Radar" concept
  // (see phase6-review.md §9) with four briefing sections: Today, Needs Your
  // Decision, In Progress, Recent Activity — all backed by real plan/work-order
  // data, no fabricated metrics.
  "dashboard.title":          { en: "Dashboard",          de: "Cockpit" },
  "dashboard.subtitle":       { en: "Here's what's on your plate today.", de: "Das steht heute für dich an." },
  "dashboard.hero.standby":   { en: "Awaiting mission brief.", de: "Kein Tagesplan bisher." },
  "dashboard.no_plan_sub":    { en: "Start your morning check-in and get your AI-generated daily strategy in under 30 seconds.", de: "Starte deinen Tagesstart und erhalte in wenigen Sekunden einen klaren Tagesplan." },
  "dashboard.intro":          { en: "Jarvis knows your projects, calendar, and tasks — and helps you plan the day before you even ask.", de: "Jarvis kennt deine Projekte, deinen Kalender und deine Aufgaben — und hilft dir, den Tag zu planen, bevor du überhaupt fragst." },
  "dashboard.intro.dismiss":  { en: "Dismiss",              de: "Ausblenden" },
  "dashboard.start_checkin":  { en: "Start Morning Check-in", de: "Tagesstart beginnen" },
  "dashboard.view_plan":      { en: "View full plan",     de: "Tagesplan öffnen" },
  "dashboard.new_checkin":    { en: "New Check-in",       de: "Neuer Tagesstart" },
  "dashboard.view_all":       { en: "View all",           de: "Alle anzeigen" },
  "dashboard.open":           { en: "Open",               de: "Öffnen" },
  "dashboard.section.today":           { en: "Today",                  de: "Heute" },
  "dashboard.section.needs_decision":  { en: "Needs Your Decision",    de: "Braucht deine Entscheidung" },
  "dashboard.section.in_progress":     { en: "In Progress",            de: "In Arbeit" },
  "dashboard.section.recent_activity": { en: "Recent Activity",        de: "Letzte Aktivität" },
  "dashboard.section.active_projects": { en: "Active Projects",        de: "Aktive Projekte" },
  "dashboard.section.product_websites": { en: "Product Websites",      de: "Produkt-Websites" },
  "dashboard.project_cards.other_projects":    { en: "Other Projects",     de: "Weitere Projekte" },
  "dashboard.project_cards.load_error":        { en: "Could not load your projects:", de: "Projekte konnten nicht geladen werden:" },
  "dashboard.project_cards.next_action_empty": { en: "No next task set.",  de: "Keine nächste Aufgabe gesetzt." },
  "dashboard.project_cards.set_now":           { en: "Set now",            de: "Jetzt setzen" },
  "dashboard.project_cards.compact_today":     { en: "today",              de: "heute" },
  "dashboard.project_cards.compact_one_day":   { en: "1 day",              de: "1 Tag" },
  "dashboard.project_cards.compact_days":      { en: "{n} days",           de: "{n} Tage" },
  "dashboard.project_cards.stale_hint":        { en: "Not updated in over 3 days", de: "Seit über 3 Tagen nicht aktualisiert" },
  "dashboard.data_source.connected":     { en: "Second Brain connected — {n} notes", de: "Second Brain verbunden — {n} Notizen" },
  "dashboard.data_source.stale":         { en: "Second Brain — last synced {time}",  de: "Second Brain — zuletzt synchronisiert {time}" },
  "dashboard.data_source.not_configured":{ en: "Second Brain not configured",        de: "Second Brain nicht konfiguriert" },
  "dashboard.data_source.fetch_failed":  { en: "Second Brain — sync failed",         de: "Second Brain — Synchronisierung fehlgeschlagen" },
  "dashboard.data_source.read_error":    { en: "Second Brain — read error ({n} notes readable)", de: "Second Brain — Lesefehler ({n} Notizen lesbar)" },
  "dashboard.today.priority_label":    { en: "Priority",               de: "Priorität" },
  "dashboard.decision.empty_title":    { en: "Nothing needs your decision.", de: "Nichts wartet auf deine Entscheidung." },
  "dashboard.decision.empty_desc":     { en: "Work orders waiting for your approval will show up here.", de: "Arbeitsaufträge, die auf deine Freigabe warten, erscheinen hier." },
  "dashboard.progress.empty_title":    { en: "Nothing in progress.",   de: "Nichts läuft gerade." },
  "dashboard.progress.empty_desc":     { en: "Running and queued work orders will show up here.", de: "Laufende und eingereihte Arbeitsaufträge erscheinen hier." },
  "dashboard.activity.empty_title":    { en: "No recent activity.",    de: "Keine aktuelle Aktivität." },
  "dashboard.activity.empty_desc":     { en: "Activity from your work orders will show up here.", de: "Aktivität aus deinen Arbeitsaufträgen erscheint hier." },
  "dashboard.activity.created":        { en: "Created",                de: "Erstellt" },
  "dashboard.activity.started":        { en: "Started",                de: "Gestartet" },
  "dashboard.activity.completed":      { en: "Completed",              de: "Abgeschlossen" },

  // ── Morning check-in ───────────────────────────────────────────────────────
  "morning.title":            { en: "Morning Check-in",   de: "Tagesstart" },
  "morning.subtitle":         { en: "Dump your morning state. The AI handles the structure.", de: "Sag CommandPilot kurz, wie dein Tag aussieht. Daraus entsteht ein klarer Tagesplan." },
  "morning.quick_input":      { en: "Quick Input",        de: "Schnelleingabe" },
  "morning.quick_label":      { en: "Dump everything here — the AI will structure it", de: "Schreib, wie dein Tag aussieht – CommandPilot strukturiert es." },
  "morning.quick_ph":         { en: "Woke up at 7:00, energy 6/10, slightly tired. Morning run at 08:00, team call at 14:00. Need to finish the Q3 report...", de: "Um 7:00 aufgewacht, Energie 6/10, leicht müde. Morgenlauf um 08:00, Teamcall um 14:00. Q3-Bericht fertigstellen..." },
  "morning.vitals":           { en: "Morning Vitals",     de: "Vitaldaten" },
  "morning.wake_time":        { en: "Wake Time",          de: "Aufgestanden um" },
  "morning.sleep_quality":    { en: "Sleep Quality",      de: "Schlafqualität" },
  "morning.energy_level":     { en: "Energy Level",       de: "Energielevel" },
  "morning.avail_hours":      { en: "Available Hours",    de: "Verfügbare Stunden" },
  "morning.body_status":      { en: "Body / Physical Status", de: "Körper" },
  "morning.body_ph":          { en: "Sore legs, light headache, feeling fresh...", de: "Spannung, Schmerzen, ungewöhnliche Müdigkeit?" },
  "morning.mood":             { en: "Mood",               de: "Stimmung" },
  "morning.mood_ph":          { en: "Focused, anxious, motivated, neutral...", de: "In einem Wort: wie fühlst du dich?" },
  "morning.agenda":           { en: "Today's Agenda",     de: "Tagesplanung" },
  "morning.fixed_events":     { en: "Fixed Events (one per line — include time)", de: "Feste Termine (einer pro Zeile – mit Uhrzeit)" },
  "morning.fixed_ph":         { en: "Gym at 10:00\nTennis at 18:00\nTeam call at 14:00", de: "Gym um 10:00\nTennis um 18:00\nTeamcall um 14:00" },
  "morning.tasks":            { en: "Important Tasks (one per line)", de: "Wichtige Aufgaben (eine pro Zeile)" },
  "morning.tasks_ph":         { en: "Finish Q3 report draft\nReview project proposal\nRespond to client emails", de: "Q3-Bericht fertigstellen\nProjektvorschlag prüfen\nKunden-E-Mails beantworten" },
  "morning.constraints":      { en: "Constraints / Hard Limits", de: "Tagesgrenzen" },
  "morning.constraints_ph":   { en: "No work after 21:00. Don't schedule deep work right after intense exercise.", de: "Keine Arbeit nach 21:00. Keine Tiefarbeit direkt nach intensivem Sport." },
  "morning.generate":         { en: "Generate Today's Plan", de: "Tagesplan erstellen" },
  "morning.retry":            { en: "Retry Plan Generation", de: "Tagesplan erneut erstellen" },
  "morning.generating":       { en: "Generating your daily plan...", de: "CommandPilot strukturiert deinen Tag..." },
  "morning.generating_sub":   { en: "This takes about 5-10 seconds.", de: "Das dauert etwa 5–10 Sekunden." },
  "morning.checkin_hint":     { en: "Your check-in was saved. Clicking \"Generate\" will retry plan generation without creating a duplicate.", de: "Dein Tagesstart wurde gespeichert. Du kannst den Tagesplan jetzt erneut erstellen." },
  "morning.history.title":    { en: "Recent check-ins",  de: "Letzte Tagesstarts" },
  "morning.history.energy":   { en: "Energy",             de: "Energie" },
  "morning.history.sleep":    { en: "Sleep",              de: "Schlaf" },
  "morning.plan_history.title":    { en: "Past plans",             de: "Frühere Tagespläne" },
  "morning.plan_history.untitled": { en: "(no main win recorded)", de: "(kein Haupt-Ziel hinterlegt)" },

  // ── Plan View ──────────────────────────────────────────────────────────────
  "plan.based_on_review":     { en: "Based on your recent evening review", de: "Basierend auf deiner letzten Abend-Reflexion" },
  "plan.main_win":            { en: "Main Win",           de: "Wichtigstes Ergebnis" },
  "plan.top_priorities":      { en: "Top 3 Priorities",   de: "Die 3 wichtigsten Schritte" },
  "plan.schedule":            { en: "Time-Blocked Schedule", de: "Tagesstruktur" },
  "plan.energy_strategy":     { en: "Energy Strategy",    de: "Energie & Körper" },
  "plan.not_today":           { en: "Not Today",          de: "Heute bewusst nicht" },
  "plan.eve_questions":       { en: "Evening Review Questions", de: "Fragen für die Abend-Reflexion" },
  // Block type labels (values used as badge text)
  "block.deep_work":          { en: "Deep Work",          de: "Tiefarbeit" },
  "block.admin":              { en: "Admin",              de: "Verwaltung" },
  "block.sport":              { en: "Sport",              de: "Sport" },
  "block.break":              { en: "Break",              de: "Pause" },
  "block.social":             { en: "Social",             de: "Sozial" },
  "block.learning":           { en: "Learning",           de: "Lernen" },
  "block.personal":           { en: "Personal",           de: "Persönlich" },
  "block.other":              { en: "Other",              de: "Sonstiges" },

  // ── Evening Review ─────────────────────────────────────────────────────────
  "review.title":             { en: "Evening Review",     de: "Abend-Reflexion" },
  "review.subtitle":          { en: "Close the day. Capture what mattered.", de: "Blick zurück auf den Tag. Was hat funktioniert, was nicht?" },
  "review.today_questions":   { en: "Today's Questions",  de: "Fragen für heute" },
  "review.eod_vitals":        { en: "End-of-Day Vitals",  de: "Vitaldaten am Abend" },
  "review.energy_end":        { en: "Energy at end",      de: "Energie am Abend" },
  "review.overall_day":       { en: "Overall day",        de: "Gesamter Tag" },
  "review.execution":         { en: "Execution",          de: "Umsetzung" },
  "review.completed":         { en: "Completed (one per line)", de: "Erledigt (eine pro Zeile)" },
  "review.completed_ph":      { en: "Finished Q3 report draft\nResponded to client emails", de: "Q3-Bericht fertiggestellt\nKunden-E-Mails beantwortet" },
  "review.missed":            { en: "Missed / didn't happen (one per line)", de: "Nicht geschafft (eine pro Zeile)" },
  "review.missed_ph":         { en: "Project proposal review — pushed to tomorrow", de: "Projektvorschlag-Review – auf morgen verschoben" },
  "review.carry_over":        { en: "Carry over to tomorrow (one per line)", de: "Auf morgen übertragen (eine pro Zeile)" },
  "review.carry_over_ph":     { en: "Review project proposal\nFollow up with client", de: "Projektvorschlag prüfen\nMit Kunden nachfassen" },
  "review.reflection":        { en: "Reflection",         de: "Reflexion" },
  "review.biggest_win":       { en: "Biggest win today",  de: "Größter Erfolg heute" },
  "review.biggest_win_ph":    { en: "What actually mattered?", de: "Was hat wirklich gezählt?" },
  "review.lesson":            { en: "Key lesson",         de: "Wichtigste Erkenntnis" },
  "review.lesson_ph":         { en: "What would you do differently?", de: "Was würdest du anders machen?" },
  "review.raw":               { en: "Raw reflection (optional brain dump)", de: "Freie Reflexion (optional)" },
  "review.raw_ph":            { en: "Anything else on your mind...", de: "Was ist dir sonst noch aufgefallen..." },
  "review.save":              { en: "Save Review",        de: "Reflexion speichern" },
  "review.saved":             { en: "Review saved.",      de: "Reflexion gespeichert." },
  "review.saved_sub":         { en: "Rest well. Tomorrow is a clean slate.", de: "Ruh dich aus. Morgen ist ein neuer Tag." },
  "review.back":              { en: "Back to Dashboard",  de: "Zurück zum Cockpit" },
  "review.history.title":     { en: "Recent reviews",     de: "Letzte Reflexionen" },

  // ── Rules ──────────────────────────────────────────────────────────────────
  "rules.title":              { en: "Personal Rules",     de: "Regeln" },
  "rules.subtitle":           { en: "Your operating principles. The AI uses these to personalize every plan.", de: "Deine Regeln fließen in jeden Tagesplan ein." },

  // ── Jarvis (second-brain chat) ────────────────────────────────────────────────
  "jarvis.title":             { en: "Jarvis",             de: "Jarvis" },
  "jarvis.placeholder":       { en: "Ask Jarvis anything...", de: "Frag Jarvis etwas..." },
  "jarvis.send":              { en: "Send",               de: "Senden" },
  "jarvis.thinking":          { en: "Thinking...",        de: "Denkt nach..." },
  "jarvis.sources":           { en: "Sources used",       de: "Verwendete Quellen" },
  "jarvis.base_context":      { en: "Base context",       de: "Basiskontext" },
  "jarvis.calendar_sources":  { en: "Calendar",           de: "Kalender" },
  "jarvis.task_sources":      { en: "Open tasks (Notion)", de: "Offene Aufgaben (Notion)" },
  "jarvis.work_order_sources": { en: "Work Orders",         de: "Work Orders" },
  "jarvis.project_sources":    { en: "Projects",            de: "Projekte" },
  "jarvis.you_label":         { en: "You",                de: "Du" },
  "jarvis.error_banner":      { en: "Jarvis could not answer:", de: "Jarvis konnte nicht antworten:" },
  "jarvis.retry":             { en: "Retry",              de: "Nochmal versuchen" },
  "jarvis.open_mobile":       { en: "Open Jarvis",        de: "Jarvis öffnen" },
  "jarvis.close":             { en: "Close",              de: "Schließen" },

  // ── Command Jarvis bar (Interactive Operating System pass) ───────────────────
  "jarvis.command_bar.title":    { en: "Command Jarvis",  de: "Command Jarvis" },
  "jarvis.command_bar.subtitle": { en: "Ask, prepare, prioritize, or execute across your workspace...", de: "Frag, bereite vor, priorisiere oder handle über dein ganzes Workspace hinweg ..." },

  // Per-route default context (JarvisContext, lib/jarvisContext.tsx) — the
  // fallback shown until a page pushes something more specific (e.g. a
  // selected project). Not user-facing navigation labels (those are the
  // nav.* keys) — these are Jarvis's own framing of "what am I looking at."
  "jarvis.context.home.title":         { en: "Home",       de: "Home" },
  "jarvis.context.home.summary":       { en: "Your daily command center.", de: "Deine tägliche Kommandozentrale." },
  "jarvis.context.projects.title":     { en: "Projects",   de: "Projekte" },
  "jarvis.context.projects.summary":   { en: "Review projects, risks and next moves.", de: "Projekte, Risiken und nächste Schritte im Blick behalten." },
  "jarvis.context.operator.title":     { en: "Operator",   de: "Operator" },
  "jarvis.context.operator.summary":   { en: "Review and control execution.", de: "Ausführung prüfen und steuern." },
  "jarvis.context.daily_plan.title":   { en: "Daily Plan", de: "Tagesplan" },
  "jarvis.context.daily_plan.summary": { en: "Review today's priorities.", de: "Die heutigen Prioritäten durchgehen." },
  "jarvis.context.settings.title":     { en: "Settings",   de: "Einstellungen" },
  "jarvis.context.settings.summary":   { en: "Rules and preferences.", de: "Regeln und Einstellungen." },

  // Quick-action labels — doubles as the literal message sent for the
  // generic (non-entity) ones; entity-specific contexts (selected project,
  // work order) build a real-data prompt separately and reuse only the label.
  "jarvis.qa.review_today":         { en: "Review today",           de: "Heute durchgehen" },
  "jarvis.qa.check_blocked":        { en: "Check blocked work",     de: "Blockierte Arbeit prüfen" },
  "jarvis.qa.prioritize_projects":  { en: "Prioritize projects",    de: "Projekte priorisieren" },
  "jarvis.qa.show_risks":           { en: "Show risks",             de: "Risiken anzeigen" },
  "jarvis.qa.summarize_running":    { en: "Summarize running work", de: "Laufende Arbeit zusammenfassen" },
  "jarvis.qa.define_next_move":     { en: "Define next move",       de: "Nächsten Schritt festlegen" },
  // Empty-state welcome block (Visual Fidelity Sprint — Higgsfield
  // Focus-Deck-Referenz): static hint text, not clickable — no new
  // send-on-click behavior was added along with the visual polish.
  "jarvis.suggestion.try":    { en: "Try:",               de: "Versuch's mit:" },
  "jarvis.suggestion.1":      { en: "Review my project status", de: "Meinen Projektstatus prüfen" },
  "jarvis.suggestion.3":      { en: "Plan my day",        de: "Meinen Tag planen" },

  // ── Jarvis suggested actions (JARVIS-C1 — Command Layer) ────────────────────
  "jarvis.suggested_action.heading":       { en: "Proposal",          de: "Vorschlag" },
  "jarvis.suggested_action.team_type":     { en: "Team",              de: "Team" },
  "jarvis.suggested_action.target_repo":   { en: "Repo",              de: "Repo" },
  "jarvis.suggested_action.risk":          { en: "Risk",              de: "Risiko" },
  "jarvis.suggested_action.risk.low":      { en: "low",               de: "niedrig" },
  "jarvis.suggested_action.risk.medium":   { en: "medium",            de: "mittel" },
  "jarvis.suggested_action.risk.high":     { en: "high",              de: "hoch" },
  "jarvis.suggested_action.requires_approval_yes": { en: "Needs approval for every step", de: "Jeder Schritt braucht Freigabe" },
  "jarvis.suggested_action.requires_approval_no":  { en: "Standard approval scope", de: "Standard-Freigabe-Rahmen" },
  "jarvis.suggested_action.confirm":       { en: "Confirm",           de: "Bestätigen" },
  "jarvis.suggested_action.reject":        { en: "Reject",            de: "Ablehnen" },
  "jarvis.suggested_action.deciding":      { en: "Working...",        de: "Wird verarbeitet..." },
  "jarvis.suggested_action.confirmed":     { en: "Work order created", de: "Work Order angelegt" },
  "jarvis.suggested_action.rejected":      { en: "Rejected",          de: "Abgelehnt" },
  "jarvis.suggested_action.view_work_order": { en: "View work order", de: "Work Order ansehen" },
  "jarvis.suggested_action.error_retry":   { en: "Failed — try again:", de: "Fehlgeschlagen — nochmal versuchen:" },

  // ── Jarvis Intelligence States (contextual workspace pass) ──────────────────
  // Kickers: the small line above "Jarvis" naming what's currently in view.
  "jarvis.kicker.home":             { en: "Home",                     de: "Home" },
  "jarvis.kicker.projects_none":    { en: "Projects — no selection",  de: "Projekte — keine Auswahl" },
  "jarvis.kicker.project_selected": { en: "Project selected",         de: "Projekt ausgewählt" },
  "jarvis.kicker.operator":         { en: "Operator",                 de: "Operator" },
  "jarvis.kicker.daily_plan":       { en: "Daily plan",               de: "Tagesplan" },
  "jarvis.kicker.settings":         { en: "Settings",                 de: "Einstellungen" },

  "jarvis.panel.quick_intelligence_label": { en: "Quick intelligence",      de: "Schnelle Analyse" },
  "jarvis.panel.next_steps_label":         { en: "Possible next steps",     de: "Mögliche nächste Schritte" },
  "jarvis.panel.decisions_label":          { en: "Recent decisions",        de: "Letzte Entscheidungen" },

  // Context snapshot field labels — only rendered when the field's real
  // value exists (see JarvisContextSnapshot); never fabricated.
  "jarvis.snapshot.status":              { en: "Status",              de: "Status" },
  "jarvis.snapshot.priority":            { en: "Priority",            de: "Priorität" },
  "jarvis.snapshot.next_move":           { en: "Next move",           de: "Nächster Schritt" },
  "jarvis.snapshot.risk":                { en: "Risk / blocker",      de: "Risiko / Blocker" },
  "jarvis.snapshot.today":               { en: "Today",               de: "Heute" },
  "jarvis.snapshot.decisions":           { en: "Needs decision",      de: "Entscheidung nötig" },
  "jarvis.snapshot.running":             { en: "In progress",         de: "In Arbeit" },
  "jarvis.snapshot.no_plan":             { en: "No plan generated yet", de: "Noch kein Plan erstellt" },
  "jarvis.snapshot.plan_for":            { en: "Plan for",            de: "Plan für" },
  "jarvis.snapshot.awaiting_approval":   { en: "awaiting approval",   de: "wartet auf Freigabe" },
  "jarvis.snapshot.in_progress_suffix":  { en: "in progress",         de: "in Arbeit" },

  // Quick-intelligence descriptions/working/result labels — only defined for
  // actions that get the bespoke "working state -> mode label" treatment;
  // actions without one fall back to the generic jarvis.thinking label and
  // the plain "Jarvis" role label (see JarvisChat.tsx).
  "jarvis.qa.analyze_risks":          { en: "Analyze risks",                        de: "Risiken analysieren" },
  "jarvis.qa.analyze_risks_desc":     { en: "Review blockers and weak points",      de: "Blocker und Schwachstellen prüfen" },
  "jarvis.qa.analyze_risks_working":  { en: "Analyzing risks…",                     de: "Risiken werden analysiert…" },
  "jarvis.qa.analyze_risks_result":   { en: "Risk analysis",                        de: "Risikoanalyse" },
  "jarvis.qa.review_progress":        { en: "Review progress",                      de: "Fortschritt prüfen" },
  "jarvis.qa.review_progress_desc":   { en: "Assess current state and recent movement", de: "Aktuellen Stand und Bewegung einschätzen" },
  "jarvis.qa.review_progress_working": { en: "Reviewing project…",                  de: "Projekt wird geprüft…" },
  "jarvis.qa.review_progress_result": { en: "Progress review",                      de: "Fortschrittsprüfung" },
  "jarvis.qa.define_next_move_desc":  { en: "Turn context into one concrete next step", de: "Kontext in einen konkreten nächsten Schritt verwandeln" },
  "jarvis.qa.define_next_move_working": { en: "Defining next move…",                de: "Nächster Schritt wird festgelegt…" },
  "jarvis.qa.define_next_move_result": { en: "Next move",                           de: "Nächster Schritt" },
  "jarvis.qa.create_action":          { en: "Create action",                        de: "Aktion erstellen" },
  "jarvis.qa.create_action_desc":     { en: "Prepare an executable Suggested Action", de: "Eine ausführbare Aktion vorbereiten" },
  "jarvis.qa.create_action_working":  { en: "Preparing action…",                    de: "Aktion wird vorbereitet…" },
  "jarvis.qa.create_action_result":   { en: "Suggested action",                     de: "Vorgeschlagene Aktion" },

  "jarvis.qa.review_today_desc":      { en: "Assess priorities and time blocks for today.", de: "Prioritäten und Zeitblöcke für heute prüfen." },
  "jarvis.qa.review_today_working":   { en: "Reviewing today's plan…",              de: "Heutiger Plan wird geprüft…" },
  "jarvis.qa.review_today_result":    { en: "Today's review",                       de: "Tagesrückblick" },
  "jarvis.qa.check_blocked_desc":     { en: "See what's waiting on your approval.", de: "Sehen, was auf deine Freigabe wartet." },
  "jarvis.qa.check_blocked_working":  { en: "Checking blocked work…",               de: "Blockierte Arbeit wird geprüft…" },
  "jarvis.qa.check_blocked_result":   { en: "Blocked work",                         de: "Blockierte Arbeit" },
  "jarvis.qa.prioritize_projects_desc": { en: "Decide what deserves attention first.", de: "Entscheiden, was zuerst Aufmerksamkeit braucht." },
  "jarvis.qa.prioritize_projects_working": { en: "Prioritizing projects…",          de: "Projekte werden priorisiert…" },
  "jarvis.qa.prioritize_projects_result": { en: "Project priorities",               de: "Projektprioritäten" },
  "jarvis.qa.plan_day_desc":          { en: "Turn today's context into a plan.",    de: "Den heutigen Kontext in einen Plan verwandeln." },
  "jarvis.qa.plan_day_working":       { en: "Planning your day…",                   de: "Dein Tag wird geplant…" },
  "jarvis.qa.plan_day_result":        { en: "Day plan",                             de: "Tagesplan" },

  "jarvis.suggestion.1_desc":         { en: "Check status, priority and risk across your projects.", de: "Status, Priorität und Risiko deiner Projekte prüfen." },
  "jarvis.qa.show_risks_desc":        { en: "Surface risks across active projects.", de: "Risiken über aktive Projekte hinweg aufdecken." },
  "jarvis.qa.summarize_running_desc": { en: "See what's currently executing.",      de: "Sehen, was gerade läuft." },

  // ── Settings (Visual Fidelity Sprint — Higgsfield Focus-Deck-Referenz) ──────
  "settings.title":           { en: "Settings",           de: "Einstellungen" },
  "settings.subtitle":        { en: "Manage your account, language and AI settings.", de: "Verwalte dein Konto, deine Sprache und KI-Einstellungen." },
  "settings.account":         { en: "Account",            de: "Konto" },
  "settings.account_desc":    { en: "Your sign-in details and session controls.", de: "Deine Anmeldedaten und Sitzungsverwaltung." },
  "settings.signed_in":       { en: "Signed in",          de: "Angemeldet" },
  "settings.sign_out":        { en: "Sign out",           de: "Abmelden" },
  "settings.language":        { en: "Language",           de: "Sprache" },
  "settings.language_desc":   { en: "Choose your preferred language for the interface.", de: "Wähle deine bevorzugte Sprache für die Oberfläche." },
  "settings.language_saved":  { en: "Language updated.",  de: "Sprache aktualisiert." },
  "settings.ai_model":        { en: "AI Model",           de: "KI-Modell" },
  "settings.ai_model_desc":   { en: "The AI model used by CommandPilot.", de: "Das von CommandPilot verwendete KI-Modell." },
  // No internal/dev-facing detail (".env") shown to the user — just the
  // model name and that it's the active one.
  "settings.ai_model_active": { en: "Active AI model", de: "Aktives KI-Modell" },
  "settings.runner.title": { en: "Local runner", de: "Runner verbinden" },
  "settings.runner.desc": {
    en: "Connect a local machine so Jarvis-approved work orders can actually run — no tokens, just a code.",
    de: "Verbinde einen lokalen Rechner, damit freigegebene Work Orders wirklich ausgeführt werden können — kein Token, nur ein Code.",
  },
  "settings.runner.code_label": { en: "Code from the runner", de: "Code vom Runner" },
  "settings.runner.label_label": { en: "Name (optional)", de: "Name (optional)" },
  "settings.runner.label_placeholder": { en: "e.g. Work laptop", de: "z. B. Arbeitslaptop" },
  "settings.runner.connect": { en: "Connect", de: "Verbinden" },
  "settings.runner.connected_as": { en: "Connected: {label}", de: "Verbunden: {label}" },
  "settings.runner.hint": {
    en: "Run \"python scripts/run_work_order_daemon.py --pair\" on the machine you want to connect — it will print a code to enter here.",
    de: "Führe \"python scripts/run_work_order_daemon.py --pair\" auf dem Rechner aus, den du verbinden willst — er zeigt einen Code, den du hier einträgst.",
  },
  "settings.runner.empty": { en: "No runner connected yet.", de: "Noch kein Runner verbunden." },
  "settings.runner.load_error": { en: "Could not load connections:", de: "Verbindungen konnten nicht geladen werden:" },
  "settings.runner.connected_since": { en: "connected", de: "verbunden seit" },
  "settings.runner.last_used": { en: "last used", de: "zuletzt aktiv" },
  "settings.runner.never_used": { en: "never used yet", de: "noch nie aktiv" },
  "settings.runner.revoke": { en: "Disconnect", de: "Trennen" },

  // ── Login ──────────────────────────────────────────────────────────────────
  "login.title":              { en: "Log in to CommandPilot", de: "Bei CommandPilot anmelden" },
  "login.session_expired":    { en: "Your session expired. Please log in again.", de: "Deine Sitzung ist abgelaufen. Bitte melde dich erneut an." },
  "login.email":              { en: "Email",              de: "E-Mail" },
  "login.password":           { en: "Password",           de: "Passwort" },
  "login.submit":             { en: "Log in",             de: "Anmelden" },
  "login.new_here":           { en: "New here?",          de: "Neu hier?" },
  "login.create_account":     { en: "Create an account",  de: "Konto erstellen" },

  // ── Signup ─────────────────────────────────────────────────────────────────
  "signup.title":             { en: "Create your CommandPilot account", de: "CommandPilot-Konto erstellen" },
  "signup.check_email":       { en: "Check your email to confirm your account, then log in.", de: "Prüfe deine E-Mails, um dein Konto zu bestätigen, und melde dich dann an." },
  "signup.name":              { en: "Name",               de: "Name" },
  "signup.email":             { en: "Email",              de: "E-Mail" },
  "signup.password":          { en: "Password",           de: "Passwort" },
  "signup.submit":            { en: "Sign up",            de: "Registrieren" },
  "signup.have_account":      { en: "Already have an account?", de: "Bereits ein Konto?" },
  "signup.login_link":        { en: "Log in",             de: "Anmelden" },

  // ── Plan detail ────────────────────────────────────────────────────────────
  "plan.back":                { en: "Back",               de: "Zurück" },
  "plan.start_review":        { en: "Evening Review",     de: "Abend-Reflexion" },
  "plan.load_error":          { en: "Could not load plan.", de: "Tagesplan konnte nicht geladen werden." },

  // ── Rules manager ──────────────────────────────────────────────────────────
  "rules.rule":               { en: "rule",               de: "Regel" },
  "rules.rules":              { en: "rules",              de: "Regeln" },
  "rules.active_suffix":      { en: "— active rules are injected into every AI plan.", de: "— fließen in jeden Tagesplan ein." },
  "rules.add":                { en: "Add Rule",           de: "Regel hinzufügen" },
  "rules.form_title":         { en: "Title",              de: "Titel" },
  "rules.form_rule":          { en: "Rule",               de: "Regel" },
  "rules.form_category":      { en: "Category",           de: "Kategorie" },
  "rules.form_priority":      { en: "Priority",           de: "Priorität" },
  "rules.save":               { en: "Save Rule",          de: "Regel speichern" },
  "rules.empty_title":        { en: "No rules yet",       de: "Noch keine Regeln" },
  "rules.empty_desc":         { en: "Rules are used as context by the AI to personalize every plan. Add your operating principles.", de: "Noch keine Regeln angelegt. Erstelle Leitplanken, damit CommandPilot besser versteht, wie du planen möchtest." },
  "rules.confirm_delete":     { en: "Delete this rule?",  de: "Diese Regel löschen?" },
  "rules.disable":            { en: "Disable",            de: "Deaktivieren" },
  "rules.enable":             { en: "Enable",             de: "Aktivieren" },

  // ── Buttons ────────────────────────────────────────────────────────────────
  "button.create_plan":       { en: "Create Plan",        de: "Tagesplan erstellen" },
  "button.retry":             { en: "Try Again",          de: "Erneut versuchen" },
  "button.start_checkin":     { en: "Start Check-in",     de: "Tagesstart beginnen" },
  "button.open_plan":         { en: "Open Today's Plan",  de: "Tagesplan öffnen" },
  "button.start_review":      { en: "Start Review",       de: "Abend-Reflexion beginnen" },
  "button.save":              { en: "Save",               de: "Speichern" },
  "button.cancel":            { en: "Cancel",             de: "Abbrechen" },
  "button.back":              { en: "Back",               de: "Zurück" },
  "button.logout":            { en: "Log out",            de: "Abmelden" },
  "button.login":             { en: "Log in",             de: "Anmelden" },
  "button.signup":            { en: "Sign up",            de: "Konto erstellen" },
  "button.new_rule":          { en: "New Rule",           de: "Neue Regel" },
  "button.edit":              { en: "Edit",               de: "Bearbeiten" },
  "button.remove":            { en: "Remove",             de: "Entfernen" },

  // ── Plan sections ──────────────────────────────────────────────────────────
  "plan.day_mode":            { en: "Day Mode",           de: "Tagesmodus" },
  "plan.main_outcome":        { en: "Key Outcome",        de: "Wichtigstes Ergebnis" },
  "plan.key_steps":           { en: "Three Most Important Steps", de: "Die 3 wichtigsten Schritte" },
  "plan.structure":           { en: "Day Structure",      de: "Tagesstruktur" },
  "plan.energy_body":         { en: "Energy & Body",      de: "Energie & Körper" },
  "plan.evening_reflection":  { en: "Evening Reflection", de: "Abend-Reflexion" },
  "plan.recent":              { en: "Previous Plans",     de: "Letzte Tagespläne" },

  // ── Morning check-in fields ────────────────────────────────────────────────
  "field.wake_time":          { en: "Woke up at",         de: "Aufgestanden um" },
  "field.energy":             { en: "Energy",             de: "Energie" },
  "field.sleep":              { en: "Sleep",              de: "Schlaf" },
  "field.body":               { en: "Body",               de: "Körper" },
  "field.mood":               { en: "Mood",               de: "Stimmung" },
  "field.fixed_events":       { en: "Fixed Events",       de: "Feste Termine" },
  "field.important_tasks":    { en: "Important Tasks",    de: "Wichtige Aufgaben" },
  "field.raw_input":          { en: "Free Note",          de: "Freie Notiz" },
  "field.available_hours":    { en: "Available Hours",    de: "Verfügbare Stunden" },
  "field.day_constraints":    { en: "Day Limits",         de: "Tagesgrenzen" },

  // ── Placeholders ───────────────────────────────────────────────────────────
  "ph.wake_time":             { en: "e.g. 06:45",         de: "z. B. 06:45" },
  "ph.energy":                { en: "How much energy do you have right now? (1–5)", de: "Wie viel Energie hast du gerade? (1–5)" },
  "ph.sleep":                 { en: "How did you sleep? (1–5)", de: "Wie hast du geschlafen? (1–5)" },
  "ph.body":                  { en: "Tension, pain, unusual fatigue?", de: "Spannung, Schmerzen, ungewöhnliche Müdigkeit?" },
  "ph.mood":                  { en: "In one word: how do you feel?", de: "In einem Wort: wie fühlst du dich?" },
  "ph.fixed_events":          { en: "What's fixed in your calendar today?", de: "Was steht heute fix im Kalender?" },
  "ph.important_tasks":       { en: "What really needs to happen today?", de: "Was muss heute wirklich passieren?" },
  "ph.raw_input":             { en: "Everything that's still on your mind.", de: "Alles, was dir noch im Kopf rumgeht." },
  "ph.available_hours":       { en: "How many hours for focused work?", de: "Wie viele Stunden für fokussierte Arbeit?" },
  "ph.day_constraints":       { en: "What's not possible today?", de: "Was geht heute nicht?" },

  // ── Empty states ───────────────────────────────────────────────────────────
  "empty.cockpit":            { en: "No plan yet for today. Start with the morning check-in when you're ready.", de: "Noch kein Tagesplan für heute. Starte deinen Tagesstart, wenn du bereit bist." },
  "empty.plans":              { en: "Nothing here yet.",  de: "Hier ist noch nichts." },
  "empty.first_plan":         { en: "Start with the first plan", de: "Ersten Tagesplan erstellen" },
  "empty.rules":              { en: "No rules yet. Start with one — more will come over time.", de: "Noch keine Regeln angelegt. Erstelle Leitplanken, damit CommandPilot besser versteht, wie du planen möchtest." },
  "empty.review":             { en: "Nothing reflected today. Three minutes is enough.", de: "Heute noch keine Reflexion. Drei Minuten reichen." },

  // ── Errors & help ──────────────────────────────────────────────────────────
  "error.session_expired":    { en: "You've been logged out. Log back in and you're good to go.", de: "Deine Sitzung ist abgelaufen. Bitte melde dich erneut an." },
  "error.plan_failed":        { en: "Your plan couldn't be created right now. Try again in a moment.", de: "Der Tagesplan konnte nicht erstellt werden. Bitte versuche es gleich noch einmal." },
  "error.load_failed":        { en: "Couldn't load. Try again in a moment.", de: "Konnte nicht geladen werden. Bitte versuche es gleich noch einmal." },
  "error.save_failed":        { en: "Couldn't save. Try again in a moment.", de: "Konnte nicht gespeichert werden. Bitte versuche es gleich noch einmal." },
  "error.login_failed":       { en: "Login failed. Check your email and password.", de: "Anmeldung fehlgeschlagen. Bitte prüfe E-Mail und Passwort." },
  "error.signup_failed":      { en: "Account couldn't be created. Check your details or try again in a moment.", de: "Konto konnte nicht erstellt werden. Bitte prüfe deine Eingaben und versuche es erneut." },
  "help.beta_notice":         { en: "CommandPilot is currently in private beta. Some things are not yet final.", de: "CommandPilot befindet sich in der privaten Testphase. Manches ist noch nicht final." },
  "help.report_issue":        { en: "If the error persists, please let me know.", de: "Wenn der Fehler bleibt, gib kurz Bescheid." },

  // ── Settings language ──────────────────────────────────────────────────────
  "settings.language.help":   { en: "The language applies to the entire interface. New plans will be created in the selected language. Existing plans remain in their original language.", de: "Die Sprache ändert die Oberfläche und zukünftige KI-Pläne. Bereits erstellte Pläne bleiben unverändert." },
  "settings.language.changed":{ en: "Language changed. Your next plan will be created in the new language.", de: "Sprache geändert. Dein nächster Tagesplan wird in der neuen Sprache erstellt." },

  // ── Auth ───────────────────────────────────────────────────────────────────
  "auth.welcome_back":        { en: "Welcome back",       de: "Willkommen zurück" },
  "auth.login.subtitle":      { en: "Log in to get to your cockpit.", de: "Melde dich an, um dein Cockpit zu öffnen." },
  "auth.signup.title":        { en: "Create account",     de: "Konto erstellen" },
  "auth.signup.subtitle":     { en: "A few steps, then your first day begins.", de: "Wenige Schritte, dann startet dein erster Tagesplan." },
  "auth.no_account":          { en: "No account yet? Sign up", de: "Noch kein Konto? Registrieren" },
  "auth.has_account":         { en: "Already registered? Log in", de: "Bereits registriert? Anmelden" },
  "auth.private_beta_hint":   { en: "CommandPilot is currently in private beta. If you don't have access yet, get in touch.", de: "CommandPilot ist in privater Testphase. Ohne Zugang einfach kurz melden." },

  // ── Projects ───────────────────────────────────────────────────────────────
  "projects.title":                { en: "Projects",             de: "Projekte" },
  "projects.subtitle":             { en: "Active projects feed into every morning plan.", de: "Aktive Projekte fließen in jeden Tagesplan ein." },
  "projects.add":                  { en: "Add Project",          de: "Projekt hinzufügen" },
  "projects.save":                 { en: "Save Project",         de: "Projekt speichern" },
  "projects.save_changes":         { en: "Save Changes",         de: "Änderungen speichern" },
  "projects.edit":                 { en: "Edit",                 de: "Bearbeiten" },
  "projects.archive":              { en: "Archive",              de: "Archivieren" },
  "projects.confirm_archive":      { en: "Archive this project?", de: "Dieses Projekt archivieren?" },
  "projects.empty_title":          { en: "No projects yet",      de: "Noch keine Projekte" },
  "projects.empty_desc":           { en: "Add your active projects here. Active and waiting projects will appear as context in your daily plan.", de: "Füge deine aktiven Projekte hinzu. Sie fließen als Kontext in deinen Tagesplan ein." },
  "projects.field_name":           { en: "Project Name",         de: "Projektname" },
  "projects.field_description":    { en: "Description (optional)", de: "Beschreibung (optional)" },
  "projects.field_next_action":    { en: "Next Action",          de: "Nächste Aktion" },
  "projects.field_next_action_ph": { en: "What's the single next step?", de: "Was ist der nächste konkrete Schritt?" },
  "projects.field_risk":           { en: "Risk / Blocker (optional)", de: "Risiko / Blocker (optional)" },
  "projects.field_risk_ph":        { en: "What could slow this down?", de: "Was könnte dieses Projekt bremsen?" },
  "projects.field_website_url":    { en: "Website (optional)", de: "Website (optional)" },
  "projects.field_website_url_ph": { en: "https://your-product.com", de: "https://dein-produkt.de" },
  "projects.field_status":         { en: "Status",               de: "Status" },
  "projects.field_priority":       { en: "Priority",             de: "Priorität" },
  "projects.status.active":        { en: "Active",               de: "Aktiv" },
  "projects.status.waiting":       { en: "Waiting",              de: "Wartend" },
  "projects.status.paused":        { en: "Paused",               de: "Pausiert" },
  "projects.status.backlog":       { en: "Backlog",              de: "Backlog" },
  "projects.status.done":          { en: "Done",                 de: "Erledigt" },
  "projects.status.archived":      { en: "Archived",             de: "Archiviert" },
  "projects.priority.high":        { en: "High",                 de: "Hoch" },
  "projects.priority.medium":      { en: "Medium",               de: "Mittel" },
  "projects.priority.low":         { en: "Low",                  de: "Niedrig" },
  "projects.summary.at_risk":      { en: "at risk",              de: "gefährdet" },
  "projects.detail.ask_jarvis":    { en: "Ask Jarvis about this project", de: "Jarvis zu diesem Projekt fragen" },
  "projects.detail.select_hint":   { en: "Select a project to see full details.", de: "Wähle ein Projekt, um alle Details zu sehen." },
  "projects.detail.empty_title":   { en: "No project selected",  de: "Kein Projekt ausgewählt" },

  // ── Background Operator / Dev Team Control Plane ──────────────────────────────
  "operator.title":                { en: "Background Operator",  de: "Background Operator" },
  // Deliberately doesn't claim "mock data" or "no execution" unconditionally
  // here anymore — both are now state-dependent (see mock_banner/live_banner
  // below, and the claude_code runner adapter for real execution) and a
  // static claim otherwise misrepresents a genuinely live, executing work
  // order as permanently a demo (OP-UX-001).
  "operator.subtitle":             { en: "Background dev team control plane.", de: "Control Plane fürs Background Dev Team." },
  "operator.mock_banner":          { en: "Demo Mode — API unavailable or request failed, showing seed data instead. No backend, no execution, no external access. Check the browser console for the actual error.", de: "Demo-Modus — API nicht erreichbar oder Anfrage fehlgeschlagen, zeige stattdessen Seed-Daten. Kein Backend, keine Ausführung, kein externer Zugriff. Details zum tatsächlichen Fehler stehen in der Browser-Konsole." },
  "operator.live_banner":          { en: "Live from the CommandPilot API. No execution, no external access yet.", de: "Live aus der CommandPilot-API. Noch keine Ausführung, kein externer Zugriff." },
  "operator.missing_context":      { en: "Missing context",      de: "Fehlender Kontext" },
  "operator.required":             { en: "required",             de: "erforderlich" },
  "operator.optional":             { en: "optional",             de: "optional" },
  "operator.empty_title":          { en: "No work orders",       de: "Keine Work Orders" },
  "operator.load_error":           { en: "Could not load this work order:", de: "Work Order konnte nicht geladen werden:" },
  "operator.empty_desc":           { en: "Background work orders will appear here once created.", de: "Background Work Orders erscheinen hier, sobald sie erstellt wurden." },
  "operator.back":                 { en: "Back to Operator",     de: "Zurück zum Operator" },

  // "running" needs a local runner (24.09.2026) — found during the five-day
  // self-test prep: nothing here executes automatically. Points at the
  // existing, already-correct "Local Runner" tab/commands (LocalRunnerPanel.tsx)
  // instead of restating a command here, so there is exactly one place the
  // real start command lives.
  "operator.running_needs_runner_banner": {
    en: "This work order is running — but nothing executes automatically. A local runner on your machine (or your running daemon) has to do the work. Open the \"Local Runner\" tab below for the exact start command.",
    de: "Diese Work Order läuft — aber nichts passiert automatisch. Ein lokaler Runner auf deinem Rechner (oder dein laufender Daemon) muss die Arbeit ausführen. Öffne unten den Tab „Lokaler Runner\" für den genauen Startbefehl.",
  },
  "operator.running_needs_runner_cta": { en: "Open Local Runner", de: "Lokalen Runner öffnen" },

  // Work order status (11 states)
  "operator.status.draft":             { en: "Draft",              de: "Entwurf" },
  "operator.status.approved":          { en: "Approved",           de: "Genehmigt" },
  "operator.status.queued":            { en: "Queued",             de: "Eingereiht" },
  "operator.status.running":           { en: "Running",            de: "Läuft" },
  "operator.status.needs_approval":    { en: "Needs Approval",     de: "Freigabe nötig" },
  "operator.status.blocked":           { en: "Blocked",            de: "Blockiert" },
  "operator.status.failed":            { en: "Failed",             de: "Fehlgeschlagen" },
  "operator.status.review_ready":      { en: "Review Ready",       de: "Review bereit" },
  "operator.status.accepted":          { en: "Accepted",           de: "Akzeptiert" },
  "operator.status.rework_requested":  { en: "Rework Requested",   de: "Überarbeitung angefordert" },
  "operator.status.cancelled":         { en: "Cancelled",          de: "Abgebrochen" },

  // Agent roles
  "operator.role.product":    { en: "Product Agent",   de: "Product Agent" },
  "operator.role.architect":  { en: "Architect Agent",  de: "Architect Agent" },
  "operator.role.coder":      { en: "Coder Agent",      de: "Coder Agent" },
  "operator.role.qa":         { en: "QA Agent",         de: "QA Agent" },
  "operator.role.reviewer":   { en: "Reviewer Agent",   de: "Reviewer Agent" },
  "operator.role.reporter":   { en: "Reporter Agent",   de: "Reporter Agent" },

  // Agent run status
  "operator.run_status.queued":    { en: "Queued",    de: "Eingereiht" },
  "operator.run_status.running":   { en: "Running",   de: "Läuft" },
  "operator.run_status.blocked":   { en: "Blocked",   de: "Blockiert" },
  "operator.run_status.failed":    { en: "Failed",    de: "Fehlgeschlagen" },
  "operator.run_status.completed": { en: "Completed", de: "Abgeschlossen" },

  // Artifact types
  "operator.artifact.plan":        { en: "Plan",         de: "Plan" },
  "operator.artifact.diff":        { en: "Diff",         de: "Diff" },
  "operator.artifact.test_output": { en: "Test Output",  de: "Test-Output" },
  "operator.artifact.review":      { en: "Review",       de: "Review" },
  "operator.artifact.summary":     { en: "Summary",      de: "Zusammenfassung" },
  "operator.artifact.screenshot":  { en: "Screenshot",   de: "Screenshot" },
  "operator.artifact.prompt":      { en: "Prompt",       de: "Prompt" },

  // Activity log levels
  "operator.log.info":              { en: "Info",              de: "Info" },
  "operator.log.warning":           { en: "Warning",           de: "Warnung" },
  "operator.log.error":             { en: "Error",             de: "Fehler" },
  "operator.log.approval_required": { en: "Approval Required", de: "Freigabe nötig" },

  // Review verdicts
  "operator.verdict.ready_for_review": { en: "Ready for Review", de: "Bereit zum Review" },
  "operator.verdict.needs_fix":        { en: "Needs Fix",        de: "Braucht Korrektur" },
  "operator.verdict.blocked":          { en: "Blocked",          de: "Blockiert" },
  "operator.verdict.unsafe":           { en: "Unsafe",           de: "Unsicher" },

  // Detail page sections
  "operator.section.goal":                { en: "Goal",                     de: "Ziel" },
  "operator.section.repo":                { en: "Repository",               de: "Repository" },
  "operator.section.created_by":          { en: "Created by",               de: "Erstellt von" },
  "operator.section.time_limit":          { en: "Time limit",               de: "Zeitlimit" },
  "operator.section.minutes":             { en: "min",                      de: "Min." },
  "operator.section.acceptance_criteria": { en: "Acceptance criteria",      de: "Akzeptanzkriterien" },
  "operator.section.approval_scope":      { en: "Approval Scope",           de: "Approval Scope" },
  "operator.section.allowed_actions":     { en: "Allowed",                  de: "Erlaubt" },
  "operator.section.requires_approval":   { en: "Requires approval",       de: "Braucht Freigabe" },
  "operator.section.blocked_actions":     { en: "Blocked",                  de: "Blockiert" },
  "operator.section.allowed_paths":       { en: "Allowed paths",            de: "Erlaubte Pfade" },
  "operator.section.blocked_paths":       { en: "Blocked paths",            de: "Blockierte Pfade" },
  "operator.section.max_cost":            { en: "Max cost",                 de: "Max. Kosten" },
  "operator.section.agent_runs":          { en: "Agent Runs",               de: "Agent Runs" },
  "operator.section.activity_log":        { en: "Activity Log",             de: "Activity Log" },
  "operator.section.artifacts":           { en: "Artifacts",                de: "Artifacts" },
  "operator.section.review_package":      { en: "Review Package",           de: "Review Package" },
  "operator.section.recommended_next_step": { en: "Recommended next step", de: "Empfohlener nächster Schritt" },
  "operator.section.summary":             { en: "Summary",                  de: "Zusammenfassung" },
  "operator.section.files_changed":       { en: "Files changed",           de: "Geänderte Dateien" },
  "operator.section.tests_run":           { en: "Tests run",                de: "Ausgeführte Tests" },
  "operator.section.risks":               { en: "Risks",                    de: "Risiken" },
  "operator.section.open_questions":      { en: "Open questions",          de: "Offene Fragen" },
  "operator.section.needs_human_review":  { en: "Needs human review",      de: "Braucht menschliches Review" },
  "operator.section.safety_rules":        { en: "Safety Rules",             de: "Safety Rules" },
  "operator.section.autonomous_allowed":  { en: "Autonomous — allowed",     de: "Autonom erlaubt" },
  "operator.section.needs_approval_list": { en: "Needs approval",          de: "Braucht Freigabe" },
  "operator.section.blocked_list":        { en: "Blocked",                  de: "Blockiert" },
  "operator.section.no_runs":             { en: "No agent runs yet.",       de: "Noch keine Agent Runs." },
  "operator.section.no_activity":         { en: "No activity yet.",         de: "Noch keine Activity." },
  "operator.section.no_artifacts":        { en: "No artifacts yet.",        de: "Noch keine Artifacts." },
  "operator.section.no_review_package":   { en: "No review package yet — work order is not review-ready.", de: "Noch kein Review Package — Work Order ist noch nicht review-ready." },
  "operator.section.execution_plan":      { en: "Execution Plan",           de: "Execution Plan" },
  "operator.section.technical_details":   { en: "Technical details",        de: "Technische Details" },
  "operator.section.progress":            { en: "Progress",                 de: "Fortschritt" },
  "operator.section.no_steps":            { en: "No steps planned yet.",    de: "Noch keine Steps geplant." },
  "operator.section.output_summary":      { en: "Output",                   de: "Ergebnis" },
  "operator.section.blocked_reason":      { en: "Blocked reason",           de: "Blockiert wegen" },
  "operator.section.no_scope_warning":    { en: "No approval scope — this work order has no defined boundaries. Treat with extra caution.", de: "Kein Approval Scope — dieses Work Order hat keine definierten Grenzen. Besondere Vorsicht geboten." },
  "operator.section.no_blocked_actions_warning": { en: "This approval scope has no blocked-actions list.", de: "Dieser Approval Scope hat keine Liste blockierter Aktionen." },

  // Live execution / activity stream — see components/operator/StepPipeline.tsx, ActivityFeed.tsx
  "operator.live.badge":         { en: "Live",            de: "Live" },
  "operator.live.stream_title":  { en: "Activity Stream", de: "Activity Stream" },

  // Work order step status (7 states)
  "operator.step_status.pending":   { en: "Pending",   de: "Ausstehend" },
  "operator.step_status.queued":    { en: "Queued",    de: "Eingereiht" },
  "operator.step_status.running":   { en: "Running",   de: "Läuft" },
  "operator.step_status.blocked":   { en: "Blocked",   de: "Blockiert" },
  "operator.step_status.completed": { en: "Completed", de: "Abgeschlossen" },
  "operator.step_status.failed":    { en: "Failed",    de: "Fehlgeschlagen" },
  "operator.step_status.skipped":   { en: "Skipped",   de: "Übersprungen" },

  // Lifecycle controls
  "operator.lifecycle.title":            { en: "Lifecycle",              de: "Lifecycle" },
  "operator.lifecycle.approve":          { en: "Approve",                de: "Genehmigen" },
  "operator.lifecycle.mark_queued":      { en: "Mark Queued",            de: "Als eingereiht markieren" },
  "operator.lifecycle.mark_running":     { en: "Mark Running",           de: "Als laufend markieren" },
  "operator.lifecycle.request_rework":   { en: "Request Rework",         de: "Überarbeitung anfordern" },
  "operator.lifecycle.accept":           { en: "Accept",                 de: "Akzeptieren" },
  "operator.lifecycle.requeue":          { en: "Requeue",                de: "Erneut einreihen" },
  "operator.lifecycle.cancel":           { en: "Cancel",                 de: "Abbrechen" },
  "operator.lifecycle.demo_note":        { en: "Showing seed data — connect the API to control a real work order.", de: "Zeigt Seed-Daten — für echte Steuerung API verbinden." },
  "operator.lifecycle.cancel_confirm_message": { en: "Cancel this work order? This cannot be undone. If a runner is currently executing it, cancelling here does not stop that process immediately — it only marks the work order withdrawn so its eventual result can no longer be imported.", de: "Dieses Work Order abbrechen? Das kann nicht rückgängig gemacht werden. Falls gerade ein Runner läuft, wird dieser Prozess dadurch nicht sofort gestoppt — nur der Work-Order-Status wird zurückgezogen, sodass ein späteres Ergebnis nicht mehr importiert werden kann." },
  "operator.lifecycle.cancel_confirm_yes": { en: "Yes, cancel",             de: "Ja, abbrechen" },
  "operator.lifecycle.cancel_confirm_no":  { en: "No, keep it",            de: "Nein, behalten" },
  "operator.lifecycle.stop":               { en: "Stop",                   de: "Stoppen" },
  "operator.lifecycle.stop_confirm_message": { en: "Stop this work order? The local runner checks for this roughly every 15 seconds and will kill its process as soon as it sees it — any work from this run that wasn't already saved is lost.", de: "Dieses Work Order stoppen? Der lokale Runner prüft das etwa alle 15 Sekunden und beendet seinen Prozess, sobald er es sieht — noch nicht gespeicherte Arbeit aus diesem Lauf geht dabei verloren." },
  "operator.lifecycle.stop_confirm_yes":   { en: "Yes, stop",              de: "Ja, stoppen" },
  "operator.lifecycle.autonomous_start":   { en: "Start autonomously",     de: "Autonom starten" },
  "operator.lifecycle.autonomous_start_confirm_message": {
    en: "Runs fully automatically until review_ready — every ticketplan step, no further clicks — using whatever adapter/budget your local daemon (scripts/run_work_order_daemon.py) is configured with. \"Accept\" afterwards stays your call, and a sandbox run's diff always stays an artifact to review, never applied automatically. Nothing happens if no daemon is currently running.",
    de: "Läuft komplett automatisch bis review_ready — jeder Ticketplan-Step, ohne weitere Klicks — mit dem Adapter/Budget, das dein lokaler Daemon (scripts/run_work_order_daemon.py) gerade konfiguriert hat. \"Akzeptieren\" bleibt danach deine Entscheidung, und der Diff eines Sandbox-Laufs bleibt immer ein Artefact zum Prüfen, wird nie automatisch angewendet. Passiert nichts, falls gerade kein Daemon läuft.",
  },
  "operator.lifecycle.autonomous_start_confirm_yes": { en: "Yes, start autonomously", de: "Ja, autonom starten" },

  // Agent run attempts (CP-OP02 bounded auto-retry)
  "operator.agent_run.attempt_label":        { en: "Attempt",                             de: "Attempt" },
  "operator.agent_run.retry_reason_prefix":  { en: "Auto-retry — technical failure in attempt", de: "Auto-Retry — technischer Fehler in Attempt" },

  // Work order failure banner (CP-OP02)
  "operator.failure_banner.title": { en: "This work order failed.", de: "Dieses Work Order ist fehlgeschlagen." },
  "operator.failure_reason.generic": { en: "No further detail was recorded for this failure.", de: "Für diesen Fehlschlag wurde kein weiterer Grund erfasst." },
  "operator.failure_reason.technical_failure_with_worktree_changes": { en: "A technical failure occurred and the working tree had already changed — auto-retry was skipped to avoid compounding a half-finished change. Check the run's output log and decide manually.", de: "Ein technischer Fehler ist aufgetreten und der Working Tree hatte sich bereits verändert — Auto-Retry wurde übersprungen, um keine halbfertige Änderung zu verschlimmern. Bitte Run-Log prüfen und manuell entscheiden." },
  "operator.failure_reason.technical_failure_retries_exhausted": { en: "All automatic retry attempts (max. 3) were exhausted after repeated technical failures. Human intervention is required.", de: "Alle automatischen Retry-Versuche (max. 3) wurden nach wiederholten technischen Fehlern aufgebraucht. Menschliches Eingreifen nötig." },
  "operator.failure_reason.technical_failure_budget_exhausted": { en: "The configured budget was used up across retry attempts before a result could be produced.", de: "Das konfigurierte Budget wurde über die Retry-Versuche hinweg aufgebraucht, bevor ein Ergebnis vorlag." },

  // Runner prompt
  "operator.prompt.generate": { en: "Generate Runner Prompt", de: "Runner-Prompt generieren" },
  "operator.prompt.copy":     { en: "Copy Prompt",            de: "Prompt kopieren" },
  "operator.prompt.copied":   { en: "Copied!",                de: "Kopiert!" },
  "operator.prompt.title":    { en: "Runner Prompt",          de: "Runner-Prompt" },
  "operator.prompt.hint":     { en: "Paste this directly into Claude Code or Codex.", de: "Direkt in Claude Code oder Codex einfügen." },

  // Local runner harness (OP-Runner-002)
  "operator.runner.title":       { en: "Local Runner",          de: "Local Runner" },
  "operator.runner.note":        { en: "Execution runs locally on your machine — CommandPilot's backend never runs shell commands or launches Claude Code itself.", de: "Ausführung läuft lokal auf deiner Maschine — das CommandPilot-Backend führt selbst keine Shell-Kommandos aus und startet auch nicht Claude Code." },
  "operator.runner.powershell_note": { en: "Commands below are PowerShell — copy each one as-is.", de: "Die Befehle unten sind PowerShell — jeden genau so kopieren." },
  "operator.runner.cross_repo_title": { en: "Cross-repo work order", de: "Cross-Repo Work Order" },
  "operator.runner.cross_repo_control_plane": { en: "Control Plane: CommandPilot — every command below (runner start, execute, import) runs here, in this repo.", de: "Control Plane: CommandPilot — jeder Befehl unten (Runner starten, ausführen, importieren) läuft hier, in diesem Repo." },
  "operator.runner.cross_repo_target": { en: "Execution Context (Claude/Codex works here, not in CommandPilot):", de: "Execution Context (Claude/Codex arbeitet hier, nicht in CommandPilot):" },
  "operator.runner.cross_repo_import": { en: "Result import always happens back in CommandPilot (step 5 below) — never inside the target repo.", de: "Der Ergebnis-Import passiert immer zurück in CommandPilot (Schritt 5 unten) — niemals im Target Repo." },
  "operator.runner.step1_title": { en: "1. Set your API token (once per PowerShell window)", de: "1. API-Token setzen (einmal pro PowerShell-Fenster)" },
  "operator.runner.step1_hint":  { en: "Replace the text between the quotes with your real token from Runbook §1 — never share this token anywhere, including in chat.", de: "Ersetze den Text zwischen den Anführungszeichen durch deinen echten Token aus Runbook §1 — diesen Token nirgends teilen, auch nicht im Chat." },
  "operator.runner.step2_title": { en: "2. Approve and queue this work order", de: "2. Diese Work Order genehmigen und einreihen" },
  "operator.runner.step2_hint":  { en: "Use the Lifecycle buttons above: Approve, then Mark Queued. Do NOT click Mark Running yourself — the runner does that in the next step.", de: "Nutze die Lifecycle-Buttons oben: Genehmigen, dann Als eingereiht markieren. NICHT selbst auf Als laufend markieren klicken — das macht der Runner im nächsten Schritt." },
  "operator.runner.step3_title": { en: "3. Start the runner (writes the prompt, sets status to running)", de: "3. Runner starten (schreibt den Prompt, setzt Status auf running)" },
  "operator.runner.step4_manual_title": { en: "4a. Manual: paste prompt.md into Claude Code / Codex", de: "4a. Manuell: prompt.md in Claude Code / Codex einfügen" },
  "operator.runner.step4_manual_hint": { en: "Open the prompt file below, paste its contents into a fresh Claude Code or Codex session, and save its result JSON as result.json in the same folder.", de: "Öffne die Prompt-Datei unten, füge den Inhalt in eine neue Claude Code- oder Codex-Session ein und speichere das Ergebnis-JSON als result.json im selben Ordner." },
  "operator.runner.step4_auto_title": { en: "4b. Or: let the claude_code adapter run it (semi-automatic)", de: "4b. Oder: den claude_code-Adapter ausführen lassen (teilautomatisch)" },
  "operator.runner.step4_auto_hint": { en: "Requires the claude CLI, and Claude Code must already be trusted for this workspace (run `claude` here interactively once if you haven't). Not fully unattended — see Runbook.", de: "Braucht die claude-CLI, und Claude Code muss für diesen Workspace bereits als vertrauenswürdig bestätigt sein (falls noch nicht geschehen: `claude` einmal interaktiv hier ausführen). Nicht vollständig unbeaufsichtigt — siehe Runbook." },
  "operator.runner.step5_title": { en: "5. Import the result", de: "5. Ergebnis importieren" },
  "operator.runner.hint":        { en: "Session files land in tmp/work-order-runs/<id>/ (using this work order's real id) — check run.log there if something goes wrong.", de: "Session-Dateien landen unter tmp/work-order-runs/<id>/ (mit der echten ID dieser Work Order) — bei Problemen dort run.log prüfen." },
  "operator.runner.copy":        { en: "Copy", de: "Kopieren" },
  "operator.runner.copied":      { en: "Copied!", de: "Kopiert!" },
  "operator.runner.badge_no_credits":   { en: "no Claude credits used", de: "keine Claude-Credits" },
  "operator.runner.badge_uses_credits": { en: "uses Claude credits", de: "verbraucht Claude-Credits" },
  "operator.runner.budget_required_hint": {
    en: "Required: claude_code execute refuses to run without an explicit budget — either --max-budget-usd (shown above, edit the value) or a COMMANDPILOT_CLAUDE_MAX_BUDGET_USD environment variable. Never defaults silently. Prompt-file / manual paste above cost nothing from CommandPilot's side.",
    de: "Pflicht: claude_code execute startet nicht ohne explizites Budget — entweder --max-budget-usd (oben, Wert anpassen) oder die Umgebungsvariable COMMANDPILOT_CLAUDE_MAX_BUDGET_USD. Es gibt nie einen stillen Standardwert. Prompt-file / manuelles Einfügen oben kosten nichts von CommandPilot-Seite.",
  },

  // Per-step execution toggle + sandbox adapter (applies to both 4b/4c below)
  "operator.runner.per_step_toggle_label": { en: "Step-by-step execution (--per-step)", de: "Step-für-Step-Ausführung (--per-step)" },
  "operator.runner.per_step_toggle_hint": {
    en: "One call per ticket-plan step instead of one call for the whole order — each step's status updates live as it finishes, instead of only at the very end. Costs more (N calls instead of 1). Applies to both commands below.",
    de: "Ein Aufruf pro Ticketplan-Step statt ein Aufruf für die ganze Work Order — jeder Step-Status aktualisiert sich live, sobald er fertig ist, statt erst ganz am Ende. Kostet mehr (N Aufrufe statt 1). Gilt für beide Befehle unten.",
  },
  "operator.runner.step4_sandbox_title": { en: "4c. Or: fully automatic in an isolated Docker sandbox", de: "4c. Oder: vollautomatisch in einer isolierten Docker-Sandbox" },
  "operator.runner.step4_sandbox_hint": {
    en: "Runs unattended inside a disposable container + disposable repo clone — your real working tree is never touched. Changes land as a diff artifact on this work order for you to review, never applied automatically.",
    de: "Läuft unbeaufsichtigt in einem Wegwerf-Container + einem Wegwerf-Repo-Klon — dein echtes Arbeitsverzeichnis wird nie angefasst. Änderungen landen als Diff-Artefact an dieser Work Order zum Prüfen, werden nie automatisch angewendet.",
  },
  "operator.runner.sandbox_docker_required_hint": {
    en: "Requires Docker (one-time: docker build -t commandpilot-sandbox:latest scripts/sandbox).",
    de: "Braucht Docker (einmalig: docker build -t commandpilot-sandbox:latest scripts/sandbox).",
  },
  "operator.runner.waiting_for_daemon_hint": {
    en: "Waiting for a local daemon — start scripts/run_work_order_daemon.py if it isn't already running; it'll pick this up automatically.",
    de: "Wartet auf einen lokalen Daemon — scripts/run_work_order_daemon.py starten, falls er nicht schon läuft; er holt das automatisch ab.",
  },

  // Runner phase indicator + current run folder (OP-Workflow-UI-001)
  "operator.runner.run_folder_label": { en: "Current run folder", de: "Aktueller Run-Ordner" },
  "operator.runner.phase.not_started": { en: "Not started yet", de: "Noch nicht gestartet" },
  "operator.runner.phase.not_started_hint": {
    en: "Run step 3 below to generate the prompt and start tracking this run.",
    de: "Führe Schritt 3 unten aus, um den Prompt zu erzeugen und diesen Run zu verfolgen.",
  },
  "operator.runner.phase.prompt_generated": { en: "Prompt generated", de: "Prompt erzeugt" },
  "operator.runner.phase.prompt_generated_hint": {
    en: "Work order is running, but no AgentRun record is confirmed yet. If you haven't started a local runner yet, run step 3 (or step 4) below. If a runner already ran here (e.g. via the script), check run.log in the run folder above.",
    de: "Work Order steht auf running, aber es gibt noch keinen bestätigten AgentRun-Eintrag. Falls du noch keinen lokalen Runner gestartet hast, führe unten Schritt 3 (oder Schritt 4) aus. Falls hier bereits ein Runner lief (z. B. über das Skript), prüfe run.log im Run-Ordner oben.",
  },
  "operator.runner.phase.awaiting_result": { en: "Awaiting result", de: "Wartet auf Ergebnis" },
  "operator.runner.phase.awaiting_result_hint": {
    en: "Runner started — paste the prompt into Claude Code/Codex (or let it auto-execute), then run step 5 to import the result.",
    de: "Runner gestartet — Prompt in Claude Code/Codex einfügen (oder automatisch ausführen lassen), dann Schritt 5 zum Importieren ausführen.",
  },
  "operator.runner.phase.import_failed": { en: "Import failed", de: "Import fehlgeschlagen" },
  "operator.runner.phase.import_failed_hint": {
    en: "The last import did not complete successfully — check run.log and the AgentRun's output above for the cause, fix it, then re-run step 5.",
    de: "Der letzte Import ist nicht sauber durchgelaufen — Ursache in run.log und im AgentRun-Output oben prüfen, beheben, dann Schritt 5 erneut ausführen.",
  },
  "operator.runner.phase.review_ready": { en: "Review ready", de: "Review bereit" },
  "operator.runner.phase.review_ready_hint": {
    en: "Import succeeded and a review package was written — see the Review Package section above.",
    de: "Import erfolgreich, Review Package wurde geschrieben — siehe Abschnitt Review Package oben.",
  },

  // List page CTA + empty state (OP-Create-001)
  "operator.list.new_button":    { en: "New Work Order", de: "Neue Work Order" },
  "operator.empty_cta":          { en: "Create first Work Order", de: "Erste Work Order erstellen" },
  "operator.list.needs_attention": { en: "Needs Attention", de: "Braucht Aufmerksamkeit" },
  "operator.list.in_progress":     { en: "In Progress",     de: "In Arbeit" },
  "operator.list.queue":           { en: "Queue",           de: "Warteschlange" },
  "operator.list.completed":       { en: "Completed",       de: "Abgeschlossen" },

  // Create flow (OP-Create-001)
  "operator.create.title":                 { en: "New Work Order",        de: "Neue Work Order" },
  "operator.create.subtitle":              { en: "Define the goal, approval scope, and ticket plan.", de: "Ziel, Approval Scope und Ticketplan festlegen." },
  "operator.create.section_basics":        { en: "Basics",                de: "Grunddaten" },
  "operator.create.section_target_repo":   { en: "Target Repo (optional, cross-repo)", de: "Target Repo (optional, Cross-Repo)" },
  "operator.create.section_target_repo_hint": { en: "Leave both blank if this work order edits CommandPilot itself. Fill them in only if the runner should work in a different, external project (e.g. Sommercamps/CampsPilot) — the generated runner prompt will then clearly separate Control Plane (CommandPilot) from Target Repo.", de: "Leer lassen, wenn diese Work Order CommandPilot selbst betrifft. Nur ausfüllen, wenn der Runner in einem anderen, externen Projekt arbeiten soll (z.B. Sommercamps/CampsPilot) — der generierte Runner-Prompt trennt dann klar zwischen Control Plane (CommandPilot) und Target Repo." },
  "operator.create.field_target_repo_name": { en: "Target repo name", de: "Target-Repo-Name" },
  "operator.create.field_target_repo_name_ph": { en: "e.g. Sommercamps / CampsPilot", de: "z.B. Sommercamps / CampsPilot" },
  "operator.create.field_target_repo_path": { en: "Target repo path (local, informational only)", de: "Target-Repo-Pfad (lokal, nur informativ)" },
  "operator.create.field_target_repo_path_ph": { en: "e.g. C:\\Users\\you\\Projects\\campspilot", de: "z.B. C:\\Users\\du\\Projekte\\campspilot" },
  "operator.create.field_target_repo_path_safety": { en: "This path is only shown as context in the runner prompt and the Local Runner panel — CommandPilot never reads it, executes anything there, or changes directory automatically.", de: "Dieser Pfad wird nur als Kontext im Runner-Prompt und im Local-Runner-Panel angezeigt — CommandPilot liest ihn nicht, führt dort nichts aus und wechselt auch nicht automatisch das Verzeichnis." },
  "operator.create.section_criteria":      { en: "Acceptance Criteria",   de: "Akzeptanzkriterien" },
  "operator.create.section_scope":         { en: "Approval Scope",        de: "Approval Scope" },
  "operator.create.field_title":           { en: "Title",                 de: "Titel" },
  "operator.create.field_title_ph":        { en: "e.g. Prepare CS-302 to CS-305", de: "z.B. CS-302 bis CS-305 vorbereiten" },
  "operator.create.field_goal":            { en: "Goal / Description",   de: "Ziel / Beschreibung" },
  "operator.create.field_goal_ph":         { en: "What should the background team accomplish?", de: "Was soll das Background-Team erreichen?" },
  "operator.create.field_repo":            { en: "Repository / Project", de: "Repo / Projekt" },
  "operator.create.field_time_limit":      { en: "Time limit (minutes)", de: "Zeitlimit (Minuten)" },
  "operator.create.field_team_type":       { en: "Team type",            de: "Team-Typ" },
  "operator.create.field_team_type_hint":  { en: "\"development\" is the first team type — not the only one.", de: "\"development\" ist der erste Team-Typ — nicht der einzige." },
  "operator.create.field_criteria":        { en: "Acceptance criteria (one per line)", de: "Akzeptanzkriterien (eine pro Zeile)" },
  "operator.create.field_allowed":         { en: "Allowed actions (one per line)", de: "Erlaubte Aktionen (eine pro Zeile)" },
  "operator.create.field_requires_approval": { en: "Requires approval (one per line)", de: "Braucht Freigabe (eine pro Zeile)" },
  "operator.create.field_blocked":         { en: "Blocked actions (one per line)", de: "Blockierte Aktionen (eine pro Zeile)" },
  "operator.create.field_allowed_paths":   { en: "Allowed paths (optional, one per line)", de: "Erlaubte Pfade (optional, eine pro Zeile)" },
  "operator.create.field_blocked_paths":   { en: "Blocked paths (optional, one per line)", de: "Blockierte Pfade (optional, eine pro Zeile)" },
  "operator.create.defaults_hint":         { en: "Pre-filled with the standard Background Dev Team scope, including safe default paths — edit freely.", de: "Vorausgefüllt mit dem Standard-Scope fürs Background Dev Team, inklusive sicherer Default-Pfade — frei anpassbar." },
  "operator.create.warning_no_allowed_paths": { en: "Allowed actions permit code changes, but Allowed paths is empty — the runner would have no path boundary. Consider adding at least one path, e.g. frontend/**.", de: "Erlaubte Aktionen erlauben Code-Änderungen, aber Erlaubte Pfade ist leer — der Runner hätte keine Pfad-Grenze. Füge mindestens einen Pfad hinzu, z.B. frontend/**." },
  "operator.create.steps_hint":            { en: "6 ticket-plan steps (Product → Architect → Coder → QA → Reviewer → Reporter) are created automatically.", de: "6 Ticketplan-Steps (Product → Architect → Coder → QA → Reviewer → Reporter) werden automatisch angelegt." },
  "operator.create.submit":                { en: "Create Work Order",    de: "Work Order erstellen" },
  "operator.create.submitting":            { en: "Creating...",          de: "Wird erstellt..." },
  "operator.create.error_required":        { en: "Required.",            de: "Pflichtfeld." },
  "operator.create.error_time_limit":      { en: "Must be greater than 0.", de: "Muss größer als 0 sein." },
  "operator.create.error_blocked_required": { en: "At least one blocked action is required — this is a hard safety rule, not a formality.", de: "Mindestens eine blockierte Aktion ist erforderlich — das ist eine harte Safety-Regel, keine Formalität." },
  "operator.create.error_criteria_required": { en: "At least one acceptance criterion is required.", de: "Mindestens ein Akzeptanzkriterium ist erforderlich." },
  "operator.create.error_banner":          { en: "Could not create the work order:", de: "Work Order konnte nicht erstellt werden:" },
  "operator.create.cancel":                { en: "Cancel",                de: "Abbrechen" },

  // ── Common ─────────────────────────────────────────────────────────────────
  "common.loading":           { en: "Loading...",         de: "Wird geladen..." },
  "common.error":             { en: "Something went wrong", de: "Etwas ist schiefgelaufen" },
  "common.save":              { en: "Save",               de: "Speichern" },
  "common.cancel":            { en: "Cancel",             de: "Abbrechen" },
  "common.dismiss":           { en: "Dismiss",            de: "Schließen" },
};

/** Look up a translation. Falls back to "en" then the raw key. */
export function t(key: string, lang: Lang): string {
  const entry = dict[key];
  if (!entry) return key;
  return entry[lang] ?? entry["en"] ?? key;
}

/**
 * React hook — returns a translation function bound to the current user language.
 * Usage: const t = useT();  then  t("nav.dashboard")
 */
export function useT(): (key: string) => string {
  const { language } = useAuth();
  return (key: string) => t(key, language);
}
