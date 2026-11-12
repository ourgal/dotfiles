[CmdletBinding()]
param (
    [Parameter(Mandatory)] [string] $Torrent,
    [Parameter(Mandatory)] [string] $Ventoy,
    [string] $Iso,
    [string] $Match = "*.iso"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($Iso) {
    $dest = "${Ventoy}:\$Iso"
    if (Test-Path $dest) {
        Write-Host "$Iso already on ${Ventoy}:, skipping"
        exit 0
    }
}

$dir = Join-Path $env:TEMP ([IO.Path]::GetFileNameWithoutExtension($Torrent))
New-Item -ItemType Directory -Force -Path $dir | Out-Null
aria2c --dir="$dir" --seed-time=0 --follow-torrent=mem "$Torrent"
if ($LASTEXITCODE -ne 0) { throw "aria2c failed with exit code $LASTEXITCODE" }

$iso = Get-ChildItem $dir -Recurse -File -Filter $Match |
    Sort-Object Length -Descending |
    Select-Object -First 1
if (-not $iso) { throw "No file matching $Match found in $dir" }

$dest = "${Ventoy}:\$($iso.Name)"
Copy-Item $iso.FullName $dest -Force
Remove-Item $dir -Recurse -Force
Write-Host "$($iso.Name) copied to $dest"
