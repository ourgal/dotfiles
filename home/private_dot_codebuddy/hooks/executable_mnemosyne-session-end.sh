#!/usr/bin/env bash
# CodeBuddy SessionEnd hook: save a compact summary of the session to Mnemosyne.
# Uses the global scope so it survives across projects and sessions. All failures
# are silent; a missing transcript or Mnemosyne never blocks session teardown.
set -u

if [ -z "${HERMES_HOME:-}" ]; then
  if [ -n "${LOCALAPPDATA:-}" ]; then
    HERMES_HOME="$LOCALAPPDATA/hermes"
  else
    HERMES_HOME="$HOME/.hermes"
  fi
fi
export HERMES_HOME
export MNEMOSYNE_DEFAULT_SCOPE=global

mnemosyne_bin="$HERMES_HOME/.mnemosyne/venv/Scripts/mnemosyne.exe"
if [ ! -x "$mnemosyne_bin" ]; then
  mnemosyne_bin="$(command -v mnemosyne 2>/dev/null || true)"
fi
[ -n "$mnemosyne_bin" ] || exit 0
command -v jq >/dev/null 2>&1 || exit 0

payload="$(cat 2>/dev/null || true)"
transcript="$(printf '%s' "$payload" | jq -r '.transcript_path // empty' 2>/dev/null || true)"
[ -n "$transcript" ] && [ -f "$transcript" ] || exit 0

cwd="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null || true)"
project="$(basename "${cwd:-$PWD}" 2>/dev/null || echo project)"

summary="$(jq -rs '
  [ .[]
    | select(.type == "message")
    | select((.role // "") == "user" or (.role // "") == "assistant")
    | { role: .role, text: ((.content // []) | map(.text // empty) | join(" ")) }
  ] as $messages
  | ([$messages[] | select(.role == "user") | .text] | last // "") as $user
  | ([$messages[] | select(.role == "assistant") | .text] | last // "") as $assistant
  | "User: " + ($user[0:300]) + "\nAssistant: " + ($assistant[0:300])
' "$transcript" 2>/dev/null || true)"
[ -n "$summary" ] || exit 0

"$mnemosyne_bin" store "CodeBuddy session in $project: $summary" codebuddy 0.5 \
  >/dev/null 2>&1 || true
