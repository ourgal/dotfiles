# anime-fetch: download a HEVC/AV1 release into the Seanime library.
#
#   make                              use the title copied to the clipboard
#   make ARGS="Mushoku Tensei III"    pass a title (and flags) to the script
#   make ARGS="Mushoku Tensei III --dry-run"

ARGS          ?=
.DEFAULT_GOAL := run

.PHONY: run test
run:
	uv run anime-fetch $(ARGS)

test:
	uv run pytest
