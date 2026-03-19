"""Natural language command dispatcher."""

from rich.console import Console

from ..config import load_tasks, load_config, get_anthropic_key
from ..display import print_thinking, print_error

console = Console()


def cmd_do(text: str):
    if not text:
        print_error("Tell me what you want to do.")
        return

    if not get_anthropic_key():
        print_error("ANTHROPIC_API_KEY not set — needed for natural language commands.")
        return

    config = load_config()
    chapters = config.get("chapters", [])
    tasks = load_tasks()

    print_thinking("figuring out what to do...")
    from ..ai import parse_nl_command
    result = parse_nl_command(text, tasks, chapters)
    action = result.get("action", "unknown")

    if action == "add_task":
        from .tasks import cmd_add
        cmd_add(
            result["description"],
            due_date=result.get("due_date"),
            tags=result.get("tags", []),
            weekly=result.get("weekly", False),
            priority=result.get("priority"),
        )
    elif action == "done":
        from .tasks import cmd_done
        cmd_done(result.get("task_text", text))
    elif action == "qn":
        from .note import cmd_qn
        cmd_qn(result.get("text", text))
    else:
        print_error(
            "Couldn't figure out what to do from that.\n"
            "  Try [bold]gti add[/bold], [bold]gti done[/bold], or [bold]gti qn[/bold] directly."
        )
