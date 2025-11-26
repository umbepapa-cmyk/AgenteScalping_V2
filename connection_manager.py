import logging
import asyncio
from ib_async import IB

class ConnectionManager:
    """
    Gestisce il ciclo di vita della connessione con IB Gateway,
    inclusa la logica di riconnessione automatica.
    """
    def __init__(self, host: str, port: int, client_id: int):
        self.ib = IB()
        self._host = host
        self._port = port
        self._client_id = client_id
        self._connection_retries = 5
        self._retry_delay = 10  # Secondi
        self._register_event_handlers()

    def _register_event_handlers(self):
        """Registra i gestori per gli eventi di connessione e errore."""
        self.ib.connectedEvent += self.on_connected
        self.ib.disconnectedEvent += self.on_disconnected
        self.ib.errorEvent += self.on_error

    def on_connected(self):
        """Callback eseguita dopo una connessione riuscita."""
        # CORREZIONE: La versione del server si trova nell'attributo 'client'
        server_version = self.ib.client.serverVersion()
        logging.info(f"Connessione a IB Gateway stabilita. Versione Server: {server_version}")

    def on_disconnected(self):
        """Callback eseguita alla disconnessione."""
        logging.warning("Disconnesso da IB Gateway.")

    def on_error(self, reqId, errorCode, errorString, contract=None):
        """Gestisce gli errori API, escludendo i messaggi informativi."""
        # CORREZIONE: Ignora i codici informativi comuni (es. 2104, 2106, 2158)
        informational_codes = {2104, 2106, 2108, 2158}
        if errorCode not in informational_codes:
            logging.error(f"Errore API IB: reqId={reqId}, Code={errorCode}, Msg='{errorString}'")

    async def connect(self):
        """Tenta la connessione con logica di re-tentativo (solo async pulito)."""
        for attempt in range(1, self._connection_retries + 1):
            try:
                if attempt == 1 and not await self._probe_gateway_port():
                    logging.error(
                        "Impossibile raggiungere %s:%s. Verifica che IB Gateway/TWS sia avviato e che il firewall non blocchi la porta.",
                        self._host,
                        self._port,
                    )
                logging.info(f"Tentativo {attempt}/{self._connection_retries} di connessione a {self._host}:{self._port} (async)...")
                await self.ib.connectAsync(self._host, self._port, clientId=self._client_id, timeout=45)
                if self.ib.isConnected():
                    return True
            except (ConnectionRefusedError, asyncio.TimeoutError) as e:
                logging.error(
                    "Connessione fallita (%s): %r. Assicurarsi che IB Gateway/TWS sia in esecuzione e la porta aperta.",
                    type(e).__name__,
                    e,
                )
                if attempt < self._connection_retries:
                    await asyncio.sleep(self._retry_delay)
            except Exception as e:
                logging.critical(f"Errore di connessione imprevisto: {e}")
                break
        logging.critical("Tutti i tentativi di connessione sono falliti. L'agente si arresterà.")
        return False

    async def _probe_gateway_port(self, timeout: int = 3) -> bool:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=timeout,
            )
            writer.close()
            if hasattr(writer, "wait_closed"):
                await writer.wait_closed()
            return True
        except Exception as exc:
            logging.debug("Probe porta IB fallita: %s", exc)
            return False

    def disconnect(self):
        """Disconnette in modo pulito."""
        if self.ib.isConnected():
            logging.info("Disconnessione da IB Gateway in corso...")
            self.ib.disconnect()

    def is_connected(self) -> bool:
        """Controlla se la connessione è attiva."""
        return self.ib.isConnected()