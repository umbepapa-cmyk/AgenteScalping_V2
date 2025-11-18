# Istruzioni rapide per AI coding agent — AgenteTrading_V3

Scopo: fornire al Copilot/AI le informazioni essenziali per essere produttivo velocemente in questo repo. L'obiettivo finale del progetto è sviluppare un agente di trading autonomo che generi profitto.

## Big picture
- Due componenti principali:
  - `agente_analitico.py`: entrypoint dell'agente asincrono che si connette a TWS/IB Gateway (usando `ib_async`). Gestisce eventi, qualificazione contratti, logging su CSV e il ciclo di vita dell'applicazione.
  - `ai_analyst.py`: decide che operazione svolgere.
- Flusso dati: Dati di mercato da IB → event handlers in `agente_analitico.py` → invocazione di `AiAnalyst` per decisioni di trading (`get_trading_decision`) → logging su `trading_log_avanzato.csv`.
- Conoscenza per RAG: Lo script `knowledge_builder.py` processa i PDF nella cartella `ebooks/` e li indicizza in un database vettoriale (`chroma_db/`), che viene poi usato da `ai_analyst.py` per arricchire i prompt.

## File chiave e pattern da conoscere
- **`agente_analitico.py`**
  - Entrypoint: `asyncio.run(main())`.
  - Configurazione: Legge `config.ini` per i parametri di connessione (host, port, client_id) e la versione della strategia.
  - Event handlers: Le callback come `on_connected` sono sincrone, ma possono (e devono) avviare task asincroni con `asyncio.create_task` per operazioni non bloccanti.
  - Logging CSV: `CSVHandler` gestisce la scrittura su file CSV, assicurandosi che l'header venga scritto una sola volta. I campi sono definiti in `LOG_FIELDS`.

- **`ai_analyst.py`**
  - Import opzionali: Gestisce l'assenza di `langchain` e `langchain-google-genai`, abilitando un fallback funzionale senza crashare.
  - Chiavi API: Carica le chiavi da variabili d'ambiente (es. `GEMINI_API_KEY`), tipicamente definite in un file `.env`.
  - Database Vettoriale: Utilizza `chroma_db/` se presente. Se la cartella o i moduli mancano, le funzionalità RAG vengono disabilitate silenziosamente.
  - API LangChain: Utilizza `PromptTemplate`, `RunnableParallel` e il metodo `.ainvoke` per le chiamate asincrone all'LLM.

## Dipendenze e comandi di setup
- **Dipendenze minime (solo agente):**
  - `pip install ib_insync python-dotenv`
- **Dipendenze opzionali (per funzionalità AI/RAG):**
  - `pip install langchain langchain-google-genai chromadb`
- **Comandi utili:**
  - **Diagnostica:** `python check_setup.py` (verifica porte, dipendenze, config e chiavi API).
  - **Costruire DB per RAG:** `python knowledge_builder.py` (da eseguire dopo aver aggiunto PDF in `ebooks/`).
  - **Avvio agente:** `python agente_analitico.py`.
  - **Analisi performance:** `python performance_analyzer.py` (genera un report a fine giornata).

## Convenzioni di progetto
- **Fault-tolerance:** `ai_analyst.py` è progettato per non interrompere l'agente principale. Se l'AI fallisce, viene presa una decisione di default (`HOLD`) e l'errore viene loggato.
- **Asincronia:** Le operazioni I/O-bound (come le chiamate API all'LLM) devono essere `async` per non bloccare il loop di `ib_async`.
- **Configurazione separata:** La logica di business (`agente_analitico.py`) è separata dalla configurazione di connessione (`config.ini`) e dalle chiavi segrete (`.env`).
- **Logging strutturato:** Il trading è loggato su file CSV (`trading_log_avanzato.csv`), mentre l'attività generale dell'agente e gli errori vanno su `trading_agent.log`.

## Debug / troubleshooting (errori comuni)
- **Problemi di connessione a IB:**
  - Eseguire `python check_setup.py` per verificare se le porte di TWS/Gateway sono aperte e raggiungibili.
  - Assicurarsi che `client_id` in `config.ini` sia unico per ogni istanza dell'agente in esecuzione.
- **Errori relativi a LangChain / Chroma all'avvio:**
  - Se non si intende usare l'AI, questi errori possono essere ignorati (l'agente userà il fallback).
  - Se si vuole usare l'AI, assicurarsi di aver installato i pacchetti corretti e di aver impostato la `GEMINI_API_KEY` nel file `.env`.
- **File di log vuoto (`trading_log_avanzato.csv`):**
  - Verificare che il processo abbia i permessi di scrittura nella directory.
  - Controllare `trading_agent.log` per eventuali errori durante l'inizializzazione del `CSVHandler`.

## Modifiche tipiche e punti di estensione
- **Aggiungere campi al log CSV:** Aggiornare la lista `LOG_FIELDS` in `agente_analitico.py` e assicurarsi che i nuovi dati vengano passati alla funzione `log_trade_event`.
- **Cambiare il modello LLM:** Modificare `ai_analyst.py` nella sezione dove viene istanziato `GoogleGenerativeAI`. Mantenere la logica di fallback.
- **Aggiungere una nuova strategia:** La logica decisionale è incapsulata in `get_trading_decision` in `ai_analyst.py`. Si può modificare il prompt o la logica di preparazione dei dati per implementare nuove strategie.
