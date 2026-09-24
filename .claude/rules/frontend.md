---
paths:
  - "frontend/**"
---

# Frontend-Regeln (CommandPilot)

Ergänzt `CLAUDE.md` — hier stehen nur frontend-spezifische, aktionable Details.

- **i18n-Pattern**: Alle nutzersichtbaren Strings gehören in `frontend/lib/i18n.ts`
  als `"key": { en: "...", de: "..." }`. Immer beide Sprachen zusammen ergänzen, nie
  nur eine. JSON-Keys, die vom Backend kommen (z. B. `status`-Werte), bleiben
  englisch und werden erst beim Rendern lokalisiert.
- **Komponenten-Ordnung**: Feature-Komponenten unter `components/<feature>/`
  (dashboard, morning, plans, projects, review, rules, layout). Geteilte Primitives
  unter `components/ui/`.
- **Einzige Token-Quellen**: `lib/api.ts` (zentrale Backend-Calls, hängt den Bearer-
  Token an) und `lib/auth.tsx` (Supabase-Auth-Context, bootstrapt nur bei
  `SIGNED_IN`). Nicht direkt `supabase.auth` aus Komponenten heraus aufrufen.
- Nach jeder Änderung: `npm run lint && npm run type-check` — es gibt keinen
  Test-Runner als Sicherheitsnetz.
- **`components/operator/*` / `lib/mockWorkOrders.ts`**: Mock-Daten-Fallback bei
  API-Fehlern darf nie UI-transparent (ohne sichtbaren Fehlerzustand) erfolgen —
  das verdeckt echte Ausfälle. Siehe `CLAUDE.md` § Bekannte Risiken.

Auth-/Security-Grundregeln (Bearer-Token-Fluss, Ownership) stehen in `CLAUDE.md` —
hier nicht erneut duplizieren.
