"""Planning session — break goals into this week's work with Claude's help."""

from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ..config import load_tasks, save_tasks, load_config, get_next_task_id, get_anthropic_key
from ..display import print_tasks_table, print_ai_message, print_thinking, confirm
from ..ai import ask_claude, parse_planning_input

console = Console()


def cmd_plan():
    tasks = load_tasks()
    config = load_config()

    todo_tasks = [t for t in tasks if t.get("status") in ("todo", "in-progress")]

    if not todo_tasks:
        console.print(Panel(
            "You have no active tasks. Add some with [bold cyan]gti add \"task description\"[/bold cyan] first.",
            border_style="yellow",
            padding=(1, 2),
        ))
        return

    console.print(Panel(
        "[bold]Here's what you've got left to do:[/bold]",
        border_style="blue",
        padding=(0, 1),
    ))
    print_tasks_table(todo_tasks, title="Active Tasks")

    currently_weekly = [t for t in todo_tasks if t.get("weekly")]
    if currently_weekly:
        console.print(f"\n[dim]You already have {len(currently_weekly)} task(s) marked for this week. "
                      f"They're starred (★) above.[/dim]")

    # Ask Claude for a planning suggestion
    print_thinking("thinking about your week...")

    task_descriptions = "\n".join(
        f"- [#{t['id']}] {t['description']} (status: {t['status']})"
        for t in todo_tasks
    )

    chapters = config.get("chapters", [])
    chapter_list = ""
    if chapters:
        chapter_list = "\nDissertation chapters: " + ", ".join(
            f"Ch{i+1}: {ch}" for i, ch in enumerate(chapters)
        )

    suggestion = ask_claude(
        f"Here are all the user's active dissertation tasks:\n{task_descriptions}\n{chapter_list}\n\n"
        f"Suggest which 3-5 tasks make the most sense to focus on THIS WEEK, and briefly explain why "
        f"(one sentence per task). Be concrete and prioritize momentum. "
        f"Format as a simple numbered list with task IDs and your reasoning."
    )

    print_ai_message(suggestion, title="planning take")

    # Let user describe what they want to work on
    console.print("\n[bold]What do you want to focus on this week?[/bold]")
    if get_anthropic_key():
        console.print("[dim]Describe it naturally, or enter task IDs (e.g. 1, 3). "
                      "You can also mention new tasks and I'll help you add them.[/dim]")
    else:
        console.print("[dim]Enter task IDs from the list above (e.g. 1, 3, 5), "
                      "or press Enter to keep current selection.[/dim]")

    user_input = Prompt.ask("This week's focus", default="").strip()
    if not user_input:
        console.print("[dim]No changes made to weekly tasks.[/dim]")
        return

    # Parse the input — natural language if API key available, ID fallback otherwise
    selected_ids = set()
    new_task_proposals = []

    if get_anthropic_key():
        console.print("[dim]Parsing...[/dim]")
        parsed = parse_planning_input(user_input, todo_tasks, chapters)
        selected_ids = set(parsed.get("select_ids", []))
        new_task_proposals = parsed.get("new_tasks", [])
    else:
        # Fallback: parse comma-separated IDs
        for part in user_input.split(","):
            part = part.strip()
            if part.isdigit():
                selected_ids.add(int(part))

    # Update weekly flags on existing tasks
    for t in tasks:
        t["weekly"] = False
    updated = []
    for t in tasks:
        if t["id"] in selected_ids:
            t["weekly"] = True
            updated.append(t["description"])

    # Handle new task proposals
    newly_added = []
    if new_task_proposals:
        console.print(f"\n[bold]I spotted {len(new_task_proposals)} new task(s) you mentioned:[/bold]")
        for proposal in new_task_proposals:
            desc = proposal.get("description", "")
            inferred_due = proposal.get("due_date") or ""
            inferred_tags = proposal.get("tags") or []

            console.print(f"\n  [cyan]→[/cyan] [bold]{desc}[/bold]")
            if not confirm("  Add this task?", default=True):
                continue

            due = Prompt.ask("  Due date (YYYY-MM-DD)", default=inferred_due).strip() or None
            if due:
                try:
                    datetime.strptime(due, "%Y-%m-%d")
                except ValueError:
                    console.print("  [yellow]Invalid date format, skipping due date.[/yellow]")
                    due = None

            tag_default = ", ".join(inferred_tags) if inferred_tags else ""
            tag_input = Prompt.ask("  Tags (comma-separated)", default=tag_default).strip()
            tags = [s.strip() for s in tag_input.split(",") if s.strip()] if tag_input else []

            add_weekly = confirm("  Add to this week's focus?", default=True)

            new_task = {
                "id": get_next_task_id(tasks),
                "description": desc,
                "status": "todo",
                "created_at": datetime.now().isoformat(),
                "due_date": due,
                "tags": tags,
                "weekly": add_weekly,
            }
            tasks.append(new_task)
            newly_added.append(new_task)
            if add_weekly:
                updated.append(desc)

    save_tasks(tasks)

    if updated or newly_added:
        if updated:
            console.print(f"\n[green]✓[/green] This week's tasks:")
            for desc in updated:
                console.print(f"  [cyan]★[/cyan] {desc}")
        if newly_added:
            console.print(f"\n[green]✓[/green] Added {len(newly_added)} new task(s):")
            for t in newly_added:
                console.print(f"  [green]+[/green] #{t['id']}: {t['description']}")

    # Auto-prioritize all active tasks
    active = [t for t in tasks if t.get("status") != "done"]
    if active and get_anthropic_key():
        console.print("\n[dim]Ranking your tasks by priority...[/dim]")
        from ..ai import prioritize_tasks
        rankings = prioritize_tasks(active)
        if rankings:
            priority_map = {r["id"]: r["priority"] for r in rankings}
            for t in tasks:
                if t["id"] in priority_map:
                    t["priority"] = priority_map[t["id"]]
            save_tasks(tasks)
            console.print("[dim]Done — use [bold]gti reorder[/bold] to adjust if needed.[/dim]")

    console.print("\n[dim]Run [bold]gti today[/bold] to see your daily view.[/dim]")
