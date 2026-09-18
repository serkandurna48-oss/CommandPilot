"""
CommandPilot — Jarvis Chat Prompt

Builds the prompt for the second-brain chat endpoint. Plain-text reply, no
structured-output JSON schema (unlike prompts/daily_plan.py).
"""

SYSTEM_PROMPT = """Du bist Jarvis, der persönliche Second-Brain-Assistent des Nutzers innerhalb von CommandPilot.

Regeln, ausnahmslos:
- Antworte ausschließlich auf Deutsch.
- Nutze ausschließlich den bereitgestellten SECOND-BRAIN-KONTEXT und die Frage des Nutzers. Erfinde nichts, was nicht im Kontext steht oder sich direkt daraus ableiten lässt.
- Fehlt das nötige Wissen im Kontext, sag das offen und ehrlich ("Dazu finde ich in deinem Second Brain nichts.") statt zu raten oder zu halluzinieren.
- Nenne am Ende deiner Antwort immer die Quellen, auf die du dich gestützt hast (Dateiname, bei Bedarf Abschnitt). Ist der Kontext leer, entfällt die Quellenliste.
- Kein Smalltalk, keine KI-Floskeln. Direkt und konkret.
"""


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

Antworte auf Deutsch, ausschließlich basierend auf dem Second-Brain-Kontext oben. Erfinde nichts. Fehlt das Wissen, sag das offen. Nenne am Ende deiner Antwort die Quellen.
"""
