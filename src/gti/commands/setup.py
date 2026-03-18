"""Setup command — first-time dissertation project configuration."""

from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

from ..config import save_config, save_tasks, ensure_dirs, is_setup, get_next_task_id

console = Console()


def run_setup():
    ensure_dirs()

    if is_setup():
        if not Confirm.ask("[yellow]gti is already set up. Reconfigure?[/yellow]"):
            return

    console.print(Panel(
        "Let's get you set up. I'll ask about your dissertation and each chapter "
        "so we can figure out what you actually need to do before you defend.",
        title="[bold cyan]get-through-it setup[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))

    topic = Prompt.ask("\n[bold]What is your dissertation about?[/bold] (1-2 sentences)")

    defense_date_str = Prompt.ask(
        "\n[bold]When is your defense date?[/bold]",
        default="not yet scheduled"
    )

    chapters_raw = Prompt.ask("\n[bold]How many chapters does it have?[/bold]", default="5")
    try:
        num_chapters = int(chapters_raw)
    except ValueError:
        num_chapters = 5

    console.print(f"\n[dim]Give each chapter a short title:[/dim]")
    chapters = []
    for i in range(1, num_chapters + 1):
        ch = Prompt.ask(f"  Chapter {i}")
        chapters.append(ch)

    # Walk through each chapter to seed tasks
    tasks = []
    console.print(Panel(
        "Now let's go through each chapter so I know where you stand. "
        "This will build your initial task list.",
        border_style="blue",
        padding=(1, 1),
    ))

    for i, chapter in enumerate(chapters, 1):
        console.print(f"\n[bold cyan]Chapter {i}: {chapter}[/bold cyan]")

        status = Prompt.ask(
            "  Where are you with this chapter?",
            default=""
        ).strip()

        still_needed = Prompt.ask(
            "  What still needs to be done before it's finished?",
            default=""
        ).strip()

        next_step = Prompt.ask(
            "  What's the immediate next step?",
            default=""
        ).strip()

        when = Prompt.ask(
            "  When do you think you'll work on that next step?",
            default=""
        ).strip()

        # Create a task for the next step if they gave one
        if next_step:
            task = {
                "id": get_next_task_id(tasks),
                "description": next_step,
                "status": "todo",
                "created_at": datetime.now().isoformat(),
                "due_date": when if when else None,
                "tags": [f"ch{i}", chapter.lower().replace(" ", "-")[:20]],
                "weekly": False,
                "chapter": i,
                "chapter_name": chapter,
                "context": {
                    "status": status,
                    "still_needed": still_needed,
                },
            }
            tasks.append(task)
            console.print(f"  [green]✓[/green] Added task: [dim]{next_step}[/dim]")

    config = {
        "topic": topic,
        "chapters": chapters,
        "defense_date": defense_date_str,
        "created_at": datetime.now().isoformat(),
    }
    save_config(config)
    if tasks:
        save_tasks(tasks)

    console.print()
    console.print(Panel(
        f"[green]You're all set.[/green]\n\n"
        f"[bold]Dissertation:[/bold] {topic}\n"
        f"[bold]Chapters:[/bold] {len(chapters)}\n"
        f"[bold]Defense:[/bold] {defense_date_str}\n"
        f"[bold]Tasks created:[/bold] {len(tasks)}\n\n"
        f"[dim]Next steps:[/dim]\n"
        f"  [cyan]gti tasks[/cyan]   — see everything you need to do\n"
        f"  [cyan]gti plan[/cyan]    — figure out this week's work\n"
        f"  [cyan]gti today[/cyan]   — daily view + message from your friend\n"
        f"  [cyan]gti friend[/cyan]  — just talk",
        title="[bold green]Setup complete[/bold green]",
        border_style="green",
        padding=(1, 2),
    ))
