"""Weekly review command."""

from datetime import datetime, timedelta
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ..config import load_tasks, save_tasks, load_index, NOTES_DIR, ensure_dirs
from ..display import print_ai_message, print_tasks_table
from ..commands.note import SECTION_TITLES

console = Console()


def cmd_week():
    ensure_dirs()
    tasks = load_tasks()
    now = datetime.now()
    week_ago = now - timedelta(days=7)

    # Tasks completed this week
    done_this_week = [
        t for t in tasks
        if t.get("status") == "done"
        and t.get("completed_at")
        and datetime.fromisoformat(t["completed_at"]) >= week_ago
    ]

    console.print(Panel(
        "[bold]Weekly Review[/bold]\n[dim]Let's look back at the week and set up the next one.[/dim]",
        border_style="blue",
        padding=(1, 2),
    ))

    if done_this_week:
        console.print(f"\n[bold green]Completed this week ({len(done_this_week)} tasks):[/bold green]")
        print_tasks_table(done_this_week, title="")
    else:
        console.print("\n[dim]No tasks marked done this week — that's okay, let's talk about what happened.[/dim]")

    # Guided reflection prompts
    console.print()
    wins = Prompt.ask("[bold cyan]What were your wins this week?[/bold cyan] (even small ones count)", default="").strip()
    console.print()
    stuck = Prompt.ask("[bold cyan]What didn't get done, and why?[/bold cyan]", default="").strip()
    console.print()
    priority = Prompt.ask("[bold cyan]What's the main priority for next week?[/bold cyan]", default="").strip()

    # Get a genuine end-of-week message from Claude
    console.print("\n[dim]Getting your friend's take on the week...[/dim]")

    done_list = ", ".join(f'"{t["description"]}"' for t in done_this_week) if done_this_week else "none logged"
    from ..ai import ask_claude
    msg = ask_claude(
        f"It's the end of the user's work week. Here's their reflection:\n"
        f"- Tasks completed: {done_list}\n"
        f"- Wins: {wins or 'not shared'}\n"
        f"- Didn't get done: {stuck or 'not shared'}\n"
        f"- Priority next week: {priority or 'not shared'}\n\n"
        f"Give them a genuine, warm end-of-week message (3-4 sentences max). "
        f"Acknowledge the real things they shared. "
        f"End with something forward-looking but not cheesy."
    )
    print_ai_message(msg, title="end of week")

    # Save as a weekly review note
    from pathlib import Path
    from ..config import load_index, save_index

    date_str = now.strftime("%B %d, %Y")
    filename = now.strftime("%Y-%m-%d") + "-weekly-review.md"
    filepath = NOTES_DIR / filename

    done_md = "\n".join(f"- {t['description']}" for t in done_this_week) or "_(none logged)_"

    content = (
        f"---\n"
        f"date: {now.isoformat()}\n"
        f"project: dissertation\n"
        f"type: weekly-review\n"
        f"tags: [\"weekly-review\"]\n"
        f"---\n\n"
        f"# Weekly Review — {date_str}\n\n"
        f"## Tasks completed\n{done_md}\n\n"
        f"## Wins\n{wins or '_(skipped)_'}\n\n"
        f"## What didn't get done\n{stuck or '_(skipped)_'}\n\n"
        f"## Priority next week\n{priority or '_(skipped)_'}\n\n"
        f"## Friend dude's take\n{msg}\n"
    )

    filepath.write_text(content, encoding="utf-8")

    index = load_index()
    index.append({
        "date": now.isoformat(),
        "file": str(filepath),
        "project": "dissertation",
        "type": "weekly-review",
        "summary": f"Weekly review: {priority[:60] if priority else 'week ' + date_str}",
        "tags": ["weekly-review"],
    })
    save_index(index)

    console.print(f"\n[dim]Review saved to {filepath}[/dim]")

    # Offer to re-plan the week
    from rich.prompt import Confirm
    if Confirm.ask("\nWant to plan next week's tasks now?", default=True):
        from .plan import cmd_plan
        cmd_plan()
