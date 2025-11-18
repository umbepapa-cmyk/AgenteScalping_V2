AI Trading Agent per Interactive Brokers

Questo progetto implementa un agente di trading automatizzato che utilizza Interactive Brokers (IB Gateway/TWS) per l'esecuzione degli ordini e Google Gemini (via LangChain) per l'analisi di mercato e il processo decisionale.

🚀 Funzionalità

Connessione Asincrona: Gestione robusta della connessione con IB Gateway tramite ib_async.

Analisi AI: Utilizza un modello LLM (Gemini) per analizzare i dati di mercato e decidere se comprare, vendere o mantenere.

RAG (Retrieval-Augmented Generation): Arricchisce le decisioni dell'AI consultando una base di conoscenza costruita da PDF finanziari (cartella ebooks).

Logging Avanzato: Traccia decisioni, performance e log tecnici.

Analisi Performance: Script dedicato per generare report su P&L e accuratezza.

🛠️ Installazione

Clona il repository:

git clone [https://github.com/TUO_USERNAME/TUO_REPO.git](https://github.com/TUO_USERNAME/TUO_REPO.git)
cd TUO_REPO


Crea un ambiente virtuale:

python -m venv .venv
# Windows
.venv\Scripts\activate
# Mac/Linux
source .venv/bin/activate


Installa le dipendenze:

pip install -r requirements.txt


Configurazione:

Crea un file .env basato sulle tue chiavi API:

GEMINI_API_KEY=la_tua_chiave_qui


Configura config.ini con le porte corrette di TWS/Gateway (es. 7497 per TWS Live, 4002 per Gateway Paper).

▶️ Utilizzo

Avvia IB Gateway o TWS e assicurati che l'API sia abilitata.

Verifica il setup (opzionale ma consigliato):

python check_setup.py


Costruisci la conoscenza (se hai aggiunto PDF in ebooks/):

python knowledge_builder.py


Avvia l'agente:

python agente_analitico.py


📂 Struttura

agente_analitico.py: Entry point principale.

ai_analyst.py: Logica decisionale dell'AI.

connection_manager.py: Wrapper per la connessione IB.

knowledge_builder.py: Script per indicizzare i PDF in ChromaDB.