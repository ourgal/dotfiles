#!/usr/bin/env bash
# Hermes shell hook: on_session_end. Payload arrives on stdin.
cat >/dev/null
# notify-send uses the session bus, not DISPLAY. Headless hosts fail open via || true.
notify-send "Hermes" "Task finished" 2>/dev/null || true
if command -v paplay >/dev/null 2>&1 && command -v ffmpeg >/dev/null 2>&1; then
  ffmpeg -hide_banner -loglevel error \
    -f lavfi -i 'sine=frequency=784:duration=0.12' \
    -f lavfi -i 'sine=frequency=1047:duration=0.18' \
    -filter_complex '[0:a][1:a]concat=n=2:v=0:a=1[out]' \
    -map '[out]' -f wav - 2>/dev/null | paplay --volume=65536 2>/dev/null || true
fi
printf '{}\n'
