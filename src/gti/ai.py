"""Claude AI integration for gti."""

from datetime import datetime
from .config import load_config, load_tasks, get_anthropic_key


def build_system_prompt() -> str:
    """Build the dynamic system prompt with dissertation context."""
    config = load_config()
    tasks = load_tasks()
    today = datetime.now().strftime("%B %d, %Y")

    dissertation_topic = config.get("topic", "their dissertation")
    defense_date = config.get("defense_date", "not yet set")

    active_tasks = [t for t in tasks if t.get("status") != "done"]
    task_list = ""
    if active_tasks:
        task_lines = []
        for t in active_tasks[:10]:  # limit to 10 tasks in prompt
            weekly_marker = " [THIS WEEK]" if t.get("weekly") else ""
            task_lines.append(f"  - [{t['status']}] {t['description']}{weekly_marker}")
        task_list = "\n".join(task_lines)
    else:
        task_list = "  (no active tasks)"

    return f"""You are the user's get-through-it companion — a chill, encouraging friend who happens to know everything about their dissertation work. You're not a coach or therapist, just a smart friend who believes in them. You know their dissertation topic, their defense date, and what they've been working on. Keep responses brief and genuine. No toxic positivity — acknowledge when things are hard, but keep the energy forward-moving. Use light humor when appropriate. Never be preachy.

Current context:
- Today: {today}
- Dissertation: {dissertation_topic}
- Defense date: {defense_date}
- Active tasks:
{task_list}"""


def get_client():
    """Get the Anthropic client."""
    import anthropic
    key = get_anthropic_key()
    if not key:
        return None
    return anthropic.Anthropic(api_key=key)


def ask_claude(prompt: str, extra_context: str = "", model: str = "claude-sonnet-4-6") -> str:
    """Send a prompt to Claude and return the response."""
    client = get_client()
    if not client:
        return "[ANTHROPIC_API_KEY not set — skipping AI response]"

    system = build_system_prompt()
    if extra_context:
        system = f"{system}\n\n{extra_context}"

    message = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def extract_tags(note_content: str) -> list[str]:
    """Extract tags from note content using Claude."""
    client = get_client()
    if not client:
        return []

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": f"""Extract 3-5 keyword tags from this note. Return ONLY a JSON array of lowercase strings, nothing else.

Note:
{note_content[:2000]}

Return format: ["tag1", "tag2", "tag3"]"""
        }],
    )
    try:
        import json
        text = message.content[0].text.strip()
        # Find the JSON array in the response
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return []


def prioritize_tasks(tasks: list) -> list[dict]:
    """Ask Haiku to rank tasks by priority. Returns [{id, priority}] ordered highest first."""
    client = get_client()
    if not client:
        return []

    today = datetime.now().strftime("%Y-%m-%d")
    task_list = "\n".join(
        f"  ID {t['id']}: {t['description']} | due: {t.get('due_date') or 'not set'} | status: {t['status']}"
        for t in tasks
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        messages=[{
            "role": "user",
            "content": f"""Today is {today}. Rank these dissertation tasks by priority (1 = most urgent/important).
Consider: explicit due dates, urgency in the description, status, and logical dependencies.

{task_list}

Return ONLY a JSON array ordered from highest to lowest priority:
[{{"id": 3, "priority": 1}}, {{"id": 1, "priority": 2}}, ...]"""
        }],
    )

    try:
        import json
        text = message.content[0].text.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return []


def match_task_by_description(user_input: str, tasks: list) -> int | None:
    """Match natural language to an active task. Returns task ID or None."""
    client = get_client()
    if not client:
        return None

    task_list = "\n".join(f"  ID {t['id']}: {t['description']}" for t in tasks)

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=10,
        messages=[{
            "role": "user",
            "content": f"""The user says they finished: "{user_input}"

Active tasks:
{task_list}

Which task ID best matches? Return ONLY the integer ID, or "null" if nothing fits."""
        }],
    )

    try:
        import re
        text = message.content[0].text.strip()
        if text.lower() == "null":
            return None
        match = re.search(r'\b(\d+)\b', text)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return None


def generate_day_summary(daily_note_content: str) -> str:
    """Synthesize a day's notes into a concise summary. Uses Sonnet for quality."""
    client = get_client()
    if not client:
        return ""

    system = build_system_prompt()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=system,
        messages=[{
            "role": "user",
            "content": f"""Here are today's notes:

{daily_note_content}

Write a concise day summary (3-5 bullet points) capturing: what was accomplished, key decisions or insights, and what's next. Be concrete and factual — this is for future reference, not motivation. Do not restate things verbatim from the notes, synthesize them.

Output plain markdown bullet points (lines starting with "- "). No heading. No extra blank lines between bullets."""
        }],
    )
    return message.content[0].text


def parse_quick_notes(daily_note_content: str, chapters: list) -> dict:
    """Parse quick notes from a daily note for wrap-day processing.

    Returns:
      {
        "potential_tasks": ["text of actionable item", ...],
        "chapter_observations": {"Ch3: name": ["observation text", ...], ...}
      }
    """
    client = get_client()
    if not client:
        return {"potential_tasks": [], "chapter_observations": {}}

    chapter_list = "\n".join(f"- Ch{i+1}: {ch}" for i, ch in enumerate(chapters))

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": f"""Look through this daily note and focus on the "Quick Note" sections.

Dissertation chapters:
{chapter_list}

Daily note:
{daily_note_content[:4000]}

Do two things:

1. Find any reminders, to-dos, or action items in the quick notes (things like "remember to...", "look up...", "need to..."). These are potential tasks.

2. Find any factual observations or findings (e.g. "WT neuroblasts grow 1.8x faster than mutant neuroblasts"). Route each to the most relevant chapter if clear.

Return ONLY JSON:
{{
  "potential_tasks": ["item 1", "item 2"],
  "chapter_observations": {{
    "Ch3: chapter-name": ["observation 1", "observation 2"]
  }}
}}

Only include entries that genuinely qualify. Use exact chapter labels from the list above."""
        }],
    )

    try:
        import json
        text = message.content[0].text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return {"potential_tasks": [], "chapter_observations": {}}


def extract_chapter_updates(daily_note_content: str, chapters: list) -> dict:
    """Extract chapter-relevant content from a daily note.

    Returns {chapter_label: bullet_summary} only for chapters with relevant content.
    """
    client = get_client()
    if not client:
        return {}

    chapter_list = "\n".join(f"- Ch{i+1}: {ch}" for i, ch in enumerate(chapters))

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{
            "role": "user",
            "content": f"""Read this daily note and extract content relevant to each dissertation chapter.

Dissertation chapters:
{chapter_list}

Daily note:
{daily_note_content[:4000]}

For each chapter that has clearly relevant content in the daily note, write a brief bullet-point summary of what was done, decided, or learned about that chapter.

Only include chapters with genuinely relevant content — do not stretch. Each value should be plain markdown bullet points (lines starting with "- ", separated by single newlines, no blank lines between them). Return as JSON:
{{"Ch3: chapter-name": "- bullet 1\\n- bullet 2"}}

If nothing is clearly relevant to any chapter, return {{}}"""
        }],
    )

    try:
        import json
        text = message.content[0].text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return {}


def generate_week_summary(week_notes_content: str, done_tasks: list, wins: str, stuck: str, priority: str) -> str:
    """Generate a weekly wrap summary."""
    client = get_client()
    if not client:
        return ""

    system = build_system_prompt()
    done_list = "\n".join(f"- {t['description']}" for t in done_tasks) if done_tasks else "_(none logged)_"

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=system,
        messages=[{
            "role": "user",
            "content": f"""It's the end of the work week. Here's the user's reflection:
- Tasks completed: {done_list}
- Wins: {wins or 'not shared'}
- What didn't get done: {stuck or 'not shared'}
- Priority next week: {priority or 'not shared'}

Give them a genuine, warm end-of-week message (3-4 sentences). Acknowledge what they actually shared. End with something forward-looking but not cheesy."""
        }],
    )
    return message.content[0].text


def find_note_file(query: str, index: list) -> str | None:
    """Match a natural language description to a note file path. Returns absolute path or None."""
    client = get_client()
    if not client:
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    index_summary = "\n".join(
        f"  file: {entry.get('file', '')} | date: {entry.get('date', '')[:10]} | "
        f"type: {entry.get('tags', [''])[0] if entry.get('tags') else 'session'} | "
        f"summary: {entry.get('summary', '')}"
        for entry in sorted(index, key=lambda x: x.get("date", ""), reverse=True)
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{
            "role": "user",
            "content": f"""Today is {today}. The user wants to open a note matching: "{query}"

Available notes (most recent first):
{index_summary}

Return ONLY the full file path of the best matching note, nothing else.
If nothing matches, return "null"."""
        }],
    )

    text = message.content[0].text.strip()
    if text and text != "null":
        return text
    return None


def generate_daily_summary(completed_tasks: list, extra_context: str = "") -> str:
    """Generate a brief end-of-day recap."""
    client = get_client()
    if not client:
        return "Good work today."

    system = build_system_prompt()
    today = datetime.now().strftime("%B %d, %Y")
    completed_list = (
        "\n".join(f"  - {t['description']}" for t in completed_tasks)
        if completed_tasks else "  (none logged in tasks)"
    )
    extra = f"\nThey also mentioned: {extra_context}" if extra_context else ""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=system,
        messages=[{
            "role": "user",
            "content": f"""It's the end of {today}. The user is wrapping up for the day.

Tasks completed today:
{completed_list}{extra}

Give them a brief, genuine end-of-day recap — acknowledge what they got done and leave them in a good headspace for tomorrow. Under 4 sentences. Casual and real, not cheesy."""
        }],
    )

    return message.content[0].text


def parse_planning_input(user_input: str, existing_tasks: list, chapters: list) -> dict:
    """Parse natural language planning input into selected task IDs and new tasks to create.

    Returns: {"select_ids": [int, ...], "new_tasks": [{"description": str, "due_date": str|null, "tags": [str, ...]}]}
    """
    client = get_client()
    if not client:
        return {"select_ids": [], "new_tasks": []}

    today = datetime.now().strftime("%Y-%m-%d")
    task_list = "\n".join(
        f"  ID {t['id']}: {t['description']} (status: {t['status']})"
        for t in existing_tasks
    )
    chapter_list = ", ".join(f"Ch{i+1}: {ch}" for i, ch in enumerate(chapters)) if chapters else "none listed"

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"""Today is {today}. The user is managing dissertation tasks.

Existing tasks:
{task_list}

Dissertation chapters: {chapter_list}

The user said: "{user_input}"

Your job:
1. Identify which existing task IDs the user wants to focus on this week (by matching their description to existing tasks).
2. Identify any new tasks the user mentioned that don't exist yet.
   - For each new task, infer a due_date (YYYY-MM-DD) if they mentioned a day/date, otherwise null.
   - Infer relevant tags from chapter names or topic keywords if obvious, otherwise empty list.

Return ONLY valid JSON, nothing else:
{{
  "select_ids": [list of existing task IDs to mark as weekly],
  "new_tasks": [
    {{"description": "task description", "due_date": "YYYY-MM-DD or null", "tags": ["tag1"]}}
  ]
}}"""
        }],
    )

    try:
        import json
        text = message.content[0].text.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(text[start:end])
    except Exception:
        pass
    return {"select_ids": [], "new_tasks": []}


def summarize_note(note_content: str) -> str:
    """Generate a one-line summary of a note using Claude."""
    client = get_client()
    if not client:
        return "Session notes"

    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=80,
        messages=[{
            "role": "user",
            "content": f"""Write a single concise sentence (under 15 words) summarizing the key work done in these session notes. Return ONLY the sentence, nothing else.

{note_content[:1500]}"""
        }],
    )
    return message.content[0].text.strip()


def chat_with_claude(messages: list[dict], model: str = "claude-sonnet-4-6") -> str:
    """Send a multi-turn conversation to Claude."""
    client = get_client()
    if not client:
        return "[ANTHROPIC_API_KEY not set — set it to chat with your friend dude]"

    system = build_system_prompt()

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    return response.content[0].text
