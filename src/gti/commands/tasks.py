"""Task management commands."""

from datetime import datetime
from rich.console import Console
from rich.prompt import Prompt

from ..config import load_tasks, save_tasks, get_next_task_id, get_anthropic_key
from ..display import print_success, print_error, task_groups_display, print_tasks_table, print_ai_message, print_thinking, confirm

console = Console()


def cmd_add(description: str, due_date: str = None, tags: list = None, weekly: bool = False):
    tasks = load_tasks()
    task = {
        "id": get_next_task_id(tasks),
        "description": description,
        "status": "todo",
        "created_at": datetime.now().isoformat(),
        "due_date": due_date,
        "tags": tags or [],
        "weekly": weekly,
    }
    tasks.append(task)
    save_tasks(tasks)
    weekly_note = " [cyan](scheduled for this week)[/cyan]" if weekly else ""
    console.print(f"[green]✓[/green] Added task [bold]#{task['id']}[/bold]: {description}{weekly_note}")


def cmd_tasks(show_all: bool = False):
    tasks = load_tasks()
    if not show_all:
        tasks = [t for t in tasks if t.get("status") != "done"]
    if not tasks:
        if show_all:
            console.print("[dim]No tasks yet. Use [bold]gti add[/bold] to add some.[/dim]")
        else:
            console.print("[dim]No active tasks. Use [bold]gti tasks --all[/bold] to see everything.[/dim]")
        return
    task_groups_display(tasks)


def cmd_done(task_identifier: str):
    tasks = load_tasks()
    active = [t for t in tasks if t.get("status") != "done"]

    # Resolve to a task ID — integer or natural language
    task_id = None
    try:
        task_id = int(task_identifier)
    except ValueError:
        if get_anthropic_key():
            print_thinking("matching to a task...")
            from ..ai import match_task_by_description
            task_id = match_task_by_description(task_identifier, active)
            if task_id is None:
                print_error("Couldn't match that to a task. Use [bold]gti tasks[/bold] to see IDs.")
                return
        else:
            print_error("Pass a task ID number (ANTHROPIC_API_KEY not set for natural language matching).")
            return

    for task in tasks:
        if task["id"] == task_id:
            if task["status"] == "done":
                console.print(f"[dim]Task #{task_id} is already done.[/dim]")
                return
            task["status"] = "done"
            task["completed_at"] = datetime.now().isoformat()
            save_tasks(tasks)

            if get_anthropic_key():
                from ..ai import ask_claude
                msg = ask_claude(
                    f'The user just finished this task: "{task["description"]}". '
                    f'Give them a brief, genuine one-liner (not cheesy) acknowledging it. '
                    f'Keep it under 20 words.'
                )
                console.print(f"\n[green]✓[/green] Done: [strikethrough]{task['description']}[/strikethrough]")
                print_ai_message(msg, title="nice", mood="cheer")
            else:
                print_success(f"Done: {task['description']}")

            # Offer a quick note
            console.print()
            if confirm("  Quick note on how it went?", default=False):
                from .note import cmd_quick_note
                cmd_quick_note(task)
            return

    print_error(f"No task with ID {task_id}. Use [bold]gti tasks[/bold] to see IDs.")


def cmd_reorder():
    """Manually set task priority order."""
    tasks = load_tasks()
    active = [t for t in tasks if t.get("status") != "done"]
    if not active:
        console.print("[dim]No active tasks to reorder.[/dim]")
        return

    console.print("\n[bold]Current task order:[/bold]")
    print_tasks_table(active, title="Active Tasks")

    console.print("\n[dim]Enter task IDs in priority order, highest first (e.g. [bold]3, 1, 4, 2[/bold]).[/dim]")
    console.print("[dim]Press Enter to keep current order.[/dim]")
    order_input = Prompt.ask("Priority order", default="").strip()
    if not order_input:
        console.print("[dim]No changes made.[/dim]")
        return

    ordered_ids = []
    for part in order_input.split(","):
        part = part.strip()
        if part.isdigit():
            ordered_ids.append(int(part))

    if not ordered_ids:
        print_error("No valid task IDs found.")
        return

    # Assign priority based on position
    priority_map = {task_id: i + 1 for i, task_id in enumerate(ordered_ids)}
    updated = 0
    for t in tasks:
        if t["id"] in priority_map:
            t["priority"] = priority_map[t["id"]]
            updated += 1
        elif t.get("status") != "done" and t["id"] not in priority_map:
            # Tasks not mentioned go to the end
            t["priority"] = len(ordered_ids) + 99

    save_tasks(tasks)
    console.print(f"\n[green]✓[/green] Priority updated for {updated} task(s).")
    print_tasks_table([t for t in tasks if t.get("status") != "done"], title="Reordered Tasks")


def cmd_start(task_id: int):
    """Mark a task as in-progress."""
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "in-progress"
            save_tasks(tasks)
            print_success(f"Started: {task['description']}")
            return
    print_error(f"No task with ID {task_id}.")
