all: config ssh-keys
	chezmoi apply

config:
	@if [ ! -f ~/.config/chezmoi/chezmoi.toml ]; then \
		mkdir -p ~/.config/chezmoi; \
		chezmoi apply -- ~/.config/chezmoi/chezmoi.toml; \
	fi

ssh-keys:
	@if [ ! -f ~/.ssh/id_ed25519 ] || [ ! -f ~/.ssh/id_ed25519.pub ]; then \
		chezmoi apply -- ~/.ssh/id_ed25519 ~/.ssh/id_ed25519.pub; \
	fi

hermes-tui:
	hermes --tui --continue chezmoi

geminicommit:
	gmc -ap
