ifeq ($(OS),Windows_NT)
    SHELL := powershell.exe
endif

.SHELLFLAGS := -NoProfile -ExecutionPolicy Bypass -Command
usb_letter := $(shell (Get-Volume | Where-Object { $$_.DriveType -eq "Removable" -and $$_.Size -gt 1GB }).DriveLetter)
VENTOY ?= $(shell (Get-Volume -FileSystemLabel Ventoy -ErrorAction SilentlyContinue).DriveLetter)

.PHONY: all copy

all:
	@robocopy src "$(usb_letter):" /E; if ($$LASTEXITCODE -lt 8) { exit 0 } else { exit $$LASTEXITCODE }

copy:
	@if (-not "$(VENTOY)") { throw "Ventoy flash disk not found; pass VENTOY=<letter>, e.g. make copy VENTOY=G" }
	@robocopy src/ventoy "$(VENTOY):\ventoy" /E; if ($$LASTEXITCODE -ge 8) { exit $$LASTEXITCODE }
	@robocopy src/config "$(VENTOY):\config" /E; if ($$LASTEXITCODE -ge 8) { exit $$LASTEXITCODE }
	@Write-Host "Ventoy configs copied to $(VENTOY):"
