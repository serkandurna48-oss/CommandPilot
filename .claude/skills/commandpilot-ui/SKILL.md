---
name: commandpilot-ui
description: CommandPilot's UI/UX design lead — refines and extends the existing Focus Deck system (dark graphite + Bronze/Copper, persistent Jarvis rail). Does not invent a new visual direction. Use for any CommandPilot frontend route redesign, layout pass, or visual-consistency review.
---

# CommandPilot UI

This skill makes Claude the dedicated design lead for CommandPilot's frontend.
It is **not** the general-purpose `frontend-design` skill — that one is for
greenfield visual direction. This one starts from a locked direction (Focus
Deck) and refines within it. If a task is a brand-new surface with no visual
precedent in this repo, use `frontend-design` instead; if it touches an
existing or Focus-Deck-adjacent route, use this one.

## Design truth — read before touching any route

In this order:

1. `docs/design/commandpilot-focus-deck-implementation-plan.md` — the locked
   design system (tokens, layout model, rationale).
2. `frontend/components/layout/FocusDeckShell.tsx`, `IconRail.tsx`,
   `JarvisRail.tsx`, `FocusDeckMobileNav.tsx`, `MobileJarvisOverlay.tsx` — the
   actual shell implementation, source of truth over any doc if they disagree.
3. `frontend/app/(app)/settings/page.tsx` — reference for a finished,
   visually-locked route (per CLAUDE.md: "visually locked ... Fidelity-Pass
   gegen Higgsfield-Referenz bestanden"). Match its restraint, not just its
   colors.
4. `frontend/components/dashboard/HomeBriefing.tsx` — reference for
   composition: one dominant priority, supporting sections, no card-grid
   sprawl.
5. `C:\Users\serka\dev\commandpilot-design-v2\01-current-ui\` and
   `\02-master-concepts\` — Higgsfield design references, if present on this
   machine. Outside the git repo, never reference them as if they were
   committed, never copy files from there into the repo.

Never invent a new palette, type system, or layout model. If a route looks
wrong, the fix is to bring it in line with the above — not to redesign the
system around it.

## The locked system, in real tokens

Pull current values from `frontend/tailwind.config.ts` and
`frontend/app/globals.css` before relying on the summary below — the code is
authoritative, this is a map, not the territory.

**Color** (`tailwind.config.ts`, `globals.css`):
- Foundation: `--bg-app: #0b0b0c`, `--bg-surface: #17171a`,
  `--bg-elevated: #1e1e22` — graphite/charcoal, never pure black, never a
  lighter neutral grey.
- Brand/action accent: `brand-*` scale (`#faf3ec` → `#3d2414`), Bronze/Copper/
  Ember family. `brand-600` (`#9c5e33`) is the standard filled-button color
  (`--interactive-bg-primary-default`). This is the *only* accent — never add
  a second accent hue for "AI" moments.
- Status colors (`status.success/warning/danger/info`) are a **separate**
  family from brand — never substitute a status color for brand, never use
  brand to mean "success."
- Text: `--text-primary #f2efea`, `--text-secondary #a8a29a`,
  `--text-tertiary #7a756d`, `--text-accent` = `brand-500`.
- Borders are hairline alpha-whites (`--border-light` 6% → `--border-heavy`
  24%), not solid greys — this is how surfaces separate without boxing
  everything in a card.

**Type** (`tailwind.config.ts` `fontFamily`):
- `sans` (Inter) — all application UI, the default.
- `serif` (`"Source Serif 4"`, quoted — see the code comment on why unquoted
  breaks silently) — sparingly, for the one big human/briefing headline per
  view (e.g. `HomeBriefing`'s greeting). Never for navigation, wordmarks, or
  routine UI text.
- `mono` (JetBrains Mono) — technical metadata only (IDs, timestamps, repo
  paths, status enums a developer would recognize as code).

**Geometry**: restrained radius vocabulary — subtle on surfaces, medium on
interactive controls, high (pill) only on the composer/input and small
pill-shaped badges. Don't introduce a fourth radius value without a reason
tied to the element's role.

## What "on-brand" excludes

Do not drift toward: generic SaaS blue, purple AI gradients, glassmorphism,
soft grey card-shadow kits, or "futuristic AI" visual clichés (glowing
orbs, particle fields, neon circuits). These are the opposite of Focus Deck's
calm, editorial, bronze-on-graphite identity.

Also avoid, independent of palette: dashboards built as a wall of
independent-looking cards. Prefer sections, whitespace, dividers, alignment,
and hierarchy over nested cards, excessive borders, decorative icon
containers, and unnecessary badges — see `HomeBriefing.tsx` for the target
composition style versus the older `CommandHero`/`ProjectRadar`/
`SignalNoisePanel` card-grid components it replaced (deleted, but visible in
git history at `76f4789` if you need the "don't do this" reference).

## Layout model

Desktop: `[ICON RAIL] [PERSISTENT JARVIS RAIL] [WORKSPACE]`. Jarvis is a
permanent intelligence layer that survives route changes (one
`FocusDeckShell` instance under `app/(app)/layout.tsx` — see CLAUDE.md's
"Jarvis" section) — never a chatbot widget that resets or floats above
content. Workspace itself should read as calm, wide, and intentional, not
cramped around the rail.

Mobile: workspace-first, bottom navigation (`FocusDeckMobileNav.tsx`), Jarvis
as a FAB/overlay (`MobileJarvisOverlay.tsx`) rather than a persistent column.
Don't just reflow the desktop card stack — design the mobile hierarchy
on its own terms.

## Icon discipline

Icons earn their place by improving navigation or comprehension. Cut
decorative icons on every section heading, meaningless chevrons, and icon-in-
a-circle containers that exist only to fill space next to a heading.

## Information hierarchy

Every screen answers one question: what's the most important thing here? One
element dominates (a priority, a decision, a single number) — everything else
visibly supports it. If a screen's elements all carry equal visual weight,
that's the defect to fix, not a style choice to preserve.

## Copy

User-language over architecture-language. "Needs your decision," not
"Approval State Queue." "Run again," not "Transition to queued." Match the
verbs already used across the app (see `frontend/lib/i18n.ts` for the
existing vocabulary) rather than introducing new synonyms for the same
concept — consistency across routes matters more than any single string's
cleverness.

## Real data only

Never invent metrics, agent counts, infrastructure stats, activity, progress,
or model names to make a screen look richer. If the real data is empty or
unavailable, design a strong, honest empty state instead — this is the same
"no silent fallback" principle CLAUDE.md already applies to Jarvis
(`frontend/lib/mockWorkOrders.ts`'s mock-fallback risk is the cautionary
example, not a pattern to extend into new UI).

## Safety boundary

A UI pass must never silently change backend behavior, APIs, work-order
state-machine semantics, approval semantics, auth, or runner behavior. If a
visual idea implies a new product capability (a control that needs a backend
endpoint that doesn't exist, a status that isn't in the state machine), flag
it and stop — don't fake it with a control that doesn't actually do anything.

## Workflow — one route at a time

Never redesign multiple routes in one pass. For the route in scope:

1. **Audit** the current route as implemented (read the real component, not
   just a screenshot from memory). Report composition problems, hierarchy
   problems, unnecessary UI, and any inconsistency with the Focus Deck
   reference routes (Settings, Home Briefing) — before writing any code.
2. **Design** one focused change addressing what the audit found. State what
   you're changing and why, referencing the specific token/pattern from
   "design truth" above that justifies it.
3. **Implement.**
4. **Screenshot the real route** (`/run` skill or the project's own dev
   server, then Chrome automation) — never judge a visual change by reading
   the JSX.
5. **Critique the screenshot** against: the design reference, the rest of the
   Focus Deck system, and neighboring finished routes. List concrete,
   specific differences — not "looks fine."
6. **Simplification pass** before calling it done — can a card disappear, a
   border disappear, an icon disappear, two surfaces merge into one, wording
   get simpler? Remove anything visible only because it was easy to add.
7. **Responsive check** at ~1440px desktop and ~390px mobile — mobile gets
   its own intentional hierarchy, not a stacked copy of desktop.
8. Repeat 3–7 until the route reads as the same product as its neighbors.
   Stop at "this visually belongs to CommandPilot," not "code compiles."

Lock the route (state clearly that it's done) before moving to the next one.
