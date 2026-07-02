#!/usr/bin/env bash
# herdr-catchup dispatch script. Two roles:
#   run.sh <mode>                     action entrypoint: herdr invokes this
#                                     headless (cwd = plugin dir). Opens the
#                                     matching [[panes]] entrypoint with the
#                                     focused pane's project directory.
#   run.sh --in-pane <mode> [target]  inside the plugin pane: project cwd,
#                                     real TTY. Runs catchup.
# catchup resolves sessions by exact cwd match and fork needs a foreground
# TTY, so catchup only ever runs in the pane, never in role 1.
set -euo pipefail

AGENTS=(codex claude opencode pi-agent)

# ---------- Role 2: inside the plugin pane ----------

hold_open() {
  printf '\n[press Enter to close]'
  read -r || true
}

in_pane() {
  local mode="${1:-}" target="${2:-}" rc=0

  if ! command -v catchup >/dev/null 2>&1; then
    echo "herdr-catchup: 'catchup' not found on PATH."
    echo "Install it with:"
    echo "  go install github.com/wilbeibi/catchup@latest"
    echo "and make sure \$(go env GOPATH)/bin is on your PATH."
    hold_open
    exit 1
  fi

  case "$mode" in
    summary)
      catchup --since-compact || rc=$?
      hold_open
      exit "$rc"
      ;;
    fork)
      catchup fork && exit 0
      ;;
    handoff)
      if [ -z "$target" ]; then
        echo "Hand off this session to:"
        PS3="agent> "
        select target in "${AGENTS[@]}"; do
          [ -n "${target:-}" ] && break
        done
        if [ -z "${target:-}" ]; then
          echo "herdr-catchup: cancelled"
          exit 0
        fi
      fi
      catchup fork --into "$target" && exit 0
      ;;
    *)
      echo "herdr-catchup: unknown mode '$mode'"
      hold_open
      exit 1
      ;;
  esac

  # fork/handoff failed (e.g. no sessions here) — keep the error readable
  hold_open
  exit 1
}

if [ "${1:-}" = "--in-pane" ]; then
  shift
  in_pane "$@"
fi

# ---------- Role 1: action entrypoint (headless, cwd = plugin dir) ----------

mode="${1:-}"
case "$mode" in
  summary|fork|handoff) ;;
  *)
    echo "usage: run.sh [--in-pane] summary|fork|handoff [target]" >&2
    exit 1
    ;;
esac

: "${HERDR_BIN_PATH:?herdr-catchup: HERDR_BIN_PATH not set}"
plugin_id="${HERDR_PLUGIN_ID:-wilbeibi.catchup}"

json_field() {
  printf '%s' "${HERDR_PLUGIN_CONTEXT_JSON:-}" \
    | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" \
    | head -n1
}

cwd="$(json_field focused_pane_cwd)"
if [ -z "$cwd" ]; then
  cwd="$(json_field workspace_cwd)"
fi
if [ -z "$cwd" ] || [ ! -d "$cwd" ]; then
  echo "herdr-catchup: could not resolve a project directory from the invocation context" >&2
  exit 1
fi

# summary is read-only: don't steal focus from the working agent pane.
# fork/handoff need the user's keyboard next, so focus the new pane.
focus_flag="--focus"
if [ "$mode" = "summary" ]; then
  focus_flag="--no-focus"
fi

exec "$HERDR_BIN_PATH" plugin pane open \
  --plugin "$plugin_id" \
  --entrypoint "$mode" \
  --placement split \
  --direction right \
  --cwd "$cwd" \
  "$focus_flag"
