ifeq ($(OS),Windows_NT)
    SHELL := powershell.exe
endif

.SHELLFLAGS := -NoProfile -ExecutionPolicy Bypass -Command
usb_letter := $(shell (Get-Volume | Where-Object { $$_.DriveType -eq "Removable" -and $$_.Size -gt 1GB }).DriveLetter)
VENTOY ?= $(shell (Get-Volume -FileSystemLabel Ventoy -ErrorAction SilentlyContinue).DriveLetter)

.PHONY: all copy wim arch alpine freebsd netbsd nixos

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
	@$$ErrorActionPreference = "Stop"; $$j = Invoke-RestMethod "https://mirror.nju.edu.cn/.mirrorz/iso.json"; $$u = ($$j | Where-Object { $$_.distro -eq "$(DISTRO)" } | ForEach-Object { $$_.urls } | Where-Object { $$_.name -like "$(ISO_MATCH)" } | Select-Object -First 1).url; if (-not $$u) { throw "No $(DISTRO) ISO matching $(ISO_MATCH)" }; $$name = Split-Path $$u -Leaf; $$path = Join-Path $$env:TEMP $$name; aria2c -d "$$env:TEMP" -o $$name "https://mirror.nju.edu.cn$$u" --allow-overwrite=true; if ($$name -like "*.xz") { xz -d $$path; $$name = $$name -replace "\.xz$$", ""; $$path = Join-Path $$env:TEMP $$name }; Copy-Item $$path "$(VENTOY):\$$name" -Force; Remove-Item $$path, "$$path.aria2" -ErrorAction SilentlyContinue; Write-Host "$(DISTRO) ISO copied to $(VENTOY):\$$name"
