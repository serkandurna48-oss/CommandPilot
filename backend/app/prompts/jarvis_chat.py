"""
CommandPilot — Jarvis Chat Prompt

Builds the prompt for the second-brain chat endpoint. Structured JSON output
(reply + suggested_actions) via OpenAI's strict json_schema mode — same
pattern as prompts/daily_plan.py, not a second AI pipeline (JARVIS-C1,
Phase 3). See app/services/ai_service.py's generate_chat_reply() and
app/models/jarvis.py's JarvisChatAI for where JSON_SCHEMA is used and parsed.
"""

from datetime import datetime, timezone

_DE_WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def build_system_prompt(language: str = "de") -> str:
    """
    language mirrors prompts/daily_plan.py's build_user_prompt() contract:
    the profile's language ("en"/"de"), defaulting to "de" here only because
    that was this prompt's original hardcoded behavior — callers should
    always pass the real profile language (see routers/jarvis.py). Unlike
    daily_plan.py, the *instructional* prose stays German throughout (it's
    talking to the model, not the user) — only the two rules whose content
    reaches the user (which language to reply in, and the exact wording of
    the honest "I don't know" admission) vary.
    """
    is_de = language != "en"
    lang_rule = "Antworte ausschließlich auf Deutsch." if is_de else "Antworte ausschließlich auf Englisch (Englisch, nicht Deutsch)."
    no_knowledge_example = (
        '"Dazu finde ich in deinem Second Brain nichts."'
        if is_de
        else '"I can\'t find anything about that in your Second Brain."'
    )
    return f"""Du bist Jarvis, der persönliche Second-Brain-Assistent des Nutzers innerhalb von CommandPilot — wie ein kompetenter Kollege, dem er vertraut, nicht wie ein steifer Corporate-Assistent.

Regeln, ausnahmslos:
- {lang_rule}
- Nutze ausschließlich den bereitgestellten SECOND-BRAIN-KONTEXT und die Frage des Nutzers. Erfinde nichts, was nicht im Kontext steht oder sich direkt daraus ableiten lässt.
- Fehlt das nötige Wissen im Kontext, sag das offen und ehrlich ({no_knowledge_example}) statt zu raten oder zu halluzinieren.
- Schreibe KEINE eigene Quellenliste und KEINE "Quellen:"-Zeile in dein reply-Feld — die Oberfläche zeigt die Quellen bereits separat an. Das reply-Feld enthält ausschließlich den inhaltlichen Text.
- Ton: sehr locker und Bro-Style, wie ein kluger Kumpel, der genau weiß wovon er redet — nicht wie eine KI, nicht wie ein Assistent im Anzug. Kurze, punchy Sätze, ruhig umgangssprachlich und mit Ecken und Kanten. Das ist KEIN Widerspruch zu professionell: locker im Ton, aber scharf und präzise im Inhalt — bei Business- und Strategie-Themen wird die Aussage dadurch nicht oberflächlicher, sondern genau so durchdacht wie sonst, nur ohne Corporate-Floskeln ("Das ist eine großartige Frage!", "Gerne helfe ich dir weiter") und ohne Steifheit. Beispiel für den Ton: "Deine CampPilot-Roadmap hängt grad an einem Punkt: Du hast noch kein Ticket für den nächsten Schritt definiert. Blockiert nix akut, aber du verlierst Momentum, je länger das offen bleibt." Genau so — locker im Ton, scharf im Inhalt, nie das eine auf Kosten vom anderen. Der Ton ändert nur WIE du's sagst, nicht WAS: Fakten bleiben exakt aus dem Kontext.
- Sag nicht nur WAS im Kontext steht, sondern in ein bis zwei Sätzen auch WARUM es gerade zählt oder was der Nutzer als Nächstes damit machen sollte. Der Mehrwert muss aus der Antwort selbst rausspringen, nicht nur rohe Fakten auflisten — aber nichts erfinden, das nicht aus dem Kontext ableitbar ist.

AUSGABEFORMAT: reines JSON-Objekt, keine Markdown-Codeblöcke, keine Erklärung außerhalb des Objekts. Genau diese zwei Top-Level-Felder:
{{
  "reply": "<deine Antwort an den Nutzer, siehe Regeln oben>",
  "suggested_actions": [ ... ]
}}

suggested_actions — Vorschläge für mögliche Work Orders, NICHT deren Ausführung:
- Beschreibt die Nachricht ein konkretes Ziel oder Vorhaben, das zu Code-/Projektarbeit werden könnte (z. B. "bereite X vor", "leg mir Work Orders an für Y", "plane Z"): fülle suggested_actions mit GENAU ZWEI Einträgen — nie einem, nie mehr als zwei.
- Ist die Nachricht eine gewöhnliche Wissensfrage ohne erkennbares Handlungsziel: suggested_actions bleibt ein leeres Array [].
- Jeder Eintrag hat genau diese Felder: title, description, team_type (Standard "development", falls kein anderes Team erkennbar ist), target_repo_name (Repo-Name oder null, falls unklar), risk ("low"|"medium"|"high"), requires_approval (true/false — ob ein Mensch vor jeder Teilaktion nicken muss), sources (Liste aus source_file/source_heading — nur Quellen, die die Beschreibung tatsächlich stützen, sonst ein leeres Array).
- suggested_actions sind Vorschläge zur Vorschau in der Oberfläche — niemals eine Ausführung, niemals eine automatische Bestätigung. Ein Mensch entscheidet dort explizit über Bestätigen oder Ablehnen; ohne diesen Klick passiert nichts.
"""


# Backward-compat default (German) — existing tests/callers that referenced
# the old module-level constant keep working; app/services/ai_service.py's
# generate_chat_reply() calls build_system_prompt(language) directly instead.
SYSTEM_PROMPT = build_system_prompt("de")


JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reply", "suggested_actions"],
    "properties": {
        "reply": {
            "type": "string",
            "description": "The reply text to show the user, in German. Never includes a sources list — the UI renders sources separately.",
        },
        "suggested_actions": {
            "type": "array",
            "maxItems": 2,
            "description": (
                "Exactly two entries when, and only when, the user's message describes a "
                "goal that could become work — never one, never more than two. Empty for "
                "ordinary knowledge questions."
            ),
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "title", "description", "team_type", "target_repo_name",
                    "risk", "requires_approval", "sources",
                ],
                "properties": {
                    "title": {"type": "string", "description": "Short, specific work order title."},
                    "description": {"type": "string", "description": "The work order's goal — what should get done."},
                    "team_type": {"type": "string", "description": "E.g. 'development'."},
                    "target_repo_name": {"type": ["string", "null"], "description": "Target repo name, or null if unclear."},
                    "risk": {"type": "string", "enum": ["low", "medium", "high"]},
                    "requires_approval": {"type": "boolean", "description": "Whether a human should approve every sub-action, not just the sensitive ones."},
                    "sources": {
                        "type": "array",
                        "description": "Only sources that actually support this proposal — empty array if none.",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["source_file", "source_heading"],
                            "properties": {
                                "source_file": {"type": "string"},
                                "source_heading": {"type": "string", "description": "Empty string if the source is a whole file, not a specific section."},
                            },
                        },
                    },
                },
            },
        },
    },
}


def build_chat_prompt(message: str, history: list[dict], context_block: str, language: str = "de") -> str:
    """
    Build the user-turn prompt: today's date, second-brain context, prior
    turns, current question. context_block is a pre-formatted, pre-budgeted
    block from vault_service (see get_context_for_query) — empty string when
    the vault is unavailable or nothing matched, in which case the model is
    instructed to say so rather than invent an answer. language mirrors
    build_system_prompt()'s contract — the trailing reply-language
    instruction is repeated here (same reinforcement pattern as
    daily_plan.py's lang_instruction) since it's the last thing the model
    reads before generating.

    The leading HEUTIGES DATUM line (found missing 23.09.2026, live in the
    browser — Jarvis said "heute" about a calendar event that was actually
    tomorrow) is the model's only anchor for "heute"/"morgen"/"diese Woche":
    calendar_service/notion_tasks_service events and due dates are absolute
    ISO timestamps, and without this line the model has no way to know what
    "today" even is. daily_plan.py's build_user_prompt() already includes
    checkin['checkin_date'] for the same reason — this brings jarvis_chat.py
    to parity. UTC, not localized — see the inline comment above date_line
    for why.
    """
    # UTC, not a local Europe/Berlin zoneinfo lookup — matches
    # google_calendar_service.py/outlook_calendar_service.py's own
    # datetime.now(timezone.utc) (they pass "Europe/Berlin" only as a string
    # to the Composio API, never resolve it locally, precisely because
    # Windows dev machines don't ship IANA tzdata without an extra
    # dependency). Worst case this is off by the UTC/CET(-2) offset for an
    # hour or two around local midnight — negligible next to having no
    # "today" anchor at all, which is the bug this line fixes.
    now = datetime.now(timezone.utc)
    date_line = f"HEUTIGES DATUM: {now.date().isoformat()} ({_DE_WEEKDAYS[now.weekday()]})"

    context_section = (
        f"SECOND-BRAIN-KONTEXT:\n{context_block}"
        if context_block
        else "SECOND-BRAIN-KONTEXT: (leer — im Vault wurde nichts Passendes gefunden oder der Vault ist nicht verfügbar)"
    )

    history_lines = [
        f"{'Nutzer' if turn.get('role') == 'user' else 'Jarvis'}: {turn.get('content', '')}"
        for turn in history
    ]
    history_text = "\n".join(history_lines) if history_lines else "(kein bisheriger Verlauf)"
    lang_instruction = "Antworte auf Deutsch" if language != "en" else "Antworte auf Englisch (English, not German)"

    return f"""{date_line}

{context_section}

BISHERIGER VERLAUF:
{history_text}

AKTUELLE FRAGE:
{message}

{lang_instruction}, ausschließlich basierend auf dem Second-Brain-Kontext oben. Erfinde nichts. Fehlt das Wissen, sag das offen. Schreibe keine eigene Quellenliste oder "Quellen:"-Zeile in das reply-Feld — das übernimmt die Oberfläche separat. Gib genau das im Systemprompt beschriebene JSON-Objekt zurück (reply + suggested_actions), sonst nichts.
"""
