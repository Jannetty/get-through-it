"""Open notes in VSCode."""

import subprocess
from pathlib import Path
from rich.console import Console

from ..config import NOTES_DIR, load_index, get_anthropic_key
from ..display import print_error

console = Console()


def cmd_open(query: str = None):
    if not NOTES_DIR.exists():
        print_error(f"Notes directory doesn't exist yet: {NOTES_DIR}")
        return

    if not query:
        _open_in_vscode(NOTES_DIR)
        return

    # Try to match query to a specific note
    index = load_index()
    if not index:
        console.print("[dim]No notes yet — opening the notes folder.[/dim]")
        _open_in_vscode(NOTES_DIR)
        return

    if get_anthropic_key():
        console.print(f"[dim]Finding note matching: {query}...[/dim]")
        from ..ai import find_note_file
        file_path = find_note_file(query, index)
        if file_path:
            path = Path(file_path)
            if path.exists():
                _open_in_vscode(NOTES_DIR, path)
                return
            console.print(f"[yellow]Matched note not found on disk, opening folder instead.[/yellow]")
        else:
            console.print(f"[yellow]No match found for \"{query}\", opening folder.[/yellow]")
    else:
        console.print("[dim]ANTHROPIC_API_KEY not set — opening notes folder.[/dim]")

    _open_in_vscode(NOTES_DIR)


def _open_in_vscode(*paths):
    """Open one or more paths in VSCode."""
    str_paths = [str(p) for p in paths]
    try:
        subprocess.run(["code"] + str_paths, check=True)
        if len(str_paths) > 1:
            console.print(f"[dim]Opened {paths[-1].name} in VSCode.[/dim]")
        else:
            console.print(f"[dim]Opened notes folder in VSCode.[/dim]")
    except FileNotFoundError:
        print_error(
            "VSCode CLI not found. Make sure 'code' is in your PATH.\n"
            "In VSCode: Cmd+Shift+P → 'Shell Command: Install code command in PATH'"
        )
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to open VSCode: {e}")
