"""Main CLI entry point for gti."""

import click
from rich.console import Console
from .config import is_setup, get_anthropic_key

console = Console()


def check_setup(ctx, param, value):
    """Check if setup has been run before most commands."""
    return value


@click.group()
@click.version_option(version="0.1.0", prog_name="gti")
def cli():
    """get-through-it — dissertation productivity tool with a friend dude assistant."""
    pass


@cli.command(name="help")
def help_cmd():
    """Show all available commands."""
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold magenta", padding=(0, 2))
    table.add_column("Command", style="bold cyan", no_wrap=True)
    table.add_column("What it does")

    rows = [
        ("gti setup",           "First-time setup — walks through your chapters and seeds your task list"),
        ("gti tasks",           "View all tasks grouped by status, sorted by priority"),
        ("gti add \"...\"",     "Add a task manually"),
        ("gti done <id|text>",  "Mark a task done — pass an ID or describe it in plain English"),
        ("gti reorder",         "Manually set task priority order"),
        ("gti plan",            "Claude helps you pick this week's focus and ranks your tasks"),
        ("gti today",           "Daily view + a message from your friend dude"),
        ("gti note",            "Structured session note — appended to today's daily note"),
        ("gti qn [text]",        "Quick freeform note — type inline or run bare to get a prompt"),
        ("gti wrap day",        "End of day — synthesize notes, find tasks, update chapter notes"),
        ("gti wrap week",       "End of week — reflection, summary, chapter note updates"),
        ("gti pomo [id]",       "25/5 Pomodoro timer — offers to log a note when done"),
        ("gti find \"...\"",    "Search your notes with Claude"),
        ("gti open [query]",    "Open notes in VSCode — optionally jump to a specific note"),
        ("gti friend",          "Open-ended chat with your friend dude"),
    ]

    for cmd, desc in rows:
        table.add_row(cmd, desc)

    console.print(Panel(
        table,
        title="[bold]get-through-it[/bold]",
        border_style="cyan",
        padding=(1, 2),
    ))


@cli.command()
def setup():
    """Interactive first-time setup for your dissertation project."""
    from .commands.setup import run_setup
    run_setup()


@cli.command()
@click.argument("description")
@click.option("--due", "-d", default=None, help="Due date (YYYY-MM-DD)")
@click.option("--tags", "-t", default=None, help="Comma-separated tags")
@click.option("--weekly", "-w", is_flag=True, default=False, help="Mark as this week's task")
def add(description, due, tags, weekly):
    """Add a new task to your dissertation tasks."""
    _require_setup()
    from .commands.tasks import cmd_add
    tag_list = [t.strip() for t in tags.split(",")] if tags else []
    cmd_add(description, due_date=due, tags=tag_list, weekly=weekly)


@cli.command()
@click.option("--all", "show_all", is_flag=True, default=False, help="Show all tasks including done")
def tasks(show_all):
    """Show all dissertation tasks."""
    _require_setup()
    from .commands.tasks import cmd_tasks
    cmd_tasks(show_all=show_all)


@cli.command()
def plan():
    """Interactive planning session — figure out this week's work with Claude."""
    _require_setup()
    _require_api_key()
    from .commands.plan import cmd_plan
    cmd_plan()


@cli.command()
def today():
    """Show today's tasks and a message from your friend dude."""
    _require_setup()
    from .commands.today import cmd_today
    cmd_today()


@cli.command()
@click.argument("task_identifier")
def done(task_identifier):
    """Mark a task as done. Pass an ID or describe it in plain English."""
    _require_setup()
    from .commands.tasks import cmd_done
    cmd_done(task_identifier)


@cli.command()
def reorder():
    """Manually set task priority order."""
    _require_setup()
    from .commands.tasks import cmd_reorder
    cmd_reorder()


@cli.command()
@click.argument("text", nargs=-1, required=False)
def qn(text):
    """Append a quick freeform note to today's daily note."""
    _require_setup()
    from rich.prompt import Prompt
    from .commands.note import cmd_qn
    if text:
        note_text = " ".join(text)
    else:
        note_text = Prompt.ask("[bold cyan]Quick note[/bold cyan]").strip()
    if note_text:
        cmd_qn(note_text)


@cli.command()
@click.argument("task_id", type=int, required=False)
def pomo(task_id):
    """Start a Pomodoro timer (25 min work, 5 min break)."""
    _require_setup()
    from .commands.pomo import cmd_pomo
    cmd_pomo(task_id)


@cli.command()
@click.option("--task-id", "-t", type=int, default=None, help="Associate note with a task")
def note(task_id):
    """Write a structured session note."""
    _require_setup()
    from .commands.note import cmd_note
    cmd_note(task_id=task_id)


@cli.command()
@click.argument("query", nargs=-1)
def find(query):
    """Search notes using Claude."""
    _require_setup()
    _require_api_key()
    from .commands.find import cmd_find
    cmd_find(" ".join(query))


@cli.group()
def wrap():
    """End-of-day or end-of-week wrap-up."""
    pass


@wrap.command(name="day")
def wrap_day():
    """Synthesize today's notes, append a summary, and update chapter notes."""
    _require_setup()
    _require_api_key()
    from .commands.wrap import cmd_wrap_day
    cmd_wrap_day()


@wrap.command(name="week")
def wrap_week():
    """Close out the week — reflection, summary, and chapter note updates."""
    _require_setup()
    _require_api_key()
    from .commands.wrap import cmd_wrap_week
    cmd_wrap_week()


@cli.command()
@click.argument("query", nargs=-1, required=False)
def open(query):
    """Open notes in VSCode. Optionally describe a note to jump straight to it."""
    _require_setup()
    from .commands.open_notes import cmd_open
    cmd_open(" ".join(query) if query else None)


@cli.command()
def friend():
    """Open-ended chat with your friend dude."""
    _require_setup()
    _require_api_key()
    from .commands.friend import cmd_friend
    cmd_friend()


def _require_setup():
    """Exit with a helpful message if setup hasn't been run."""
    if not is_setup():
        console.print("[bold yellow]Looks like you haven't set up gti yet.[/bold yellow]")
        console.print("Run [bold cyan]gti setup[/bold cyan] to get started.")
        raise SystemExit(1)


def _require_api_key():
    """Exit with a helpful message if ANTHROPIC_API_KEY isn't set."""
    if not get_anthropic_key():
        console.print("[bold red]ANTHROPIC_API_KEY is not set.[/bold red]")
        console.print("Add [bold]export ANTHROPIC_API_KEY=your-key-here[/bold] to your [bold]~/.zshrc[/bold], then either:")
        console.print("  • Open a new terminal window, or")
        console.print("  • Run [bold]source ~/.zshrc[/bold] in this one")
        raise SystemExit(1)
