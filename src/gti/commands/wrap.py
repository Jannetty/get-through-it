"""End-of-day and end-of-week wrap commands."""

from datetime import datetime, timedelta
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ..config import (
    load_tasks, save_tasks, load_config, load_index, save_index,
    get_daily_note_path, ensure_daily_note, ensure_daily_note_indexed,
    get_next_task_id, NOTES_DIR, CHAPTER_NOTES_DIR, get_anthropic_key, ensure_dirs, update_index_entry,
    format_time,
)
from ..display import print_ai_message, print_thinking, print_success, confirm
from rich.prompt import Prompt

console = Console()


def cmd_wrap_day():
    ensure_dirs()
    now = datetime.now()
    daily_path = get_daily_note_path()

    if not daily_path.exists():
        console.print("[dim]No daily note for today yet — add some notes first with [bold]gti note[/bold] or [bold]gti day[/bold].[/dim]")
        return

    content = daily_path.read_text(encoding="utf-8")

    if not get_anthropic_key():
        console.print("[bold red]ANTHROPIC_API_KEY not set — needed for wrap.[/bold red]")
        return

    # Generate and append day summary
    print_thinking("reading today's notes...")
    from ..ai import generate_day_summary
    summary = generate_day_summary(content)

    print_ai_message(summary, title="day summary", mood="cheer")

    time_str = format_time(now)
    summary_section = f"\n---\n\n## Day Summary — {time_str}\n\n{summary}\n"
    with open(daily_path, "a", encoding="utf-8") as f:
        f.write(summary_section)

    update_index_entry(str(daily_path), {"summary": f"Daily note — {now.strftime('%b %d')} (wrapped)"})

    # Parse quick notes for tasks and chapter observations
    config = load_config()
    chapters = config.get("chapters", [])

    if chapters:
        console.print("[dim]Parsing quick notes...[/dim]")
        from ..ai import parse_quick_notes, extract_chapter_updates
        qn_parsed = parse_quick_notes(content, chapters)

        # Offer to create tasks from action items
        potential_tasks = qn_parsed.get("potential_tasks", [])
        if potential_tasks:
            console.print(f"\n[bold]Found {len(potential_tasks)} potential task(s) in your quick notes:[/bold]")
            tasks = load_tasks()
            any_added = False
            for item in potential_tasks:
                console.print(f"\n  [cyan]→[/cyan] {item}")
                if confirm("  Add as a task?", default=True):
                    from datetime import datetime as dt
                    task = {
                        "id": get_next_task_id(tasks),
                        "description": item,
                        "status": "todo",
                        "created_at": dt.now().isoformat(),
                        "due_date": None,
                        "tags": [],
                        "weekly": False,
                    }
                    tasks.append(task)
                    any_added = True
                    console.print(f"  [green]✓[/green] Added as task #{task['id']}")
            if any_added:
                save_tasks(tasks)

        # Route chapter observations to chapter notes
        chapter_obs = qn_parsed.get("chapter_observations", {})

        # Also extract general chapter updates from session notes
        console.print("[dim]Checking for chapter-relevant content...[/dim]")
        all_updates = extract_chapter_updates(content, chapters)

        # Merge: chapter_obs entries go into chapter notes too
        for chapter_label, obs_list in chapter_obs.items():
            obs_text = "\n".join(f"- {o}" for o in obs_list)
            if chapter_label in all_updates:
                all_updates[chapter_label] = all_updates[chapter_label] + "\n" + obs_text
            else:
                all_updates[chapter_label] = obs_text

        if all_updates:
            for chapter_label, chapter_content in all_updates.items():
                console.print(f"\n  [cyan]→[/cyan] [bold]{chapter_label}[/bold]")
                for line in chapter_content.strip().splitlines()[:6]:
                    console.print(f"    [dim]{line}[/dim]")
                response = Prompt.ask(
                    "  Add to this chapter note? [[bold]Y[/bold]/n/other chapter name]",
                    default=""
                ).strip().lower()
                if not response or response in ("y", "yes"):
                    _append_to_chapter_note(chapter_label, chapter_content, now)
                    console.print(f"  [green]✓[/green] Updated: {chapter_label}")
                elif response in ("n", "no"):
                    console.print("  [dim]Skipped.[/dim]")
                else:
                    target = _match_chapter(response, chapters)
                    if target:
                        _append_to_chapter_note(target, chapter_content, now)
                        console.print(f"  [green]✓[/green] Added to: {target}")
                    else:
                        console.print("  [dim]Couldn't match that to a chapter — skipped.[/dim]")
        else:
            console.print("[dim]No chapter-specific content found.[/dim]")

    update_index_entry(str(daily_path), {"summary": f"Daily note — {now.strftime('%b %d')} (wrapped)"})
    console.print(f"\n[dim]Day wrapped. Use [bold]gti open[/bold] to browse your notes.[/dim]")


def cmd_wrap_week():
    ensure_dirs()
    now = datetime.now()

    # Collect this week's daily notes
    week_notes = []
    for i in range(7):
        d = (now - timedelta(days=i)).date()
        path = get_daily_note_path(d)
        if path.exists():
            week_notes.append((d, path.read_text(encoding="utf-8")))

    tasks = load_tasks()
    week_ago = now - timedelta(days=7)
    done_this_week = [
        t for t in tasks
        if t.get("status") == "done"
        and t.get("completed_at")
        and datetime.fromisoformat(t["completed_at"]) >= week_ago
    ]

    console.print(Panel(
        "[bold]Weekly Wrap[/bold]\n[dim]Let's close out the week.[/dim]",
        border_style="blue",
        padding=(1, 2),
    ))

    if done_this_week:
        console.print(f"\n[bold green]Completed this week ({len(done_this_week)} tasks):[/bold green]")
        for t in done_this_week:
            console.print(f"  [green]✓[/green] {t['description']}")
    else:
        console.print("\n[dim]No tasks marked done this week.[/dim]")

    console.print()
    wins = Prompt.ask("[bold cyan]What were your wins this week?[/bold cyan]", default="").strip()
    console.print()
    stuck = Prompt.ask("[bold cyan]What didn't get done, and why?[/bold cyan]", default="").strip()
    console.print()
    priority = Prompt.ask("[bold cyan]Main priority for next week?[/bold cyan]", default="").strip()

    if not get_anthropic_key():
        console.print("[bold red]ANTHROPIC_API_KEY not set — needed for wrap.[/bold red]")
        return

    print_thinking("reflecting on your week...")
    from ..ai import generate_week_summary
    week_content = "\n\n---\n\n".join(content for _, content in week_notes)
    msg = generate_week_summary(week_content, done_this_week, wins, stuck, priority)
    print_ai_message(msg, title="week wrap", mood="cheer")

    # Save weekly note
    date_str = now.strftime("%B %d, %Y")
    filename = now.strftime("%Y-%m-%d") + "-weekly-wrap.md"
    filepath = NOTES_DIR / filename

    done_md = "\n".join(f"- {t['description']}" for t in done_this_week) or "_(none logged)_"
    content = (
        f"---\n"
        f"date: {now.isoformat()}\n"
        f"project: dissertation\n"
        f"type: weekly-wrap\n"
        f"tags: [\"weekly-wrap\"]\n"
        f"---\n\n"
        f"# Weekly Wrap — {date_str}\n\n"
        f"## Tasks completed\n\n{done_md}\n\n"
        f"## Wins\n\n{wins or '_(skipped)_'}\n\n"
        f"## What didn't get done\n\n{stuck or '_(skipped)_'}\n\n"
        f"## Priority next week\n\n{priority or '_(skipped)_'}\n\n"
        f"## Friend's take\n\n{msg}\n"
    )
    filepath.write_text(content, encoding="utf-8")

    index = load_index()
    index.append({
        "date": now.isoformat(),
        "file": str(filepath),
        "project": "dissertation",
        "task_id": None,
        "summary": f"Weekly wrap — {now.strftime('%b %d')}",
        "tags": ["weekly-wrap"],
    })
    save_index(index)

    print_success(f"Weekly wrap saved.")

    if confirm("\nPlan next week now?", default=True):
        from .plan import cmd_plan
        cmd_plan()


def _match_chapter(text: str, chapters: list) -> str | None:
    """Try to match plain-language input to a chapter label like 'Ch3: ...'"""
    text_lower = text.lower()
    for i, ch in enumerate(chapters):
        label = f"Ch{i+1}: {ch}"
        if f"ch{i+1}" in text_lower or f"chapter {i+1}" in text_lower:
            return label
        words = [w for w in ch.lower().split() if len(w) > 4]
        if any(w in text_lower for w in words):
            return label
    return None


def _append_to_chapter_note(chapter_label: str, content: str, now: datetime):
    """Append a dated excerpt to the appropriate chapter note file."""
    slug = chapter_label.lower()
    for ch in " :/()\\":
        slug = slug.replace(ch, "-")
    slug = slug.strip("-")[:40]
    filepath = CHAPTER_NOTES_DIR / f"{slug}.md"

    date_str = now.strftime("%B %d, %Y")
    section = f"\n## {date_str}\n\n{content}\n"

    if not filepath.exists():
        filepath.write_text(f"# {chapter_label} — Notes\n\n{section}", encoding="utf-8")
    else:
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(section)

    # Register in index so gti open can find it
    index = load_index()
    path_str = str(filepath)
    existing = next((e for e in index if e.get("file") == path_str), None)
    if existing:
        existing["date"] = now.isoformat()
        existing["summary"] = f"{chapter_label} — last updated {now.strftime('%b %d')}"
    else:
        index.append({
            "date": now.isoformat(),
            "file": path_str,
            "project": "dissertation",
            "task_id": None,
            "summary": f"{chapter_label} — notes",
            "tags": ["chapter-note"],
        })
    save_index(index)
