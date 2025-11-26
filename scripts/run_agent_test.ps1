<#
Run the trading agent test against a remote IB Gateway.

Usage:
  .\run_agent_test.ps1 -ServerIp 203.0.113.12 -Port 4002 -TestTrades 5 -TestDuration 300

This script activates the venv, starts the agent with --ib-host pointing to the server
and stores console output into `trading_agent_server_test.log`.
#>

param(
    [Parameter(Mandatory=$true)] [string]$ServerIp,
    [int]$Port = 4002,
    [int]$TestTrades = 5,
    [int]$TestDuration = 300
)

Write-Host "Run agent test against IB Gateway at $($ServerIp):$Port"

if (-not (Test-Path .\.venv\Scripts\Activate.ps1)) {
    Write-Error "Virtualenv not found. Create and install deps first: python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt"
    exit 1
}

Write-Host "Activating venv"
. .\.venv\Scripts\Activate.ps1

$logFile = "trading_agent_server_test.log"
Write-Host "Starting agent; logs -> $logFile"

$cmd = "python agente_analitico.py --ib-host $ServerIp --ib-port $Port --force-live --test-trades $TestTrades --test-duration $TestDuration --log-level DEBUG --log-file $logFile"
Write-Host $cmd

try {
  # Start the process natively in this PowerShell session
  $proc = Start-Process -FilePath python -ArgumentList 'agente_analitico.py','--ib-host',$ServerIp,'--ib-port',$Port,'--force-live','--test-trades',$TestTrades,'--test-duration',$TestDuration,'--log-level','DEBUG','--log-file',$logFile -NoNewWindow -PassThru -Wait
  exit $proc.ExitCode
} catch {
  Write-Error "Errore durante l'avvio dell'agente: $_"
}

Write-Host "Agent process finished. See $logFile and logs/trade_log.csv"
