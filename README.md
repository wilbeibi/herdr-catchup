# herdr-catchup — cross-agent session handoff for herdr

herdr-catchup is a [herdr](https://herdr.dev) plugin for cross-agent coding-session handoff: from the pane an agent is working in, read that session, fork it, or hand it to a different agent — Claude Code to Codex, Cursor to OpenCode — without re-explaining the job.

```bash
herdr plugin install wilbeibi/herdr-catchup
```

### Pick up a session in the next pane over

An agent pane hits its limit. You press a key. A pane opens beside it running another agent that already knows the job.

This plugin is [catchup](https://github.com/wilbeibi/catchup) wired into herdr. catchup reads the local session history for Codex, Claude Code, Antigravity, Cline, Copilot CLI, Cursor, DeepSeek (dsh), Kimi, OpenCode, Pi Agent, and ZCode, and picks the work back up in the same agent or a different one. herdr knows which pane you are looking at, which agent is in it, and which session that agent holds — and that last one is something catchup cannot work out alone.

Six actions: read a session, fork it, hand it to a new agent, hand it to an agent already running in another pane, ask that agent to review it, or watch the multi-round threads those reviews can turn into.

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

Every action but `threads` works on the exact session the focused pane's agent holds, in that pane's project directory; `threads` is per-user, not per-session. `summary`, `send`, `ask`, and `threads` open as popups — session-modal, over the layout, gone when they close, so reading a session never rearranges your panes. `fork` and `handoff` open a real split to the right, because what they launch is an agent, and an agent has to be a pane herdr can see.

Each action is available from the pane, workspace, tab, and selection menus.

| Action | What it does |
|---|---|
| `wilbeibi.catchup.summary` | `catchup --since-compact` — that pane's session as clean Markdown. Leaves the running agent alone. |
| `wilbeibi.catchup.fork` | `catchup fork` — resumes the session natively in the new pane, e.g. `claude --resume <id> --fork-session`. Full state. |
| `wilbeibi.catchup.handoff` | Asks which agent (codex / claude / agy / cline / copilot / cursor / opencode / pi-agent), then `catchup fork --into <choice>` — a **new** agent, started with the transcript in hand. |
| `wilbeibi.catchup.send` | Lists the agents **already running** in this herdr session, renders the transcript to a file, and hands the one you pick its path. No new process; the agent in that pane picks the work up. |
| `wilbeibi.catchup.ask` | Same delivery, review framing: the other agent is asked to attack the assumptions of your latest turn, name a cheaper alternative, and say where it breaks. Two models arguing, one round. |

| `wilbeibi.catchup.threads` | The relay's thread list: every cross-agent conversation, what it is waiting on, and the command that unsticks it. See [Rounds](#rounds-the-relay). |

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

## Rounds: the relay

`ask` is one round and no acknowledgement: it types a path into another pane and stops. Two models that need to converge — a design and its critic, three rounds deep — need the hard part on top of that: knowing whether the other agent actually answered.

`bin/relay.py` is that layer. A thread is a directory of immutable numbered Markdown files plus a rebuildable index; delivery is `herdr agent prompt`; and the only acknowledgement is the peer running `relay.py reply <message-id>`. Python rather than more bash because a message store needs read-modify-write under a lock, an atomic rename, and JSON — and macOS ships no `flock(1)`.

```bash
# from inside a herdr pane, as an agent or by hand
python3 bin/relay.py ask --to reviewer --note-file plan.md --mode debate --max-rounds 4
python3 bin/relay.py status T-1cd39e19
python3 bin/relay.py list --format text     # what the `threads` action shows
python3 bin/relay.py cancel T-1cd39e19
```

The prompt the peer receives carries the whole protocol, so it works against an agent with nothing installed:

```
[HERDR-CATCHUP] thread=T-1cd39e19 message=T-1cd39e19-m001 mode=debate kind=request round=1/4
An agent in another pane sent you work. Read this file first, it is the whole task:
  ~/.local/state/herdr-catchup/threads/T-1cd39e19/001-request.md
When you are done, write your response as Markdown to a file and run exactly:
  python3 .../relay.py reply T-1cd39e19-m001 --file <your-response.md>
That command is the only acknowledgement that counts. Going idle is not one.
```

In `--mode debate` that reply *is* the next request — one artifact, two roles — and the thread closes itself when `--max-rounds` is spent or a reply lands after the deadline. In `--mode ask` the answer goes back to the asker as a closing notice and the thread ends there.

**Three facts, never collapsed.** *accepted*: herdr took the submission. *failed*: herdr refused it — durable, retryable with `relay.py retry`, and it burns no round. *answered*: the peer ran `reply`. Only the third is an acknowledgement. An idle agent is not one, and neither is a settled `agent prompt --wait`: that call tracks pane lifecycle, not a turn, so it cannot confirm any particular message was answered. The relay never passes `--wait` — it would also park the sender inside its own turn, leaving the reply nowhere to land.

**Identity is the pane.** Messages are addressed to the pane id resolved at send time, because live agent names get reassigned. If a different provider now occupies that pane, delivery and replies refuse (`peer_recycled`) rather than typing a stranger's work into it. A *session* change in the same pane — `/clear`, a restart, a fork to answer from — is recorded in the result and proceeds, since there is no rebind command and refusing would strand the thread.

**Watch it from a pane.** v1 ships no sweeper: a background sleeper started from an agent's shell inherits that agent's environment for as long as it lives, and a launchd unit is more machinery than this needs. The watchdog is you, one keypress away —

```
2 thread(s), 1 needing attention   ~/.local/state/herdr-catchup/threads

T-1cd39e19   open       debate  round 2/4  3 msg  12m ago
    awaiting_reply: T-1cd39e19-m003  (18m left)
      relay.py reply T-1cd39e19-m003 --file <f>
T-f8cdcbe1   done       ask     round 1/1  2 msg  2h ago
```

State lives under `$HERDR_CATCHUP_STATE`, else `$XDG_STATE_HOME/herdr-catchup`, else `~/.local/state/herdr-catchup`. Artifacts are never rewritten, so a finished debate is a readable record of who said what, in order.

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

Needs herdr 0.7.5 or newer, on Linux or macOS. 0.7.5 is where `agent prompt` landed, and `send` and `ask` are nothing without it.

## Limits and non-goals

- **Not a memory system.** It moves one session, once. No merged histories, no long-term store, no index across projects.
- **Conversation, plus dead ends.** A transcript bound for another agent carries the messages and the tool calls the source agent's own log marked failed. Successful tool calls, command output, and reasoning traces are stripped.
- **Read-only except `fork`**, which launches an agent CLI.
- **A handoff is a transcript, not native state.** Cross-agent `fork --into` seeds the new agent with the conversation; only same-agent fork keeps the agent's own session state.
- **Pane-scoped.** The session comes from the focused pane, and the project directory from that pane's cwd. A pane sitting somewhere with no agent and no sessions finds nothing, and a session started elsewhere isn't reachable from here.
- **`ask` is one round.** The action delivers a review request and stops. Rounds, deadlines, and acknowledgement are the relay's job, and you opt into them explicitly.
- **One unanswered request per thread.** Sending a correction while the peer is still working would put two live questions in one thread, and no answer ordering makes sense after that. `cancel` and open a new thread; `cancel` is thread-level, so the new thread carries no link back to the cancelled one.
- **Same machine.** A message is a local path typed into a local pane. `--machine` panes and remote agents are out of scope for v1.
- **The 30-minute default deadline is a guess.** Nothing has measured how long a real review round takes. A deadline never kills a turn — it only marks the request overdue and stops a late reply from opening another round.
- **No arguments yet.** herdr plugin actions take no parameters, so session search (`catchup -q`) isn't wired up, and a fixed handoff target has to come from `config.env` rather than the key you pressed.
- **Linux and macOS only**, herdr 0.7.5+.

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

python3 tests/test_relay.py    # the relay's failure matrix, against a scriptable fake herdr
```

The relay's tests are deliberately not a happy-path demo: two agents agreeing is the weakest evidence this code can produce. They cover refused delivery, retry, recycled panes, session drift, expired and late replies, forged callers, cancel, path traversal through `--to`/`--thread`, and concurrent writers.

## Ideas

- A key per target agent (`handoff-codex`, …), so a handoff is one press and no menu, and more than one target can have a key. `config.env`'s `handoff_target` covers the single-default case today; `bin/run.sh handoff <target>` already takes the argument, so each extra key is three lines of manifest.
- Session search, `catchup -q "topic"`, once actions can take arguments.
- Handing off work that isn't a local session. `catchup fork --into <agent> --from <file | - | url>` seeds an agent from a transcript, a pipe, or a URL — a pane could pick up a job that started on another machine.

## License

MIT
