all:
	chezmoi apply

config:
	chezmoi apply -- ~/.config/chezmoi/chezmoi.toml

hermes-tui:
	hermes --tui --continue chezmoi

geminicommit:
	gmc -ap
