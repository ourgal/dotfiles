[CmdletBinding()]
param (
    [Parameter(Mandatory)] [string] $Distro,
    [Parameter(Mandatory)] [string] $Match,
    [Parameter(Mandatory)] [string] $Ventoy
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$domain = "https://mirror.nju.edu.cn"
$record = Invoke-RestMethod "$domain/.mirrorz/iso.json" |
    Where-Object { $_.distro -eq $Distro } |
    ForEach-Object { $_.urls } |
    Where-Object { $_.name -like $Match } |
    Select-Object -First 1
if (-not $record) { throw "No $Distro ISO matching $Match" }

$urlName = Split-Path $record.url -Leaf
$diskName = $urlName -replace "\.xz$", ""
$dest = "${Ventoy}:\$diskName"
if (Test-Path $dest) {
    Write-Host "$diskName already on ${Ventoy}:, skipping"
    exit 0
}

$tmp = Join-Path $env:TEMP $urlName
aria2c -d $env:TEMP -o $urlName "$domain$($record.url)" --allow-overwrite=true
if ($LASTEXITCODE -ne 0) { throw "aria2c failed with exit code $LASTEXITCODE" }
if ($urlName -like "*.xz") {
    xz -d $tmp
    if ($LASTEXITCODE -ne 0) { throw "xz failed with exit code $LASTEXITCODE" }
    $tmp = Join-Path $env:TEMP $diskName
}

Copy-Item $tmp $dest -Force
Remove-Item $tmp, "$tmp.aria2" -ErrorAction SilentlyContinue
Write-Host "$Distro ISO copied to $dest"
