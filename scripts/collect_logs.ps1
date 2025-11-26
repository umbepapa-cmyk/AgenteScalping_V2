<#
Collect logs from a remote server via scp/ssh. You must have key-based auth or passwordless scp configured.

Usage:
  $env:REMOTE_HOST = '203.0.113.12'
  $env:REMOTE_USER = 'deploy'
  .\collect_logs.ps1

This will attempt to copy:
 - remote: /var/log/ibgateway/ibgateway.log (example)
 - remote: ~/AgenteScalping/trading_agent_server_test.log
 - remote: ~/AgenteScalping/logs/trade_log.csv

Adjust remote paths as needed.
#>

$remote = $env:REMOTE_HOST
$user = $env:REMOTE_USER
if (-not $remote -or -not $user) {
    Write-Error "Set REMOTE_HOST and REMOTE_USER environment variables before running."
    exit 1
}

$items = @("~/AgenteScalping/trading_agent_server_test.log", "~/AgenteScalping/logs/trade_log.csv")
foreach ($it in $items) {
    Write-Host "Copying $it from $user@$remote"
    $localName = Split-Path $it -Leaf
    $scpCmd = "scp $($user)@$($remote):$it ./$localName"
    Write-Host $scpCmd
    cmd /c $scpCmd
}

Write-Host "Logs copied to current folder. Inspect the files and upload here if you want me to analyze them."
