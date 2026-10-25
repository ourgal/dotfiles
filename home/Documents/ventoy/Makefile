ifeq ($(OS),Windows_NT)
    SHELL := powershell.exe
endif

.SHELLFLAGS := -NoProfile -ExecutionPolicy Bypass -Command
usb_letter := $(shell (Get-Volume | Where-Object { $$_.DriveType -eq "Removable" -and $$_.Size -gt 1GB }).DriveLetter)
all:
	@robocopy src "$(usb_letter):" /E; if ($$LASTEXITCODE -lt 8) { exit 0 } else { exit $$LASTEXITCODE }
