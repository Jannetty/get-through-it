"""Note-taking command — appends timestamped sections to the daily note."""

from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ..config import load_tasks, ensure_daily_note, ensure_daily_note_indexed, ensure_dirs
from ..display import print_success

console = Console()


PROMPTS = [
    ("worked_on",   "What did you work on?"),
    ("got_done",    "What did you actually get done?"),
    ("in_progress", "What's still in progress / where did you leave off?"),
    ("pick_up_next","What do you want to pick up next time?"),
    ("decisions",   "Any decisions, realizations, or things to remember? [dim](Enter to skip)[/dim]"),
    ("feeling",     "How are you feeling about it? [dim](Enter to skip)[/dim]"),
]

SECTION_TITLES = {
    "worked_on":    "What did you work on",
    "got_done":     "What did you get done",
    "in_progress":  "Still in progress",
    "pick_up_next": "Pick up next time",
    "decisions":    "Decisions & notes",
    "feeling":      "Feeling",
}


def cmd_note(task_id: int = None):
    ensure_dirs()
    now = datetime.now()

    task_desc = ""
    if task_id is not None:
        tasks = load_tasks()
        for t in tasks:
            if t["id"] == task_id:
                task_desc = t["description"]
                break

    label = f" — {task_desc}" if task_desc else ""
    console.print(Panel(
        f"[bold]Session note[/bold]{label}\n[dim]Answer each prompt — press Enter to move on.[/dim]",
        border_style="blue",
        padding=(1, 2),
    ))

    answers = {}
    for key, prompt_text in PROMPTS:
        console.print()
        answer = Prompt.ask(f"[bold cyan]{prompt_text}[/bold cyan]", default="").strip()
        answers[key] = answer

    _append_session_section(now, task_desc, answers, task_id)
    print_success("Added to today's note.")
    console.print(f"[dim]Use [bold]gti open[/bold] to browse your notes.[/dim]")


def cmd_qn(text: str):
    """Append a freeform quick note to today's daily note."""
    ensure_dirs()
    now = datetime.now()
    time_str = now.strftime("%-I:%M %p")
    section = f"\n## Quick Note — {time_str}\n{text}\n"

    daily_path = ensure_daily_note()
    with open(daily_path, "a", encoding="utf-8") as f:
        f.write(section)

    ensure_daily_note_indexed(daily_path, now)
    console.print("[dim]Added to today's note.[/dim]")


def cmd_quick_note(task: dict):
    """Lightweight post-task note — two prompts, appended to today's daily note."""
    ensure_dirs()
    now = datetime.now()
    task_desc = task.get("description", "")

    console.print()
    how = Prompt.ask("  [bold cyan]How'd it go?[/bold cyan]", default="").strip()
    console.print()
    next_up = Prompt.ask(
        "  [bold cyan]Anything to pick up next time?[/bold cyan] [dim](Enter to skip)[/dim]",
        default=""
    ).strip()

    if not how and not next_up:
        return

    answers = {"got_done": how, "pick_up_next": next_up}
    _append_session_section(now, task_desc, answers, task.get("id"))
    console.print(f"\n  [dim]Note added to today's note.[/dim]")


def _append_session_section(now: datetime, task_desc: str, answers: dict, task_id=None):
    """Append a timestamped session section to today's daily note."""
    time_str = now.strftime("%-I:%M %p")
    header = f"\n## Session — {time_str}"
    if task_desc:
        header += f" — {task_desc}"
    header += "\n"

    body = ""
    for key, title in SECTION_TITLES.items():
        content = answers.get(key, "").strip()
        if content:
            body += f"\n**{title}:** {content}\n"

    if not body:
        return

    daily_path = ensure_daily_note()
    with open(daily_path, "a", encoding="utf-8") as f:
        f.write(header + body)

    ensure_daily_note_indexed(daily_path, now)
