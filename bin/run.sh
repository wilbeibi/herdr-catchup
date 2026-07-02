#!/usr/bin/env bash
# herdr-catchup dispatch script. Two roles:
#   run.sh <mode> [target]            action entrypoint: herdr invokes this
#                                     headless, cwd = plugin dir. Splits a
#                                     pane off the focused one and re-invokes
#                                     itself inside it.
#   run.sh --in-pane <mode> [target]  inside the split pane: project cwd,
#                                     real TTY. Runs catchup.
# catchup resolves sessions by exact cwd match and fork needs a foreground
# TTY, so catchup must only ever run in the pane, never in role 1.
set -euo pipefail

AGENTS=(codex claude opencode pi-agent)

in_pane() {
  local mode="${1:-}" target="${2:-}"

  if ! command -v catchup >/dev/null 2>&1; then
    echo "herdr-catchup: 'catchup' not found on PATH."
    echo "Install it with:"
    echo "  go install github.com/wilbeibi/catchup@latest"
    echo "and make sure \$(go env GOPATH)/bin is on your PATH."
    exit 1
  fi

  case "$mode" in
    summary)
      exec catchup --since-compact
      ;;
    fork)
      exec catchup fork
      ;;
    handoff)
      if [ -z "$target" ]; then
        echo "Hand off this session to:"
        PS3="agent> "
        select target in "${AGENTS[@]}"; do
          [ -n "${target:-}" ] && break
        done
      fi
      exec catchup fork --into "$target"
      ;;
    *)
      echo "herdr-catchup: unknown mode '$mode'" >&2
      exit 1
      ;;
  esac
}

if [ "${1:-}" = "--in-pane" ]; then
  shift
  in_pane "$@"
fi

mode="${1:-}"
target="${2:-}"
case "$mode" in
  summary|fork|handoff) ;;
  *)
    echo "usage: run.sh [--in-pane] summary|fork|handoff [target]" >&2
    exit 1
    ;;
esac

if [ -z "${HERDR_PANE_ID:-}" ]; then
  echo "herdr-catchup: no focused pane; focus a pane in your project first" >&2
  exit 0
fi
: "${HERDR_BIN_PATH:?herdr-catchup: HERDR_BIN_PATH not set}"

self="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run.sh"
case "$self" in
  *"'"*)
    echo "herdr-catchup: plugin path contains a single quote; unsupported" >&2
    exit 1
    ;;
esac

out="$("$HERDR_BIN_PATH" pane split "$HERDR_PANE_ID" --direction right --ratio 0.45)"
new_pane="$(printf '%s' "$out" \
  | sed -n 's/.*"pane_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
  | head -n1)"
if [ -z "$new_pane" ]; then
  echo "herdr-catchup: could not parse pane_id from pane split output: $out" >&2
  exit 1
fi

"$HERDR_BIN_PATH" pane rename "$new_pane" "catchup:$mode" || true

# This string is typed into the user's interactive shell (fish, zsh, or
# bash), so it must parse identically in all of them: one command, a
# single-quoted absolute path, whitelisted bare-word args only.
cmd="bash '$self' --in-pane $mode"
if [ -n "$target" ]; then
  cmd="$cmd $target"
fi
"$HERDR_BIN_PATH" pane run "$new_pane" "$cmd"
