# herdr-catchup

Catch up on, fork, and hand off coding-agent sessions from inside [herdr](https://herdr.dev).

[catchup](https://github.com/wilbeibi/catchup) reads local agent session history (Codex, Claude Code, OpenCode, Pi Agent) and can resume a session natively or seed a *different* agent with the transcript. This plugin puts that one keystroke away in herdr: an agent pane hits its usage limit, you press a key, and a new pane opens next to it running another agent that already knows the whole conversation.

## Install

Prerequisite — the `catchup` binary:

```bash
go install github.com/wilbeibi/catchup@latest
# make sure $(go env GOPATH)/bin is on your PATH
```

Then:

```bash
herdr plugin install wilbeibi/herdr-catchup
```

## Actions

Each action opens a plugin pane to the right, started in the focused pane's project directory — which is how catchup finds the right session. The summary pane stays in the background and closes on Enter; fork and handoff panes take focus, since you'll be typing into the agent they launch.

| Action | What it does |
|---|---|
| `wilbeibi.catchup.summary` | Shows `catchup --since-compact` — a clean Markdown summary of the newest session in this project, without touching the running agent. |
| `wilbeibi.catchup.fork` | Runs `catchup fork` — natively resumes the newest session in the new pane (e.g. `claude --resume <id> --fork-session`). |
| `wilbeibi.catchup.handoff` | Asks which agent to hand off to (codex / claude / opencode / pi-agent), then runs `catchup fork --into <choice>` — the target agent starts seeded with the session transcript. |

Invoke ad hoc with `herdr plugin action invoke wilbeibi.catchup.<action>`, or bind keys:

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

## How it works, and limits

- catchup resolves sessions by the working directory, and `fork` launches the agent CLI interactively — so every action runs catchup inside a real pane (`herdr plugin pane open --cwd <project>`), never headless. Errors (`no sessions found`, missing binary, handing off to the same agent) print in that pane and wait for Enter, so they can't vanish unread.
- If an action seems to do nothing (no pane appears), check `herdr plugin log list --plugin wilbeibi.catchup` — pre-pane failures land there.
- Requires herdr ≥ 0.7.0 on Linux or macOS.

## Local development

```bash
herdr plugin link /path/to/herdr-catchup
herdr plugin action list --plugin wilbeibi.catchup
herdr plugin action invoke wilbeibi.catchup.summary
```

## Future ideas

- Per-agent handoff actions (`handoff-codex`, …) for zero-prompt keybindings — `bin/run.sh handoff <target>` already supports it; each is a three-line manifest addition.
- A `worktree.created` event hook that offers a catch-up summary in new worktrees.
- Session search (`catchup -q`) once actions can take arguments.

## License

MIT
