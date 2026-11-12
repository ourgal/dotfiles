ifeq ($(OS),Windows_NT)
    SHELL := powershell.exe
endif

.SHELLFLAGS := -NoProfile -ExecutionPolicy Bypass -Command
usb_letter := $(shell (Get-Volume | Where-Object { $$_.DriveType -eq "Removable" -and $$_.Size -gt 1GB }).DriveLetter)
VENTOY ?= $(shell (Get-Volume -FileSystemLabel Ventoy -ErrorAction SilentlyContinue).DriveLetter)
TINY10_TORRENT ?= https://archive.org/download/tiny-10-23-h2/tiny-10-23-h2_archive.torrent
TINY10_ISO ?= tiny10 x64 23h2.iso

.PHONY: all copy wim arch alpine freebsd netbsd nixos tiny10

all:
	@robocopy src "$(usb_letter):" /E; if ($$LASTEXITCODE -lt 8) { exit 0 } else { exit $$LASTEXITCODE }

copy:
	@if (-not "$(VENTOY)") { throw "Ventoy flash disk not found; pass VENTOY=<letter>, e.g. make copy VENTOY=G" }
	@robocopy src/ventoy "$(VENTOY):\ventoy" /E; if ($$LASTEXITCODE -ge 8) { exit $$LASTEXITCODE }
	@robocopy src/config "$(VENTOY):\config" /E; if ($$LASTEXITCODE -ge 8) { exit $$LASTEXITCODE }
	@Write-Host "Ventoy configs copied to $(VENTOY):"

wim:
	@if (-not "$(VENTOY)") { throw "Ventoy flash disk not found; pass VENTOY=<letter>, e.g. make wim VENTOY=G" }
	@aria2c -d "$$env:TEMP" -o Edgeless.iso --allow-overwrite=true https://legacy.edgeless.top/api/v2/info/iso_addr
	@7z e "$$env:TEMP/Edgeless.iso" sources/boot.wim "-o$$env:TEMP" -y
	@Move-Item "$$env:TEMP/boot.wim" "$(VENTOY):\Edgeless.vim" -Force
	@Remove-Item "$$env:TEMP/Edgeless.iso", "$$env:TEMP/Edgeless.iso.aria2" -ErrorAction SilentlyContinue
	@Write-Host "Edgeless wim copied to $(VENTOY):\Edgeless.vim"

arch: DISTRO := Arch Linux
arch: ISO_MATCH := *x86_64, CLI-only*
alpine: DISTRO := Alpine
alpine: ISO_MATCH := *x86_64, standard*
freebsd: DISTRO := FreeBSD
freebsd: ISO_MATCH := *amd64, bootonly iso.xz*
netbsd: DISTRO := NetBSD
netbsd: ISO_MATCH := *amd64, iso*
nixos: DISTRO := NixOS
nixos: ISO_MATCH := *x86_64, minimal iso*

arch alpine freebsd netbsd nixos:
	@if (-not "$(VENTOY)") { throw "Ventoy flash disk not found; pass VENTOY=<letter>, e.g. make $@ VENTOY=G" }
	@.\download-iso.ps1 -Distro "$(DISTRO)" -Match "$(ISO_MATCH)" -Ventoy "$(VENTOY)"

tiny10:
	@if (-not "$(VENTOY)") { throw "Ventoy flash disk not found; pass VENTOY=<letter>, e.g. make tiny10 VENTOY=G" }
	@.\download-torrent.ps1 -Torrent "$(TINY10_TORRENT)" -Ventoy "$(VENTOY)" -Iso "$(TINY10_ISO)"
