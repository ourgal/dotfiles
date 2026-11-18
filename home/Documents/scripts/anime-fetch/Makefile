# anime-fetch: download a HEVC/AV1 release into the Seanime library.
#
#   make                              use the title copied to the clipboard
#   make ARGS="Mushoku Tensei III"    pass a title (and flags) to the script
#   make ARGS="Mushoku Tensei III --dry-run"
#   make ARGS="--all --dry-run"        sync every Watching + Releasing series

ARGS          ?=
.DEFAULT_GOAL := run

.PHONY: run test
run:
	uv run anime-fetch $(ARGS)

test:
	uv run pytest
