# get-through-it — a vibe-coded friend to help you finish your doctoral dissertation

You've scheduled your defense date. You have your chapters outlined and the set of work you have to do before you submit is well defined. There is light at the end of the tunnel.

`gti` is a CLI tool that helps you get through it. It includes incredibly simple task tracking, Pomodoro timers, daily notes, and a Claude-powered friend dude who knows your work and checks in on you.

---

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for installation
- An [Anthropic API key](https://console.anthropic.com/) (most features require one — $5 of credits will last a long time at this usage level)
- [VSCode](https://code.visualstudio.com/) if you want to be able to open the notes gti makes for reference or to edit manually

---

## Installation

Clone the repo and install with `uv`:

```sh
git clone https://github.com/Jannetty/get-through-it.git
cd get-through-it
uv tool install --editable .
```

The `--editable` flag means any changes you make to the source are picked up immediately without reinstalling. This is important if you plan on tinkering with the tool and don't want to have to reinstall each time you make a change. If you just plan on using the tool as-is you can just call `uv tool install`.

Set your Anthropic API key — add this to your `~/.zshrc` (or `~/.bashrc`):

```sh
export ANTHROPIC_API_KEY="sk-ant-..."
```

Then reload your shell:

```sh
source ~/.zshrc
```

Run first-time setup:

```sh
gti setup
```

This walks you through your dissertation topic, defense date, and chapter structure, and seeds your initial task list.

---

## Daily workflow

### Start your day

```sh
gti today
```

Your friend dude checks in with a note about your week's tasks and defense date.

### Work sessions

Start a Pomodoro timer — the dude watches you work:

```sh
gti pomo          # free session
gti pomo 3        # link to task #3
```

Before the timer starts you'll be asked what you're planning to work on. After the 25 minutes you'll be asked what you got done (defaults to "still working on it"). Both get logged to today's daily note automatically.

### Quick notes

Jot anything down without interrupting your flow — no quotes needed:

```sh
gti qn remember to check whether the parity fix holds for edge cases
gti qn wt neuroblasts grow 1.8x faster than mutant neuroblasts
```

These get appended to today's daily note with a timestamp. During `gti wrap day`, Claude will scan them for action items (offering to turn them into tasks) and route factual observations to the appropriate chapter notes.

### Structured session notes

For a more thorough debrief after a work session:

```sh
gti note
gti note -t 3    # associate with task #3
```

Six guided prompts: what you worked on, what you got done, what's in progress, what to pick up next, decisions/realizations, and how you're feeling. All appended to today's daily note.

### Tasks

```sh
gti tasks                    # view all active tasks, sorted by priority
gti add "description"        # add a task
gti add "description" -d 2026-03-21 -t chapter_3  # with due date and tags
gti done 3                   # mark task #3 done
gti done "I fixed the parity issue"   # natural language — Claude matches it
gti reorder                  # manually set priority order
```

### End of day

```sh
gti wrap day
```

Claude reads your full daily note and:

1. Appends a synthesis section at the bottom summarizing what you accomplished
2. Scans quick notes for action items and offers to create tasks from them
3. Routes factual observations and findings to the relevant chapter notes

Your original notes are never modified — Claude only appends below a `---` divider.

### Plan your week

```sh
gti plan
```

Shows your active tasks, Claude suggests which 3-5 to focus on this week, and you describe what you want to tackle in plain English. New tasks mentioned in your response are detected and you're walked through adding them with inferred due dates and tags.

### End of week

```sh
gti wrap week
```

Reflection prompts (wins, what didn't get done, next week's priority), a Claude-generated summary, saved as a weekly note. Offers to run `gti plan` for the new week when done.

### Chat with your friend dude

```sh
gti friend
```

Open-ended conversation. The dude has context on your dissertation topic, defense date, active tasks, and recent notes. Type `bye` to exit.

---

## Notes and where they live

All notes are stored in `~/.gti/projects/dissertation/`:

```bash
~/.gti/
  projects/
    dissertation/
      tasks.json               ← your task list
      config.json              ← dissertation topic, defense date, chapters
      notes/
        2026-03-18-daily.md    ← one per day (all session content flows here)
        2026-03-18-weekly-wrap.md
        ...
      chapter-notes/
        ch3-volume-based-gr... ← persistent per-chapter notes, updated by wrap day
        ...
```

### Opening your notes

```sh
gti open                          # opens the notes folder in VSCode
gti open "yesterday's daily note"
gti open "last week's weekly wrap"
gti open "the note about neuroblast growth"
```

`gti open` with a description uses Claude to find the best matching note and opens it directly in VSCode alongside the notes folder so you can browse.

> **Note:** `gti open` requires the VSCode `code` CLI to be installed. If you get a "command not found" error, open VSCode and run **Cmd+Shift+P** → `Shell Command: Install 'code' command in PATH`, then restart your terminal.

### Note format

Daily notes are plain Markdown with YAML frontmatter. Each session, check-in, quick note, and Pomodoro gets a timestamped `##` section appended in order. At the end of the day after `gti wrap day`, a `## Day Summary` section is added at the bottom.

```markdown
---
date: 2026-03-18T09:12:00
project: dissertation
type: daily
---

# Daily Note — March 18, 2026

## Pomodoro — 9:15 AM
**Task:** #3 — Modify volume-based growth regulation
**Plan:** fix parity between regulated and unregulated lineages
**Result:** still working on it

## Quick Note — 11:03 AM
wt neuroblasts grow 1.8x faster than mutant neuroblasts

## Session — 2:30 PM — Modify volume-based growth regulation
**What did you work on:** cell count parity
**What did you get done:** got cell count parity working, lineage volume still off

---

## Day Summary — 5:45 PM

- Fixed cell count parity in the volume-based growth regulation implementation
- Identified lineage volume discrepancy as the remaining issue
- WT neuroblast growth rate finding logged — routed to Ch3 notes
```

### Searching notes

```sh
gti find "volume-based growth regulation"
gti find "what did I decide about the VAE approach"
gti find "times I felt stuck on chapter 3"
```

Claude reads your note index and the content of recent notes to find relevant passages and explain why they match.

---

## All commands

| Command | What it does |
|---|---|
| `gti setup` | First-time setup |
| `gti today` | Daily view + friend dude check-in |
| `gti tasks` | All active tasks, sorted by priority |
| `gti add "..."` | Add a task (use quotes) |
| `gti done <id or text>` | Mark a task done |
| `gti reorder` | Manually set task priority |
| `gti plan` | Pick this week's focus with Claude |
| `gti pomo [id]` | 25/5 Pomodoro timer |
| `gti note` | Structured session note |
| `gti qn <text>` | Quick freeform note — no quotes needed |
| `gti wrap day` | End-of-day synthesis + chapter note updates |
| `gti wrap week` | End-of-week reflection and summary |
| `gti find "..."` | Search notes with Claude |
| `gti open [query]` | Open notes in VSCode |
| `gti friend` | Chat with your friend dude |

---

## Tips

- **`gti qn` is your friend.** Any observation, reminder, or stray thought goes here. Don't let the perfect be the enemy of the good — log it and let `gti wrap day` sort it out.
- **Daily notes accumulate throughout the day.** Every `gti note`, `gti pomo`, and `gti qn` appends to the same file. Open it in VSCode with `gti open` to see everything in one place.
- **Chapter notes build over time.** Each `gti wrap day` extracts what's relevant to each chapter and appends it. After a few weeks they become a living record of your progress on each chapter.
- **The dude is chill.** If something is hard, he'll say so. He's not going to give you toxic positivity. He just believes in you.

---

## Thoughts? Questions? Suggestions?

This thing is like 95% vibe coded, so errors are possibly very likely. I'm very open to suggestion. Feel free to open an issue or PR or anything else.

In the future I think it would be fun to generalize the dude to work on multiple projects (you may notice the structure of the notes folders is designed with that future functionality in mind), but for now I need to graduate so tinkering is back burnered!
