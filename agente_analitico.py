import logging
from pathlib import Path

import asyncio
import configparser
from ib_async import Contract, util

# Importa la nuova classe dal file che abbiamo creato
from connection_manager import ConnectionManager
# Importa l'analista AI
from ai_analyst import AiAnalyst

# --- Configurazione del Logging Professionale ---
log_file = Path(__file__).parent / 'trading_agent.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
# Riduci la verbosità dei log interni di ib_async per vedere solo gli avvisi/errori
util.logToConsole(logging.WARNING)


async def main():
    """Punto di ingresso principale dell'applicazione."""
    
    # 1. Caricamento della configurazione da file
    config = configparser.ConfigParser()
    config_path = Path(__file__).parent / 'config.ini'
    if not config_path.exists():
        logging.critical(f"File di configurazione 'config.ini' non trovato. L'agente non può partire.")
        return
        
    config.read(config_path)
    
    # --- CORREZIONE: Specifica la sezione quando leggi i valori ---
    ib_config = config['IB']
    strategy_config = config['STRATEGY']
    
    # 2. Inizializzazione del Connection Manager
    # --- CORREZIONE: Aggiungi valori di fallback per gestire l'assenza di chiavi ---
    conn_manager = ConnectionManager(
        host=ib_config.get('host', '127.0.0.1'),
        port=ib_config.getint('port', 4002),
        client_id=ib_config.getint('client_id', 1)
    )

    # Inizializzazione dell'Analista AI
    ai_analyst = AiAnalyst(strategy_version=strategy_config.get('version', 'default'))

    try:
        # 3. Connessione a IB Gateway
        if not await conn_manager.connect():
            return # Termina se la connessione iniziale fallisce

        # 4. Definizione e qualificazione del contratto (come esempio)
        # --- CORREZIONE: Aggiungi valori di fallback anche qui ---
        contract = Contract()
        contract.symbol = strategy_config.get('symbol', 'EUR')
        contract.secType = strategy_config.get('sec_type', 'CASH')
        contract.exchange = strategy_config.get('exchange', 'IDEALPRO')
        contract.currency = strategy_config.get('currency', 'USD')
        
        # Qualifica il contratto usando l'istanza di IB dal connection manager
        await conn_manager.ib.qualifyContractsAsync(contract)
        logging.info(f"Contratto qualificato con successo: {contract.localSymbol}")

        # --- CORREZIONE: "Sveglia" la connessione dati di mercato per questo contratto ---
        logging.info("Attivazione del flusso dati di mercato per il contratto...")
        conn_manager.ib.reqMktData(contract, '', False, False)
        await asyncio.sleep(2)  # Attendi 2 secondi per permettere l'attivazione
        conn_manager.ib.cancelMktData(contract)
        logging.info("Flusso dati di mercato attivato.")

        async def handle_new_bar(symbol, bar_snapshot):
            last_bar = bar_snapshot[-1]
            logging.info(
                "Nuova barra %s | O=%.5f H=%.5f L=%.5f C=%.5f",
                symbol, last_bar.open, last_bar.high, last_bar.low, last_bar.close
            )
            decision, reason = await ai_analyst.get_trading_decision(bar_snapshot)
            logging.info("Decisione AI per %s: %s (%s)", symbol, decision, reason)

        def on_bar_update(bars, has_new_bar):
            if not has_new_bar:
                return
            snapshot = list(bars)
            symbol = getattr(bars.contract, "symbol", "UNKNOWN")
            asyncio.create_task(handle_new_bar(symbol, snapshot))

        bars = conn_manager.ib.reqRealTimeBars(contract, 5, 'MIDPOINT', False)
        bars.updateEvent += on_bar_update

        # 5. Mantiene l'agente in esecuzione per ascoltare gli eventi
        logging.info("Agente avviato correttamente. In attesa di dati di mercato... Premere Ctrl+C per terminare.")
        await asyncio.Event().wait()

    except (KeyboardInterrupt, asyncio.CancelledError):
        logging.info("Richiesta di arresto ricevuta (Ctrl+C).")
    
    finally:
        # 6. Procedura di arresto controllato (Graceful Shutdown)
        logging.info("Avvio procedura di arresto controllato...")
        if conn_manager and conn_manager.is_connected():
            conn_manager.ib.reqGlobalCancel()  # Cancella tutti gli ordini aperti
            await asyncio.sleep(1)  # Breve attesa per la conferma
            conn_manager.disconnect()
        logging.info("Arresto dell'agente completato.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Programma terminato dall'utente.")
