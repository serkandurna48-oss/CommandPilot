Auftrag-ID: JARVIS-D1
Arbeitsverzeichnis: C:\Users\serka\dev\cp-design
Branch: feat/design-system
Ausgangscommit: 4f97361

ZIEL
Das CommandPilot-Frontend bekommt eine eigene, ruhige und präzise Gestaltung.
Orientierung: die klare Informationshierarchie von Linear, die konsistenten
Grundlagen von Vercels Geist. Keine Marke nachbauen — eine eigene Jarvis-
Identität. Neutrale dunkle Flächen, zurückhaltende Akzentfarbe, klare
Typografie und Abstände, eindeutige Aktionen, echte Statusanzeigen.

Dieser Auftrag liefert einen klickbaren Entwurf zur Beurteilung. Die breite
Umstellung auf Operator, Dashboard und übrige Seiten folgt erst danach.

BESITZVERHÄLTNISSE — parallel läuft JARVIS-M1 im Worktree cp-multiagent
Du darfst ändern:
  frontend/app/globals.css, frontend/tailwind.config.ts,
  frontend/components/ui/*, frontend/components/layout/*,
  frontend/app/design-preview/* (neu), frontend/lib/i18n.ts (nur neue Strings)
Du darfst NICHT ändern:
  backend/**, scripts/**, supabase/**,
  frontend/components/jarvis/*, frontend/components/operator/*
Musst du außerhalb deiner Liste etwas ändern: melden statt tun.

PHASE 1 — Bestandsaufnahme und Briefing. Danach anhalten.
Sieh dir den echten Stand an, nicht die Dokumentation: welche UI-Komponenten
existieren in components/ui, wie ist das Theme heute aufgebaut, wie sieht
/jarvis nach Auftrag A1 tatsächlich aus. A1 hat die Quellenansicht bereits
geändert — Treffer und Basiskontext sind jetzt getrennt, und das Modell
schreibt keine "Quellen:"-Zeile mehr in den Fließtext. Bau darauf auf.
Liefere ein kurzes Designbriefing: Gestaltungsregeln, Skalen für Typografie,
Abstände und Radien, Statusfarben. Zwei bis drei Vorschläge für die
Akzentfarbe, damit Serkan an einer Stelle entscheidet statt an zwanzig.

PHASE 2 — Designwerte und Primitive
Gemeinsame Tokens für Flächen, Text, Akzent, Status, Abstände, Radien und
Typografie. Bestehende Komponenten in components/ui gezielt weiterentwickeln
statt ersetzen. Neue Bibliotheken nur bei konkretem Bedarf und mit Rückfrage.
Kein Theme-Umschalter, keine zweite Farbwelt.

PHASE 3 — Klickbarer Entwurf unter /design-preview
Eine eigene Route, deutlich als Prototyp gekennzeichnet, nicht in der
Navigation verlinkt. Sie zeigt ohne echte API-Aufrufe:
  - App-Rahmen mit klar gegliederter Navigation; Jarvis und Arbeitsaufträge
    leicht erreichbar
  - Jarvis-Unterhaltung: sinnvolle Inhaltsbreite, formatierte Antworten,
    angenehmer Eingabebereich
  - Quellen kompakt, bei Bedarf aufklappbar, mit sichtbarer Unterscheidung
    zwischen tatsächlich verwendeten Quellen und Basiskontext
  - Auftragsvorschau als reine Gestaltung. Der Command Layer existiert noch
    nicht — die Karten dürfen nichts anlegen und müssen als Prototyp erkennbar
    sein. Keine vorgetäuschte Funktion.
  - optionales Detailpanel für Quellen oder Aufträge auf großen Displays
  - alle Zustände: leer, lang, ladend, fehlerhaft mit Wiederholung
Zusätzlich: fest eingetragene Statusbehauptungen wie "System Online" entfernen
oder an überprüfbare Daten binden.

PHASE 4 — Rahmen und Chat übernehmen die Gestaltung
Erst nach Serkans Freigabe des Entwurfs. App-Rahmen und /jarvis bekommen die
Tokens. Die Struktur der Jarvis-Komponenten bleibt unverändert — sie gehören
M1. Wenn das Design dort strukturelle Änderungen bräuchte: melden, nicht tun.

NICHT-ZIELE
Kein Backend-Umbau, keine neuen Integrationen, keine Agentenausführung, keine
Neugestaltung von Operator und Dashboard, kein Eingriff in Authentifizierung,
Fehlerbehandlung oder Sprachunterstützung.

ABNAHME
- Browserprüfung auf Desktop und schmalem Mobilbildschirm: nichts
  abgeschnitten, kein störendes horizontales Scrollen
- lesbarer Kontrast, sichtbarer Tastaturfokus, beschriftete Bedienelemente,
  funktionierende Tastaturbedienung
- lange Antworten und viele Quellen bleiben bedienbar
- bestehende APIs, Auth, Fehlerbehandlung und Sprachen weiterhin funktionsfähig
- scripts/check.ps1 grün
- Screenshots der wichtigsten Zustände, dazu der klickbare Stand

ÜBERGABE
Nach jeder Phase: Commit-IDs, Ausgabe von check.ps1, was du selbst im Browser
geprüft hast, ungetestete Bereiche, Einschränkungen. Commit erlaubt, wenn
check.ps1 grün ist und du vorher zwei Zeilen dazu sagst. Nicht pushen, nicht
nach main mergen.
Nach Phase 1 und nach Phase 3 anhalten und auf Serkan warten.

Referenzen:
  https://linear.app/now/behind-the-latest-design-refresh
  https://vercel.com/geist/stack