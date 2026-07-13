{{ $distro := "Arch Linux" -}}
{{ $like := "*x86_64, CLI-only*" -}}
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
function Get-UrlBasename {
  [CmdletBinding()]
  param (
      [Parameter(Mandatory)]
      [String]$url
  )
  ([uri] $url).Segments[-1]
}
function Get-IsoUrl {
  [CmdletBinding()]
  param (
      [Parameter(Mandatory)]
      [Object[]]$data,
      [Parameter(Mandatory)]
      [String]$distro,
      [Parameter(Mandatory)]
      [String]$like
  )
  foreach ($item in $data){
    if ($item.distro -eq $distro) {
      foreach ($url in $item.urls){
        if ($url.name -like $like) {
          return $url.url
        }
      }
    }
  }
  throw "Could not find any $distro iso"
}
$domain = "https://mirror.nju.edu.cn"
$json_url = "$domain/.mirrorz/iso.json"
$json_filename = Get-UrlBasename $json_url
Invoke-WebRequest -Uri $json_url -OutFile $json_filename

$iso_json = Get-Content -Raw $json_filename | ConvertFrom-Json

$path = Get-IsoUrl $iso_json "{{ $distro }}" "{{ $like }}"

aria2c "$domain/$path"

Remove-Item $json_filename
