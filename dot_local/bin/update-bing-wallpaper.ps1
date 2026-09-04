$ErrorActionPreference = "Stop"

$apiUrl = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1"
try {
    $response = Invoke-RestMethod -Uri $apiUrl -Method Get -TimeoutSec 15
    if ($response.images -and $response.images[0].url) {
        $imageUrl = "https://www.bing.com" + $response.images[0].url
        $wallpaperDir = Join-Path $env:USERPROFILE "Pictures\BingWallpapers"
        if (-not (Test-Path $wallpaperDir)) {
            New-Item -ItemType Directory -Path $wallpaperDir -Force | Out-Null
        }
        $ext = [System.IO.Path]::GetExtension($imageUrl)
        if ([string]::IsNullOrEmpty($ext)) { $ext = ".jpg" }
        $fileName = "bing_" + (Get-Date -Format "yyyyMMdd") + $ext
        $targetFile = Join-Path $wallpaperDir $fileName

        Invoke-WebRequest -Uri $imageUrl -OutFile $targetFile -TimeoutSec 30 -UseBasicParsing

        if (Test-Path $targetFile) {
            $code = @"
using System;
using System.Runtime.InteropServices;
public class WallpaperSetter {
    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni);
}
"@
            Add-Type -TypeDefinition $code -ErrorAction SilentlyContinue
            [WallpaperSetter]::SystemParametersInfo(20, 0, $targetFile, 3)
            Write-Output "Updated wallpaper: $imageUrl"
        }
    } else {
        Write-Warning "Bing API returned no images."
    }
} catch {
    Write-Warning "Failed to update wallpaper: $_"
    exit 1
}