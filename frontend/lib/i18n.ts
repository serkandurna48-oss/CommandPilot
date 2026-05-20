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
  // ── Navigation ─────────────────────────────────────────────────────────────
  "nav.dashboard":            { en: "Dashboard",          de: "Übersicht" },
  "nav.morning":              { en: "Morning",            de: "Morgen" },
  "nav.review":               { en: "Review",             de: "Rückblick" },
  "nav.rules":                { en: "Rules",              de: "Regeln" },
  "nav.settings":             { en: "Settings",           de: "Einstellungen" },

  // ── Dashboard ──────────────────────────────────────────────────────────────
  "dashboard.title":          { en: "Dashboard",          de: "Übersicht" },
  "dashboard.subtitle":       { en: "Your personal command center.", de: "Deine persönliche Kommandozentrale." },
  "dashboard.no_plan":        { en: "No plan for today yet.", de: "Noch kein Plan für heute." },
  "dashboard.no_plan_sub":    { en: "Start your morning check-in and get your AI-generated daily strategy in under 30 seconds.", de: "Starte deinen morgendlichen Check-in und erhalte deine KI-generierte Tagesstrategie in unter 30 Sekunden." },
  "dashboard.start_checkin":  { en: "Start Morning Check-in", de: "Morgendlichen Check-in starten" },
  "dashboard.today_plan":     { en: "Today's Plan",       de: "Heutiger Plan" },
  "dashboard.view_plan":      { en: "View full plan",     de: "Plan anzeigen" },
  "dashboard.new_checkin":    { en: "New Check-in",       de: "Neuer Check-in" },
  "dashboard.eve_review":     { en: "Evening Review",     de: "Abendlicher Rückblick" },
  "dashboard.recent_plans":   { en: "Recent Plans",       de: "Letzte Pläne" },

  // ── Morning check-in ───────────────────────────────────────────────────────
  "morning.title":            { en: "Morning Check-in",   de: "Morgendlicher Check-in" },
  "morning.subtitle":         { en: "Dump your morning state. The AI handles the structure.", de: "Schreib deinen Morgenzustand rein. Die KI übernimmt die Struktur." },
  "morning.quick_input":      { en: "Quick Input",        de: "Schnelleingabe" },
  "morning.quick_label":      { en: "Dump everything here — the AI will structure it", de: "Alles hier rein — die KI strukturiert es" },
  "morning.quick_ph":         { en: "Woke up at 7:00, energy 6/10, slightly tired. Morning run at 08:00, team call at 14:00. Need to finish the Q3 report...", de: "Um 7:00 aufgewacht, Energie 6/10, leicht müde. Morgenlauf um 08:00, Teamcall um 14:00. Q3-Bericht fertigstellen..." },
  "morning.vitals":           { en: "Morning Vitals",     de: "Morgendliche Vitaldaten" },
  "morning.wake_time":        { en: "Wake Time",          de: "Aufwachzeit" },
  "morning.sleep_quality":    { en: "Sleep Quality",      de: "Schlafqualität" },
  "morning.energy_level":     { en: "Energy Level",       de: "Energielevel" },
  "morning.avail_hours":      { en: "Available Hours",    de: "Verfügbare Stunden" },
  "morning.body_status":      { en: "Body / Physical Status", de: "Körperlicher Zustand" },
  "morning.body_ph":          { en: "Sore legs, light headache, feeling fresh...", de: "Beine wund, leichte Kopfschmerzen, frisch..." },
  "morning.mood":             { en: "Mood",               de: "Stimmung" },
  "morning.mood_ph":          { en: "Focused, anxious, motivated, neutral...", de: "Fokussiert, angespannt, motiviert, neutral..." },
  "morning.agenda":           { en: "Today's Agenda",     de: "Heutige Agenda" },
  "morning.fixed_events":     { en: "Fixed Events (one per line — include time)", de: "Feste Termine (einer pro Zeile — mit Uhrzeit)" },
  "morning.fixed_ph":         { en: "Gym at 10:00\nTennis at 18:00\nTeam call at 14:00", de: "Gym um 10:00\nTennis um 18:00\nTeamcall um 14:00" },
  "morning.tasks":            { en: "Important Tasks (one per line)", de: "Wichtige Aufgaben (eine pro Zeile)" },
  "morning.tasks_ph":         { en: "Finish Q3 report draft\nReview project proposal\nRespond to client emails", de: "Q3-Bericht fertigstellen\nProjektvorschlag prüfen\nKunden-E-Mails beantworten" },
  "morning.constraints":      { en: "Constraints / Hard Limits", de: "Einschränkungen / Grenzen" },
  "morning.constraints_ph":   { en: "No work after 21:00. Don't schedule deep work right after intense exercise.", de: "Keine Arbeit nach 21:00. Kein Tiefarbeit direkt nach intensivem Sport." },
  "morning.generate":         { en: "Generate Today's Plan", de: "Heutigen Plan generieren" },
  "morning.retry":            { en: "Retry Plan Generation", de: "Plangenerierung wiederholen" },
  "morning.generating":       { en: "Generating your daily plan...", de: "Erstelle deinen Tagesplan..." },
  "morning.generating_sub":   { en: "This takes about 5-10 seconds.", de: "Das dauert etwa 5–10 Sekunden." },
  "morning.checkin_hint":     { en: "Your check-in was saved. Clicking \"Generate\" will retry plan generation without creating a duplicate.", de: "Dein Check-in wurde gespeichert. Klicke auf \"Generieren\", um die Plangenerierung erneut zu versuchen." },

  // ── Plan View ──────────────────────────────────────────────────────────────
  "plan.based_on_review":     { en: "Based on your recent evening review", de: "Basierend auf deinem letzten Abendrückblick" },
  "plan.main_win":            { en: "Main Win",           de: "Hauptziel" },
  "plan.top_priorities":      { en: "Top 3 Priorities",   de: "Top 3 Prioritäten" },
  "plan.schedule":            { en: "Time-Blocked Schedule", de: "Zeitblockplan" },
  "plan.energy_strategy":     { en: "Energy Strategy",    de: "Energiestrategie" },
  "plan.not_today":           { en: "Not Today",          de: "Nicht heute" },
  "plan.eve_questions":       { en: "Evening Review Questions", de: "Abendliche Reflexionsfragen" },
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
  "review.title":             { en: "Evening Review",     de: "Abendlicher Rückblick" },
  "review.subtitle":          { en: "Close the day. Capture what mattered.", de: "Schließe den Tag ab. Halte fest, was wichtig war." },
  "review.today_questions":   { en: "Today's Questions",  de: "Heutige Fragen" },
  "review.eod_vitals":        { en: "End-of-Day Vitals",  de: "Abendliche Vitaldaten" },
  "review.energy_end":        { en: "Energy at end",      de: "Energie am Abend" },
  "review.overall_day":       { en: "Overall day",        de: "Gesamter Tag" },
  "review.execution":         { en: "Execution",          de: "Ausführung" },
  "review.completed":         { en: "Completed (one per line)", de: "Erledigt (eine pro Zeile)" },
  "review.completed_ph":      { en: "Finished Q3 report draft\nResponded to client emails", de: "Q3-Bericht fertiggestellt\nKunden-E-Mails beantwortet" },
  "review.missed":            { en: "Missed / didn't happen (one per line)", de: "Verpasst / nicht passiert (eine pro Zeile)" },
  "review.missed_ph":         { en: "Project proposal review — pushed to tomorrow", de: "Projektvorschlag-Review — auf morgen verschoben" },
  "review.carry_over":        { en: "Carry over to tomorrow (one per line)", de: "Auf morgen übertragen (eine pro Zeile)" },
  "review.carry_over_ph":     { en: "Review project proposal\nFollow up with client", de: "Projektvorschlag prüfen\nMit Kunden nachfassen" },
  "review.reflection":        { en: "Reflection",         de: "Reflexion" },
  "review.biggest_win":       { en: "Biggest win today",  de: "Größter Erfolg heute" },
  "review.biggest_win_ph":    { en: "What actually mattered?", de: "Was hat wirklich gezählt?" },
  "review.lesson":            { en: "Key lesson",         de: "Wichtigste Erkenntnis" },
  "review.lesson_ph":         { en: "What would you do differently?", de: "Was würdest du anders machen?" },
  "review.raw":               { en: "Raw reflection (optional brain dump)", de: "Freie Reflexion (optionaler Gedankendump)" },
  "review.raw_ph":            { en: "Anything else on your mind...", de: "Was ist dir sonst noch auf dem Herzen..." },
  "review.save":              { en: "Save Review",        de: "Rückblick speichern" },
  "review.saved":             { en: "Review saved.",      de: "Rückblick gespeichert." },
  "review.saved_sub":         { en: "Rest well. Tomorrow is a clean slate.", de: "Ruh dich aus. Morgen ist ein neuer Anfang." },
  "review.back":              { en: "Back to Dashboard",  de: "Zurück zur Übersicht" },

  // ── Rules ──────────────────────────────────────────────────────────────────
  "rules.title":              { en: "Personal Rules",     de: "Persönliche Regeln" },
  "rules.subtitle":           { en: "Your operating principles. The AI uses these to personalize every plan.", de: "Deine Leitprinzipien. Die KI nutzt diese, um jeden Plan zu personalisieren." },

  // ── Settings ───────────────────────────────────────────────────────────────
  "settings.title":           { en: "Settings",           de: "Einstellungen" },
  "settings.subtitle":        { en: "Account, preferences, and integrations.", de: "Konto, Präferenzen und Integrationen." },
  "settings.account":         { en: "Account",            de: "Konto" },
  "settings.signed_in_as":    { en: "Signed in as",       de: "Angemeldet als" },
  "settings.sign_out":        { en: "Sign out",           de: "Abmelden" },
  "settings.preferences":     { en: "Preferences",        de: "Einstellungen" },
  "settings.language":        { en: "Language",           de: "Sprache" },
  "settings.language_saved":  { en: "Language updated.",  de: "Sprache aktualisiert." },
  "settings.ai_model":        { en: "AI Model",           de: "KI-Modell" },

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
  "plan.start_review":        { en: "Evening Review",     de: "Abendlicher Rückblick" },
  "plan.load_error":          { en: "Could not load plan.", de: "Plan konnte nicht geladen werden." },

  // ── Rules ──────────────────────────────────────────────────────────────────
  "rules.rule":               { en: "rule",               de: "Regel" },
  "rules.rules":              { en: "rules",              de: "Regeln" },
  "rules.active_suffix":      { en: "— active rules are injected into every AI plan.", de: "— aktive Regeln werden in jeden KI-Plan eingefügt." },
  "rules.add":                { en: "Add Rule",           de: "Regel hinzufügen" },
  "rules.form_title":         { en: "Title",              de: "Titel" },
  "rules.form_rule":          { en: "Rule",               de: "Regel" },
  "rules.form_category":      { en: "Category",           de: "Kategorie" },
  "rules.form_priority":      { en: "Priority",           de: "Priorität" },
  "rules.save":               { en: "Save Rule",          de: "Regel speichern" },
  "rules.empty_title":        { en: "No rules yet",       de: "Noch keine Regeln" },
  "rules.empty_desc":         { en: "Rules are used as context by the AI to personalize every plan. Add your operating principles.", de: "Regeln werden von der KI als Kontext genutzt, um jeden Plan zu personalisieren. Füge deine Leitprinzipien hinzu." },
  "rules.confirm_delete":     { en: "Delete this rule?",  de: "Diese Regel löschen?" },
  "rules.disable":            { en: "Disable",            de: "Deaktivieren" },
  "rules.enable":             { en: "Enable",             de: "Aktivieren" },

  // ── Common ─────────────────────────────────────────────────────────────────
  "common.loading":           { en: "Loading...",         de: "Wird geladen..." },
  "common.error":             { en: "Something went wrong", de: "Etwas ist schiefgelaufen" },
  "common.save":              { en: "Save",               de: "Speichern" },
  "common.cancel":            { en: "Cancel",             de: "Abbrechen" },
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
