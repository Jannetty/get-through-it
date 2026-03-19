"""Friend dude — open-ended chat with your Claude companion."""

from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ..config import load_index, get_anthropic_key
from ..ai import chat_with_claude
from ..display import print_thinking, print_dude_chat

console = Console()


def _get_recent_notes_context(n: int = 3) -> str:
    """Load content from the n most recent notes for context."""
    index = load_index()
    if not index:
        return ""
    recent = sorted(index, key=lambda x: x.get("date", ""), reverse=True)[:n]
    snippets = []
    for entry in recent:
        filepath = Path(entry.get("file", ""))
        if filepath.exists():
            try:
                content = filepath.read_text(encoding="utf-8")
                snippets.append(
                    f"[{entry.get('date', '')[:10]}] {entry.get('summary', '')}\n{content[:800]}"
                )
            except Exception:
                pass
    if not snippets:
        return ""
    return "Recent session notes:\n\n" + "\n\n---\n\n".join(snippets)


def cmd_friend():
    if not get_anthropic_key():
        console.print("[red]ANTHROPIC_API_KEY not set.[/red] Add it to [bold]~/.zshrc[/bold] and run [bold]source ~/.zshrc[/bold] or open a new terminal.")
        return

    recent_notes = _get_recent_notes_context()

    console.print(Panel(
        "Your friend dude is here. Type [bold]bye[/bold] or press [bold]Ctrl+C[/bold] to leave.",
        title="[bold cyan]friend dude[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))

    conversation = []

    # Warm opener from the friend
    opener_prompt = (
        "Say a brief, warm hello to the user — just a sentence or two. "
        "Reference something specific about their dissertation work if you know it. "
        "Ask how things are going or what's on their mind."
    )
    if recent_notes:
        opener_prompt = f"{opener_prompt}\n\n{recent_notes}"

    print_thinking("saying hello...")
    opener = chat_with_claude(
        [{"role": "user", "content": opener_prompt}]
    )
    print_dude_chat(opener)
    conversation.append({"role": "user", "content": opener_prompt})
    conversation.append({"role": "assistant", "content": opener})

    while True:
        try:
            user_input = Prompt.ask("[bold]you[/bold]").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input:
            continue
        if user_input.lower() in ("bye", "exit", "quit", "goodbye"):
            print_dude_chat("Later. You've got this.")
            break

        conversation.append({"role": "user", "content": user_input})
        print_thinking()
        response = chat_with_claude(conversation)
        conversation.append({"role": "assistant", "content": response})
        print_dude_chat(response)

        # Keep conversation from growing unbounded
        if len(conversation) > 20:
            conversation = conversation[-20:]
