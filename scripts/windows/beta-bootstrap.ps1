[CmdletBinding()]
param(
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"

$PackageRoot = Split-Path -Parent $PSCommandPath
$BuildInfo = Join-Path $PackageRoot "build-info.ps1"
if (-not (Test-Path -LiteralPath $BuildInfo)) {
    throw "DubLocal package metadata is missing: $BuildInfo"
}
. $BuildInfo

$RepositoryUrl = "https://github.com/ArrowSK/dublocal.git"
$ExpectedBranch = "main"
$AppHome = Join-Path $env:LOCALAPPDATA "DubLocal"
$SourceRoot = Join-Path $AppHome "app"
$VenvRoot = Join-Path $SourceRoot ".venv"
$Python = Join-Path $VenvRoot "Scripts\python.exe"
$LogDirectory = Join-Path $AppHome "logs"
$LogFile = Join-Path $LogDirectory "dublocal.log"
$ErrorLogFile = Join-Path $LogDirectory "dublocal.error.log"
$Url = "http://127.0.0.1:7861"
$SetupMarker = Join-Path $AppHome "bootstrap-revision"

New-Item -ItemType Directory -Force -Path $AppHome, $LogDirectory | Out-Null

function Show-Failure([string]$Message) {
    Add-Type -AssemblyName PresentationFramework
    [void][System.Windows.MessageBox]::Show(
        "$Message`n`nNo finished DubLocal outputs or models were changed.`n`nSetup log: $LogFile",
        "DubLocal Beta",
        "OK",
        "Error"
    )
    throw $Message
}

function Test-Ready {
    try {
        Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri "$Url/" | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Require-Command([string]$Name, [string]$Message) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Show-Failure $Message
    }
}

function Find-Python {
    Require-Command "py.exe" "Python 3.11–3.13 is required. Install it from python.org, then open DubLocal again."
    foreach ($Version in @("3.13", "3.12", "3.11")) {
        & py.exe "-$Version" -c "import sys; raise SystemExit(0 if (3, 11) <= sys.version_info < (3, 14) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @("py.exe", "-$Version")
        }
    }
    Show-Failure "DubLocal needs Python 3.11, 3.12, or 3.13. Install a supported Python version, then open DubLocal again."
}

function Invoke-Git([string[]]$Arguments) {
    $result = & git @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ($result | Out-String)
    }
    return ($result | Out-String).Trim()
}

function Ensure-Checkout {
    Require-Command "git.exe" "Git is required for DubLocal's managed installation and safe updater. Install Git for Windows, then open DubLocal again."
    if (-not (Test-Path -LiteralPath (Join-Path $SourceRoot ".git"))) {
        if (Test-Path -LiteralPath $SourceRoot) {
            Show-Failure "The managed DubLocal folder already exists but is not a Git checkout: $SourceRoot"
        }
        & git clone --branch $ExpectedBranch --single-branch $RepositoryUrl $SourceRoot
        if ($LASTEXITCODE -ne 0) {
            Show-Failure "DubLocal could not download its official GitHub repository. Check your internet connection and try again."
        }
        if ($DubLocalBuildSha) {
            & git -C $SourceRoot cat-file -e "$DubLocalBuildSha^{commit}" 2>$null
            if ($LASTEXITCODE -eq 0) {
                & git -C $SourceRoot reset --hard $DubLocalBuildSha
                if ($LASTEXITCODE -ne 0) {
                    Show-Failure "DubLocal could not select the packaged beta revision."
                }
            } else {
                Show-Failure "The packaged beta revision is not available on the official main branch."
            }
        }
    }

    $origin = Invoke-Git @("-C", $SourceRoot, "remote", "get-url", "origin")
    $branch = Invoke-Git @("-C", $SourceRoot, "branch", "--show-current")
    if ($origin -notin @($RepositoryUrl, "https://github.com/ArrowSK/dublocal")) {
        Show-Failure "The managed DubLocal checkout points to an unexpected Git remote. DubLocal will not overwrite it."
    }
    if ($branch -ne $ExpectedBranch) {
        Show-Failure "The managed DubLocal checkout is on '$branch', not '$ExpectedBranch'. DubLocal will not rewrite another branch."
    }
}

function Ensure-Environment {
    $currentRevision = Invoke-Git @("-C", $SourceRoot, "rev-parse", "HEAD")
    $installedRevision = if (Test-Path -LiteralPath $SetupMarker) { Get-Content -Raw $SetupMarker } else { "" }
    if ((Test-Path -LiteralPath $Python) -and ($installedRevision.Trim() -eq $currentRevision)) {
        return
    }

    $basePython = Find-Python
    if (-not (Test-Path -LiteralPath $Python)) {
        & $basePython[0] $basePython[1] -m venv $VenvRoot
        if ($LASTEXITCODE -ne 0) {
            Show-Failure "DubLocal could not create its private Python environment."
        }
        & $Python -m pip install --disable-pip-version-check --upgrade pip
        if ($LASTEXITCODE -ne 0) {
            Show-Failure "DubLocal could not prepare pip in its private environment."
        }
    }
    & $Python -m pip install --disable-pip-version-check -e $SourceRoot
    if ($LASTEXITCODE -ne 0) {
        Show-Failure "DubLocal could not install its application dependencies."
    }
    Set-Content -NoNewline -Path $SetupMarker -Value $currentRevision
}

function Stop-DubLocalProcess {
    Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
        Where-Object { $_.CommandLine -like "*dublocal.launcher_runtime*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}

try {
    if ((Test-Ready) -and (-not $ForceRestart)) {
        Start-Process $Url
        exit 0
    }
    if ($ForceRestart) {
        Stop-DubLocalProcess
        Start-Sleep -Seconds 1
    }

    Ensure-Checkout
    Ensure-Environment
    if (-not (Get-Command "ffmpeg.exe" -ErrorAction SilentlyContinue) -or -not (Get-Command "ffprobe.exe" -ErrorAction SilentlyContinue)) {
        Add-Type -AssemblyName PresentationFramework
        [void][System.Windows.MessageBox]::Show(
            "FFmpeg was not found. DubLocal will open, but normal media processing needs FFmpeg. Install FFmpeg and reopen the app.",
            "DubLocal Beta"
        )
    }

    $env:DUBLOCAL_BETA_BOOTSTRAP = $PSCommandPath
    $env:DUBLOCAL_INBROWSER = "0"
    $env:DUBLOCAL_PORT = "7861"
    Start-Process -FilePath $Python -ArgumentList "-m", "dublocal.launcher_runtime" -WorkingDirectory $SourceRoot -WindowStyle Hidden -RedirectStandardOutput $LogFile -RedirectStandardError $ErrorLogFile
    for ($Attempt = 0; $Attempt -lt 120; $Attempt += 1) {
        if (Test-Ready) {
            Start-Process $Url
            exit 0
        }
        Start-Sleep -Milliseconds 500
    }
    Show-Failure "DubLocal did not become ready. Review the launcher logs and try again."
} catch {
    Show-Failure $_.Exception.Message
}
