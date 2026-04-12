#!/usr/bin/env bash
#
# macro-claude session monitor hook.
#
# Invoked by Claude Code via ~/.claude/settings.json hooks for events:
#   SessionStart, SessionEnd, UserPromptSubmit, PreToolUse, PostToolUse,
#   Stop, StopFailure.
#
# Writes a compact JSON file per session to $STATUS_DIR which the macropad
# plugin polls via FileSystemWatcher.
#
# Status file format:
#   {
#     "session_id":     "<uuid>",
#     "cwd":            "/abs/path",
#     "status":         "idle"|"working"|"waiting"|"error",
#     "last_event":     "Stop"|"UserPromptSubmit"|"Notification"|...,
#     "last_event_s":   <unix seconds>,
#     "heartbeat_s":    <unix seconds>,
#     "turn_started_s": <unix seconds>|null,
#     "idle_since_s":   <unix seconds>|null
#   }
#
# Final "thinking"/"stuck" resolution is done in the plugin based on
# heartbeat_s, CPU usage, and JSONL mtime — this script only records raw
# events so it never blocks Claude Code.

set -o errexit
set -o nounset
set -o pipefail

readonly STATUS_DIR="${HOME}/.claude/session-status"
mkdir -p -- "${STATUS_DIR}"

input="$(cat)"

session_id="$(jq --raw-output '.session_id // empty' <<<"${input}")"
event="$(jq --raw-output '.hook_event_name // empty' <<<"${input}")"
cwd="$(jq --raw-output '.cwd // empty' <<<"${input}")"
message="$(jq --raw-output '.message // empty' <<<"${input}")"

if [[ -z "${session_id}" || -z "${event}" ]]; then
  exit 0
fi

status_file="${STATUS_DIR}/${session_id}.json"
now_s="$(date +%s)"

# SessionEnd removes the status file — session no longer exists.
if [[ "${event}" == "SessionEnd" ]]; then
  # -f needed on macOS BSD rm (no --force long form)
  rm -f -- "${status_file}"
  exit 0
fi

status=""
case "${event}" in
  SessionStart | Stop)
    status="idle"
    ;;
  UserPromptSubmit | PreToolUse | PostToolUse)
    status="working"
    ;;
  Notification)
    # Claude Code fires Notification for two very different things:
    #
    #   1. "Claude needs your permission to use <tool>"
    #      "Claude is waiting for plan approval"
    #      — real blocking gates, we want the macropad to show
    #      Waiting so the user sees which session needs them.
    #
    #   2. "Claude is waiting for your input"
    #      — sent after a turn finishes. Semantically identical to
    #      Idle, the session is no longer blocked on itself; the
    #      user just has the turn back. Showing this as Waiting
    #      would flag every finished-turn session as "needs you"
    #      even though nothing is actually blocked.
    #
    # Distinguish by the message field: "waiting for your input"
    # is Idle, everything else (permission, approval, plan) is
    # Waiting. Match is case-insensitive and tolerates minor
    # wording drift between Claude Code versions.
    #
    # Lowercase via `tr` rather than `${message,,}` because the
    # latter is a Bash 4+ feature and /usr/bin/env bash on stock
    # macOS is still 3.2. Users without a Homebrew bash would
    # otherwise hit "bad substitution" and the hook would stop
    # updating status files entirely on every Notification event.
    message_lc="$(printf '%s' "${message}" | tr '[:upper:]' '[:lower:]')"
    case "${message_lc}" in
      *"waiting for your input"*)
        # Same semantic as Stop — turn done, user has control.
        status="idle"
        event="Stop"
        ;;
      *)
        status="waiting"
        ;;
    esac
    ;;
  StopFailure)
    status="error"
    ;;
  *)
    # Unknown event: nothing to record.
    exit 0
    ;;
esac

existing="{}"
# -s checks that the file is non-empty. An empty file can happen
# when a previous invocation of this script was killed between
# `> ${status_file}` (which truncates) and the jq write — once the
# file is zero-byte, `cat` returns an empty string, jq rejects it
# as invalid JSON, set -o errexit bails, and the file stays empty
# forever. Guard against that loop here.
if [[ -s "${status_file}" ]]; then
  existing="$(cat -- "${status_file}")"
fi

jq \
  --arg sid "${session_id}" \
  --arg cwd "${cwd}" \
  --arg status "${status}" \
  --arg event "${event}" \
  --argjson now "${now_s}" \
  '
    . as $existing
    | {
        session_id:     $sid,
        cwd:            $cwd,
        status:         $status,
        last_event:     $event,
        last_event_s:   $now,
        heartbeat_s:    $now,
        turn_started_s: (
          if $event == "UserPromptSubmit" then $now
          elif ($existing.turn_started_s // null) != null and $status == "working"
            then $existing.turn_started_s
          else null
          end
        ),
        idle_since_s:   (if $status == "idle" then $now else null end)
      }
  ' <<<"${existing}" >"${status_file}.tmp.$$" \
  && mv "${status_file}.tmp.$$" "${status_file}"
