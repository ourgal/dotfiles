all:
	chezmoi apply

config:
	mkdir -p ~/.config/chezmoi
	chezmoi apply -- ~/.config/chezmoi/chezmoi.toml

ssh-keys:
	chezmoi apply -- ~/.ssh/id_ed25519 ~/.ssh/id_ed25519.pub

hermes-tui:
	hermes --tui --continue chezmoi

geminicommit:
	gmc -ap
