# Server-side setup script (Windows PowerShell) to extract, install and run
# Usage: Run PowerShell as admin and execute ./server_setup.ps1 from package root
param(
    [string]$ZipPath = "..\AgenteScalping_deploy.zip"
)
if (Test-Path $ZipPath) {
    Write-Host "Extracting $ZipPath"
    Expand-Archive -Path $ZipPath -DestinationPath . -Force
}
if (-not (Test-Path .env)) {
    if (Test-Path .env.example) {
        Copy-Item .env.example .env
        Write-Host "Copied .env.example -> .env. Edit .env and run script again to continue." -ForegroundColor Yellow
        return
    } else {
        Write-Host "No .env or .env.example found. Create .env with credentials and re-run." -ForegroundColor Red
        return
    }
}
# If Docker Desktop is installed and docker-compose available
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host "Starting docker-compose (Windows)"
    docker-compose up -d --build
    return
}
# Fallback: create venv
if (Get-Command python -ErrorAction SilentlyContinue) {
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    Write-Host "Virtualenv created and dependencies installed. Run the agent with:`n.\.venv\Scripts\Activate.ps1`n`python agente_analitico.py --env-file .env`" -ForegroundColor Green
    return
}
Write-Host "No Docker or Python found on PATH. Install Docker Desktop or Python3 and re-run." -ForegroundColor Red
