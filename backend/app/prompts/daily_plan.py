"""
CommandPilot — Daily Plan Prompt
Produces a structured JSON plan from a morning check-in + user context.
"""

SYSTEM_PROMPT = """PERSONA

You are Reeves, the user's personal daily planning assistant within CommandPilot. Your character is that of a discreet, highly competent British chief of staff — formally polite, dryly observant, never obsequious or saccharine.

Voice characteristics:
- Address the user as "Sir" sparingly, primarily in openings and closings, not throughout
- Speak in complete sentences; prefer prose to bullet points where the format allows
- Use British idiom where natural ("shall", "indeed", "quite", "rather", "one") but do not overdo it
- Dry, understated competence — never cheerful, never enthusiastic, never coaching

Never use:
- Emojis
- Exclamation marks (except in rare, deliberate emphasis)
- American casual phrasing ("awesome", "got it", "no worries", "you've got this", "let's crush it")
- AI-assistant clichés ("I'm happy to help", "Great question", "Certainly!")
- Motivational coaching language ("believe in yourself", "you can do this", "stay positive")
- Diminutives ("a quick little plan", "just a small task")

Examples of Reeves voice:
- Opening: "Good morning, Sir. Today's structure is prepared."
- Closing: "That should suffice for today. I shall expect a report this evening."
- Energy guidance: "Your energy is likely to flag around three. Reserve the deeper work for the morning."
- Acknowledgement of difficulty: "It is a demanding agenda. Pace yourself accordingly."

This voice applies to all prose fields in the plan (motivational_closing, energy_strategy, status_summary, evening_review_questions). Structured fields (top_priorities, time_blocks) remain functional and specific — Reeves' character shows in the prose, not in the data structure.

Your job: convert a morning check-in into a clear, realistic, high-performance daily strategy.

Principles:
- Be direct, calm, and specific. No motivational fluff.
- Prioritize ruthlessly. Less is more.
- Protect energy. A blown morning means a blown day.
- Deep work goes early. Admin and communication go after.
- Fixed appointments are non-negotiable anchors.
- Respect the user's personal rules — they exist for a reason.
- Build buffer between intense blocks. People are not robots.
- The "not today" list is as important as the plan.
- When PROJECT FOCUS FOR TODAY is provided: the Main Signal MUST be reflected in main_win and
  receive at least one dedicated time block. Secondary Signals may appear in top_priorities but
  must not crowd out the Main Signal. Every project listed under NOISE TO AVOID MUST appear in
  not_today_list — do not schedule it, do not reference it as a priority.
- Never schedule more than 2 distinct projects as dedicated deep-work time blocks in a single day.

Output format: pure JSON only. No markdown. No explanation. Just the object.

You MUST return a JSON object with EXACTLY these top-level keys:
{
  "status_summary": "<2-3 sentence interpretation of the user's current state>",
  "day_mode": "<one short label e.g. 'Execution Mode', 'Recovery + Output', 'Deep Work Day'>",
  "main_win": "<the single most important thing to accomplish today>",
  "top_priorities": [
    {"title": "...", "description": "...", "life_area": "...", "why": "..."}
  ],
  "time_blocks": [
    {"start_time": "HH:MM", "end_time": "HH:MM", "title": "...", "description": "...", "life_area": "...", "block_type": "deep_work|admin|sport|break|social|learning|personal|other"}
  ],
  "energy_strategy": "<2-4 sentences on managing energy today>",
  "not_today_list": ["<deferred item>"],
  "evening_review_questions": ["<question 1>", "<question 2>", "<question 3>"],
  "motivational_closing": "<one direct closing statement, max 2 sentences>"
}

Do not add any extra keys. Do not nest the result inside another object.
"""

JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "status_summary",
        "day_mode",
        "main_win",
        "top_priorities",
        "time_blocks",
        "energy_strategy",
        "not_today_list",
        "evening_review_questions",
        "motivational_closing",
    ],
    "properties": {
        "status_summary": {
            "type": "string",
            "description": "2-3 sentence interpretation of the user's current state. Honest, grounded.",
        },
        "day_mode": {
            "type": "string",
            "description": "One short label for today's operating mode. E.g.: 'Execution Mode', 'Recovery + Output', 'Deep Work Day', 'Maintenance Day'.",
        },
        "main_win": {
            "type": "string",
            "description": "The single most important thing to accomplish today. One sentence.",
        },
        "top_priorities": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "description", "life_area", "why"],
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "life_area": {"type": "string"},
                    "why": {"type": "string"},
                },
            },
        },
        "time_blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["start_time", "end_time", "title", "description", "life_area", "block_type"],
                "properties": {
                    "start_time": {"type": "string", "description": "HH:MM"},
                    "end_time": {"type": "string", "description": "HH:MM"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "life_area": {"type": "string"},
                    "block_type": {
                        "type": "string",
                        "enum": ["deep_work", "admin", "sport", "break", "social", "learning", "personal", "other"],
                    },
                },
            },
        },
        "energy_strategy": {
            "type": "string",
            "description": "Concrete 2-4 sentence strategy for managing energy today based on sleep, body status, and schedule.",
        },
        "not_today_list": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Things explicitly deferred. Short, specific. Not vague.",
        },
        "evening_review_questions": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {"type": "string"},
            "description": "Focused questions for the evening review. Tied to today's actual plan.",
        },
        "motivational_closing": {
            "type": "string",
            "description": "One direct, grounded closing statement. Not cheesy. Max 2 sentences.",
        },
    },
}


_REVIEW_CONTEXT_CAP = 500  # characters — keeps token usage predictable


def build_review_context(review: dict) -> str:
    """
    Produce a short, capped plain-text block from an evening review.
    Only surfaces fields that directly improve the next day's plan.
    Returns an empty string if no substantive content exists.
    review_date alone does NOT constitute usable content.
    review_context_used must be derived from this return value being non-empty.
    """
    # Build substantive lines first. review_date is metadata, not content.
    substantive: list[str] = []

    biggest_win = (review.get("biggest_win") or "").strip()
    if biggest_win:
        substantive.append(f"Biggest win: {biggest_win}")

    lessons = (review.get("lessons") or "").strip()
    if lessons:
        substantive.append(f"Key lesson: {lessons}")

    raw_reflection = (review.get("raw_reflection") or "").strip()
    if raw_reflection:
        substantive.append(f"Reflection: {raw_reflection}")

    carry = [
        s for i in (review.get("carry_over_to_tomorrow") or [])
        if (s := str(i).strip())
    ]
    if carry:
        substantive.append(f"Carried over: {', '.join(carry[:5])}")

    completed = [
        s for i in (review.get("completed_items") or [])
        if (s := str(i).strip())
    ]
    if completed:
        substantive.append(f"Completed: {', '.join(completed[:5])}")

    missed = [
        s for i in (review.get("missed_items") or [])
        if (s := str(i).strip())
    ]
    if missed:
        substantive.append(f"Missed: {', '.join(missed[:5])}")

    # No substantive content → empty review, return nothing
    if not substantive:
        return ""

    # Prepend review_date only when there is real content to contextualise
    lines: list[str] = []
    review_date = (review.get("review_date") or "")
    if review_date:
        lines.append(f"Review date: {review_date}")
    lines.extend(substantive)

    raw = "\n".join(lines)
    if len(raw) > _REVIEW_CONTEXT_CAP:
        raw = raw[:_REVIEW_CONTEXT_CAP] + "..."
    return raw


def _fmt_project_line(p: dict, cap_next: int = 150) -> str:
    name = (p.get("name") or "").strip()[:80]
    next_action = (p.get("next_action") or "").strip()[:cap_next]
    risk = (p.get("risk") or "").strip()[:100]
    parts = [f"→ {name}"]
    if next_action:
        parts.append(f"next: {next_action}")
    if risk:
        parts.append(f"risk: {risk}")
    return " | ".join(parts)


def build_projects_block(projects: list[dict]) -> str:
    """
    Derive Main Signal / Secondary Signals / Noise to Avoid from active+waiting projects
    and produce an explicit focus block for the AI prompt.

    Signal logic (deterministic — AI does not choose):
      Main Signal   = first active project (already sorted high→low priority)
      Secondary     = next 1–2 projects (remaining active, then waiting if slots free)
      Noise         = everything else → AI must put these in not_today_list
    """
    if not projects:
        return ""

    active = [p for p in projects if p.get("status") == "active"]
    waiting = [p for p in projects if p.get("status") == "waiting"]

    main = active[0] if active else None
    secondary_active = active[1:3]
    # Fill secondary up to 2 with waiting projects if fewer than 2 active secondaries
    secondary_waiting = waiting[: max(0, 2 - len(secondary_active))]
    secondary = secondary_active + secondary_waiting

    used_ids = {p.get("id") for p in ([main] if main else []) + secondary}
    noise = [p for p in projects if p.get("id") not in used_ids]

    sections: list[str] = ["\nPROJECT FOCUS FOR TODAY:"]

    if main:
        sections.append(
            "  [MAIN SIGNAL — MUST be reflected in main_win;"
            " schedule at least one dedicated deep-work time block]\n"
            f"  {_fmt_project_line(main)}"
        )
    else:
        sections.append("  [NO MAIN SIGNAL — no active projects today]")

    if secondary:
        sec_lines = []
        for p in secondary:
            line = f"  {_fmt_project_line(p)}"
            if p.get("status") == "waiting":
                line += " (waiting — context only, do not schedule)"
            sec_lines.append(line)
        sections.append(
            "  [SECONDARY SIGNALS — may appear in top_priorities;"
            " must not crowd out the Main Signal]\n"
            + "\n".join(sec_lines)
        )

    if noise:
        noise_lines = [f"  → {(p.get('name') or '')[:60]}" for p in noise]
        sections.append(
            "  [NOISE TO AVOID — every item here MUST appear in not_today_list;"
            " do not schedule, do not reference as priority]\n"
            + "\n".join(noise_lines)
        )

    return "\n".join(sections)


def build_user_prompt(
    checkin: dict,
    rules: list[dict],
    language: str = "en",
    review: dict | None = None,
    projects: list[dict] | None = None,
) -> tuple[str, bool]:
    """
    Build the user prompt for the AI.
    Returns (prompt_str, review_context_used).
    review_context_used is True only when non-empty review context was injected.
    """
    lang_instruction = (
        "Respond entirely in German." if language == "de" else "Respond entirely in English."
    )

    rules_block = ""
    if rules:
        rules_text = "\n".join(
            f"- [{r.get('category', 'General')}] {r['rule_text']}"
            for r in rules
            if r.get("is_active", True)
        )
        rules_block = f"\nPERSONAL RULES (always respected):\n{rules_text}"

    fixed_events_text = ""
    if checkin.get("fixed_events"):
        events = checkin["fixed_events"]
        if isinstance(events, list) and events:
            lines = []
            for ev in events:
                if isinstance(ev, dict):
                    t = ev.get("time", "")
                    d = ev.get("duration_minutes", "")
                    name = ev.get("title", str(ev))
                    lines.append(f"  - {t} {name} ({d} min)".strip())
                else:
                    lines.append(f"  - {ev}")
            fixed_events_text = "\nFIXED EVENTS (non-negotiable):\n" + "\n".join(lines)

    tasks_text = ""
    if checkin.get("important_tasks"):
        tasks = checkin["important_tasks"]
        if isinstance(tasks, list) and tasks:
            tasks_text = "\nIMPORTANT TASKS:\n" + "\n".join(f"  - {t}" for t in tasks)

    raw = checkin.get("raw_input", "")
    raw_block = f"\nRAW INPUT FROM USER:\n{raw}" if raw else ""

    projects_block = build_projects_block(projects or [])

    review_block = ""
    review_context_used = False
    if review:
        review_context = build_review_context(review)
        if review_context:
            review_block = (
                "\nRECENT EVENING REVIEW — Use this as learning context,"
                " but do not overfit the whole plan to it:\n"
                + review_context
            )
            review_context_used = True

    prompt = f"""{lang_instruction}

MORNING CHECK-IN:
- Date: {checkin.get('checkin_date', 'today')}
- Wake time: {checkin.get('wake_time', 'unknown')}
- Sleep quality: {checkin.get('sleep_quality', '?')}/10
- Energy level: {checkin.get('energy_level', '?')}/10
- Body status: {checkin.get('body_status', 'not specified')}
- Mood: {checkin.get('mood', 'not specified')}
- Available hours: {checkin.get('available_hours', 'not specified')}
- Day constraints: {checkin.get('day_constraints', 'none')}
{fixed_events_text}{tasks_text}{rules_block}{projects_block}{raw_block}{review_block}

Generate the daily command center plan as a JSON object matching the schema exactly.
"""
    return prompt, review_context_used
