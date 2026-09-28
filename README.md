# herdr-catchup — cross-agent session handoff for herdr

herdr-catchup is a [herdr](https://herdr.dev) plugin for cross-agent coding-session handoff: from the pane an agent is working in, read that session, fork it, or hand it to a different agent — Claude Code to Codex, Cursor to OpenCode — without re-explaining the job.

```bash
herdr plugin install wilbeibi/herdr-catchup
```

### Pick up a session in the next pane over

An agent pane hits its limit. You press a key. A pane opens beside it running another agent that already knows the job.

This plugin is [catchup](https://github.com/wilbeibi/catchup) wired into herdr. catchup reads the local session history for Codex, Claude Code, Antigravity, Cline, Copilot CLI, Cursor, DeepSeek (dsh), Kimi, OpenCode, Pi Agent, and ZCode, and picks the work back up in the same agent or a different one. herdr knows which pane you are looking at, which agent is in it, and which session that agent holds — and that last one is something catchup cannot work out alone.

Five actions: read a session, fork it, hand it to a new agent, hand it to an agent already running in another pane, or ask that agent to review it.

## Install

First the `catchup` binary — 1.0 or newer for the full `send`/`ask` transcript, since `--agent` and the failed tool calls it carries arrived there. Every action works on 0.9, minus those.

```bash
brew install wilbeibi/tap/catchup

# or a prebuilt binary, no Go needed
curl -fsSL https://catchup.pages.dev/install.sh | sh

# or from source
go install github.com/wilbeibi/catchup@latest   # then put $(go env GOPATH)/bin on your PATH
```

Then:

```bash
herdr plugin install wilbeibi/herdr-catchup
```

It is also listed in the [herdr plugin marketplace](https://herdr.dev/plugins/), which indexes public repos tagged `herdr-plugin`.

## Actions

Every action works on the exact session the focused pane's agent holds, in that pane's project directory. `summary`, `send`, and `ask` open as popups — session-modal, over the layout, gone when they close, so reading a session never rearranges your panes. `fork` and `handoff` open a real split to the right, because what they launch is an agent, and an agent has to be a pane herdr can see.

Each action is available from the pane, workspace, tab, and selection menus.

| Action | What it does |
|---|---|
| `wilbeibi.catchup.summary` | `catchup --since-compact` — that pane's session as clean Markdown. Leaves the running agent alone. |
| `wilbeibi.catchup.fork` | `catchup fork` — resumes the session natively in the new pane, e.g. `claude --resume <id> --fork-session`. Full state. |
| `wilbeibi.catchup.handoff` | Asks which agent (codex / claude / agy / cline / copilot / cursor / opencode / pi-agent), then `catchup fork --into <choice>` — a **new** agent, started with the transcript in hand. |
| `wilbeibi.catchup.send` | Lists the agents **already running** in this herdr session, renders the transcript to a file, and hands the one you pick its path. No new process; the agent in that pane picks the work up. |
| `wilbeibi.catchup.ask` | Same delivery, review framing: the other agent is asked to attack the assumptions of your latest turn, name a cheaper alternative, and say where it breaks. When it finishes, this pane's agent is prompted to read the review and say what it would change. Two models arguing, one round. |

`send` and `ask` are the two that only exist because of herdr: catchup can render any session, but only herdr knows which agents are alive right now and how to reach them.

### Configuration

Optional, and there is no file until you write one. herdr creates the directory; `herdr plugin info wilbeibi.catchup` prints its path.

```bash
# $HERDR_PLUGIN_CONFIG_DIR/config.env
handoff_target = codex     # skip the handoff menu, always hand off to this agent
placement = split          # tile summary/send/ask instead of popping them up
                           # (split | overlay | tab | zoomed; unset = popup)
worktree_fork = on         # on worktree.created, fork the origin session into it
```

`worktree_fork` is off by default: creating a worktree should not silently start an agent. Turned on, a new worktree opens with a split already running `catchup fork --dir <origin checkout>` — the session that motivated the branch, picked up in the tree made for it.

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
| DeepSeek (dsh) | ✓ | ✓ resume | — |
| ZCode | ✓ | — | — |

*Fork in place* uses each agent's own resume path. Claude Code, Codex, OpenCode, and Pi Agent can branch a session, leaving the original intact; Antigravity, Cline, Copilot, Cursor, DeepSeek, and Kimi have no fork, so their native resume continues the session where it stopped. ZCode is a desktop app with no CLI to resume from, so it can only be read. *Handoff target* is what `catchup fork --into` can launch: Kimi cannot start interactive with a seed prompt, ZCode has no CLI at all, and dsh takes its opening prompt from a per-install profile — those three can be read and (except ZCode) forked, but not handed to.

herdr does not recognize DeepSeek or ZCode as pane agents, so those two never get the `--id` pinning below; they fall back to the newest session in the pane's directory, which is right whenever nothing else is running there.

`send` and `ask` have a wider reach than the table: they deliver text to a pane, so the receiving agent can be any agent herdr recognizes, including ones catchup cannot read. Only the *source* pane has to be an agent on this list.

## How it works

**Which session.** catchup on its own selects the newest session in a directory. In herdr that is often the wrong one — two agents in one project is an ordinary afternoon, and recency cannot tell them apart. So the plugin reads `focused_pane_id` from the invocation context, asks `herdr agent get` for that pane's agent and session id, and pins every catchup call with `--id`. When herdr has no session for the pane (an unrecognized agent, a plain shell), it falls back to selecting by directory.

**Where it runs.** `fork` launches an agent CLI interactively and the menus need a keyboard, so every action runs catchup inside a pane (`herdr plugin pane open --cwd <project>`), never headless. What role 1 resolved reaches that pane through `--env`, per pane, rather than a file — two herdr sessions sharing one state directory would race, and pinning the wrong pane's session is the exact failure this plugin exists to prevent. Splits are pinned beside the originating pane with `--target-pane`, not beside whatever happens to be focused when they open; popups take no target, since herdr opens those against the active pane by definition. Errors — no sessions here, missing binary, handing an agent its own session — print in that pane and wait for Enter. They can't vanish unread. A non-zero exit is passed through rather than flattened, so when the agent `fork` launched is the thing that failed, its own status (signals as 128+signum) is what the pane reports.

**How a transcript travels.** `send` and `ask` write the transcript to a file under the plugin's state directory — rendered with `catchup --agent`, the format written for a model to read, failed tool calls included — and prompt the other agent with its path. `herdr agent prompt` types into a live TUI; tens of KB of pasted transcript is slow at best and truncated at worst, so only the path is typed. The prompt names where the work came from and says the file is a record, not instructions — another model's output should not arrive as a command.

No pane at all? The failure happened before the pane existed. It's in `herdr plugin log list --plugin wilbeibi.catchup`.

**How a review comes back.** When the reviewer finishes, the source pane's agent — once it is idle or done — gets one line telling it to read the review with `catchup <agent> --id <reviewer session> --agent --last 1` (or `--dir <reviewer cwd>` when herdr names no session) and say what it would change, as another model's opinion, not instructions. Nothing comes back when the reviewer was mid-turn when asked, or is an agent catchup cannot read. The line is typed the moment the source agent goes idle or done, so if you are typing in that pane just then, the two collide.

Needs herdr 0.9.0 or newer, on Linux or macOS. 0.9.0 is where `agent prompt --wait --until` landed, which `ask` needs to know the review has started.

## Limits and non-goals

- **Not a memory system.** It moves one session, once. No merged histories, no long-term store, no index across projects.
- **Conversation, plus dead ends.** A transcript bound for another agent carries the messages and the tool calls the source agent's own log marked failed. Successful tool calls, command output, and reasoning traces are stripped.
- **Read-only except `fork`**, which launches an agent CLI.
- **A handoff is a transcript, not native state.** Cross-agent `fork --into` seeds the new agent with the conversation; only same-agent fork keeps the agent's own session state.
- **Pane-scoped.** The session comes from the focused pane, and the project directory from that pane's cwd. A pane sitting somewhere with no agent and no sessions finds nothing, and a session started elsewhere isn't reachable from here.
- **One round, not a debate.** `ask` delivers a review request, and one reply comes back to the source pane once its agent is ready for input. No further rounds and no debate loop — that is an orchestrator, and herdr is already the layer that owns panes and agent lifecycle.
- **No arguments yet.** herdr plugin actions take no parameters, so session search (`catchup -q`) isn't wired up, and a fixed handoff target has to come from `config.env` rather than the key you pressed.
- **Linux and macOS only**, herdr 0.9.0+.

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

- A key per target agent (`handoff-codex`, …), so a handoff is one press and no menu, and more than one target can have a key. `config.env`'s `handoff_target` covers the single-default case today; `bin/run.sh handoff <target>` already takes the argument, so each extra key is three lines of manifest.
- Session search, `catchup -q "topic"`, once actions can take arguments.
- Handing off work that isn't a local session. `catchup fork --into <agent> --from <file | - | url>` seeds an agent from a transcript, a pipe, or a URL — a pane could pick up a job that started on another machine.

## License

MIT
