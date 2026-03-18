"""Find command — search notes using Claude."""

import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from ..config import load_index, NOTES_DIR
from ..ai import ask_claude

console = Console()

MAX_NOTES_TO_READ = 15


def cmd_find(query: str):
    index = load_index()

    if not index:
        console.print("[dim]No notes yet. Write some with [bold]gti note[/bold].[/dim]")
        return

    console.print(f"[dim]Searching {len(index)} notes for: [bold]{query}[/bold]...[/dim]\n")

    # Sort by date descending, take the most recent notes to include content for
    sorted_index = sorted(index, key=lambda x: x.get("date", ""), reverse=True)

    # Build context: full index metadata + content of the most recent/relevant notes
    index_summary = json.dumps([
        {
            "date": e.get("date", ""),
            "file": Path(e.get("file", "")).name,
            "summary": e.get("summary", ""),
            "tags": e.get("tags", []),
            "task_id": e.get("task_id"),
        }
        for e in sorted_index
    ], indent=2)

    # Include full content of up to MAX_NOTES_TO_READ most recent notes
    note_contents = []
    for entry in sorted_index[:MAX_NOTES_TO_READ]:
        filepath = Path(entry.get("file", ""))
        if filepath.exists():
            try:
                content = filepath.read_text(encoding="utf-8")
                note_contents.append(
                    f"=== {filepath.name} ===\n{content[:1500]}\n"
                )
            except Exception:
                pass

    notes_block = "\n".join(note_contents)

    prompt = f"""The user is looking for notes matching this query: "{query}"

Here is the full index of all notes (metadata only):
{index_summary}

Here is the content of the most recent {len(note_contents)} notes:
{notes_block}

Please identify which notes are relevant to the query. For each relevant note:
1. State the filename
2. Give a 1-2 sentence explanation of why it's relevant
3. Quote the most relevant snippet (under 40 words)

Format your response as a simple list. If nothing is relevant, say so honestly."""

    result = ask_claude(prompt, model="claude-sonnet-4-6")

    console.print(Panel(
        result,
        title=f"[bold cyan]Notes matching: {query}[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print(f"[dim]Notes are in: {NOTES_DIR}[/dim]")
