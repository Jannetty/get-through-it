"""Pomodoro timer command."""

import time
import sys
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TimeRemainingColumn, TextColumn
from rich.prompt import Prompt

from ..config import load_tasks, save_tasks, ensure_daily_note, ensure_daily_note_indexed, format_time
from ..display import DUDE, confirm

console = Console()

WORK_MINUTES = 25
BREAK_MINUTES = 5


def _run_timer(label: str, total_seconds: int, bar_color: str = "cyan"):
    """Plain timer for break phase."""
    with Progress(
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=40, style=bar_color, complete_style=bar_color),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(label, total=total_seconds)
        try:
            for _ in range(total_seconds):
                time.sleep(1)
                progress.advance(task, 1)
        except KeyboardInterrupt:
            return False
    return True


def _run_timer_with_dude(label: str, total_seconds: int, bar_color: str = "cyan"):
    """Work phase timer — dude watches alongside the progress bar, blinks every ~30s."""
    from rich.live import Live
    from rich.table import Table as RTable
    from rich.text import Text

    progress = Progress(
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=35, style=bar_color, complete_style=bar_color),
        TimeRemainingColumn(),
    )
    pomo_task = progress.add_task(label, total=total_seconds)

    def get_dude(elapsed):
        return DUDE["blink"] if (elapsed % 32) >= 30 else DUDE["watching"]

    def make_layout(elapsed):
        table = RTable.grid(padding=(0, 2))
        table.add_column(width=9, vertical="middle")
        table.add_column()
        table.add_row(Text(get_dude(elapsed), style="cyan"), progress)
        return table

    with Live(make_layout(0), refresh_per_second=4, console=console) as live:
        try:
            for i in range(total_seconds):
                time.sleep(1)
                progress.advance(pomo_task, 1)
                live.update(make_layout(i + 1))
        except KeyboardInterrupt:
            return False
    return True


def _bell():
    """Terminal bell."""
    sys.stdout.write("\a")
    sys.stdout.flush()


def _append_to_daily(section: str):
    now = datetime.now()
    daily_path = ensure_daily_note()
    with open(daily_path, "a", encoding="utf-8") as f:
        f.write(section)
    ensure_daily_note_indexed(daily_path, now)


def cmd_pomo(task_id: int = None):
    tasks = load_tasks()
    task = None

    if task_id is not None:
        for t in tasks:
            if t["id"] == task_id:
                task = t
                break
        if task is None:
            console.print(f"[red]No task with ID {task_id}.[/red] Use [bold]gti tasks[/bold] to see IDs.")
            return
        if task.get("status") == "todo":
            task["status"] = "in-progress"
            save_tasks(tasks)

    task_label = f'[bold]{task["description"]}[/bold]' if task else "free session"

    # Pre-session: what are you planning to work on?
    console.print()
    plan = Prompt.ask("[bold cyan]What are you planning to work on?[/bold cyan]").strip()

    start_time = datetime.now()
    time_str = format_time(start_time)

    task_line = f"**Task:** #{task['id']} — {task['description']}\n" if task else ""
    pre_section = (
        f"\n## Pomodoro — {time_str}\n"
        f"{task_line}"
        f"**Plan:** {plan}\n"
    )
    _append_to_daily(pre_section)

    console.print(Panel(
        f"[bold cyan]{WORK_MINUTES} min[/bold cyan] — {task_label}\n"
        f"[dim]Press Ctrl+C to cancel.[/dim]",
        border_style="cyan",
        padding=(1, 2),
    ))

    completed = _run_timer_with_dude(f"  Work  [{WORK_MINUTES} min]", WORK_MINUTES * 60, bar_color="cyan")

    if not completed:
        console.print("\n[yellow]Pomodoro cancelled.[/yellow]")
        end_time = datetime.now()
        _append_to_daily(f"**Result:** Cancelled at {format_time(end_time)}\n")
        return

    _bell()
    console.print(f"\n[bold green]Pomodoro done![/bold green] Time for a {BREAK_MINUTES}-minute break.")

    take_break = confirm("Start break timer?", default=True)
    if take_break:
        _run_timer(f"  Break [{BREAK_MINUTES} min]", BREAK_MINUTES * 60, bar_color="green")
        _bell()
        console.print("\n[bold]Break over.[/bold] Good to go again.\n")

    # Post-session note
    result = Prompt.ask(
        "[bold cyan]What did you get done?[/bold cyan]",
        default="Still working on it"
    ).strip()

    _append_to_daily(f"**Result:** {result}\n")
    console.print("[dim]Logged to today's note.[/dim]")
