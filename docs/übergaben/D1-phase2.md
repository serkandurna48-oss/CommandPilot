# JARVIS-D1 — Übergabe Phase 2 (Designwerte und Primitive)

Commit: `ace1b8c` — feat: Design-Tokens für Akzent, Status und Typografie
Basis: `f9d3462` (Auftragsdokumente JARVIS-M1/D1)

## Was geändert wurde

- `frontend/tailwind.config.ts` — vollständige `brand`-Skala 50–900 (gedämpftes
  Steel-Blue als Akzent), neue `status`-Skala (`success`/`warning`/`danger`/
  `neutral`), bewusst getrennt vom Akzent.
- `frontend/app/globals.css` — JetBrains Mono korrekt geladen (war deklariert,
  nie importiert); Range-Slider-Thumb von hartkodiertem Indigo-Hex auf
  `brand-500`/`brand-400` umgestellt (einzige Stelle mit rohem CSS statt
  Tailwind-Klassen).
- `frontend/components/ui/Badge.tsx` — `rounded` → `rounded-md` (6px-Konvention
  für Chips/Badges).

## Entscheidung: Akzent vs. LIFE_AREA_COLORS.work

Serkans Bedingung: "ein Blau, nicht zwei" — `#3b82f6` (work-Kategoriefarbe,
`frontend/types/index.ts`) und der neue Akzent dürfen nicht kollidieren.
Gelöst über Unterscheidbarkeit statt Zusammenlegung: neuer Akzent-Basiswert
`brand-600 #3f6483` (H206° S33% L33%) vs. `work #3b82f6` (H217° S91% L60%) —
Sättigungs-Delta 33% vs. 91%. `types/index.ts` liegt außerhalb der
Auftrags-Dateiliste und wurde nicht angefasst; Serkan hat diese Lösung
akzeptiert und explizit keinen Folgeauftrag für `types/index.ts` gestellt.

**Korrektur in Phase 3 nachgetragen** (siehe D1-phase3.md): `brand-600` als
Basis für die Button-Primärvariante war mit ~3.2:1 gegen `slate-950` zu knapp
für eine Primäraktion. Für interaktive Zustände (Buttons, aktive Navigation,
Fokusringe) gilt jetzt `brand-400`/`brand-500`; `brand-600` und dunkler bleibt
Rändern, Flächen und Füllungen vorbehalten.

## check.ps1

Grün: 39 Backend-Tests, Type-Check, Lint.

Nebenbefund: In diesem Worktree (`cp-design`) existierte noch kein `.venv` —
canonical unter Repo-Root neu angelegt und `backend/requirements*.txt`
installiert, sonst wäre `check.ps1` nie grün geworden. Reine
Environment-Einrichtung, keine Code-Änderung.

## Im Browser geprüft

Dev-Server (Port 3001) gestartet, `/login` gerendert — Button, Icon-Kachel und
Fokus-Elemente zeigen den neuen Akzent korrekt kompiliert, keine
Konsolenfehler. Dev-Server danach wieder gestoppt.

## Ungetestet / Einschränkungen

- Sidebar (aktiver Nav-Zustand), Badge/RatingDots in echter Nutzung,
  Jarvis-Quellenzeilen mit JetBrains Mono — alle hinter Login, keine
  Testzugangsdaten vorhanden. In Phase 3 im auth-freien Prototyp nachgeholt.
- `package-lock.json` war bereits vor dieser Arbeit verändert (nicht von mir)
  — bewusst nicht committet.
