import pandas as pd
import os
import logging

LOG_FILENAME = 'trading_log_avanzato.csv'
BALANCE_FILE = 'balance_data.txt'
AGENT_LOG_FILE = 'trading_agent.log' # Per leggere le lezioni apprese

def generate_report():
    """ 
    Genera il report giornaliero leggendo i file di log e bilancio.
    Modificato per includere le "LEZIONI APPRESE" dal log principale.
    """
    
    logging.basicConfig(level=logging.INFO, format='%(message)s') # Configurazione base per l'output
    
    # 1. Lettura dati di bilancio
    initial_balance = 0.0
    final_balance = 0.0
    
    if os.path.exists(BALANCE_FILE):
        try:
            with open(BALANCE_FILE, 'r') as f:
                for line in f:
                    if 'initial_balance' in line:
                        initial_balance = float(line.split('=')[1].strip())
                    elif 'final_balance' in line:
                        final_balance = float(line.split('=')[1].strip())
        except Exception as e:
            logging.error(f"Errore lettura {BALANCE_FILE}: {e}")
    
    # 2. Lettura log di trading (CSV)
    if not os.path.exists(LOG_FILENAME) or os.path.getsize(LOG_FILENAME) < 150: # Dimensione minima header
        logging.info("\n=======================================================")
        logging.info("REPORT NON GENERATO: Nessun trade trovato in " + LOG_FILENAME)
        if initial_balance > 0 and final_balance > 0:
            total_change = final_balance - initial_balance
            logging.info(f"Saldo Trovato: Iniziale {initial_balance:.2f}, Finale {final_balance:.2f}. Variazione: {total_change:+.2f} USD")
        logging.info("=======================================================")
        return

    try:
        df = pd.read_csv(LOG_FILENAME)
        if df.empty:
            logging.info(f"{LOG_FILENAME} è vuoto. Nessun report da generare.")
            return
    except pd.errors.EmptyDataError:
        logging.info(f"{LOG_FILENAME} è vuoto o corrotto. Nessun report da generare.")
        return
    except Exception as e:
        logging.error(f"Errore imprevisto durante la lettura di {LOG_FILENAME}: {e}")
        return

    # --- Calcoli dal DataFrame ---
    
    # Converte PNL e Commissioni in numerico, gestendo 'N/A' o stringhe
    df['PNL_Realizzato_NETTO'] = pd.to_numeric(df['PNL_Realizzato_NETTO'], errors='coerce').fillna(0.0)
    df['Costo_Commissioni_Stimate'] = pd.to_numeric(df['Costo_Commissioni_Stimate'], errors='coerce').fillna(0.0)
    
    total_trades = len(df)
    total_net_pnl = df['PNL_Realizzato_NETTO'].sum()
    total_commissions = df['Costo_Commissioni_Stimate'].sum()
    
    # Calcolo Accuratezza
    profitable_trades = len(df[df['PNL_Realizzato_NETTO'] > 0])
    accuracy_avg = (profitable_trades / total_trades) * 100 if total_trades > 0 else 0.0
    
    # Cerca l'ultima accuratezza registrata
    try:
        accuracy_last_str = df['Accuratezza_Totale_%'].iloc[-1].replace('%', '')
        accuracy_last = float(accuracy_last_str)
    except (IndexError, ValueError):
        accuracy_last = accuracy_avg # Fallback
    
    # Calcolo P&L da bilancio (se disponibile)
    pnl_balance = 0.0
    if initial_balance > 0 and final_balance > 0:
        pnl_balance = final_balance - initial_balance
    elif initial_balance > 0 and final_balance == 0:
        logging.warning("Manca 'final_balance' in balance_data.txt. Il P&L da bilancio sarà 0.")

    # --- 3. Lettura Lezioni Apprese dal Log Principale ---
    lessons_learned = []
    if os.path.exists(AGENT_LOG_FILE):
        try:
            with open(AGENT_LOG_FILE, 'r', encoding='utf-8') as f:
                for line in f:
                    if "LEZIONE APPRESA" in line:
                        lesson_text = line.split("LEZIONE APPRESA", 1)[1].strip()
                        lessons_learned.append(lesson_text)
        except Exception as e:
            logging.error(f"Errore lettura {AGENT_LOG_FILE}: {e}")

    # --- OUTPUT REPORT ---
    logging.info("\n\n=======================================================")
    logging.info("📈 REPORT DI PERFORMANCE DELLA SESSIONE")
    logging.info("=======================================================")
    
    if initial_balance > 0:
        logging.info(f"➡️ Capitale Iniziale (Net Liquidation): {initial_balance:.2f} USD")
        if final_balance > 0:
            logging.info(f"➡️ Capitale Finale (Net Liquidation):   {final_balance:.2f} USD")
        logging.info(f"-------------------------------------------------------")
        if final_balance > 0:
            logging.info(f"💰 P&L Totale da Bilancio (REALE):     {pnl_balance:+.2f} USD")
        
    logging.info(f"💰 P&L Totale da Log CSV (Netto):      {total_net_pnl:+.2f} USD")
    logging.info(f"💸 Commissioni Totali Stimate (da CSV): {total_commissions:.2f} USD")
    logging.info(f"-------------------------------------------------------")
    logging.info(f"📊 Trade Totali Chiusi:                {total_trades}")
    logging.info(f"✅ Trade Profittevoli:                {profitable_trades}")
    logging.info(f"🎯 Accuratezza Finale:                {accuracy_last:.1f} %")
    
    logging.info("\n=======================================================")
    logging.info("📚 RIEPILOGO LEZIONI APPRESE (DALL'AI)")
    logging.info("=======================================================")
    if lessons_learned:
        for i, lesson in enumerate(lessons_learned, 1):
            logging.info(f"{i}. {lesson}")
    else:
        logging.info("Nessuna lezione appresa trovata in 'trading_agent.log'.")
    logging.info("=======================================================\n")

if __name__ == "__main__":
    generate_report()
