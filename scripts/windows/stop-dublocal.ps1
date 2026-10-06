$ErrorActionPreference = "Stop"

$Processes = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*dublocal.launcher_runtime*" }

foreach ($Process in $Processes) {
    Stop-Process -Id $Process.ProcessId -Force -ErrorAction SilentlyContinue
}

Add-Type -AssemblyName PresentationFramework
[void][System.Windows.MessageBox]::Show(
    "Stopped $($Processes.Count) DubLocal instance(s).",
    "Stop DubLocal"
)
