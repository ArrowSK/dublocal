[CmdletBinding()]
param(
    [switch]$Restart
)

$Bootstrap = Join-Path $PSScriptRoot "beta-bootstrap.ps1"
if (-not (Test-Path -LiteralPath $Bootstrap)) {
    throw "DubLocal's packaged Windows bootstrap is missing: $Bootstrap"
}

if ($Restart) {
    & $Bootstrap -ForceRestart
} else {
    & $Bootstrap
}
