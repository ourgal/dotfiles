all:
	chezmoi apply

config:
	mkdir -p ~/.config/chezmoi
	chezmoi apply -- ~/.config/chezmoi/chezmoi.toml

hermes-tui:
	hermes --tui --continue chezmoi

geminicommit:
	gmc -ap
