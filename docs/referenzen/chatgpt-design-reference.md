# UI/UX Design-Referenz — extrahiert aus der ChatGPT Web-App (Projekt-Ansicht)

Quelle: `chatgpt.com` – Projekt-Directory-Seite, Dark Mode, Viewport 1395×770, Stand 18.09.2026.
Alle Werte sind **real aus dem DOM / den Stylesheets ausgelesen** (computed styles + CSS-Custom-Properties), nicht geschätzt.

> Zweck: Dieses Dokument + `chatgpt-tokens.css` an eine Claude-Code-Session geben, damit sie eine eigene Seite baut, die denselben Design-Standards folgt. **Ziel ist das System, nicht die Kopie** — keine OpenAI-Logos, -Wortmarken oder -Illustrationen übernehmen.

---

## 1. Tech-Fundament

| Aspekt | Befund |
|---|---|
| CSS-Framework | Tailwind CSS **v4.3.1** (`@theme`-Tokens, `light-dark()`-fähig) |
| Theming | Klassenbasiert: `html.dark` / `html.light`, Tokens doppelt definiert |
| Token-Architektur | 3 Ebenen: Primitive → Semantic (`--text-primary`) → Interactive (`--interactive-bg-{variant}-{state}`) |
| Icons | Stroke-Icons, ca. 20×20 in 36×36-Buttons |
| Layout | Flex/Grid, Content-Spalte **768 px** zentriert |

**Wichtigstes Prinzip:** Die App benutzt **nie** rohe Farbwerte in Komponenten. Jede Komponente greift auf einen semantischen Token zu, und interaktive Elemente haben für **jeden State** (`default / hover / press / inactive / selected`) einen eigenen Token. Das solltest du übernehmen.

---

## 2. Farb-Tokens (Light / Dark)

### Flächen
| Token | Light | Dark |
|---|---|---|
| `--bg-primary` | `#ffffff` | `#212121` |
| `--bg-secondary` | `#e8e8e8` | `#303030` |
| `--bg-secondary-surface` | `#f9f9f9` | `#000000` |
| `--bg-tertiary` | `#f3f3f3` | `#414141` |
| `--bg-elevated-primary` (Menü/Popover) | `#ffffff` | `#1b1b1b` |
| `--bg-elevated-secondary` | `#f3f3f3` | `#000000` |
| `--bg-scrim` (Modal-Overlay) | `#00000080` | `#00000080` |
| `--bg-tooltip` | `#000000` | `#1b1b1b` |
| Sidebar-Rail / App-Hintergrund | `#ffffff` | `#000000` |

### Text
| Token | Light | Dark |
|---|---|---|
| `--text-primary` | `#0d0d0d` | `#ffffff` |
| `--text-secondary` | `#5d5d5d` | `#cdcdcd` |
| `--text-tertiary` | `#8f8f8f` | `#afafaf` |
| `--text-quaternary` | `#00000030` | `#ffffff69` |
| `--text-placeholder` | `#000000b3` | `#ffffffcc` |
| `--text-inverted` | `#ffffff` | `#0d0d0d` |
| `--text-accent` | `#3a83f7` | `#63a8f8` |
| `--link` | `#2964aa` | `#7ab7ff` |

### Rahmen (4 Gewichte — sehr wichtig für den Look)
| Token | Light | Dark |
|---|---|---|
| `--border-light` | `#0000000d` (5 %) | `#ffffff0d` |
| `--border-default` | `#0000001a` (10 %) | `#ffffff26` (15 %) |
| `--border-medium` | `#00000026` | `#ffffff26` |
| `--border-heavy` | `#00000026` | `#ffffff33` |
| `--border-xheavy` | `#00000040` | `#ffffff40` |

### Status
| Token | Light | Dark |
|---|---|---|
| `--bg-status-success` / `--text-status-success` | `#def3e5` / `#1f4e25` | `#1f4e25` / `#effaf3` |
| `--bg-status-warning` / `--text-status-warning` | `#fdf5f1` / `#d25e28` | `#45240d` / `#f1a275` |
| `--bg-status-error` / `--text-status-error` | `#fff0f0` / `#ff002a` | `#4d100e` / `#ff8583` |
| Danger-Skala | `#ff002a` → hover `#fa423e` → press `#ba2623` | `#ff002a` / `#fa423e` / `#ff6764` |
| Discovery (lila, für „Neu/AI") | `#924ff726` bg, `#643cae` label | `#924ff726` bg, `#b897f4` label |

### Interaktions-Matrix (das Herzstück)
Für jede Button-Variante existieren 5 States. Auszug Dark / Light:

| Variante | State | Background | Label |
|---|---|---|---|
| **primary** | default | `#ffffff` / `#0d0d0d` | `#0d0d0d` / `#ffffff` |
| | hover | `#ffffffcc` / `#000000cc` | unverändert |
| | press | `#ffffffe5` / `#000000e5` | unverändert |
| **secondary** | default | transparent | `#ffffff` / `#0d0d0d` |
| | hover | `#ffffff1a` / `#0000000d` | `#ffffffe5` / `#000000e5` |
| | press | `#ffffff0d` / `#0000000d` | `#ffffffcc` / `#000000cc` |
| | selected | `#ffffff1a` / `#0000000d` | `#f3f3f3` / `#0d0d0d` |
| **tertiary** (Karten) | default | `#212121` / `#ffffff` | — |
| | hover | `#181818` / `#f9f9f9` | — |
| | press | `#0d0d0d` / `#f3f3f3` | — |
| **accent** | hover | `#99ceff26` / `#0285ff0a` | `#63a8f8` / `#3a83f7` |
| **danger-primary** | default/hover/press | `#ff002a` / `#fa423e` / `#ba2623` | `#ffffff` |

Merke: **Hover in Dark = Weiß mit 10 % Alpha, Press = Weiß mit 5 %.** In Light spiegelverkehrt mit Schwarz. Nie mit fixen Grauwerten arbeiten — immer Alpha-Overlays, damit es auf jeder Fläche funktioniert.

`--surface-hover`: `#00000012` (L) / `#ffffff26` (D)
`--interactive-border-focus`: `#0d0d0d` (L) / `#ffffff` (D)

---

## 3. Typografie

**Font-Stack (system-first, keine Webfonts!):**
```
--font-sans: -apple-system-body, ui-sans-serif, -apple-system, system-ui,
             "Segoe UI", Helvetica, "Apple Color Emoji", Arial, sans-serif,
             "Segoe UI Emoji", "Segoe UI Symbol";
--font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas,
             "Liberation Mono", monospace;
```
Bemerkenswert: `-apple-system-body` an erster Stelle → erbt auf iOS/macOS die Systemschriftgröße des Nutzers (Dynamic Type). Das ist ein bewusster Accessibility-Zug.

**Semantische Text-Styles** (nicht `text-xl` o. ä. verwenden, sondern diese Rollen):

| Rolle | Size | Line-height | Weight | Letter-spacing |
|---|---|---|---|---|
| `heading-1` | 36 px | 40 px | 600 | — |
| `heading-app` (Seitentitel) | 28 px | 34 px | 400 | — |
| `heading-app-emphasized` | 28 px | 34 px | 600 | — |
| `title-1` | 28 px | 34 px | 400 | — |
| `title-1-emphasized` | 28 px | 34 px | 500 | +0.38 px |
| `title-2-emphasized` | 22 px | 28 px | 500 | −0.26 px |
| `title-3-emphasized` | 20 px | 25 px | 500 | −0.45 px |
| `heading-2` | 24 px | 28 px | 600 | — |
| `heading-3` | 18 px | 26 px | 600 | — |
| `headline` | 17 px | 22 px | 400 | — |
| `body` / `body-regular` | 16 px | 26 px | 400 | — |
| `body-emphasized` | 16 px | 26 px | 600 | — |
| `callout` | 16 px | 21 px | 400 | — |
| `body-small` | 14 px | 20 px | 400 | — |
| `body-small-medium` | 14 px | 20 px | 500 | — |
| `body-small-emphasized` | 14 px | 20 px | 600 | — |
| `subheadline-emphasized` | 14 px | 20 px | 500 | −0.18 px |
| `footnote` | 13 px | 18 px | 400 | — |
| `footnote-emphasized` | 13 px | 18 px | 500 | −0.08 px |
| `caption` | 12 px | 16 px | 400 | — |
| `monospace` | 15 px | 22 px | 400 | — |

**Regel, die man an der Seite sieht:** Die UI lebt fast vollständig von **14 px** (Listen, Buttons, Tabs, Metadaten) und **28 px** (Seitentitel). 16 px nur für Fließtext/Composer. Hierarchie kommt über **Weight (400/500/600) und Farbe (primary/secondary/tertiary)**, nicht über große Schriftgrößen.

Gewichte im Einsatz: 400 (Body), 500 (Labels, Buttons, Listen-Titel), 600 (Headings). 700+ praktisch nie.

---

## 4. Spacing, Radius, Shadow

**Spacing-Basis:** `--spacing: 0.25rem` (4 px). Alle Abstände sind Vielfache: 4 / 6 / 8 / 12 / 16 / 20 / 24.

**Radius-Skala:**
```
xs 2px · sm 4px · md 6px · lg 8px · xl 12px · 2xl 16px · 3xl 24px · 4xl 32px
```
Plus `rounded-full` für Buttons, Tabs, Pills, Avatare. **Composer benutzt 28 px** (Sonderwert zwischen 3xl und 4xl).

**Shadows — bewusst sehr zurückhaltend:**
```
--shadow-xs: 0 0 15px #0000001a
--shadow-sm: 0 1px 3px #0000001a, 0 1px 2px -1px #0000001a
--shadow-md: 0 4px 6px -1px #0000001a, 0 2px 4px -2px #0000001a
--shadow-lg: 0 10px 15px -3px #0000001a, 0 4px 6px -4px #0000001a
--drop-shadow-sm: 0 1px 2px #00000026
```
Im Dark Mode ersetzt ein **1-px-Innen-Ring in Weiß ~20 %** den Schatten (`inset 0 0 0 1px #ffffff33`). Kanten werden zusätzlich mit `--sharp-edge-top-shadow: 0 1px 0 #ffffff0d` gesetzt — ein 1-px-Highlight statt Schlagschatten.

**Elevation-Prinzip:** Tiefe entsteht durch **Flächenhelligkeit + 1-px-Border**, nicht durch Schatten. `#000000` (App) → `#212121` (Panel) → `#303030` (darüber) → `#1b1b1b` (Popover, dunkler aber mit Border).

---

## 5. Layout-Maße (gemessen)

| Element | Wert |
|---|---|
| Sidebar-Rail (collapsed) | **52 px**, `border-right: 1px rgba(255,255,255,.1)` |
| Sidebar (expanded) | `--sidebar-width: 260px` |
| Content-Spalte (Composer, Liste, Header) | **768 px**, zentriert |
| Seiten-Header-Höhe | 36 px Content-Höhe, `gap: 6px` Titel↔Icon |
| Composer | 768 × 52 px min, `border-radius: 28px` |
| Listenzeile | `min-height: 64px`, `padding: 12px` |
| Icon-Button | 36 × 36 px (Touch: 40 px) |
| Button (secondary) | Höhe 36 px, `padding: 0 12px` |
| Tab-Pill | Höhe 38 px, `padding: 9px 16px` |
| Container-Skala | xs 320 · sm 384 · md 448 · lg 512 · xl 576 · 2xl 672 · 3xl 768 · 4xl 896 · 5xl 1024 px |

Responsive-Breakpoints: Tailwind-Standard (`sm` 640, `md` 768, `lg` 1024). Die Sidebar verschwindet unter `md`; der Seitentitel fällt dort von 28 px/500 auf 18 px/400 zurück.

---

## 6. Komponenten-Spezifikationen

### 6.1 Composer (das Signature-Element)
```
Container : width 768px · min-height 52px · radius 28px
            bg #212121 (D) / #ffffff (L)
            box-shadow: inset 0 0 0 1px rgba(255,255,255,.2)   ← statt Border
            transition: background-color/border-color 200ms cubic-bezier(.4,0,.2,1)
            cursor: text  (gesamte Fläche fokussiert das Input)
Grid      : [leading | primary | trailing] + optionale header/footer-Zeile
Innenraum : padding 5px 8px (kollabiert) → 9px 8px (expandiert)
Input-Row : min-height 56px, padding-inline 7px/6px, items-center
Input     : font 16px/26px, kein Border, kein Outline
Leading   : "+"-Icon-Button 36×36, radius full
Trailing  : Text-Select ("High") + Mic-Icon-Button + primärer Action-Button
Primary-Btn: 36×36 kreisrund, Akzentfläche, Icon invertiert
```
Merkmale zum Nachbauen: **runde Pill-Form, Icon links, Controls rechts, Höhe wächst mit Inhalt bis `max(30svh, 5rem)`**, danach interner Scroll mit Fade-Maske oben/unten (`--top-fade` / `--bottom-fade`).

### 6.2 Listenzeile
```
li  : display flex · align-items center · min-height 64px · padding 12px
      font-size 14px · cursor pointer · user-select none
      border-bottom 1px #414141   (divide-y auf <ol>)
      hover  → background #ffffff1a
      active → background #ffffff0d
Inhalt: [Textblock (grow, overflow hidden)] — gap 16px — [Meta rechts]
Titel : 14px / 20px / weight 500 / --text-primary
Snippet: 14px / 20px / weight 400 / --text-secondary
         truncate (overflow hidden · text-overflow ellipsis · white-space nowrap)
         margin-top 8px
Meta  : Datum 14px / --text-secondary, rechtsbündig
Hover : Datum wird durch "…"-Icon-Button ersetzt (gleiche Breite, kein Layout-Shift)
```
Das Datum-→-Menü-Tauschen beim Hover ist ein zentrales UX-Detail: **Sekundäraktionen erscheinen erst bei Hover, ohne dass die Zeile springt.**

### 6.3 Buttons
```
.btn-secondary : height 36px · padding 0 12px · radius 9999px
                 font 14px/20px weight 500
                 bg --bg-primary (#212121 D)
                 border 1px rgba(255,255,255,.15)
                 hover → bg #ffffff1a · press → #ffffff0d
                 touch-Geräte: height 40px
.btn-primary   : bg --text-primary, label --text-inverted (invertiert!)
                 hover → 80 % Alpha der Fläche
.btn-icon      : 36×36 · radius 10px (Menü-Items) bzw. full (Toolbar)
```
Focus (nur Tastatur, `:focus-visible` bzw. `.keyboard-focused`):
`outline: 1.5px solid var(--text-primary); outline-offset: 2.5px` — bzw. `ring-2 + ring-offset-1`. **Maus-Klicks erzeugen keinen Ring.**

### 6.4 Tabs / Segmented Control
```
Tab      : radius full · padding 9px 16px · font 14px/20px weight 500
           inaktiv: color --text-tertiary (#afafaf), transparent
           aktiv  : color --text-primary + bg --interactive-bg-secondary-selected
                    + ring 1px --border-default
           transition: color/background/border 150ms cubic-bezier(.4,0,.2,1)
Segmented: Wrapper radius full, bg --bg-primary, innen inset-px-Layer #131313,
           Grid grid-cols-2, gleitender aktiver Indikator (pointer-events none)
```

### 6.5 Skeleton / Loading
Graue Platzhalterbalken in Zeilenform: `height 24px · radius 8px · width 40 %` in `--bg-tertiary`, mit Shimmer-Maske (`--mask-shimmer-offset`). Kein Spinner in Listen.

---

## 7. Motion

```
--ease-in     : cubic-bezier(.4, 0, 1, 1)
--ease-out    : cubic-bezier(0, 0, .2, 1)
--ease-in-out : cubic-bezier(.4, 0, .2, 1)     ← Standard für alle Farbwechsel
```
Dauern: **150 ms** für Farb-/Border-Transitions, **200 ms** für Composer-Flächen, **667 ms** für Spring-Bewegungen.

Für Layout-/Panel-Bewegungen benutzt die App **`linear()`-Spring-Easings** statt Beziers:
```
--spring-fast   (0.667s)  weich, kein Overshoot
--spring-common (0.667s)  Standard-Spring
--spring-bounce (0.833s)  leichter Overshoot (max 1.0005)
--spring-fast-bounce (1s) Overshoot bis 1.048
--spring-slow-bounce (1.167s) Overshoot bis 1.046
```
Die vollständigen `linear(...)`-Werte stehen in `chatgpt-tokens.css`. Alle Animationen sind mit `motion-safe:` gegatet → `prefers-reduced-motion` schaltet sie ab.

---

## 8. UX-Patterns, die den Charakter ausmachen

1. **Alles auf einer Spalte, 768 px.** Header, Composer und Liste teilen sich exakt dieselbe Breite und linke Kante. Keine Karten-Raster.
2. **Composer über der Liste, nicht am Seitenende.** Auf der Projektseite ist das Eingabefeld das erste Aktionselement direkt unter dem Titel — Primäraktion zuerst.
3. **Rail statt Sidebar.** 52 px Icon-Leiste, expandiert auf 260 px. App-Hintergrund ist reines Schwarz, der Content sitzt auf `#212121` — der Kontrast der Flächen ersetzt Trennlinien.
4. **Progressive Disclosure beim Hover.** Sekundäraktionen (Menü, Löschen) sind unsichtbar, bis die Zeile gehovt wird, und ersetzen dabei ein gleich breites Element.
5. **Flache Divider statt Karten.** Listen sind `divide-y` mit 1 px `#414141` — keine Borders, keine Schatten, keine Gaps.
6. **Inline-Editing.** Der Seitentitel ist ein `<button>` mit `appearance:none`, das wie Text aussieht und beim Klick editierbar wird.
7. **Truncation überall.** Jede Textzeile ist einzeilig mit Ellipse; die Zeilenhöhe bleibt dadurch konstant bei 64 px.
8. **Keine Webfonts, keine Icon-Font.** Systemschrift + Inline-SVGs → sofortiges First Paint, kein FOUT.
9. **Dark Mode ist gleichwertig, nicht invertiert.** Es existieren zwei vollständig eigene Wertesätze; `--bg-secondary-surface` ist z. B. in Light `#f9f9f9`, in Dark `#000000` — nicht einfach gespiegelt.
10. **Ruhige Farbigkeit.** Genau eine Akzentfarbe (Blau `#3a83f7` / `#63a8f8`), eine Gefahrenfarbe, eine Discovery-Farbe. 95 % der Fläche ist neutral.

---

## 9. Accessibility-Anforderungen (aus dem Code ablesbar)

- `:focus-visible`-Ringe mit 1.5–2 px und Offset, Farbe `--text-primary` → hoher Kontrast in beiden Themes.
- Eigene Klasse `keyboard-focused` / `not-keyboard-focused:outline-none` → Fokus nur bei Tastaturnavigation.
- `-apple-system-body` respektiert Nutzer-Schriftgröße.
- Alle Animationen `motion-safe`-gegatet.
- Touch-Targets auf `touch:`-Geräten auf 40 px erhöht (Desktop 36 px).
- Semantik: `<main>`, `<ol>/<li>` für Listen, `<h1>` für den Seitentitel, `<form>` um den Composer.
- Textkontraste: `--text-secondary` `#cdcdcd` auf `#212121` ≈ 11:1; `--text-tertiary` `#afafaf` ≈ 7:1 — beide deutlich über AA.

---

## 10. Prompt-Vorschlag für die Claude-Code-Session

> Baue [Beschreibung deiner Seite]. Halte dich strikt an das beiliegende Design-System
> (`chatgpt-design-reference.md` + `chatgpt-tokens.css`):
>
> - Übernimm `chatgpt-tokens.css` **unverändert** als Token-Layer und benutze ausschließlich
>   diese Custom Properties — keine hartcodierten Farben, Radien oder Schriftgrößen.
> - Light + Dark Mode von Anfang an, klassenbasiert (`html.dark` / `html.light`) mit
>   `prefers-color-scheme` als Default.
> - Systemschrift-Stack, keine Webfonts.
> - Content-Spalte 768 px, zentriert; Sidebar-Rail 52 px.
> - Jede interaktive Komponente bekommt alle fünf States (default/hover/press/inactive/selected)
>   über die `--interactive-*`-Tokens.
> - Tiefe über Flächenhelligkeit + 1-px-Border, nicht über Schatten.
> - Hierarchie über Weight und Textfarbe, nicht über Schriftgröße; UI-Standard ist 14 px.
> - Listen als `divide-y`, Zeilen min-height 64 px, Sekundäraktionen erst bei Hover.
> - Transitions 150 ms `cubic-bezier(.4,0,.2,1)`, Layout-Bewegungen mit den `--spring-*`-Easings,
>   alles `motion-safe`-gegatet.
> - `:focus-visible`-Ring 1.5 px `--interactive-border-focus`, Offset 2.5 px; kein Ring bei Maus.
> - Semantisches HTML, Touch-Targets ≥ 40 px auf Touch-Geräten.
>
> Kein OpenAI-Branding, keine ChatGPT-Logos oder -Wortmarken — nur das Layout- und Token-System.
