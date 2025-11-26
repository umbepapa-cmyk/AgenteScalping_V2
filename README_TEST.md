Test procedure and options to let the assistant run/collect logs
=============================================================

Goal: eseguire un test paper trading che termina al raggiungimento di 5 esecuzioni o dopo 5 minuti.

Opzioni disponibili
- Opzione A (raccomandata): esegui tu il test localmente usando lo script PowerShell `scripts\run_agent_test.ps1`.
  - Richiede che il tuo PC abbia la virtualenv e le dipendenze installate.
  - Comando di esempio:
    ```powershell
    .\.venv\Scripts\Activate.ps1
    .\scripts\run_agent_test.ps1 -ServerIp 178.156.221.35 -Port 4002 -TestTrades 5 -TestDuration 300
    ```
  - Al termine, carica qui i file `trading_agent_server_test.log` e `logs/trade_log.csv` oppure incolla i contenuti.

- Opzione B: esegui il test tramite tunnel SSH (porta locale) — utile se usi `ssh -L` come nella screenshot.
  - Apri il tunnel localmente: `ssh -L 4002:127.0.0.1:4002 root@178.156.221.35 -N` (o usa Putty/Teraterm)
  - Poi esegui lo script come se il Gateway fosse locale:
    ```powershell
    .\.venv\Scripts\Activate.ps1
    python agente_analitico.py --ib-host 127.0.0.1 --ib-port 4002 --force-live --test-trades 5 --test-duration 300 --log-level DEBUG --log-file trading_agent_server_test.log
    ```

- Opzione C (se davvero vuoi che io esegua il test): concedimi accesso temporaneo via SSH.
  - NOTA: per motivi di sicurezza NON inviare credenziali o chiavi private in chat.
  - Metodo consigliato: crea un utente temporaneo `testbot` sul server, aggiungi una public SSH key che tu controlli e poi invia qui le istruzioni su come connettermi (io non posso ricevere chiavi qui). In pratica, questa opzione richiede uno spazio di esecuzione remoto controllato da te (es. GitHub Codespaces, runner) e non è supportata direttamente via chat.

File utili creati
- `scripts/run_agent_test.ps1` : avvia l'agente dal tuo dev box verso il server e salva `trading_agent_server_test.log`.
- `scripts/collect_logs.ps1` : esempio per copiare via `scp` i log dal server (richiede key-based auth).

Log che servono per l'analisi
- `trading_agent_server_test.log` (log principale del run)
- `logs/trade_log.csv` (record di order submission / execution)
- eventuale log del gateway (se disponibile)

Se vuoi che io esegua il test, rispondi con l'opzione che scegli (A/B) e incolla l'IP del server oppure incolla i log generati.
