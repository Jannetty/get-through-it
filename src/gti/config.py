"""Configuration and data path management for gti."""

import json
import os
from pathlib import Path
from datetime import datetime, date as date_type


GTI_DIR = Path.home() / ".gti"
PROJECTS_DIR = GTI_DIR / "projects"
GLOBAL_DIR = GTI_DIR / "global"
DISSERTATION_DIR = PROJECTS_DIR / "dissertation"
NOTES_DIR = DISSERTATION_DIR / "notes"
CHAPTER_NOTES_DIR = DISSERTATION_DIR / "chapter-notes"
TASKS_FILE = DISSERTATION_DIR / "tasks.json"
CONFIG_FILE = DISSERTATION_DIR / "config.json"
INDEX_FILE = GLOBAL_DIR / "index.json"


def ensure_dirs():
    """Create all necessary directories."""
    for d in [GTI_DIR, PROJECTS_DIR, GLOBAL_DIR, DISSERTATION_DIR, NOTES_DIR, CHAPTER_NOTES_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def get_daily_note_path(d=None) -> Path:
    """Return the path for a day's daily note (does not create it)."""
    if d is None:
        d = datetime.now().date()
    elif isinstance(d, datetime):
        d = d.date()
    return NOTES_DIR / f"{d.strftime('%Y-%m-%d')}-daily.md"


def ensure_daily_note(d=None) -> Path:
    """Return the daily note path, creating it with frontmatter if it doesn't exist yet."""
    path = get_daily_note_path(d)
    if not path.exists():
        ensure_dirs()
        now = datetime.now()
        day = d if isinstance(d, date_type) else (d.date() if isinstance(d, datetime) else now.date())
        date_str = day.strftime("%B %d, %Y")
        path.write_text(
            f"---\n"
            f"date: {now.isoformat()}\n"
            f"project: dissertation\n"
            f"type: daily\n"
            f"tags: []\n"
            f"---\n\n"
            f"# Daily Note — {date_str}\n\n",
            encoding="utf-8",
        )
    return path


def ensure_daily_note_indexed(path: Path, now: datetime):
    """Add the daily note to the index if not already present."""
    index = load_index()
    path_str = str(path)
    if not any(e.get("file") == path_str for e in index):
        index.append({
            "date": now.isoformat(),
            "file": path_str,
            "project": "dissertation",
            "task_id": None,
            "summary": f"Daily note — {now.strftime('%b %d')}",
            "tags": ["daily"],
        })
        save_index(index)


def format_time(dt) -> str:
    """Cross-platform time formatting without leading zero on hour."""
    return dt.strftime("%I:%M %p").lstrip("0")


def update_index_entry(file_path: str, updates: dict):
    """Update fields on an existing index entry by file path."""
    index = load_index()
    for entry in index:
        if entry.get("file") == file_path:
            entry.update(updates)
            save_index(index)
            return


def is_setup() -> bool:
    """Check if the dissertation project has been set up."""
    return CONFIG_FILE.exists()


def load_config() -> dict:
    """Load the dissertation config."""
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE) as f:
        return json.load(f)


def save_config(config: dict):
    """Save the dissertation config."""
    ensure_dirs()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def load_tasks() -> list:
    """Load all tasks."""
    if not TASKS_FILE.exists():
        return []
    with open(TASKS_FILE) as f:
        return json.load(f)


def save_tasks(tasks: list):
    """Save tasks."""
    ensure_dirs()
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def load_index() -> list:
    """Load the global notes index."""
    if not INDEX_FILE.exists():
        return []
    with open(INDEX_FILE) as f:
        return json.load(f)


def save_index(index: list):
    """Save the global notes index."""
    ensure_dirs()
    with open(INDEX_FILE, "w") as f:
        json.dump(index, f, indent=2)


def get_next_task_id(tasks: list) -> int:
    """Get the next available task ID."""
    if not tasks:
        return 1
    return max(t["id"] for t in tasks) + 1


def get_anthropic_key() -> str | None:
    """Get the Anthropic API key from environment."""
    return os.environ.get("ANTHROPIC_API_KEY")


def chapter_note_slug(chapter_label: str) -> str:
    """Return a filesystem-safe slug for a chapter label like 'Ch3: title'."""
    slug = chapter_label.lower()
    for ch in " :/()\\":
        slug = slug.replace(ch, "-")
    return slug.strip("-")[:40]


def ensure_chapter_note_stubs(chapters: list):
    """Create empty chapter note files and index entries for any that don't exist yet."""
    ensure_dirs()
    index = load_index()
    now = datetime.now()
    changed = False

    for i, ch in enumerate(chapters):
        label = f"Ch{i+1}: {ch}"
        slug = chapter_note_slug(label)
        filepath = CHAPTER_NOTES_DIR / f"{slug}.md"

        if not filepath.exists():
            filepath.write_text(
                f"# {label} — Notes\n\n"
                f"_Notes for this chapter will be added here during `gti wrap day`._\n",
                encoding="utf-8",
            )

        path_str = str(filepath)
        if not any(e.get("file") == path_str for e in index):
            index.append({
                "date": now.isoformat(),
                "file": path_str,
                "project": "dissertation",
                "task_id": None,
                "summary": f"{label} — notes",
                "tags": ["chapter-note"],
            })
            changed = True

    if changed:
        save_index(index)
