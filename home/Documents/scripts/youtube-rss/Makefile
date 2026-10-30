# youtube-rss: convert a YouTube channel/user URL into an uploads RSS feed URL.
#
#   make                              use the URL from the system clipboard
#   make URL="https://www.youtube.com/@YouTube"
#   make URL="https://www.youtube.com/user/YouTube"
#   make URL="https://www.youtube.com/channel/UCBR8-60-B28hp2BmDPdntcQ"
#
# Override the interpreter if needed: make PYTHON=python3 URL="..."

PYTHON ?= python
URL ?=
URL_ARG = $(if $(strip $(URL)),"$(URL)")
.DEFAULT_GOAL := run

.PHONY: run test
run:
	@$(PYTHON) youtube_rss.py $(URL_ARG)

test:
	@$(PYTHON) -m unittest discover -s .
