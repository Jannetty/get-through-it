"""Task management commands."""

from datetime import datetime
from rich.console import Console
from rich.prompt import Prompt

from ..config import load_tasks, save_tasks, get_next_task_id, get_anthropic_key
from ..display import print_success, print_error, task_groups_display, print_tasks_table, print_ai_message, print_thinking, confirm

console = Console()


def cmd_add(description: str, due_date: str = None, tags: list = None, weekly: bool = False, priority: str = None):
    tasks = load_tasks()
    task = {
        "id": get_next_task_id(tasks),
        "description": description,
        "status": "todo",
        "created_at": datetime.now().isoformat(),
        "due_date": due_date,
        "tags": tags or [],
        "weekly": weekly,
        "priority": priority,
    }
    tasks.append(task)
    save_tasks(tasks)
    pri_note = f" [bold]({priority} priority)[/bold]" if priority else ""
    weekly_note = " [cyan](this week)[/cyan]" if weekly else ""
    console.print(f"[green]✓[/green] Added task [bold]#{task['id']}[/bold]: {description}{pri_note}{weekly_note}")


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

            # Offer a quick note — typing anything starts it, Enter skips
            console.print()
            how = Prompt.ask("  [bold cyan]Quick note on how it went?[/bold cyan] [dim](Enter to skip)[/dim]", default="").strip()
            if how:
                from .note import cmd_quick_note
                cmd_quick_note(task, how)
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


_STATUS_ALIASES = {
    "in-progress": {"in-progress", "in progress", "inprogress", "progress", "wip", "started", "working"},
    "done":        {"done", "complete", "completed", "finished", "finish"},
    "todo":        {"todo", "to-do", "not started", "pending", "backlog"},
}

_PRIORITY_ALIASES = {
    "high":   {"high", "urgent", "critical", "highest", "important", "hi"},
    "medium": {"medium", "med", "normal", "moderate", "mid"},
    "low":    {"low", "lowest", "minor", "lo", "nice-to-have"},
    None:     {"none", "unset", "clear", "no priority"},
}


def _resolve_status(token: str) -> str | None:
    t = token.lower().strip()
    for status, aliases in _STATUS_ALIASES.items():
        if t in aliases:
            return status
    return None


def _resolve_priority(token: str) -> tuple[bool, str | None]:
    """Returns (matched, priority_value). matched=True even when priority=None (explicit clear)."""
    t = token.lower().strip()
    for level, aliases in _PRIORITY_ALIASES.items():
        if t in aliases:
            return True, level
    return False, None


def _parse_trailing(args: list[str], resolver):
    """Try the last token, then last two joined, with optional 'to' strip. Returns (value, remaining)."""
    if len(args) >= 1:
        val = resolver(args[-1])
        found = val[0] if isinstance(val, tuple) else val
        actual = val[1] if isinstance(val, tuple) else val
        if found if isinstance(val, tuple) else found is not None:
            remaining = args[:-1]
            if remaining and remaining[-1].lower() == "to":
                remaining = remaining[:-1]
            return actual, remaining

    if len(args) >= 2:
        val = resolver(f"{args[-2]} {args[-1]}")
        found = val[0] if isinstance(val, tuple) else val
        actual = val[1] if isinstance(val, tuple) else val
        if found if isinstance(val, tuple) else found is not None:
            remaining = args[:-2]
            if remaining and remaining[-1].lower() == "to":
                remaining = remaining[:-1]
            return actual, remaining

    return None, args


def _apply_ai_changes(task_id: int, changes: dict, tasks: list):
    """Apply AI-parsed changes {status?, priority?, due_date?} to a task and save."""
    for task in tasks:
        if task["id"] == task_id:
            msgs = []
            if "status" in changes:
                old = task["status"]
                task["status"] = changes["status"]
                if changes["status"] == "done" and "completed_at" not in task:
                    task["completed_at"] = datetime.now().isoformat()
                msgs.append(f"status: [dim]{old}[/dim] → [bold]{changes['status']}[/bold]")
            if "priority" in changes:
                old = task.get("priority", "unset")
                task["priority"] = changes["priority"]
                label = changes["priority"] or "unset"
                msgs.append(f"priority: [dim]{old}[/dim] → [bold]{label}[/bold]")
            if "due_date" in changes:
                old = task.get("due_date") or "unset"
                task["due_date"] = changes["due_date"]
                msgs.append(f"due: [dim]{old}[/dim] → [bold]{changes['due_date']}[/bold]")
            save_tasks(tasks)
            for m in msgs:
                console.print(f"[green]✓[/green] [bold]#{task_id}[/bold] {m}")
            return
    print_error(f"No task with ID {task_id}.")


def cmd_set(args: list[str]):
    """Set a task's status or priority level."""
    if not args:
        print_error("Usage: gti set <task> <status|priority>\n  Status: in-progress, done, todo\n  Priority: high, medium, low, none")
        return

    # Detect whether the trailing word(s) are a status or priority
    setting_type = None
    value = None
    task_tokens = list(args)

    # Try status first
    status_val, remaining = _parse_trailing(list(args), _resolve_status)
    if status_val is not None:
        setting_type = "status"
        value = status_val
        task_tokens = remaining
    else:
        # Try priority
        pri_found, pri_val = False, None
        if len(args) >= 1:
            pri_found, pri_val = _resolve_priority(args[-1])
            if pri_found:
                task_tokens = list(args[:-1])
                if task_tokens and task_tokens[-1].lower() == "to":
                    task_tokens = task_tokens[:-1]
        if not pri_found and len(args) >= 2:
            pri_found, pri_val = _resolve_priority(f"{args[-2]} {args[-1]}")
            if pri_found:
                task_tokens = list(args[:-2])
                if task_tokens and task_tokens[-1].lower() == "to":
                    task_tokens = task_tokens[:-1]
        if pri_found:
            setting_type = "priority"
            value = pri_val

    if setting_type is None:
        # Fall back to AI for complex commands (multiple fields, natural language dates, etc.)
        if get_anthropic_key():
            print_thinking("parsing command...")
            from ..ai import parse_set_command
            from datetime import date as _date
            tasks = load_tasks()
            active = [t for t in tasks if t.get("status") != "done"]
            result = parse_set_command(" ".join(args), active, _date.today().isoformat())
            if result:
                _apply_ai_changes(result["task_id"], result.get("changes", {}), tasks)
                return
        print_error(
            "Couldn't find a status or priority in that.\n"
            "  Status: [bold]in-progress[/bold], [bold]done[/bold], [bold]todo[/bold]\n"
            "  Priority: [bold]high[/bold], [bold]medium[/bold], [bold]low[/bold], [bold]none[/bold]"
        )
        return

    if not task_tokens:
        print_error("Please also specify which task.")
        return

    identifier = " ".join(task_tokens)
    tasks = load_tasks()

    task_id = None
    try:
        task_id = int(identifier)
    except ValueError:
        if get_anthropic_key():
            print_thinking("matching to a task...")
            from ..ai import match_task_by_description
            active = [t for t in tasks if t.get("status") != "done"]
            task_id = match_task_by_description(identifier, active)
            if task_id is None:
                print_error("Couldn't match that to a task. Use [bold]gti tasks[/bold] to see IDs.")
                return
        else:
            print_error("Pass a task ID number (ANTHROPIC_API_KEY not set for natural language matching).")
            return

    for task in tasks:
        if task["id"] == task_id:
            if setting_type == "status":
                old = task["status"]
                task["status"] = value
                if value == "done" and "completed_at" not in task:
                    task["completed_at"] = datetime.now().isoformat()
                save_tasks(tasks)
                console.print(f"[green]✓[/green] [bold]#{task_id}[/bold] status: [dim]{old}[/dim] → [bold]{value}[/bold]")
            else:
                old = task.get("priority", "unset")
                task["priority"] = value
                save_tasks(tasks)
                label = value if value else "unset"
                console.print(f"[green]✓[/green] [bold]#{task_id}[/bold] priority: [dim]{old}[/dim] → [bold]{label}[/bold]")
            return

    print_error(f"No task with ID {task_id}.")
