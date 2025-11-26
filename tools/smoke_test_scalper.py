import asyncio
import configparser
import logging
from pathlib import Path

from connection_manager import ConnectionManager
from agent_core.contracts import _contract_from_spec
from agent_core.contracts import qualify_contracts_async


def load_config(path: Path = Path(__file__).parents[1] / "config.ini"):
    cfg = configparser.ConfigParser()
    cfg.read(path)
    if "IB" not in cfg or "STRATEGY" not in cfg:
        raise SystemExit(f"Sezioni [IB] o [STRATEGY] mancanti in {path}")
    ib = cfg["IB"]
    strategy = cfg["STRATEGY"]
    host = ib.get("host", "127.0.0.1")
    port = ib.getint("port", 4002)
    client_id = ib.getint("client_id", 25)
    symbol = strategy.get("symbol", "BTC").upper()
    instrument_spec = {
        "symbol": strategy.get("symbol", symbol),
        "sec_type": strategy.get("sec_type", "CRYPTO"),
        "exchange": strategy.get("exchange", "PAXOS"),
        "currency": strategy.get("currency", "USD"),
    }
    return host, port, client_id, symbol, instrument_spec


async def run_smoke_test():
    host, port, client_id, symbol, instrument_spec = load_config()
    cm = ConnectionManager(host=host, port=port, client_id=client_id)
    logging.info("Connect to IB Gateway %s:%s (client_id=%s)", host, port, client_id)
    ok = await cm.connect()
    if not ok:
        logging.error("Connessione fallita. Controlla IB Gateway e porte.")
        return 2

    try:
        try:
            cm.ib.reqMarketDataType(1)
            logging.info("Impostato MarketDataType=REAL-TIME (1)")
        except Exception as e:
            logging.warning("Impossibile impostare market data type: %s", e)

        try:
            contracts = await qualify_contracts_async(cm.ib, [symbol], instrument_specs={symbol: instrument_spec})
            contract = contracts[symbol]
            logging.info("Contratto qualificato: %s (conId=%s)", getattr(contract, "localSymbol", symbol), getattr(contract, "conId", None))
        except Exception as e:
            logging.error("Qualifica contratto fallita: %s", e)
            return 3

        # Richiedi una barra reale e aspetta la prima aggiornata
        bars_handle = cm.ib.reqRealTimeBars(contract, 5, "MIDPOINT", False)
        got_event = asyncio.Event()

        def on_update(bars, has_new_bar: bool):
            if not has_new_bar:
                return
            last = list(bars)[-1]
            logging.info("Ricevuta barra: O=%.6f H=%.6f L=%.6f C=%.6f", last.open, last.high, last.low, last.close)
            got_event.set()

        bars_handle.updateEvent += on_update

        try:
            await asyncio.wait_for(got_event.wait(), timeout=30)
            logging.info("Smoke test: barra ricevuta con successo")
        except asyncio.TimeoutError:
            logging.error("Timeout: nessuna barra real-time ricevuta in 30s. Verifica permessi market data e connessione.")
        finally:
            try:
                bars_handle.updateEvent -= on_update
                cm.ib.cancelRealTimeBars(bars_handle)
            except Exception:
                pass

    finally:
        if cm.is_connected():
            cm.disconnect()
        logging.info("Disconnessione completata")

    return 0


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    try:
        code = asyncio.run(run_smoke_test())
        raise SystemExit(code)
    except Exception as e:
        logging.critical("Errore nello smoke test: %s", e)
        raise


if __name__ == "__main__":
    main()
