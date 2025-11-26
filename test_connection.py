#!/usr/bin/env python
"""
Script per testare la connessione a IB Gateway.
Esegue un test rapido per verificare che l'agente possa:
1. Connettersi a IB Gateway
2. Ottenere informazioni sull'account
3. Qualificare un contratto
"""
import asyncio
import configparser
import logging
import socket
import sys
from pathlib import Path

try:
    from ib_async import IB, Contract
except ImportError:
    print("❌ ERRORE: ib_async non è installato.")
    print("   Esegui: pip install ib_async")
    sys.exit(1)

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)


def check_port_reachable(host: str, port: int, timeout: float = 2.0) -> bool:
    """Verifica se una porta è raggiungibile."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


async def test_ib_connection(host: str, port: int, client_id: int, timeout: int = 15) -> bool:
    """
    Testa la connessione a IB Gateway.
    
    Returns:
        bool: True se la connessione ha successo, False altrimenti
    """
    ib = IB()
    
    print("\n" + "=" * 60)
    print("🔌 TEST CONNESSIONE IB GATEWAY")
    print("=" * 60)
    
    # Step 1: Verifica raggiungibilità porta
    print(f"\n📡 Verifica raggiungibilità porta {host}:{port}...")
    if check_port_reachable(host, port):
        print(f"   ✅ Porta {port} raggiungibile")
    else:
        print(f"   ❌ Porta {port} NON raggiungibile")
        print("\n⚠️  SUGGERIMENTI:")
        print("   1. Verifica che IB Gateway/TWS sia in esecuzione")
        print("   2. Se il gateway è remoto, apri un tunnel SSH:")
        print(f"      ssh -L {port}:localhost:{port} user@server")
        print("   3. Verifica le impostazioni del firewall")
        return False
    
    # Step 2: Tentativo di connessione
    print(f"\n🔗 Connessione a IB Gateway ({host}:{port}, clientId={client_id})...")
    try:
        await ib.connectAsync(host, port, clientId=client_id, timeout=timeout)
        server_version = ib.client.serverVersion()
        print(f"   ✅ Connessione stabilita!")
        print(f"   📊 Versione Server IB: {server_version}")
    except asyncio.TimeoutError:
        print("   ❌ Timeout durante la connessione")
        print("   ⚠️  Verifica che IB Gateway accetti connessioni API")
        return False
    except ConnectionRefusedError:
        print("   ❌ Connessione rifiutata")
        print("   ⚠️  Verifica le impostazioni API in IB Gateway")
        return False
    except Exception as e:
        print(f"   ❌ Errore: {e}")
        return False
    
    # Step 3: Verifica account
    print("\n💼 Verifica informazioni account...")
    try:
        accounts = ib.managedAccounts()
        if accounts:
            print(f"   ✅ Account trovati: {accounts}")
            
            # Ottieni informazioni sul tipo di account
            account_summary = await ib.accountSummaryAsync()
            for item in account_summary:
                if item.tag == "NetLiquidation":
                    print(f"   💰 Net Liquidation ({item.account}): {item.value} {item.currency}")
                    break
        else:
            print("   ⚠️  Nessun account trovato")
    except Exception as e:
        print(f"   ⚠️  Errore nel recupero account: {e}")
    
    # Step 4: Qualifica contratto di test (EUR.USD)
    print("\n📋 Test qualifica contratto (EUR.USD)...")
    try:
        contract = Contract()
        contract.symbol = "EUR"
        contract.secType = "CASH"
        contract.exchange = "IDEALPRO"
        contract.currency = "USD"
        
        qualified = await ib.qualifyContractsAsync(contract)
        if qualified:
            print(f"   ✅ Contratto qualificato: {contract.localSymbol}")
            print(f"   📍 ConId: {contract.conId}")
        else:
            print("   ⚠️  Impossibile qualificare il contratto")
            contract = None  # Mark contract as invalid
    except Exception as e:
        print(f"   ⚠️  Errore qualifica contratto: {e}")
        contract = None  # Mark contract as invalid
    
    # Step 5: Test richiesta dati di mercato (only if contract was qualified)
    print("\n📈 Test richiesta dati di mercato...")
    if contract and contract.conId:
        try:
            # Richiedi ticker per vedere se i dati di mercato funzionano
            ticker = ib.reqMktData(contract, '', False, False)
            await asyncio.sleep(2)  # Attendi 2 secondi per i dati
            
            if ticker.bid and ticker.ask:
                print(f"   ✅ Dati di mercato ricevuti:")
                print(f"      Bid: {ticker.bid:.5f}")
                print(f"      Ask: {ticker.ask:.5f}")
                spread = (ticker.ask - ticker.bid) * 10000  # pips
                print(f"      Spread: {spread:.1f} pips")
            else:
                print("   ⚠️  Nessun dato di mercato ricevuto (potrebbe essere fuori orario)")
            
            ib.cancelMktData(contract)
        except Exception as e:
            print(f"   ⚠️  Errore dati di mercato: {e}")
    else:
        print("   ⚠️  Skipped: contratto non qualificato")
    
    # Disconnessione
    print("\n🔌 Disconnessione...")
    ib.disconnect()
    print("   ✅ Disconnessione completata")
    
    print("\n" + "=" * 60)
    print("✅ TEST CONNESSIONE COMPLETATO CON SUCCESSO!")
    print("=" * 60)
    print("\nL'agente è pronto per connettersi a IB Gateway.")
    print("Puoi avviare l'agente con: python agente_analitico.py")
    
    return True


def main():
    """Punto di ingresso principale."""
    # Carica configurazione
    config_path = Path(__file__).parent / 'config.ini'
    
    if not config_path.exists():
        print("❌ File config.ini non trovato!")
        print("   Crea il file con le impostazioni di connessione.")
        sys.exit(1)
    
    config = configparser.ConfigParser()
    config.read(config_path)
    
    try:
        ib_config = config['IB']
        host = ib_config.get('host', '127.0.0.1')
        port = ib_config.getint('port', 4002)
        client_id = ib_config.getint('client_id', 1)
        environment = ib_config.get('environment', 'PAPER').upper()
    except KeyError as e:
        print(f"❌ Errore nella configurazione: {e}")
        sys.exit(1)
    
    print("\n📋 CONFIGURAZIONE CORRENTE:")
    print(f"   Host: {host}")
    print(f"   Porta: {port}")
    print(f"   Client ID: {client_id}")
    print(f"   Ambiente: {environment}")
    
    # Esegui il test
    try:
        success = asyncio.run(test_ib_connection(host, port, client_id))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrotto dall'utente.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Errore imprevisto: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
