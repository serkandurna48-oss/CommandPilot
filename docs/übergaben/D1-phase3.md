# JARVIS-D1 — Übergabe Phase 3 (Klickbarer Entwurf unter /design-preview)

Commit: `21af89d` — feat: klickbarer Design-Entwurf unter /design-preview
Basis: `ace1b8c` (Phase 2)

## Was geändert wurde

Neu, alles unter `frontend/app/design-preview/` (nicht in der Navigation
verlinkt, kein Auth-Gate):

- `page.tsx` — Komposition: App-Rahmen (echte `Sidebar`/`MobileNav` aus
  `components/layout/*`, ohne `AppShell`/`ProtectedRoute`, damit die Route
  ohne Login testbar ist), Prototyp-Banner, Design-Tokens-Abschnitt,
  Jarvis-Ausschnitt, Auftragsvorschau, optionales Detailpanel (`lg:` aufwärts).
- `PreviewJarvisPanel.tsx` — Chat-Mock mit Zustands-Switcher (leer / kurzer
  Verlauf / langer Verlauf / lädt / Fehler+Retry), formatierte Antworten
  (Absätze, Listen, Fettungen als JSX statt Markdown-Parser — keine neue
  Bibliothek), Quellen-Split: Treffer direkt sichtbar, Basiskontext in
  `<details>` einklappbar mit Hinweistext.
- `PreviewActionCard.tsx` — Auftragsvorschau-Karte: Risiko-Badge (Status-Token),
  Freigabe-Indikator, Ziel-Repo, Quellenzahl, sichtbar deaktivierter
  Aktions-Button ("Noch nicht verfügbar") — legt nichts an, wie im Auftrag
  gefordert.
- `DesignTokens.tsx` — Referenzabschnitt: Akzent-Kontrastkorrektur vorher/
  nachher nebeneinander, volle `brand`-Skala, `status`-Farben, Typografie-Skala,
  JetBrains-Mono-Probe, Radien-Konvention.

Geändert, innerhalb der erlaubten Dateien:

- `components/ui/Button.tsx` — Primärvariante `bg-brand-600` → `bg-brand-500`
  (Hover weiterhin `brand-600`). Einzige Stelle in meinem Geltungsbereich, die
  die zu dunkle Akzent-Basis aus Phase 2 tatsächlich als interaktives Element
  nutzte; alle anderen `bg-brand-600`-Stellen im Repo liegen in Dateien
  außerhalb der Auftragsliste (Login/Signup/Settings/Dashboard/Operator/Plans)
  und bleiben unangetastet — das ist Phase-4- bzw. Nicht-Ziel-Gebiet.
- `components/layout/Sidebar.tsx` — hartkodierte "System Online"-Behauptung
  entfernt (grüner Punkt + Text, nie an echte Daten gebunden). Betrifft die
  echte, überall genutzte Sidebar, nicht nur die Prototyp-Route — bewusst so,
  weil der Auftrag das explizit als "zusätzlich" zu erledigenden Punkt nennt,
  nicht als Teil des in Phase 4 gesperrten Token-Rollouts.
- `lib/i18n.ts` — nur neue Strings, Namespace `design_preview.*` plus
  Wiederverwendung bestehender `jarvis.*`-Keys für den Mock-Chat.

## Kontrastkorrektur (Serkans Vorgabe aus dem letzten Feedback)

`brand-500` (#4f7a9c, ~4.4:1 gegen `slate-950`) jetzt Basis für Buttons; Hover
auf `brand-600`. Aktive Navigation und Fokusringe nutzten in der Sidebar bzw.
den UI-Primitiven bereits `brand-400`/`brand-500` — dort war keine Änderung
nötig. Vorher/Nachher-Vergleich ist live im Prototyp unter "Design-Tokens" zu
sehen (echte kompilierte Tailwind-Klassen, nicht nur ein statisches Bild).

## check.ps1

Grün: 39 Backend-Tests, Type-Check, Lint.

## Im Browser geprüft

Dev-Server (Port 3001) gestartet, `/design-preview` ohne Login geladen:

- Design-Tokens-Abschnitt inkl. Vorher/Nachher-Akzent, volle Skala,
  Status-Farben, Typografie, Radien — korrekt gerendert.
- Zustands-Switcher: leer, kurzer Verlauf, langer Verlauf, Fehler+Retry alle
  durchgeklickt, formatierte Antworten (Listen, Fettung) korrekt.
- Quellen-Split: Treffer direkt sichtbar, Basiskontext per `<details>`
  aufklappbar.
- Quelle anklicken → Detailpanel rechts aktualisiert sich korrekt.
- Auftragskarte anklicken → Detailpanel zeigt Titel, Beschreibung, Team, Repo,
  Freigabe-Status, Quellen (auch der Fall mit 0 Quellen korrekt als "0
  Quellen").
- Tastaturfokus sichtbar (Fokusring auf Quellen-Buttons per Screenshot
  bestätigt).
- Kein horizontales Scrollen (`document.documentElement.scrollWidth <=
  window.innerWidth` per JS geprüft).

**Gefundener und behobener Bug während der Prüfung:** Der Chat-Mock scrollte
beim ersten Laden automatisch zur letzten Nachricht und riss dabei die ganze
Seite mit herunter (Design-Tokens und Banner verschwanden aus dem ersten
Eindruck) — klassisches Flexbox-`min-h-0`-Problem plus ein `scrollIntoView`,
das schon beim Mount statt erst bei Nutzerinteraktion feuerte. Beides behoben
(`min-h-0` auf dem Scroll-Container, Auto-Scroll erst ab dem zweiten
Zustandswechsel).

## Ungetestet / Einschränkungen

- **Schmaler Mobilbildschirm nicht per echtem Screenshot verifiziert.** Der
  Browser-Automatisierungstool-Aufruf zum Verkleinern des Fensters
  (`resize_window`) hat in dieser Session keine Wirkung gezeigt (Fenster blieb
  bei 1920×911, vermutlich weil es maximiert/vom Fenstermanager kontrolliert
  war) — ich konnte das nicht umgehen. Stattdessen nur geprüft: kein
  horizontales Scrollen bei Desktop-Breite, und alle neuen Layouts nutzen
  dieselben `sm:`/`md:`/`lg:`-Breakpoint-Muster wie die bereits produktiv
  genutzten `Sidebar`/`MobileNav`/`JarvisChat`-Komponenten (z. B.
  `max-w-[85%] md:max-w-[70%]` für Chat-Bubbles direkt aus dem echten
  `JarvisChat.tsx` übernommen). Das ist eine Ableitung aus dem Code, kein
  visueller Beweis — bitte auf einem schmalen Bildschirm selbst gegenprüfen,
  bevor das als abgenommen gilt.
- Sidebar ist nicht sticky (bestehendes `AppShell`-Verhalten, unverändert
  übernommen) — bei einer langen Seite scrollt sie mit weg. Kein neuer Bug,
  aber im Prototyp sichtbar, da die Design-Tokens-Sektion die Seite lang
  macht.
- Auftragskarten-Button ist absichtlich funktionslos (disabled) — nicht mit
  einem echten Fehlerzustand verwechseln.
- Sprachumschaltung: Prototyp läuft über `useT()`/`i18n.ts` wie der Rest der
  App: ohne gespeicherte Präferenz Standard Englisch (siehe Screenshots,
  Banner-Text auf Englisch) — kein Bug, bestehendes Verhalten von
  `getUserLanguage()`.

## Halte hier an

Wie im Auftrag vorgesehen, warte ich auf deine Freigabe des Entwurfs, bevor
Phase 4 (App-Rahmen und `/jarvis` übernehmen die Tokens) beginnt.
