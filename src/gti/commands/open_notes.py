"""Open notes in VSCode."""

import subprocess
from pathlib import Path
from rich.console import Console

from ..config import NOTES_DIR, DISSERTATION_DIR, load_index, get_anthropic_key
from ..display import print_error

console = Console()


def cmd_open(query: str = None):
    if not DISSERTATION_DIR.exists():
        print_error(f"Notes directory doesn't exist yet: {DISSERTATION_DIR}")
        return

    if not query:
        _open_in_vscode(DISSERTATION_DIR)
        return

    # Try to match query to a specific note
    index = load_index()
    if not index:
        console.print("[dim]No notes yet — opening the notes folder.[/dim]")
        _open_in_vscode(DISSERTATION_DIR)
        return

    if get_anthropic_key():
        from ..ai import find_note_file
        from ..display import print_thinking
        print_thinking(f"finding: {query}...")
        # Fast pass: index metadata only
        file_path = find_note_file(query, index, read_content=False)
        if file_path:
            path = Path(file_path)
            if path.exists():
                _open_in_vscode(DISSERTATION_DIR, path)
                return
        # Deep pass: read note content
        print_thinking("looking harder...")
        file_path = find_note_file(query, index, read_content=True)
        if file_path:
            path = Path(file_path)
            if path.exists():
                _open_in_vscode(DISSERTATION_DIR, path)
                return
        console.print(f"[yellow]No match found for \"{query}\" — opening folder.[/yellow]")
    else:
        console.print("[dim]ANTHROPIC_API_KEY not set — opening notes folder.[/dim]")

    _open_in_vscode(DISSERTATION_DIR)


def _open_in_vscode(folder: Path, file: Path = None):
    """Open the notes folder in VSCode, optionally jumping to a specific file."""
    try:
        if file:
            subprocess.run(["code", str(folder), "--goto", str(file)], check=True)
            console.print(f"[dim]Opened {file.name} in VSCode.[/dim]")
        else:
            subprocess.run(["code", str(folder)], check=True)
            console.print(f"[dim]Opened notes folder in VSCode.[/dim]")
    except FileNotFoundError:
        print_error(
            "VSCode CLI not found. Make sure 'code' is in your PATH.\n"
            "In VSCode: Cmd+Shift+P → 'Shell Command: Install code command in PATH'"
        )
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to open VSCode: {e}")
