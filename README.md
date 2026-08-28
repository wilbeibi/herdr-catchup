# herdr-catchup — cross-agent session handoff for herdr

herdr-catchup is a [herdr](https://herdr.dev) plugin for cross-agent coding-session handoff: from the pane an agent is working in, read that session, fork it, or hand it to a different agent — Claude Code to Codex, Cursor to OpenCode — without re-explaining the job.

```bash
herdr plugin install wilbeibi/herdr-catchup
```

### Pick up a session in the next pane over

An agent pane hits its limit. You press a key. A pane opens beside it running another agent that already knows the job.

This plugin is [catchup](https://github.com/wilbeibi/catchup) wired into herdr. catchup reads the local session history for Codex, Claude Code, Antigravity, Cline, Copilot CLI, Cursor, Kimi, OpenCode, and Pi Agent, and picks the work back up in the same agent or a different one. herdr knows which pane you are looking at, which agent is in it, and which session that agent holds — and that last one is something catchup cannot work out alone.

Five actions: read a session, fork it, hand it to a new agent, hand it to an agent already running in another pane, or ask that agent to review it.

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

It is also listed in the [herdr plugin marketplace](https://herdr.dev/plugins/), which indexes public repos tagged `herdr-plugin`.

## Actions

Each action opens a pane to the right, in the focused pane's project directory, and works on the exact session that pane's agent holds. The summary pane stays in the background and closes on Enter. The other four take focus — you'll be typing into a menu or into the agent they launch.

| Action | What it does |
|---|---|
| `wilbeibi.catchup.summary` | `catchup --since-compact` — that pane's session as clean Markdown. Leaves the running agent alone. |
| `wilbeibi.catchup.fork` | `catchup fork` — resumes the session natively in the new pane, e.g. `claude --resume <id> --fork-session`. Full state. |
| `wilbeibi.catchup.handoff` | Asks which agent (codex / claude / agy / cline / copilot / cursor / opencode / pi-agent), then `catchup fork --into <choice>` — a **new** agent, started with the transcript in hand. |
| `wilbeibi.catchup.send` | Lists the agents **already running** in this herdr session, renders the transcript to a file, and hands the one you pick its path. No new process; the agent in that pane picks the work up. |
| `wilbeibi.catchup.ask` | Same delivery, review framing: the other agent is asked to attack the assumptions of your latest turn, name a cheaper alternative, and say where it breaks. Two models arguing, one round. |

`send` and `ask` are the two that only exist because of herdr: catchup can render any session, but only herdr knows which agents are alive right now and how to reach them.

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
description = "hand session off to a new agent"

[[keys.command]]
key = "prefix+r"
type = "plugin_action"
command = "wilbeibi.catchup.ask"
description = "ask a running agent to review this"
```

## Agent support

| Agent | Catch up | Fork in place | Handoff target |
|---|---|---|---|
| Claude Code | ✓ | ✓ branch | ✓ |
| Codex | ✓ | ✓ branch | ✓ |
| OpenCode | ✓ | ✓ branch | ✓ |
| Pi Agent | ✓ | ✓ branch | ✓ |
| Antigravity (`agy`) | ✓ | ✓ resume | ✓ |
| Cline | ✓ | ✓ resume | ✓ |
| Copilot CLI | ✓ | ✓ resume | ✓ |
| Cursor | ✓ | ✓ resume | ✓ |
| Kimi | ✓ | ✓ resume | — |

*Fork in place* uses each agent's own resume path. Claude Code, Codex, OpenCode, and Pi Agent can branch a session, leaving the original intact; Antigravity, Cline, Copilot, Cursor, and Kimi have no fork, so their native resume continues the session where it stopped. *Handoff target* is what `catchup fork --into` can launch: Kimi's CLI cannot start interactive with a seed prompt, so it can be read and forked but not handed to.

`send` and `ask` have a wider reach than the table: they deliver text to a pane, so the receiving agent can be any agent herdr recognizes, including ones catchup cannot read. Only the *source* pane has to be an agent on this list.

## How it works

**Which session.** catchup on its own selects the newest session in a directory. In herdr that is often the wrong one — two agents in one project is an ordinary afternoon, and recency cannot tell them apart. So the plugin reads `focused_pane_id` from the invocation context, asks `herdr agent get` for that pane's agent and session id, and pins every catchup call with `--id`. When herdr has no session for the pane (an unrecognized agent, a plain shell), it falls back to selecting by directory.

**Where it runs.** `fork` launches an agent CLI interactively and the menus need a keyboard, so every action runs catchup inside a real pane (`herdr plugin pane open --cwd <project>`), never headless. Errors — no sessions here, missing binary, handing an agent its own session — print in that pane and wait for Enter. They can't vanish unread.

**How a transcript travels.** `send` and `ask` write the transcript to a file under the plugin's state directory and prompt the other agent with its path. `herdr agent prompt` types into a live TUI; tens of KB of pasted transcript is slow at best and truncated at worst, so only the path is typed. The prompt names where the work came from and says the file is a record, not instructions — another model's output should not arrive as a command.

No pane at all? The failure happened before the pane existed. It's in `herdr plugin log list --plugin wilbeibi.catchup`.

Needs herdr 0.7.0 or newer, on Linux or macOS.

## Limits and non-goals

- **Not a memory system.** It moves one session, once. No merged histories, no long-term store, no index across projects.
- **Conversation only.** Tool calls, command output, and reasoning traces are stripped before the transcript reaches the next agent.
- **Read-only except `fork`**, which launches an agent CLI.
- **A handoff is a transcript, not native state.** Cross-agent `fork --into` seeds the new agent with the conversation; only same-agent fork keeps the agent's own session state.
- **Pane-scoped.** The session comes from the focused pane, and the project directory from that pane's cwd. A pane sitting somewhere with no agent and no sessions finds nothing, and a session started elsewhere isn't reachable from here.
- **One round, not a debate.** `ask` delivers a review request and stops. It does not wait for the answer, feed it back, or run rounds — that is an orchestrator, and herdr is already the layer that owns panes and agent lifecycle.
- **No arguments yet.** herdr plugin actions take no parameters, so session search (`catchup -q`) and one-key-per-target handoff aren't wired up.
- **Linux and macOS only**, herdr 0.7.0+.

## Alternatives

These solve nearby problems, and some of them pair well with this plugin rather than replacing it.

| Instead of | What that gives you | Where this differs |
|---|---|---|
| `herdr agent read`, `tmux capture-pane` | The pane's visible scrollback, live | Scrollback is truncated, interleaved with tool output, and isn't something another agent can resume from. catchup reads the agent's own session file. |
| A hand-written `HANDOFF.md` | Whatever you remembered to write down | Nothing to maintain. The transcript already exists on disk; catchup renders it on demand. |
| `claude --resume`, `codex fork` | Native resume with full session state | Same agent only. `fork --into` is the part that crosses agents. |
| [herdr-session-parker](https://github.com/iviaxpow3r/herdr-session-parker), [seshagy](https://github.com/lmilojevicc/seshagy) | Parking, discovering, and relaunching agent sessions and panes | Those manage where sessions live and how you get back to them. This one moves the conversation itself from one agent to another. |
| The [catchup](https://github.com/wilbeibi/catchup) CLI on its own | Everything here, typed by hand, anywhere | The plugin supplies the one argument that's tedious in a multi-pane setup: which project the pane you're looking at is in. |

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
