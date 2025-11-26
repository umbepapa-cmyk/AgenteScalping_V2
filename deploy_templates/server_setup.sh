#!/usr/bin/env bash
# Server-side setup script (Linux) to unzip, install, and start the docker-compose stack
# Usage on server after uploading and extracting the package:
#   chmod +x server_setup.sh
#   sudo ./server_setup.sh

set -euo pipefail
ROOT_DIR="$(pwd)"
ZIP="../AgenteScalping_deploy.zip"
if [ -f "$ZIP" ]; then
  echo "Extracting $ZIP to $ROOT_DIR"
  unzip -o "$ZIP" -d "$ROOT_DIR"
fi
# Ensure .env exists
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    echo "No .env found — copying .env.example to .env. Edit .env with real secrets and set permissions."
    cp .env.example .env
    chmod 600 .env
    echo "Please edit .env now and re-run this script if you need to add secrets."
    exit 0
  else
    echo "No .env or .env.example found. Create .env with credentials and re-run."
    exit 1
  fi
fi
# If Docker is installed, use docker-compose
if command -v docker >/dev/null 2>&1 && command -v docker-compose >/dev/null 2>&1; then
  echo "Starting docker-compose stack"
  docker-compose up -d --build
  exit 0
fi
# Fallback: create virtualenv and run the agent directly
if command -v python3 >/dev/null 2>&1; then
  python3 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  echo "To run the agent interactively use: source .venv/bin/activate && python agente_analitico.py --env-file .env"
  exit 0
fi

echo "No Docker or python3 found. Install one of these and re-run the script."