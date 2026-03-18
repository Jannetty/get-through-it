"""Today command — show daily tasks and a message from the friend dude."""

from datetime import datetime
from rich.console import Console
from rich.panel import Panel

from ..config import load_tasks, load_config, get_anthropic_key
from ..display import print_today_panel, print_thinking

console = Console()


def cmd_today():
    tasks = load_tasks()
    config = load_config()

    weekly_tasks = [
        t for t in tasks
        if t.get("weekly") and t.get("status") != "done"
    ]

    ai_message = ""
    if get_anthropic_key():
        print_thinking("checking in...")
        from ..ai import ask_claude
        defense_date = config.get("defense_date", "upcoming")
        if weekly_tasks:
            task_list = ", ".join(f'"{t["description"]}"' for t in weekly_tasks[:5])
            prompt = (
                f"The user's tasks for this week are: {task_list}. "
                f"Their defense is {defense_date}. "
                f"Give them a brief (2-3 sentence max), genuine, chill message to start the day. "
                f"Reference their actual work. No bullet points, no headers, just talk to them."
            )
        else:
            prompt = (
                f"The user has no tasks scheduled for this week yet. "
                f"Their defense is {defense_date}. "
                f"Gently nudge them to run [gti plan] to figure out the week. Keep it brief and friendly."
            )
        ai_message = ask_claude(prompt)

    print_today_panel(weekly_tasks, ai_message)

    if weekly_tasks:
        console.print(
            f"[dim]  {len(weekly_tasks)} task(s) this week · "
            f"[bold]gti pomo <id>[/bold] to start a timer · "
            f"[bold]gti done <id>[/bold] when finished[/dim]\n"
        )
