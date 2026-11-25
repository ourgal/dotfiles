#!/usr/bin/env bash
# Hermes shell hook: on_session_end. Payload arrives on stdin.
cat >/dev/null
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
  notify-send "Hermes" "Task finished" 2>/dev/null || true
fi
printf '{}\n'
