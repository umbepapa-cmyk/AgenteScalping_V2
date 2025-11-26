import argparse
import asyncio
import configparser
import logging
from pathlib import Path

from connection_manager import ConnectionManager


def load_ib_config(path: Path = Path(__file__).parents[1] / "config.ini"):
    cfg = configparser.ConfigParser()
    cfg.read(path)
    if "IB" not in cfg:
        raise SystemExit(f"Sezione [IB] non trovata in {path}")
    ib = cfg["IB"]
    host = ib.get("host", "127.0.0.1")
    port = ib.getint("port", 4002)
    client_id = ib.getint("client_id", 25)
    return host, port, client_id


async def try_connect(host: str, port: int, client_id: int) -> bool:
    cm = ConnectionManager(host=host, port=port, client_id=client_id)
    logging.info("Tentativo di connessione a %s:%s (client_id=%s)", host, port, client_id)
    ok = await cm.connect()
    if ok:
        logging.info("Connessione stabilita con successo")
        # Breve pausa per vedere gli eventi
        await asyncio.sleep(1)
        cm.disconnect()
        return True
    else:
        logging.error("Connessione non riuscita dopo i tentativi")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test connessione IB Gateway")
    parser.add_argument("--client-id", type=int, help="Override per client_id (opzionale)")
    parser.add_argument("--config", type=Path, default=Path(__file__).parents[1] / "config.ini", help="Percorso file config.ini")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    try:
        host, port, client_id = load_ib_config(args.config)
    except Exception as e:
        logging.critical("Errore nel caricare la config: %s", e)
        raise

    if args.client_id is not None:
        logging.info("Override client_id da %s a %s", client_id, args.client_id)
        client_id = args.client_id

    try:
        asyncio.run(try_connect(host, port, client_id))
    except Exception as exc:
        logging.critical("Errore eseguendo il test di connessione: %s", exc)


if __name__ == "__main__":
    main()
