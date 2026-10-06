[CmdletBinding()]
param(
    [string]$Version,
    [string]$BuildSha
)

$ErrorActionPreference = "Stop"
$RepositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $RepositoryRoot

if (-not $Version) {
    $Version = (Select-String -Path (Join-Path $RepositoryRoot "pyproject.toml") -Pattern '^version = "(.+)"$').Matches[0].Groups[1].Value
}
if (-not $BuildSha) {
    $BuildSha = (& git rev-parse HEAD).Trim()
}
if ($BuildSha -notmatch '^[0-9a-f]{7,40}$') {
    throw "Invalid build SHA: $BuildSha"
}

$BuildRoot = Join-Path $RepositoryRoot "build\windows-beta"
$Stage = Join-Path $BuildRoot "stage"
$BootstrapStage = Join-Path $Stage "bootstrap"
$Dist = Join-Path $RepositoryRoot "dist"
$Installer = Join-Path $Dist "DubLocal-$Version-Windows-Setup-unsigned.exe"

Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $BuildRoot
New-Item -ItemType Directory -Force -Path $BootstrapStage, $Dist | Out-Null
Remove-Item -Force -ErrorAction SilentlyContinue $Installer, "$Installer.sha256"

Copy-Item (Join-Path $PSScriptRoot "DubLocal.cmd") (Join-Path $Stage "DubLocal.cmd")
Copy-Item (Join-Path $PSScriptRoot "Stop-DubLocal.cmd") (Join-Path $Stage "Stop-DubLocal.cmd")
Copy-Item (Join-Path $PSScriptRoot "beta-bootstrap.ps1") (Join-Path $BootstrapStage "beta-bootstrap.ps1")
Copy-Item (Join-Path $PSScriptRoot "stop-dublocal.ps1") (Join-Path $BootstrapStage "stop-dublocal.ps1")
@"
`$DubLocalBetaVersion = '$Version'
`$DubLocalBuildSha = '$BuildSha'
"@ | Set-Content -NoNewline -Encoding utf8 (Join-Path $BootstrapStage "build-info.ps1")

$Iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $Iscc) {
    $candidate = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
    if (Test-Path -LiteralPath $candidate) {
        $Iscc = Get-Item $candidate
    }
}
if (-not $Iscc) {
    throw "Inno Setup 6 is required to build the Windows installer."
}

$IsccPath = if ($Iscc.PSObject.Properties.Name -contains "Path") { $Iscc.Path } else { $Iscc.FullName }
& $IsccPath "/DAppVersion=$Version" "/DSourceRoot=$Stage" "/DRepoRoot=$RepositoryRoot" (Join-Path $RepositoryRoot "packaging\windows\DubLocal.iss")
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Installer)) {
    throw "The DubLocal Windows installer was not created."
}

(Get-FileHash -Algorithm SHA256 $Installer).Hash.ToLowerInvariant() + "  " + (Split-Path -Leaf $Installer) |
    Set-Content -NoNewline -Encoding ascii "$Installer.sha256"
Write-Output "Built unsigned Windows beta package: $Installer"
