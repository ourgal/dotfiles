# file-organizer: sort a download folder into format-based category folders.
#
#   make                                    preview the plan, move nothing
#   make apply                              move the files
#   make apply ARGS="-v --include-hidden"   pass flags through
#   make undo                               roll back the last apply
#   make ARGS="-s D:/Downloads -d D:/sorted"   target another folder

ARGS          ?=
.DEFAULT_GOAL := run

.PHONY: run apply undo test
run:
	uv run file-organizer $(ARGS)

apply:
	uv run file-organizer --apply $(ARGS)

undo:
	uv run file-organizer --undo $(ARGS)

test:
	uv run pytest
