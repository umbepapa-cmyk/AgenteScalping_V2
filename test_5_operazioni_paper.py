#!/usr/bin/env python
"""
Test di 5 operazioni di scalping in modalità paper trading.

Questo script si connette a IB Gateway via tunnel SSH (127.0.0.1:4002) 
ed esegue 5 operazioni di scalping simulato su EUR/USD.
"""
import asyncio
import configparser
import csv
import logging
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from ib_async import IB, Contract, MarketOrder, util


# --- Configurazione del Logging ---
log_file = Path(__file__).parent / 'test_5_operazioni.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ScalpingTest')
# Riduce verbosità dei log interni di ib_async
util.logToConsole(logging.WARNING)


class ScalpingTester:
    """Classe per eseguire test di scalping in paper trading."""
    
    def __init__(self, host: str = '127.0.0.1', port: int = 4002, client_id: int = 26):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()
        self.operazioni: List[Dict[str, Any]] = []
        self.contract: Optional[Contract] = None
        self.current_position = 0
        self.quantity = 20000  # Quantità di unità per trade
        
    async def connect(self) -> bool:
        """Connette al IB Gateway."""
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"Tentativo {attempt}/{max_retries} di connessione a {self.host}:{self.port}...")
                await self.ib.connectAsync(
                    self.host, 
                    self.port, 
                    clientId=self.client_id, 
                    timeout=15
                )
                if self.ib.isConnected():
                    server_version = self.ib.client.serverVersion()
                    logger.info(f"✅ Connessione stabilita! Server version: {server_version}")
                    return True
            except (ConnectionRefusedError, asyncio.TimeoutError) as e:
                logger.warning(f"Connessione fallita: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Errore imprevisto: {e}")
                break
        logger.error("❌ Impossibile connettersi a IB Gateway.")
        return False
    
    async def setup_contract(self) -> bool:
        """Configura e qualifica il contratto EUR/USD."""
        try:
            self.contract = Contract()
            self.contract.symbol = 'EUR'
            self.contract.secType = 'CASH'
            self.contract.exchange = 'IDEALPRO'
            self.contract.currency = 'USD'
            
            await self.ib.qualifyContractsAsync(self.contract)
            logger.info(f"✅ Contratto qualificato: {self.contract.localSymbol}")
            
            # Attiva il flusso dati di mercato
            logger.info("Attivazione flusso dati di mercato...")
            self.ib.reqMktData(self.contract, '', False, False)
            await asyncio.sleep(2)
            self.ib.cancelMktData(self.contract)
            
            return True
        except Exception as e:
            logger.error(f"❌ Errore setup contratto: {e}")
            return False
    
    async def get_current_price(self) -> Optional[float]:
        """Ottiene il prezzo corrente del contratto."""
        try:
            ticker = self.ib.reqMktData(self.contract, '', True, False)
            await asyncio.sleep(1)
            
            # Prova diversi campi prezzo in ordine di preferenza
            price = None
            if ticker.last and ticker.last > 0:
                price = ticker.last
            elif ticker.close and ticker.close > 0:
                price = ticker.close
            elif ticker.bid and ticker.bid > 0:
                price = ticker.bid
            elif ticker.ask and ticker.ask > 0:
                price = ticker.ask
            
            self.ib.cancelMktData(self.contract)
            
            if price:
                logger.info(f"Prezzo corrente EUR/USD: {price:.5f}")
            else:
                logger.warning("Nessun prezzo disponibile")
            return price
        except Exception as e:
            logger.error(f"Errore nel recupero prezzo: {e}")
            return None

    async def execute_trade(self, action: str, reason: str) -> Dict[str, Any]:
        """Esegue un ordine di mercato."""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            price = await self.get_current_price()
            
            if not price:
                # Usa prezzo simulato se non disponibile
                price = 1.05000 + random.uniform(-0.002, 0.002)
                logger.warning(f"Usando prezzo simulato: {price:.5f}")
            
            order = MarketOrder(action, self.quantity)
            
            logger.info(f"Invio ordine: {action} {self.quantity} EUR/USD @ ~{price:.5f}")
            
            trade = self.ib.placeOrder(self.contract, order)
            
            # Attendi che l'ordine venga riempito (max 10 secondi)
            timeout = 10
            while not trade.isDone() and timeout > 0:
                await asyncio.sleep(0.5)
                timeout -= 0.5
            
            # Determina lo stato dell'ordine
            if trade.isDone():
                fill_price = trade.orderStatus.avgFillPrice or price
                status = 'FILLED'
                logger.info(f"✅ Ordine eseguito: {action} @ {fill_price:.5f}")
            else:
                fill_price = price
                status = 'SUBMITTED'
                logger.info(f"⏳ Ordine inviato (pending): {action} @ {fill_price:.5f}")
            
            # Aggiorna posizione
            if action == 'BUY':
                self.current_position += self.quantity
            else:
                self.current_position -= self.quantity
            
            operazione = {
                'timestamp': timestamp,
                'symbol': 'EUR/USD',
                'action': action,
                'quantity': self.quantity,
                'price': fill_price,
                'status': status,
                'reason': reason,
                'position': self.current_position
            }
            
            self.operazioni.append(operazione)
            return operazione
            
        except Exception as e:
            logger.error(f"❌ Errore esecuzione ordine: {e}")
            operazione = {
                'timestamp': timestamp,
                'symbol': 'EUR/USD',
                'action': action,
                'quantity': self.quantity,
                'price': 0.0,
                'status': 'ERROR',
                'reason': str(e),
                'position': self.current_position
            }
            self.operazioni.append(operazione)
            return operazione

    async def analyze_market_signal(self) -> tuple:
        """
        Analizza il mercato e genera un segnale di trading.
        Implementa una logica semplice per il test.
        """
        # Per il test, usa segnali casuali realistici
        signals = [
            ('BUY', 'Momentum positivo rilevato, RSI < 30'),
            ('SELL', 'Momentum negativo rilevato, RSI > 70'),
            ('BUY', 'Breakout sopra la media mobile'),
            ('SELL', 'Rottura sotto il supporto chiave'),
            ('BUY', 'Pattern di inversione bullish'),
            ('SELL', 'Pattern di inversione bearish'),
            ('BUY', 'Divergenza positiva su MACD'),
            ('SELL', 'Divergenza negativa su RSI'),
        ]
        return random.choice(signals)

    async def run_scalping_test(self, num_trades: int = 5) -> List[Dict[str, Any]]:
        """
        Esegue il test di scalping con il numero specificato di operazioni.
        
        Args:
            num_trades: Numero di operazioni da eseguire (default: 5)
            
        Returns:
            Lista delle operazioni eseguite
        """
        logger.info("=" * 60)
        logger.info(f"AVVIO TEST SCALPING - {num_trades} OPERAZIONI")
        logger.info("=" * 60)
        
        # Connessione
        if not await self.connect():
            logger.error("Test interrotto: impossibile connettersi")
            return []
        
        # Setup contratto
        if not await self.setup_contract():
            logger.error("Test interrotto: impossibile configurare il contratto")
            self.disconnect()
            return []
        
        try:
            # Esegui le operazioni
            for i in range(num_trades):
                logger.info(f"\n--- OPERAZIONE {i + 1}/{num_trades} ---")
                
                # Analizza e genera segnale
                action, reason = await self.analyze_market_signal()
                
                logger.info(f"Segnale: {action} - Motivo: {reason}")
                
                # Esegui trade
                await self.execute_trade(action, reason)
                
                # Pausa tra le operazioni (simula timing scalping)
                if i < num_trades - 1:
                    wait_time = random.uniform(2, 5)
                    logger.info(f"Attesa {wait_time:.1f}s prima della prossima operazione...")
                    await asyncio.sleep(wait_time)
            
            # Se abbiamo una posizione aperta, chiudiamola
            if self.current_position != 0:
                logger.info("\n--- CHIUSURA POSIZIONE RESIDUA ---")
                close_action = 'SELL' if self.current_position > 0 else 'BUY'
                await self.execute_trade(close_action, "Chiusura posizione di fine test")
            
        except Exception as e:
            logger.error(f"Errore durante il test: {e}")
        finally:
            self.disconnect()
        
        return self.operazioni

    def disconnect(self):
        """Disconnette dal IB Gateway."""
        if self.ib.isConnected():
            try:
                self.ib.reqGlobalCancel()
            except Exception:
                pass
            self.ib.disconnect()
            logger.info("Disconnesso da IB Gateway")

    def show_summary(self):
        """Mostra il riepilogo delle operazioni."""
        logger.info("\n" + "=" * 60)
        logger.info("RIEPILOGO OPERAZIONI")
        logger.info("=" * 60)
        
        if not self.operazioni:
            logger.info("Nessuna operazione eseguita.")
            return
        
        # Statistiche
        total_ops = len(self.operazioni)
        buys = sum(1 for op in self.operazioni if op['action'] == 'BUY')
        sells = sum(1 for op in self.operazioni if op['action'] == 'SELL')
        filled = sum(1 for op in self.operazioni if op['status'] == 'FILLED')
        errors = sum(1 for op in self.operazioni if op['status'] == 'ERROR')
        
        logger.info(f"Totale operazioni: {total_ops}")
        logger.info(f"BUY: {buys} | SELL: {sells}")
        logger.info(f"Eseguiti: {filled} | Errori: {errors}")
        
        # Calcolo P&L approssimativo
        pnl = 0.0
        buy_prices = []
        sell_prices = []
        
        for op in self.operazioni:
            if op['price'] > 0:
                if op['action'] == 'BUY':
                    buy_prices.append(op['price'])
                else:
                    sell_prices.append(op['price'])
        
        # P&L semplificato (differenza media tra sell e buy)
        if buy_prices and sell_prices:
            avg_buy = sum(buy_prices) / len(buy_prices)
            avg_sell = sum(sell_prices) / len(sell_prices)
            pnl = (avg_sell - avg_buy) * self.quantity
        
        logger.info(f"\n💰 P&L Stimato: ${pnl:.2f}")
        
        # Dettaglio operazioni
        logger.info("\n--- DETTAGLIO OPERAZIONI ---")
        for i, op in enumerate(self.operazioni, 1):
            logger.info(
                f"{i}. [{op['timestamp']}] {op['action']} {op['quantity']} @ "
                f"{op['price']:.5f} ({op['status']}) - {op['reason'][:50]}"
            )
        
        # Salva in CSV
        self.save_to_csv()
        
        logger.info("=" * 60)

    def save_to_csv(self):
        """Salva le operazioni in un file CSV."""
        csv_file = Path(__file__).parent / 'test_5_operazioni_risultati.csv'
        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                if self.operazioni:
                    writer = csv.DictWriter(f, fieldnames=self.operazioni[0].keys())
                    writer.writeheader()
                    writer.writerows(self.operazioni)
            logger.info(f"Risultati salvati in: {csv_file}")
        except Exception as e:
            logger.error(f"Errore salvataggio CSV: {e}")


async def main():
    """Punto di ingresso principale."""
    print("\n" + "=" * 60)
    print("TEST 5 OPERAZIONI SCALPING - MODALITÀ PAPER TRADING")
    print("=" * 60)
    print(f"Ora di inizio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Connessione: 127.0.0.1:4002 (via SSH tunnel)")
    print("-" * 60)
    
    # Carica configurazione se disponibile
    config_path = Path(__file__).parent / 'config.ini'
    host = '127.0.0.1'
    port = 4002
    client_id = 26
    
    if config_path.exists():
        config = configparser.ConfigParser()
        config.read(config_path)
        ib_config = config['IB']
        host = ib_config.get('host', host)
        port = ib_config.getint('port', port)
        client_id = ib_config.getint('client_id', client_id) + 1  # Usa ID diverso
    
    # Crea tester e esegui
    tester = ScalpingTester(host=host, port=port, client_id=client_id)
    
    try:
        await tester.run_scalping_test(num_trades=5)
        tester.show_summary()
    except KeyboardInterrupt:
        print("\n\nTest interrotto dall'utente.")
        tester.disconnect()
    
    print(f"\nOra di fine: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest terminato.")
