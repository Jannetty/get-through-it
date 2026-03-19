"""Rich display helpers for gti."""

from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

# ── ASCII dude ─────────────────────────────────────────────────────────────
DUDE = {
    "normal":   "  (\\/)\n  (o.o)\n  /||\\ ",
    "watching": "  (\\/)\n  (O.O)\n  /||\\ ",
    "blink":    "  (\\/)\n  (-_-)\n  /||\\ ",
    "thinking": "  (\\/)\n  (o.~)\n  /||\\ ",
    "cheer":    "  (\\/)\n\\(^.^)/\n   ||  ",
}


def _task_sort_key(task):
    """Sort key: explicit priority first, then soonest due date, then no-due-date tasks."""
    priority = task.get("priority")
    due = task.get("due_date") or ""
    try:
        datetime.strptime(due, "%Y-%m-%d")
        has_due = True
    except (ValueError, TypeError):
        has_due = False

    if priority is not None:
        # Explicit priority wins; use due date as tiebreaker within same priority
        return (0, priority, due if has_due else "9999-99-99")
    if has_due:
        # No explicit priority — sort by due date ascending (soonest first)
        return (1, 0, due)
    # No priority, no due date — go last
    return (2, 0, "")

console = Console()


def print_error(message: str):
    """Print an error message."""
    console.print(f"[bold red]Error:[/bold red] {message}")


def print_success(message: str):
    """Print a success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_info(message: str):
    """Print an info message."""
    console.print(f"[dim]{message}[/dim]")


def print_ai_message(message: str, title: str = "friend dude", mood: str = "normal"):
    """Print a message from the AI friend, with the dude to the left."""
    dude_str = DUDE.get(mood, DUDE["normal"])
    table = Table.grid(padding=(0, 1))
    table.add_column(width=9, vertical="middle")
    table.add_column()
    table.add_row(
        Text(dude_str, style="cyan"),
        Panel(message, title=f"[bold cyan]{title}[/bold cyan]", border_style="cyan", padding=(1, 2)),
    )
    console.print(table)


def print_thinking(message: str = "thinking..."):
    """Show the thinking dude alongside a dim status message."""
    table = Table.grid(padding=(0, 1))
    table.add_column(width=9)
    table.add_column(vertical="middle")
    table.add_row(
        Text(DUDE["thinking"], style="cyan dim"),
        Text(f"[dim]{message}[/dim]"),
    )
    console.print(table)


def confirm(prompt: str, default: bool = True) -> bool:
    """Case-insensitive y/n prompt (works around Rich's case-sensitive Confirm)."""
    from rich.prompt import Prompt
    default_hint = "Y/n" if default else "y/N"
    while True:
        response = Prompt.ask(f"{prompt} [{default_hint}]", default="").strip().lower()
        if not response:
            return default
        if response in ("y", "yes"):
            return True
        if response in ("n", "no"):
            return False
        console.print("[dim]Please enter y or n.[/dim]")


def print_dude_chat(message: str, mood: str = "normal"):
    """Lightweight dude + text, no panel border — for multi-turn chat."""
    dude_str = DUDE.get(mood, DUDE["normal"])
    table = Table.grid(padding=(0, 1))
    table.add_column(width=9, vertical="top")
    table.add_column()
    table.add_row(
        Text(dude_str, style="cyan"),
        Text(f"\n{message}\n", style="cyan"),
    )
    console.print(table)


def print_tasks_table(tasks: list, title: str = "Tasks"):
    """Print tasks in a formatted table."""
    if not tasks:
        console.print(f"[dim]No tasks found.[/dim]")
        return

    table = Table(
        title=title,
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
        expand=False,
    )

    table.add_column("P", style="dim", width=2)
    table.add_column("ID", style="dim", width=4)
    table.add_column("Description", min_width=30)
    table.add_column("Status", width=12)
    table.add_column("Due", width=12)
    table.add_column("Tags", width=20)
    table.add_column("Week", width=4)

    status_colors = {
        "todo": "yellow",
        "in-progress": "blue",
        "done": "green",
    }

    for task in sorted(tasks, key=_task_sort_key):
        status = task.get("status", "todo")
        color = status_colors.get(status, "white")
        status_text = Text(status, style=color)

        due = task.get("due_date", "")
        # Only show due date if it looks like a real date
        try:
            datetime.strptime(due, "%Y-%m-%d")
        except (ValueError, TypeError):
            due = ""

        tags = ", ".join(task.get("tags", []))
        weekly = "[bold cyan]★[/bold cyan]" if task.get("weekly") else ""
        priority = str(task["priority"]) if task.get("priority") is not None else ""

        desc = task.get("description", "")
        if task.get("status") == "done":
            desc_text = Text(desc, style="dim strikethrough")
        else:
            desc_text = Text(desc)

        table.add_row(
            priority,
            str(task.get("id", "")),
            desc_text,
            status_text,
            due or "",
            tags or "",
            weekly,
        )

    console.print(table)


def print_today_panel(tasks: list, ai_message: str = ""):
    """Print today's tasks panel."""
    if not tasks:
        task_lines = "[dim]No tasks scheduled for today. Use [bold]gti plan[/bold] to set up your week.[/dim]"
    else:
        lines = []
        for task in tasks:
            status = task.get("status", "todo")
            if status == "in-progress":
                bullet = "[blue]▶[/blue]"
            else:
                bullet = "[yellow]○[/yellow]"
            tags = ""
            if task.get("tags"):
                tags = f" [dim]({', '.join(task['tags'])})[/dim]"
            lines.append(f"  {bullet} [bold]{task['description']}[/bold]{tags}")
        task_lines = "\n".join(lines)

    content = task_lines
    if ai_message:
        content += f"\n\n[cyan]{ai_message}[/cyan]"

    panel = Panel(content, title="[bold]Today's Work[/bold]", border_style="blue", padding=(1, 2))

    if ai_message:
        table = Table.grid(padding=(0, 1))
        table.add_column(width=9, vertical="middle")
        table.add_column()
        table.add_row(Text(DUDE["normal"], style="cyan"), panel)
        console.print(table)
    else:
        console.print(panel)


def task_groups_display(tasks: list):
    """Display tasks grouped by status."""
    groups = {
        "in-progress": [],
        "todo": [],
        "done": [],
    }
    for task in tasks:
        status = task.get("status", "todo")
        if status in groups:
            groups[status].append(task)

    for status, group_tasks in groups.items():
        if not group_tasks:
            continue
        status_labels = {
            "in-progress": "[bold blue]In Progress[/bold blue]",
            "todo": "[bold yellow]To Do[/bold yellow]",
            "done": "[bold green]Done[/bold green]",
        }
        console.print(f"\n{status_labels[status]}")
        print_tasks_table(group_tasks, title="")
