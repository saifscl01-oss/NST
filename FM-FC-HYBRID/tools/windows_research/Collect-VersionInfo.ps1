<#
.SYNOPSIS
  Read-only: records Windows version-resource fields and SHA-256 for a game's key binaries.
.DESCRIPTION
  Uses only built-in cmdlets (Get-Item .VersionInfo, Get-FileHash). Writes ONE JSON file to -OutFile,
  which must be outside the installation directory. Never modifies the installation.
.EXAMPLE
  .\Collect-VersionInfo.ps1 -Root "D:\Games\FM26" -OutFile "C:\re\out\fm26-versioninfo.json"
#>
param(
  [Parameter(Mandatory)] [string] $Root,
  [Parameter(Mandatory)] [string] $OutFile,
  [string[]] $Names = @("fm.exe","game_plugin.dll","GameAssembly.dll","UnityPlayer.dll",
                        "FIFA22.exe","FIFA21.exe","FIFA20.exe","FIFA19.exe","FIFA18.exe","FIFA17.exe","FIFA16.exe","FIFA15.exe")
)
$ErrorActionPreference = "Stop"
$rootFull = (Resolve-Path $Root).Path
$outFull  = [System.IO.Path]::GetFullPath($OutFile)
if ($outFull.StartsWith($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "OutFile must be outside the installation directory ($rootFull)"
}
$results = @()
foreach ($n in $Names) {
  $f = Get-ChildItem -LiteralPath $rootFull -Filter $n -File -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $f) { continue }
  $vi = $f.VersionInfo
  $results += [ordered]@{
    file = $f.Name; size = $f.Length; last_write_utc = $f.LastWriteTimeUtc.ToString("o")
    sha256 = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower()
    file_version = $vi.FileVersion; product_version = $vi.ProductVersion; product_name = $vi.ProductName
    company_name = $vi.CompanyName; original_filename = $vi.OriginalFilename; file_description = $vi.FileDescription
  }
}
$doc = [ordered]@{ tool = "Collect-VersionInfo.ps1"; read_only = $true; root = $rootFull
                   collected_utc = (Get-Date).ToUniversalTime().ToString("o"); binaries = $results }
New-Item -ItemType Directory -Force -Path (Split-Path $outFull) | Out-Null
$doc | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 -LiteralPath $outFull
Write-Host "Wrote $outFull ($($results.Count) binaries)"
