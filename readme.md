AI Trading Agent per Interactive Brokers

Agent unificato per scalping discrezionale assistito da LLM su Interactive Brokers. L'intero stack gira in asincrono (`ib_async`) e combina segnali tecnici, feed esterni e ragionamento di Google Gemini per decidere se aprire bracket order con TP/SL dinamici.

## Funzionalità principali

- **Connessione resiliente** – `ConnectionManager` usa `ib_async` e probe TCP per gestire riconnessioni e filtra i codici IB rumorosi.
- **Analisi ibrida AI + indicatori** – `AiAnalyst` calcola ATR/momentum/MA e poi arricchisce il prompt con news, ricerche web, knowledge base Chroma, feed Binance crypto/forex e market-hours contestualizzati.
- **Core condiviso** – Il pacchetto `agent_core` fornisce `TradeLogger`, `ScalpingStrategy`, contract builder multi-asset e diagnostiche `ExternalIntelService`, eliminando la vecchia codebase “Agente di collegamento remoto”.
- **Gestione rischio scalping** – Filtri su ATR, momentum, cooldown, numero massimo di slot e durata posizione. Se il modello non fornisce TP/SL validi, si applica automaticamente la fallback strategy price-based.
- **CLI completa** – `agente_analitico.py` espone override runtime (config, env, log level, dry-run/live, percorso trade log, intel test).
- **Logging trasparente** – log applicativo + CSV per ogni ordine/fill con PnL cumulato; gli handler IB vengono sganciati e la sessione IB viene chiusa in modo pulito.

## Installazione rapida

```bash
python -m venv .venv
.venv\Scripts\activate              # Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
```

Prima di avviare l'agente suggeriamo di sincronizzare le dipendenze ad ogni pull:

```bash
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Configurazione

### Variabili ambiente (`.env`)

```
GEMINI_API_KEY=...       # abilita l'LLM
NEWSAPI_KEY=...          # opzionale per news
MARKETAUX_API_KEY=...    # alternativa a NewsAPI
SERPAPI_API_KEY=...      # o SERPER / GOOGLE_API_KEY + GOOGLE_CSE_ID
```

Tutte le impostazioni IB/strategiche restano in `config.ini`.

### `config.ini`

- `[IB]`: `environment` (PAPER/LIVE), `host`, `port` (7497 paper, 7496 live), `client_id`, `account`.
- `[STRATEGY]`: `symbol`, `sec_type`, `currency`, `quantity`, `auto_trade`, `scalper_price_offset`, `take_profit_pips`, `stop_loss_pips`, `atr_tp_multiplier`, `atr_sl_multiplier`, `max_concurrent_trades`, `cooldown_seconds`, `max_hold_seconds`, `min_atr`, `min_momentum`, `outside_rth`.
- `[NEWS]`: `enabled`, `provider` (`newsapi` o `marketaux`), `api_key_env`, `query` (supporta placeholder `{symbol}`, `{currency}`, `{pair}`, `{sec_type}`), finestra temporale/lingua.
- `[CRYPTO_FEED]` / `[FOREX_FEED]`: `enabled`, `symbols = BTCUSDT,ETHUSDT` ecc., `label`, `max_snapshots`. Alimentano il prompt come failover dati.

## Avvio & CLI

1. Avvia IB Gateway/TWS e abilita l'API (`Configure > API > Settings`).
2. (Opzionale) genera la knowledge base con `python knowledge_builder.py` dopo aver aggiunto PDF in `ebooks/`.
3. Avvia l'agente:

```bash
python agente_analitico.py --config config.ini --env-file .env --log-level INFO
```

Flag principali:

- `--dry-run` / `--force-live`: override di `auto_trade` senza toccare `config.ini`.
- `--log-file` e `--trade-log`: percorsi personalizzati per log testo e CSV.
- `--intel-test` + `--intel-query`: ping asincrono di NewsAPI/MarketAux e uscita immediata.
- `--env-file`: permette profili multipli (Paper vs Live) senza cambiare `.env` globale.

## Componenti principali

- `agente_analitico.py`: entrypoint asincrono, parser CLI, orchestrazione ordini e cleanup.
- `ai_analyst.py`: segnali tecnici, LLM (LangChain + Gemini), integrazione news/search/feed/RAG.
- `agent_core/trade_logging.py`: CSV logger thread-safe con tracciamento PnL.
- `agent_core/contracts.py`: costruzione/qualificazione contratti IB multi-asset con fallback automatico.
- `agent_core/scalping_strategy.py`: fallback TP/SL basati su spread bid/ask.
- `agent_core/intel.py`: utility per il comando `--intel-test`.
- `connection_manager.py`: gestione connessione IB asincrona con retry/probe.
- `news_fetcher.py`, `search_fetcher.py`, `crypto_feed.py`, `market_hours.py`: raccolta contesto per l'LLM.
- `knowledge_builder.py`: ingest PDF -> ChromaDB (`chroma_db/`).

## Logging & diagnostica

- Log applicativi in `trading_agent.log` (personalizzabile via `--log-file`).
- Trade log CSV (`logs/trade_log.csv` di default) con eventi `ORDER`/`FILL`, quantità, prezzi e PnL.
- `logs/` contiene anche output dei test (`test_10min.py`, `check_setup.py`).
- Durante lo shutdown l'agente annulla i real-time bars, market data e ordini aperti (global cancel) prima di disconnettersi.

## Struttura repository

```
AgenteScalping/
├─ agente_analitico.py
├─ agent_core/
├─ ai_analyst.py
├─ connection_manager.py
├─ crypto_feed.py
├─ market_hours.py
├─ news_fetcher.py
├─ search_fetcher.py
├─ knowledge_builder.py
├─ requirements.txt
└─ logs/
```

La precedente cartella "Agente di collegamento remoto" è stata rimossa: tutte le funzionalità sono ora consolidate qui.
