**Upload via FileZilla — Istruzioni rapide**

1) Genera il pacchetto ZIP (PowerShell, esegui dalla root del progetto):

```powershell
.\.venv\Scripts\Activate.ps1
.\package_for_filezilla.ps1 -OutZip ..\AgenteScalping_deploy.zip
```

2) Apri FileZilla e connettiti al server SFTP/FTP.
   - Modalità: SFTP (consigliata) o FTP implicito
   - Host: <178.156.221.35>
   - User: <root>
   - Pass: <Ebbenes1!>
   - Porta: <22>
   - Usa modalità passiva se il server lo richiede.

3) Trasferisci `AgenteScalping_deploy.zip` nella directory di destinazione del server.

4) Sul server estrai il contenuto e installa dipendenze (suggerimenti):

```powershell
# su Windows server (PowerShell)
Expand-Archive -Path AgenteScalping_deploy.zip -DestinationPath .\AgenteScalping
cd .\AgenteScalping
.\.venv\Scripts\Activate.ps1  # o crea un nuovo venv
pip install -r requirements.txt
```

```bash
# su Linux server
unzip AgenteScalping_deploy.zip -d AgenteScalping
cd AgenteScalping
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

5) Configurazioni sensibili:
   - Non caricare file `.venv`, `.git`, o file contenenti chiavi API (`.env` o file simili). Lo script di packaging esclude automaticamente `.env` e file sensibili.
   - Prima dell'upload: rimuovi ogni file che contiene chiavi o segreti oppure sostituisci con placeholder. Usa il file `.env.example` fornito per creare il `.env` sul server dopo l'upload.

6) Creare il file `.env` sul server (scelte sicure):

- Carica il pacchetto senza `.env`, poi connettiti al server via SSH/SFTP e crea il file `.env` nella directory dell'app. Imposta permessi stretti:

```powershell
# Windows PowerShell (server Windows)
New-Item -Path . -Name ".env" -ItemType "file" -Value "GEMINI_API_KEY=...`nNEWSAPI_KEY=..."
icacls .env /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

```bash
# Linux
cat > .env <<'EOF'
GEMINI_API_KEY=...
NEWSAPI_KEY=...
EOF
chmod 600 .env
chown <appuser>:<appuser> .env
```

- Alternativa (più sicura): memorizzare segreti nel gestore di segreti del cloud (Azure Key Vault, AWS Secrets Manager) e iniettare le variabili d'ambiente tramite il sistema di deploy o un file `EnvironmentFile` per `systemd`.

7) Avvio con variabili d'ambiente (esempio systemd):

```
[Service]
EnvironmentFile=/path/to/AgenteScalping/.env
ExecStart=/path/to/venv/bin/python /path/to/AgenteScalping/agente_analitico.py --config /path/to/AgenteScalping/config.ini
```

Assicurati che il file `.env` non sia tracciato dal repository e che abbia permessi limitati.

6) Avvio (esempio):

```bash
# Linux
source .venv/bin/activate
python agente_analitico.py --config config.ini --env-file .env --log-level INFO
```

Se vuoi, creo anche un pacchetto `.tar.gz` per upload via SSH o uno script remoto di deploy (systemd service) pronto all’uso.