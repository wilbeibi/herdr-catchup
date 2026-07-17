# herdr-catchup

### Pick up a session in the next pane over

An agent pane hits its limit. You press a key. A pane opens beside it running another agent that already knows the job.

This plugin is [catchup](https://github.com/wilbeibi/catchup) wired into [herdr](https://herdr.dev). catchup reads the local session history for Codex, Claude Code, Antigravity, Cline, Cursor, Kimi, OpenCode, and Pi Agent, and picks the work back up in the same agent or a different one. herdr knows which project the focused pane is in, which is the one thing catchup needs to find the right session.

Three actions: read a session, fork it, hand it to another agent.

## Install

First the `catchup` binary:

```bash
brew install wilbeibi/tap/catchup

# or a prebuilt binary, no Go needed
curl -fsSL https://raw.githubusercontent.com/wilbeibi/catchup/main/scripts/install.sh | sh

# or from source
go install github.com/wilbeibi/catchup@latest   # then put $(go env GOPATH)/bin on your PATH
```

Then:

```bash
herdr plugin install wilbeibi/herdr-catchup
```

## Actions

Each action opens a pane to the right, in the focused pane's project directory. That directory is how catchup finds the session. The summary pane stays in the background and closes on Enter. Fork and handoff panes take focus — you'll be typing into the agent they launch.

| Action | What it does |
|---|---|
| `wilbeibi.catchup.summary` | `catchup --since-compact` — the newest session in this project as clean Markdown. Leaves the running agent alone. |
| `wilbeibi.catchup.fork` | `catchup fork` — resumes that session natively in the new pane, e.g. `claude --resume <id> --fork-session`. Full state. |
| `wilbeibi.catchup.handoff` | Asks which agent (codex / claude / agy / cline / cursor / opencode / pi-agent), then `catchup fork --into <choice>`. The other agent starts with the transcript already in hand. |

Run one with `herdr plugin action invoke wilbeibi.catchup.<action>`, or bind keys:

```toml
[[keys.command]]
key = "prefix+c"
type = "plugin_action"
command = "wilbeibi.catchup.summary"
description = "catch up on this pane's session"

[[keys.command]]
key = "prefix+f"
type = "plugin_action"
command = "wilbeibi.catchup.fork"
description = "fork session in a new pane"

[[keys.command]]
key = "prefix+h"
type = "plugin_action"
command = "wilbeibi.catchup.handoff"
description = "hand session off to another agent"
```

## How it works

catchup finds sessions by working directory, and `fork` launches an agent CLI interactively. So every action runs catchup inside a real pane (`herdr plugin pane open --cwd <project>`), never headless. Errors — no sessions here, missing binary, handing an agent its own session — print in that pane and wait for Enter. They can't vanish unread.

No pane at all? The failure happened before the pane existed. It's in `herdr plugin log list --plugin wilbeibi.catchup`.

Needs herdr 0.7.0 or newer, on Linux or macOS.

## Local development

```bash
herdr plugin link /path/to/herdr-catchup
herdr plugin action list --plugin wilbeibi.catchup
herdr plugin action invoke wilbeibi.catchup.summary
```

## Ideas

- A key per target agent (`handoff-codex`, …), so a handoff is one press and no menu. `bin/run.sh handoff <target>` already takes the argument; each one is three lines of manifest.
- A `worktree.created` hook that forks the originating session into the new worktree. catchup has the missing piece now: sessions are keyed by directory, and `--dir` reaches a session from a tree it never ran in — `catchup fork claude --dir <origin>`.
- Session search, `catchup -q "topic"`, once actions can take arguments.
- Handing off work that isn't a local session. `catchup fork --into <agent> --from <file | - | url>` seeds an agent from a transcript, a pipe, or a URL — a pane could pick up a job that started on another machine.

## License

MIT
