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

  // ── Greeting (time-aware, used in CommandHero) ───────────────────────────────
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
  "nav.settings":             { en: "Settings",           de: "Einstellungen" },

  // ── Dashboard ──────────────────────────────────────────────────────────────
  "dashboard.title":          { en: "Dashboard",          de: "Cockpit" },
  "dashboard.subtitle":       { en: "Your personal command center.", de: "Behalte deine Tagespläne, offenen Schritte und letzten Entscheidungen im Blick." },
  "dashboard.hero.standby":   { en: "Awaiting mission brief.", de: "Kein Tagesplan bisher." },
  "dashboard.signal.main":    { en: "Signal Locked",        de: "Signal Locked" },
  "dashboard.signal.secondary": { en: "Secondary Targets", de: "Secondary Targets" },
  "dashboard.signal.noise":   { en: "Noise Suppressed",    de: "Noise Suppressed" },
  "dashboard.radar.title":    { en: "Project Radar",       de: "Projekt-Radar" },
  "dashboard.timeline.title": { en: "Mission Log",          de: "Mission Log" },
  "dashboard.momentum.title": { en: "Recent Missions",     de: "Letzte Tagespläne" },
  "dashboard.no_plan":        { en: "No plan for today yet.", de: "Noch kein Tagesplan für heute." },
  "dashboard.no_plan_sub":    { en: "Start your morning check-in and get your AI-generated daily strategy in under 30 seconds.", de: "Starte deinen Tagesstart und erhalte in wenigen Sekunden einen klaren Tagesplan." },
  "dashboard.start_checkin":  { en: "Start Morning Check-in", de: "Tagesstart beginnen" },
  "dashboard.today_plan":     { en: "Today's Plan",       de: "Heutiger Tagesplan" },
  "dashboard.view_plan":      { en: "View full plan",     de: "Tagesplan öffnen" },
  "dashboard.new_checkin":    { en: "New Check-in",       de: "Neuer Tagesstart" },
  "dashboard.eve_review":     { en: "Evening Review",     de: "Abend-Reflexion" },
  "dashboard.recent_plans":   { en: "Recent Plans",       de: "Letzte Tagespläne" },

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

  // ── Rules ──────────────────────────────────────────────────────────────────
  "rules.title":              { en: "Personal Rules",     de: "Regeln" },
  "rules.subtitle":           { en: "Your operating principles. The AI uses these to personalize every plan.", de: "Deine Regeln fließen in jeden Tagesplan ein." },

  // ── Settings ───────────────────────────────────────────────────────────────
  "settings.title":           { en: "Settings",           de: "Einstellungen" },
  "settings.subtitle":        { en: "Account, preferences, and integrations.", de: "Konto, Sprache und Verhalten." },
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
