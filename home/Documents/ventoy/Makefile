ifeq ($(OS),Windows_NT)
    SHELL := powershell.exe
endif

.SHELLFLAGS := -NoProfile -ExecutionPolicy Bypass -Command
usb_letter := $(shell (Get-Volume | Where-Object { $$_.DriveType -eq "Removable" -and $$_.Size -gt 1GB }).DriveLetter)
all:
	@rsync -avP src $(usb_letter):
