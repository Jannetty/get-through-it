"""End-of-day and end-of-week wrap commands."""

import calendar as cal_module
import re
from datetime import datetime, timedelta, date as date_type
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ..config import (
    load_tasks, save_tasks, load_config, load_index, save_index,
    get_daily_note_path, ensure_daily_note, ensure_daily_note_indexed,
    get_next_task_id, NOTES_DIR, CHAPTER_NOTES_DIR, get_anthropic_key, ensure_dirs, update_index_entry,
    format_time, chapter_note_slug,
)
from ..display import print_ai_message, print_thinking, print_success, confirm

console = Console()


def _parse_target_day(date_str):
    """Parse a day arg. Returns date object, or None on error."""
    now = datetime.now()
    if not date_str:
        return now.date()
    if date_str.lower() == "yesterday":
        return (now - timedelta(days=1)).date()
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        console.print(f"[bold red]Invalid date '{date_str}'. Use YYYY-MM-DD or 'yesterday'.[/bold red]")
        return None


def _parse_target_week(date_str):
    """Parse a week anchor arg. Returns Monday of the target calendar week, or None on error."""
    now = datetime.now()
    if not date_str:
        anchor = now.date()
    elif date_str.lower() == "last":
        anchor = (now - timedelta(weeks=1)).date()
    else:
        try:
            anchor = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            console.print(f"[bold red]Invalid date '{date_str}'. Use YYYY-MM-DD or 'last'.[/bold red]")
            return None
    return anchor - timedelta(days=anchor.weekday())


def _parse_target_month(month_str):
    """Parse a month arg (YYYY-MM or 'last'). Returns (year, month) tuple, or None on error."""
    now = datetime.now()
    if not month_str:
        return now.year, now.month
    if month_str.lower() == "last":
        d = now.replace(day=1) - timedelta(days=1)
        return d.year, d.month
    try:
        d = datetime.strptime(month_str, "%Y-%m")
        return d.year, d.month
    except ValueError:
        console.print(f"[bold red]Invalid month '{month_str}'. Use YYYY-MM or 'last'.[/bold red]")
        return None


def _parse_target_year(year_str):
    """Parse a year arg (YYYY or 'last'). Returns int year, or None on error."""
    now = datetime.now()
    if not year_str:
        return now.year
    if year_str.lower() == "last":
        return now.year - 1
    try:
        y = int(year_str)
        if 2000 <= y <= 2100:
            return y
    except (ValueError, TypeError):
        pass
    console.print(f"[bold red]Invalid year '{year_str}'. Use YYYY or 'last'.[/bold red]")
    return None


def _parse_inline_modifiers(text: str, today):
    """Parse priority and due date from inline text like 'high priority due monday'.

    Returns (priority_str_or_None, due_date_str_or_None).
    """
    text_lower = text.lower()

    # Priority
    priority = None
    if "high" in text_lower:
        priority = "high"
    elif "low" in text_lower:
        priority = "low"
    elif "medium" in text_lower or "med" in text_lower:
        priority = "medium"

    # Due date — look for "due <token>"
    due_date = None
    m = re.search(r'\bdue\s+(\S+)', text_lower)
    if m:
        day_str = m.group(1).rstrip(".,;")
        weekdays = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                    "friday": 4, "saturday": 5, "sunday": 6,
                    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
        if day_str == "today":
            due_date = today.strftime("%Y-%m-%d")
        elif day_str == "tomorrow":
            due_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        elif day_str in weekdays:
            target_wd = weekdays[day_str]
            days_ahead = target_wd - today.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            due_date = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        else:
            try:
                datetime.strptime(day_str, "%Y-%m-%d")
                due_date = day_str
            except ValueError:
                pass

    return priority, due_date


def cmd_wrap_day(date_str=None):
    ensure_dirs()
    now = datetime.now()

    target_date = _parse_target_day(date_str)
    if target_date is None:
        return

    is_past = target_date < now.date()
    target_dt = datetime.combine(target_date, datetime.min.time())
    daily_path = get_daily_note_path(target_date)

    if not daily_path.exists():
        date_label = target_date.strftime("%B %d, %Y")
        console.print(f"[dim]No daily note found for {date_label} — nothing to wrap.[/dim]")
        return

    content = daily_path.read_text(encoding="utf-8")

    if not get_anthropic_key():
        console.print("[bold red]ANTHROPIC_API_KEY not set — needed for wrap.[/bold red]")
        return

    from ..ai import generate_day_summary, revise_summary, parse_quick_notes, extract_chapter_updates, revise_chapter_content, filter_duplicate_tasks, split_chapter_content

    date_label = target_date.strftime("%B %d")
    if is_past:
        console.print(f"[dim]Wrapping [bold]{date_label}[/bold] (past day)...[/dim]\n")

    # ── Step 1: Day summary with approval loop ──────────────────────────────
    print_thinking(f"reading {'today' if not is_past else date_label + chr(39) + 's'} notes...")
    summary = generate_day_summary(content)

    while True:
        print_ai_message(summary, title="day summary draft", mood="cheer")
        response = Prompt.ask(
            "\n  Approve this summary? [[bold]Y[/bold]/feedback to revise]",
            default=""
        ).strip()
        if not response or response.lower() in ("y", "yes"):
            break
        print_thinking("revising...")
        summary = revise_summary(summary, response, content)

    time_str = format_time(now)
    summary_section = f"\n---\n\n## Day Summary — {time_str}\n\n{summary}\n"
    with open(daily_path, "a", encoding="utf-8") as f:
        f.write(summary_section)
    update_index_entry(str(daily_path), {"summary": f"Daily note — {target_date.strftime('%b %d')} (wrapped)"})

    # ── Step 2: Quick notes → potential tasks ───────────────────────────────
    config = load_config()
    chapters = config.get("chapters", [])

    if chapters:
        console.print("\n[dim]Parsing quick notes for action items...[/dim]")
        qn_parsed = parse_quick_notes(content, chapters)

        potential_tasks = qn_parsed.get("potential_tasks", [])
        if potential_tasks:
            tasks = load_tasks()
            existing_descriptions = [t["description"] for t in tasks if t.get("status") != "done"]
            if existing_descriptions:
                console.print("\n[dim]Checking for duplicate tasks...[/dim]")
                potential_tasks = filter_duplicate_tasks(potential_tasks, existing_descriptions)
        if potential_tasks:
            console.print(f"\n[bold]Found {len(potential_tasks)} potential task(s) in your quick notes:[/bold]")
            tasks = load_tasks()
            any_added = False
            for item in potential_tasks:
                console.print(f"\n  [cyan]→[/cyan] {item}")
                while True:
                    response = Prompt.ask(
                        "  Add as a task? [[bold]Y[/bold]/n]",
                        default=""
                    ).strip()
                    resp_lower = response.lower()
                    if not resp_lower or resp_lower in ("y", "yes"):
                        add_it, extra = True, ""
                        break
                    elif resp_lower.startswith("y "):
                        add_it, extra = True, response[2:]
                        break
                    elif resp_lower in ("n", "no"):
                        add_it, extra = False, ""
                        break
                    else:
                        console.print("[dim]Please enter y or n.[/dim]")
                if add_it:
                    priority, due_date = _parse_inline_modifiers(extra, now.date()) if extra else (None, None)
                    task = {
                        "id": get_next_task_id(tasks),
                        "description": item,
                        "status": "todo",
                        "priority": priority,
                        "created_at": now.isoformat(),
                        "due_date": due_date,
                        "tags": [],
                        "weekly": False,
                    }
                    tasks.append(task)
                    any_added = True
                    added_msg = f"  [green]✓[/green] Added as task #{task['id']}"
                    details = []
                    if priority:
                        details.append(f"{priority} priority")
                    if due_date:
                        details.append(f"due {due_date}")
                    if details:
                        added_msg += f" [dim]({', '.join(details)})[/dim]"
                    console.print(added_msg)
            if any_added:
                save_tasks(tasks)

        # ── Step 3: Chapter note assignments with approval loop ──────────────
        console.print("\n[dim]Identifying chapter-relevant content...[/dim]")
        all_updates = extract_chapter_updates(content, chapters)

        chapter_obs = qn_parsed.get("chapter_observations", {})
        for chapter_label, obs_list in chapter_obs.items():
            obs_text = "\n".join(f"- {o}" for o in obs_list)
            if chapter_label in all_updates:
                all_updates[chapter_label] = all_updates[chapter_label] + "\n" + obs_text
            else:
                all_updates[chapter_label] = obs_text

        if all_updates:
            console.print(f"\n[bold]Found content for {len(all_updates)} chapter(s):[/bold]")
            for chapter_label, chapter_content in list(all_updates.items()):
                while True:
                    console.print(f"\n  [cyan]→[/cyan] [bold]{chapter_label}[/bold]")
                    for line in chapter_content.strip().splitlines():
                        console.print(f"    [dim]{line}[/dim]")
                    response = Prompt.ask(
                        "  Add to chapter note? [[bold]Y[/bold]/n/feedback/other chapter name]",
                        default=""
                    ).strip()
                    if not response or response.lower() in ("y", "yes"):
                        _append_to_chapter_note(chapter_label, chapter_content, target_dt)
                        console.print(f"  [green]✓[/green] Updated: {chapter_label}")
                        break
                    elif response.lower() in ("n", "no"):
                        console.print("  [dim]Skipped.[/dim]")
                        break
                    else:
                        # Check for split routing (multiple chapters mentioned)
                        if _count_chapters_mentioned(response, chapters) >= 2:
                            print_thinking("splitting across chapters...")
                            splits = split_chapter_content(response, chapter_content, chapters)
                            if splits:
                                for split_label, split_text in splits.items():
                                    _append_to_chapter_note(split_label, split_text, target_dt)
                                    console.print(f"  [green]✓[/green] Added to: {split_label}")
                                break
                        # Single chapter redirect
                        target = _match_chapter(response, chapters)
                        if target:
                            _append_to_chapter_note(target, chapter_content, target_dt)
                            console.print(f"  [green]✓[/green] Added to: {target}")
                            break
                        # Otherwise treat as revision feedback
                        print_thinking("revising...")
                        chapter_content = revise_chapter_content(chapter_content, response, content, chapter_label)
        else:
            console.print("[dim]No chapter-specific content found.[/dim]")

    console.print(f"\n[dim]Day wrapped. Use [bold]gti open[/bold] to browse your notes.[/dim]")


def cmd_wrap_week(date_str=None):
    ensure_dirs()
    now = datetime.now()

    monday = _parse_target_week(date_str)
    if monday is None:
        return
    sunday = monday + timedelta(days=6)
    is_past = sunday < now.date()

    week_label = f"{monday.strftime('%b %d')}–{sunday.strftime('%b %d, %Y')}"

    # Collect Mon–Sun daily notes
    week_notes = []
    d = monday
    while d <= sunday:
        path = get_daily_note_path(d)
        if path.exists():
            week_notes.append((d, path.read_text(encoding="utf-8")))
        d += timedelta(days=1)

    tasks = load_tasks()
    week_start_dt = datetime.combine(monday, datetime.min.time())
    week_end_dt = datetime.combine(sunday + timedelta(days=1), datetime.min.time())
    done_this_week = [
        t for t in tasks
        if t.get("status") == "done"
        and t.get("completed_at")
        and week_start_dt <= datetime.fromisoformat(t["completed_at"]) < week_end_dt
    ]

    console.print(Panel(
        f"[bold]Weekly Wrap — {week_label}[/bold]\n[dim]Let's close out the week.[/dim]",
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

    # Save weekly note — filename anchored to Monday of that week
    filename = monday.strftime("%Y-%m-%d") + "-weekly-wrap.md"
    filepath = NOTES_DIR / filename

    done_md = "\n".join(f"- {t['description']}" for t in done_this_week) or "_(none logged)_"
    file_content = (
        f"---\n"
        f"date: {now.isoformat()}\n"
        f"project: dissertation\n"
        f"type: weekly-wrap\n"
        f"tags: [\"weekly-wrap\"]\n"
        f"---\n\n"
        f"# Weekly Wrap — {week_label}\n\n"
        f"## Tasks completed\n\n{done_md}\n\n"
        f"## Wins\n\n{wins or '_(skipped)_'}\n\n"
        f"## What didn't get done\n\n{stuck or '_(skipped)_'}\n\n"
        f"## Priority next week\n\n{priority or '_(skipped)_'}\n\n"
        f"## Friend's take\n\n{msg}\n"
    )
    filepath.write_text(file_content, encoding="utf-8")

    index = load_index()
    index.append({
        "date": now.isoformat(),
        "file": str(filepath),
        "project": "dissertation",
        "task_id": None,
        "summary": f"Weekly wrap — {week_label}",
        "tags": ["weekly-wrap"],
    })
    save_index(index)

    print_success("Weekly wrap saved.")

    if not is_past and confirm("\nPlan next week now?", default=True):
        from .plan import cmd_plan
        cmd_plan()


def cmd_wrap_month(month_str=None):
    ensure_dirs()
    now = datetime.now()

    result = _parse_target_month(month_str)
    if result is None:
        return
    target_year, target_month = result

    _, last_day = cal_module.monthrange(target_year, target_month)
    month_notes = []
    for day in range(1, last_day + 1):
        d = date_type(target_year, target_month, day)
        path = get_daily_note_path(d)
        if path.exists():
            month_notes.append((d, path.read_text(encoding="utf-8")))

    month_dt = datetime(target_year, target_month, 1)
    month_label = month_dt.strftime("%B %Y")
    is_past = (target_year, target_month) < (now.year, now.month)

    if not month_notes:
        console.print(f"[dim]No daily notes found for {month_label} — nothing to wrap.[/dim]")
        return

    tasks = load_tasks()
    month_start_dt = datetime(target_year, target_month, 1)
    month_end_dt = datetime(target_year, target_month, last_day, 23, 59, 59)
    done_this_month = [
        t for t in tasks
        if t.get("status") == "done"
        and t.get("completed_at")
        and month_start_dt <= datetime.fromisoformat(t["completed_at"]) <= month_end_dt
    ]

    console.print(Panel(
        f"[bold]Monthly Wrap — {month_label}[/bold]\n[dim]Let's reflect on the month ({len(month_notes)} days with notes).[/dim]",
        border_style="blue",
        padding=(1, 2),
    ))

    if done_this_month:
        console.print(f"\n[bold green]Completed this month ({len(done_this_month)} tasks):[/bold green]")
        for t in done_this_month:
            console.print(f"  [green]✓[/green] {t['description']}")
    else:
        console.print("\n[dim]No tasks marked done this month.[/dim]")

    console.print()
    wins = Prompt.ask("[bold cyan]What were your wins this month?[/bold cyan]", default="").strip()
    console.print()
    stuck = Prompt.ask("[bold cyan]What didn't get done, and why?[/bold cyan]", default="").strip()
    console.print()
    priority = Prompt.ask("[bold cyan]Main priority for next month?[/bold cyan]", default="").strip()

    if not get_anthropic_key():
        console.print("[bold red]ANTHROPIC_API_KEY not set — needed for wrap.[/bold red]")
        return

    print_thinking("reflecting on your month...")
    from ..ai import generate_month_summary
    month_content = "\n\n---\n\n".join(content for _, content in month_notes)
    msg = generate_month_summary(month_content, done_this_month, wins, stuck, priority)
    print_ai_message(msg, title="month wrap", mood="cheer")

    filename = month_dt.strftime("%Y-%m") + "-monthly-wrap.md"
    filepath = NOTES_DIR / filename

    done_md = "\n".join(f"- {t['description']}" for t in done_this_month) or "_(none logged)_"
    file_content = (
        f"---\n"
        f"date: {now.isoformat()}\n"
        f"project: dissertation\n"
        f"type: monthly-wrap\n"
        f"tags: [\"monthly-wrap\"]\n"
        f"---\n\n"
        f"# Monthly Wrap — {month_label}\n\n"
        f"## Tasks completed\n\n{done_md}\n\n"
        f"## Wins\n\n{wins or '_(skipped)_'}\n\n"
        f"## What didn't get done\n\n{stuck or '_(skipped)_'}\n\n"
        f"## Priority next month\n\n{priority or '_(skipped)_'}\n\n"
        f"## Friend's take\n\n{msg}\n"
    )
    filepath.write_text(file_content, encoding="utf-8")

    index = load_index()
    index.append({
        "date": now.isoformat(),
        "file": str(filepath),
        "project": "dissertation",
        "task_id": None,
        "summary": f"Monthly wrap — {month_label}",
        "tags": ["monthly-wrap"],
    })
    save_index(index)

    print_success("Monthly wrap saved.")


def cmd_wrap_year(year_str=None):
    ensure_dirs()
    now = datetime.now()

    target_year = _parse_target_year(year_str)
    if target_year is None:
        return

    is_past = target_year < now.year

    # Gather content: prefer wrap files (monthly/weekly), fall back to daily notes
    all_year_files = sorted(NOTES_DIR.glob(f"{target_year}-*.md"))
    wrap_files = [f for f in all_year_files if "wrap" in f.name]
    daily_files = [f for f in all_year_files if "daily" in f.name]

    content_parts = []
    total_chars = 0
    MAX_CHARS = 12000

    for f in wrap_files:
        text = f.read_text(encoding="utf-8")
        content_parts.append(text[:3000])
        total_chars += min(len(text), 3000)
        if total_chars >= MAX_CHARS:
            break

    if total_chars < MAX_CHARS:
        for f in daily_files:
            text = f.read_text(encoding="utf-8")
            snippet = text[:400]
            content_parts.append(snippet)
            total_chars += len(snippet)
            if total_chars >= MAX_CHARS:
                break

    if not content_parts:
        console.print(f"[dim]No notes found for {target_year} — nothing to wrap.[/dim]")
        return

    tasks = load_tasks()
    year_start_dt = datetime(target_year, 1, 1)
    year_end_dt = datetime(target_year, 12, 31, 23, 59, 59)
    done_this_year = [
        t for t in tasks
        if t.get("status") == "done"
        and t.get("completed_at")
        and year_start_dt <= datetime.fromisoformat(t["completed_at"]) <= year_end_dt
    ]

    console.print(Panel(
        f"[bold]Yearly Wrap — {target_year}[/bold]\n[dim]Let's reflect on the year ({len(daily_files)} days with notes).[/dim]",
        border_style="blue",
        padding=(1, 2),
    ))

    if done_this_year:
        console.print(f"\n[bold green]Completed this year ({len(done_this_year)} tasks):[/bold green]")
        for t in done_this_year:
            console.print(f"  [green]✓[/green] {t['description']}")
    else:
        console.print("\n[dim]No tasks marked done this year.[/dim]")

    console.print()
    wins = Prompt.ask("[bold cyan]What were your biggest wins this year?[/bold cyan]", default="").strip()
    console.print()
    stuck = Prompt.ask("[bold cyan]What didn't happen, and why?[/bold cyan]", default="").strip()
    console.print()
    priority = Prompt.ask("[bold cyan]Main priority for next year?[/bold cyan]", default="").strip()

    if not get_anthropic_key():
        console.print("[bold red]ANTHROPIC_API_KEY not set — needed for wrap.[/bold red]")
        return

    print_thinking("reflecting on your year...")
    from ..ai import generate_year_summary
    year_content = "\n\n---\n\n".join(content_parts)
    msg = generate_year_summary(year_content, done_this_year, wins, stuck, priority)
    print_ai_message(msg, title="year wrap", mood="cheer")

    filename = f"{target_year}-yearly-wrap.md"
    filepath = NOTES_DIR / filename

    done_md = "\n".join(f"- {t['description']}" for t in done_this_year) or "_(none logged)_"
    file_content = (
        f"---\n"
        f"date: {now.isoformat()}\n"
        f"project: dissertation\n"
        f"type: yearly-wrap\n"
        f"tags: [\"yearly-wrap\"]\n"
        f"---\n\n"
        f"# Yearly Wrap — {target_year}\n\n"
        f"## Tasks completed\n\n{done_md}\n\n"
        f"## Wins\n\n{wins or '_(skipped)_'}\n\n"
        f"## What didn't happen\n\n{stuck or '_(skipped)_'}\n\n"
        f"## Priority next year\n\n{priority or '_(skipped)_'}\n\n"
        f"## Friend's take\n\n{msg}\n"
    )
    filepath.write_text(file_content, encoding="utf-8")

    index = load_index()
    index.append({
        "date": now.isoformat(),
        "file": str(filepath),
        "project": "dissertation",
        "task_id": None,
        "summary": f"Yearly wrap — {target_year}",
        "tags": ["yearly-wrap"],
    })
    save_index(index)

    print_success("Yearly wrap saved.")


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


def _count_chapters_mentioned(text: str, chapters: list) -> int:
    """Count how many distinct chapters are referenced in text."""
    text_lower = text.lower()
    count = 0
    for i, ch in enumerate(chapters):
        if f"ch{i+1}" in text_lower or f"chapter {i+1}" in text_lower:
            count += 1
        else:
            words = [w for w in ch.lower().split() if len(w) > 4]
            if any(w in text_lower for w in words):
                count += 1
    return count


def _append_to_chapter_note(chapter_label: str, content: str, now: datetime):
    """Append a dated excerpt to the appropriate chapter note file."""
    slug = chapter_note_slug(chapter_label)
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
