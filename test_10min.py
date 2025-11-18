#!/usr/bin/env python
"""
Script per test di 10 minuti dell'agente di trading.
Al termine mostra l'elenco delle operazioni e il P&L totale.
"""
import subprocess
import time
import sys
import csv
from datetime import datetime
import signal

def run_test():
    print("=" * 80)
    print("AVVIO TEST 10 MINUTI - Agente di Trading")
    print("=" * 80)
    print(f"Inizio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("L'agente verrà eseguito per 10 minuti...")
    print("-" * 80)
    
    # Avvia l'agente
    processo = subprocess.Popen(
        [sys.executable, "agente_analitico.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    try:
        # Attendi 10 minuti (600 secondi)
        tempo_attesa = 600
        print(f"Attesa di {tempo_attesa} secondi ({tempo_attesa//60} minuti)...")
        
        # Monitora ogni 30 secondi
        for i in range(0, tempo_attesa, 30):
            time.sleep(30)
            tempo_rimanente = tempo_attesa - i - 30
            if tempo_rimanente > 0:
                print(f"Tempo rimanente: {tempo_rimanente//60} minuti e {tempo_rimanente%60} secondi...")
        
        print("\n" + "=" * 80)
        print("TEST COMPLETATO - Arresto agente...")
        print("=" * 80)
        
    except KeyboardInterrupt:
        print("\n\nInterrotto dall'utente.")
    finally:
        # Termina il processo
        processo.send_signal(signal.SIGTERM)
        time.sleep(2)
        if processo.poll() is None:
            processo.kill()
        
        # Raccogli output
        stdout, stderr = processo.communicate(timeout=5)
        
    # Mostra i risultati
    mostra_risultati()

def mostra_risultati():
    """Legge il CSV delle operazioni e mostra il riepilogo."""
    print("\n" + "=" * 80)
    print("RISULTATI DEL TEST")
    print("=" * 80)
    print(f"Fine: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    csv_file = "trading_log_avanzato.csv"
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            operazioni = list(reader)
        
        if not operazioni:
            print("Nessuna operazione completata durante il test.")
            return
        
        print(f"NUMERO OPERAZIONI COMPLETATE: {len(operazioni)}\n")
        print("-" * 80)
        print("ELENCO OPERAZIONI:")
        print("-" * 80)
        
        capitale_totale = 0.0
        
        for idx, op in enumerate(operazioni, 1):
            timestamp = op.get('timestamp', 'N/A')
            simbolo = op.get('symbol', 'N/A')
            azione = op.get('action', 'N/A')
            quantita = op.get('quantity', 'N/A')
            prezzo = op.get('price', 'N/A')
            decisione = op.get('trading_decision', 'N/A')
            motivo = op.get('reasoning', 'N/A')
            
            # Tenta di estrarre P&L se disponibile
            pnl = 0.0
            try:
                if 'pnl' in op and op['pnl']:
                    pnl = float(op['pnl'])
                    capitale_totale += pnl
            except:
                pass
            
            print(f"\n{idx}. {timestamp}")
            print(f"   Simbolo: {simbolo} | Azione: {azione} | Quantità: {quantita}")
            print(f"   Prezzo: {prezzo} | Decisione: {decisione}")
            if pnl != 0.0:
                print(f"   P&L: ${pnl:.2f}")
            print(f"   Motivo: {motivo[:100]}...")
        
        print("\n" + "=" * 80)
        print("RIEPILOGO FINANZIARIO")
        print("=" * 80)
        
        if capitale_totale != 0.0:
            colore = "PROFITTO" if capitale_totale > 0 else "PERDITA"
            print(f"CAPITALE {colore}: ${capitale_totale:.2f}")
        else:
            print("Capitale variazione: $0.00 (nessuna operazione chiusa o P&L non disponibile)")
        
        print("=" * 80)
        
    except FileNotFoundError:
        print(f"File {csv_file} non trovato.")
        print("Verifica che l'agente abbia creato il file di log.")
    except Exception as e:
        print(f"Errore nella lettura dei risultati: {e}")

if __name__ == "__main__":
    run_test()
