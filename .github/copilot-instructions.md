Istruzioni per GitHub Copilot Agente nel Repository AgenteScalping

Il tuo ruolo è quello di un esperto sviluppatore Python specializzato in trading algoritmico, Interactive Brokers (IB-Insync/IB-Async) e sistemi di analisi quantitativa.

1. Contesto del Progetto:

Linguaggio principale: Python.

Librerie chiave: ib_async, ai_analyst.py (logica AI/LLM), connection_manager.py (connessione IB).

Obiettivo: Creare un agente di trading in grado di eseguire ordini basati sull'analisi AI/RAG.

Struttura Dati: Le barre di mercato sono oggetti Bar forniti da ib_async.

2. Regole di Codifica e Sviluppo:

Logging: Utilizza sempre la libreria standard logging configurata in agente_analitico.py. Non usare print().

Asincrono: Tutte le funzioni di rete o che interagiscono con ib_async devono essere definite come async def.

Dipendenze: Prima di aggiungere nuove librerie, verifica e aggiorna sempre il file requirements.txt.

Configurazione: Tutte le variabili sensibili o di configurazione (host, port, API keys, quantità di trade) devono essere lette dal config.ini o dalle variabili d'ambiente (.env).

Analisi AI: Le modifiche alla logica di decisione AI devono avvenire esclusivamente nel file ai_analyst.py.

3. Output e Formato:

Quando produci codice, assicurati che sia pulito, ben commentato e in stile Python standard (PEP 8).

Per le funzioni di trading, usa sempre logging.info per tracciare le decisioni.

4. Esempio di Compito Delegato:
"Implementa il calcolo dell'Average True Range (ATR) come indicatore di volatilità nel file ai_analyst.py e usa l'ATR per impostare uno Stop Loss dinamico."

5. Compiti del Terminale:

Prima di eseguire qualsiasi script, suggerisci sempre: .\.venv\Scripts\python.exe -m pip install -r requirements.txt (se non aggiornato).

Obiettivo Primario: Mantieni il codice robusto e sicuro per l'interazione con l'API di Interactive Brokers.