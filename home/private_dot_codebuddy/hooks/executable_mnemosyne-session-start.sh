#!/usr/bin/env bash
# CodeBuddy SessionStart hook: inject a few recalled Mnemosyne memories into
# context. CodeBuddy adds SessionStart stdout to the model context. Every
# failure is silent so a missing/unavailable Mnemosyne never blocks a session.
set -u

# Native Windows Hermes home is %LOCALAPPDATA%\hermes; elsewhere it is ~/.hermes.
if [ -z "${HERMES_HOME:-}" ]; then
  if [ -n "${LOCALAPPDATA:-}" ]; then
    HERMES_HOME="$LOCALAPPDATA/hermes"
  else
    HERMES_HOME="$HOME/.hermes"
  fi
fi
export HERMES_HOME
# Recall-first: admit vector candidates even when no query word matches, so a
# SessionStart always surfaces the closest stored memories instead of abstaining.
export MNEMOSYNE_LEXICAL_GATE_MIN=0

mnemosyne_bin="$HERMES_HOME/.mnemosyne/venv/Scripts/mnemosyne.exe"
if [ ! -x "$mnemosyne_bin" ]; then
  mnemosyne_bin="$(command -v mnemosyne 2>/dev/null || true)"
fi
[ -n "$mnemosyne_bin" ] || exit 0

# Hook JSON arrives on stdin; bias the query toward the current project.
cwd="$(jq -r '.cwd // empty' 2>/dev/null || true)"
project="$(basename "${cwd:-$PWD}" 2>/dev/null || echo project)"
query="user preferences decisions and context for $project"

results=""
if command -v jq >/dev/null 2>&1; then
  results="$("$mnemosyne_bin" recall "$query" 5 --json 2>/dev/null \
    | jq -r '.results[]? | "- " + (.content // "")' 2>/dev/null \
    | head -40 || true)"
else
  results="$("$mnemosyne_bin" recall "$query" 5 2>/dev/null | head -40 || true)"
fi

if [ -n "$results" ]; then
  printf '## Mnemosyne memories (recalled for %s)\n%s\n' "$project" "$results"
fi
