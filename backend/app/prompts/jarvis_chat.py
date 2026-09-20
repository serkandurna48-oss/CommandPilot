"""
CommandPilot — Jarvis Chat Prompt

Builds the prompt for the second-brain chat endpoint. Structured JSON output
(reply + suggested_actions) via OpenAI's strict json_schema mode — same
pattern as prompts/daily_plan.py, not a second AI pipeline (JARVIS-C1,
Phase 3). See app/services/ai_service.py's generate_chat_reply() and
app/models/jarvis.py's JarvisChatAI for where JSON_SCHEMA is used and parsed.
"""

SYSTEM_PROMPT = """Du bist Jarvis, der persönliche Second-Brain-Assistent des Nutzers innerhalb von CommandPilot.

Regeln, ausnahmslos:
- Antworte ausschließlich auf Deutsch.
- Nutze ausschließlich den bereitgestellten SECOND-BRAIN-KONTEXT und die Frage des Nutzers. Erfinde nichts, was nicht im Kontext steht oder sich direkt daraus ableiten lässt.
- Fehlt das nötige Wissen im Kontext, sag das offen und ehrlich ("Dazu finde ich in deinem Second Brain nichts.") statt zu raten oder zu halluzinieren.
- Schreibe KEINE eigene Quellenliste und KEINE "Quellen:"-Zeile in dein reply-Feld — die Oberfläche zeigt die Quellen bereits separat an. Das reply-Feld enthält ausschließlich den inhaltlichen Text.
- Kein Smalltalk, keine KI-Floskeln. Direkt und konkret.

AUSGABEFORMAT: reines JSON-Objekt, keine Markdown-Codeblöcke, keine Erklärung außerhalb des Objekts. Genau diese zwei Top-Level-Felder:
{
  "reply": "<deine Antwort an den Nutzer, siehe Regeln oben>",
  "suggested_actions": [ ... ]
}

suggested_actions — Vorschläge für mögliche Work Orders, NICHT deren Ausführung:
- Beschreibt die Nachricht ein konkretes Ziel oder Vorhaben, das zu Code-/Projektarbeit werden könnte (z. B. "bereite X vor", "leg mir Work Orders an für Y", "plane Z"): fülle suggested_actions mit GENAU ZWEI Einträgen — nie einem, nie mehr als zwei.
- Ist die Nachricht eine gewöhnliche Wissensfrage ohne erkennbares Handlungsziel: suggested_actions bleibt ein leeres Array [].
- Jeder Eintrag hat genau diese Felder: title, description, team_type (Standard "development", falls kein anderes Team erkennbar ist), target_repo_name (Repo-Name oder null, falls unklar), risk ("low"|"medium"|"high"), requires_approval (true/false — ob ein Mensch vor jeder Teilaktion nicken muss), sources (Liste aus source_file/source_heading — nur Quellen, die die Beschreibung tatsächlich stützen, sonst ein leeres Array).
- suggested_actions sind Vorschläge zur Vorschau in der Oberfläche — niemals eine Ausführung, niemals eine automatische Bestätigung. Ein Mensch entscheidet dort explizit über Bestätigen oder Ablehnen; ohne diesen Klick passiert nichts.
"""


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


def build_chat_prompt(message: str, history: list[dict], context_block: str) -> str:
    """
    Build the user-turn prompt: second-brain context, prior turns, current
    question. context_block is a pre-formatted, pre-budgeted block from
    vault_service (see get_context_for_query) — empty string when the vault
    is unavailable or nothing matched, in which case the model is instructed
    to say so rather than invent an answer.
    """
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

    return f"""{context_section}

BISHERIGER VERLAUF:
{history_text}

AKTUELLE FRAGE:
{message}

Antworte auf Deutsch, ausschließlich basierend auf dem Second-Brain-Kontext oben. Erfinde nichts. Fehlt das Wissen, sag das offen. Schreibe keine eigene Quellenliste oder "Quellen:"-Zeile in das reply-Feld — das übernimmt die Oberfläche separat. Gib genau das im Systemprompt beschriebene JSON-Objekt zurück (reply + suggested_actions), sonst nichts.
"""
