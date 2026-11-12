[CmdletBinding()]
param (
    [Parameter(Mandatory)] [string] $Url,
    [Parameter(Mandatory)] [string] $Ventoy,
    [Parameter(Mandatory)] [string] $Iso
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$dest = "${Ventoy}:\$Iso"
if (Test-Path $dest) {
    Write-Host "$Iso already on ${Ventoy}:, skipping"
    exit 0
}

$tmp = Join-Path $env:TEMP $Iso
aria2c -d $env:TEMP -o $Iso $Url --allow-overwrite=true
if ($LASTEXITCODE -ne 0) { throw "aria2c failed with exit code $LASTEXITCODE" }
Copy-Item $tmp $dest -Force
Remove-Item $tmp, "$tmp.aria2" -ErrorAction SilentlyContinue
Write-Host "$Iso copied to $dest"
