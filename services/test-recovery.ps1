$ErrorActionPreference = 'Stop'
function Get-LeafChild([int]$RootPid) {
    $current = $RootPid
    while ($true) {
        $child = Get-CimInstance Win32_Process -Filter "ParentProcessId=$current" | Select-Object -First 1
        if (-not $child) { return $current }
        $current = [int]$child.ProcessId
    }
}

$serviceWrappers = Get-Process -Name 'EZVIZDashboard','EZVIZMotion' -ErrorAction Stop
$before = @{}
foreach ($wrapper in $serviceWrappers) {
    $leaf = Get-LeafChild $wrapper.Id
    if ($leaf -eq $wrapper.Id) { throw "No managed process found for $($wrapper.ProcessName)." }
    $before[$wrapper.ProcessName] = $leaf
    Stop-Process -Id $leaf -Force
}
Start-Sleep -Seconds 8
$lines = @("Recovery test: $(Get-Date -Format o)")
foreach ($name in $before.Keys) {
    $wrapper = Get-Process -Name $name -ErrorAction Stop
    $newPid = Get-LeafChild $wrapper.Id
    $restarted = $newPid -ne $wrapper.Id -and $newPid -ne $before[$name]
    $lines += "$name old_pid=$($before[$name]) new_pid=$newPid restarted=$restarted"
}
$lines | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'recovery-test.txt') -Encoding UTF8
