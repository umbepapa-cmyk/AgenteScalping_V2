import argparse
import asyncio
import configparser
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Mapping, Sequence

import nest_asyncio
from dotenv import load_dotenv
from ib_async import util

from agent_core import (
    ExternalIntelService,
    ScalpingStrategy,
    TradeLogger,
    qualify_contracts_async,
)
from ai_analyst import AiAnalyst
from connection_manager import ConnectionManager


DEFAULT_CONFIG = Path(__file__).parent / "config.ini"
DEFAULT_LOG_FILE = Path(__file__).parent / "trading_agent.log"
DEFAULT_TRADE_LOG = Path(__file__).parent / "logs" / "trade_log.csv"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI-driven IB scalping agent")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Percorso file config.ini")
    parser.add_argument("--env-file", type=Path, help="Percorso opzionale al file .env")
    parser.add_argument("--log-level", default=os.getenv("TRADING_LOG_LEVEL", "INFO"), help="Livello di log (INFO/DEBUG/...)")
    parser.add_argument("--log-file", type=Path, default=DEFAULT_LOG_FILE, help="File log principale")
    parser.add_argument("--trade-log", type=Path, default=DEFAULT_TRADE_LOG, help="File CSV per ordini/fill")
    parser.add_argument("--dry-run", action="store_true", help="Forza la modalità simulata (nessun ordine inviato)")
    parser.add_argument("--force-live", action="store_true", help="Forza l'invio ordini anche se auto_trade è False")
    parser.add_argument("--intel-test", action="store_true", help="Interroga NewsAPI/MarketAux e termina")
    parser.add_argument("--intel-query", default="stocks", help="Keyword per --intel-test")
    parser.add_argument("--ib-host", help="Override host IB (usa per connettersi al server)")
    parser.add_argument("--ib-port", type=int, help="Override port IB (usa per connettersi al server)")
    parser.add_argument("--test-trades", type=int, default=0, help="Numero di esecuzioni paper da completare prima di fermare il trading (0 = disabilitato)")
    parser.add_argument("--test-duration", type=int, default=0, help="Durata massima del test in secondi prima di fermare il trading (0 = disabilitato)")
    return parser


def configure_logging(level_name: str, logfile: Path) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    handlers = [logging.StreamHandler()]
    if logfile:
        logfile.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(logfile, encoding="utf-8"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )
    util.logToConsole(logging.WARNING)


async def run_intel_test(query: str, api_keys: Mapping[str, str | None]) -> None:
    service = ExternalIntelService({
        "newsapi": api_keys.get("NEWSAPI_KEY"),
        "marketaux": api_keys.get("MARKETAUX_API_KEY"),
    })
    summary = await service.snapshot(query=query)
    if not summary:
        logging.warning("Nessuna headline recuperata. Verificare API key o limiti di utilizzo.")
        return
    for provider, headlines in summary.items():
        logging.info("%s headlines:", provider.upper())
        for title in headlines:
            logging.info("  - %s", title)


def _build_instrument_spec(strategy_config: configparser.SectionProxy) -> Dict[str, str]:
    return {
        "symbol": strategy_config.get("symbol", "EUR"),
        "sec_type": strategy_config.get("sec_type", "CASH"),
        "exchange": strategy_config.get("exchange", "IDEALPRO"),
        "currency": strategy_config.get("currency", "USD"),
    }


def _cancel_stale_orders(ib, allowed_conids: Sequence[int], client_id: int) -> None:
    allowed = set(allowed_conids)
    cancelled = 0
    for trade in list(ib.openTrades()):
        contract = getattr(trade, "contract", None)
        order = getattr(trade, "order", None)
        if not contract or not order:
            continue
        if order.clientId != client_id:
            continue
        if contract.conId in allowed:
            continue
        ib.cancelOrder(order)
        cancelled += 1
    if cancelled:
        logging.info("Cancellati %s ordini legacy", cancelled)


async def run_agent(args: argparse.Namespace) -> None:
    if not args.config.exists():
        logging.critical("Config %s non trovato", args.config)
        return

    config = configparser.ConfigParser()
    config.read(args.config)
    if "IB" not in config or "STRATEGY" not in config:
        logging.critical("Config mancante delle sezioni obbligatorie [IB]/[STRATEGY]")
        return

    ib_config = config["IB"]
    strategy_config = config["STRATEGY"]
    news_config = config["NEWS"] if config.has_section("NEWS") else None
    crypto_feed_config = config["CRYPTO_FEED"] if config.has_section("CRYPTO_FEED") else None
    forex_feed_config = config["FOREX_FEED"] if config.has_section("FOREX_FEED") else None

    trading_env = ib_config.get("environment", "PAPER").upper()
    if trading_env not in {"PAPER", "LIVE"}:
        logging.warning("Ambiente IB '%s' non riconosciuto, uso PAPER.", trading_env)
        trading_env = "PAPER"
    default_port = 7497 if trading_env == "PAPER" else 7496
    host = args.ib_host or ib_config.get("host", "127.0.0.1")
    port = args.ib_port or ib_config.getint("port", default_port)
    client_id = ib_config.getint("client_id", 25)
    account = ib_config.get("account")
    logging.info("Configurazione IB: env=%s host=%s port=%s client_id=%s", trading_env, host, port, client_id)

    conn_manager = ConnectionManager(host=host, port=port, client_id=client_id)
    trade_logger = TradeLogger(args.trade_log)

    instrument_spec = _build_instrument_spec(strategy_config)
    symbol_alias = instrument_spec["symbol"]
    symbol_key = symbol_alias.upper()
    instrument_spec["symbol"] = symbol_key
    instrument_info = {
        "symbol": symbol_alias,
        "currency": instrument_spec["currency"],
        "sec_type": instrument_spec["sec_type"],
    }

    ai_analyst = AiAnalyst(
        strategy_version=strategy_config.get("version", "default"),
        news_config=news_config,
        instrument=instrument_info,
        crypto_feed_config=crypto_feed_config,
        forex_feed_config=forex_feed_config,
    )

    auto_trade = strategy_config.getboolean("auto_trade", fallback=False)
    if args.dry_run and args.force_live:
        raise SystemExit("--dry-run e --force-live non possono coesistere")
    if args.dry_run:
        auto_trade = False
    if args.force_live:
        auto_trade = True

    trade_quantity = strategy_config.getfloat("quantity", fallback=0.0)
    atr_tp_multiplier = strategy_config.getfloat("atr_tp_multiplier", fallback=1.5)
    atr_sl_multiplier = strategy_config.getfloat("atr_sl_multiplier", fallback=1.0)
    configured_tp = strategy_config.getfloat("take_profit_pips", fallback=0.0)
    configured_sl = strategy_config.getfloat("stop_loss_pips", fallback=0.0)
    price_precision = strategy_config.getint("price_precision", fallback=5)
    scalping_strategy = ScalpingStrategy(
        price_offset=strategy_config.getfloat("scalper_price_offset", fallback=0.0005),
        take_profit=configured_tp or 0.0010,
        stop_loss=configured_sl or 0.0005,
        price_precision=price_precision,
    )

    max_concurrent_trades = strategy_config.getint("max_concurrent_trades", fallback=1)
    cooldown_seconds = strategy_config.getint("cooldown_seconds", fallback=60)
    max_hold_seconds = strategy_config.getint("max_hold_seconds", fallback=180)
    min_atr_threshold = strategy_config.getfloat("min_atr", fallback=0.0)
    min_momentum_threshold = strategy_config.getfloat("min_momentum", fallback=0.0)
    outside_rth = strategy_config.getboolean("outside_rth", fallback=False)

    active_trade_slots = 0
    last_trade_timestamp = 0.0
    contract = None
    bars_handle = None
    bars_callback = None
    ticker = None
    exec_handler_registered = False
    # Test control counters
    completed_trades = 0
    test_target = max(0, int(getattr(args, "test_trades", 0) or 0))
    test_duration = max(0, int(getattr(args, "test_duration", 0) or 0))
    test_timeout_task = None

    def _handle_execution(trade, fill) -> None:
        execution = getattr(fill, "execution", None)
        contract = getattr(trade, "contract", None)
        if not execution or not contract:
            return
        pnl = trade_logger.log_execution(
            symbol=contract.symbol,
            action=execution.side,
            quantity=float(execution.shares),
            price=float(execution.price),
            note=f"execId={execution.execId}",
        )
        logging.info(
            "Execution %s %s qty=%s price=%s pnl=%.5f",
            execution.side,
            contract.symbol,
            execution.shares,
            execution.price,
            pnl,
        )
        nonlocal completed_trades, auto_trade
        # increment completed trades counter and check test target
        try:
            completed_trades += 1
        except Exception:
            pass
        if test_target > 0 and completed_trades >= test_target:
            if auto_trade:
                auto_trade = False
                logging.info("Test target raggiunto (%s esecuzioni). Disabilito ulteriori invii di ordini ma mantengo la connessione.", completed_trades)

    async def release_trade_slot(delay_seconds: int):
        nonlocal active_trade_slots
        await asyncio.sleep(max(1, delay_seconds))
        active_trade_slots = max(0, active_trade_slots - 1)
        logging.debug("Slot trading liberato automaticamente")

    def place_bracket(decision: str, price: float, metrics: Mapping[str, float], reason: str) -> None:
        nonlocal contract
        atr_value = float(metrics.get("atr", 0.0) or 0.0)
        dynamic_tp = atr_value * atr_tp_multiplier if atr_value > 0 else 0.0
        dynamic_sl = atr_value * atr_sl_multiplier if atr_value > 0 else 0.0
        tp_delta = max(configured_tp, dynamic_tp)
        sl_delta = max(configured_sl, dynamic_sl)

        plan = scalping_strategy.price_plan(ticker) if ticker else None
        if (tp_delta <= 0 or sl_delta <= 0) and plan:
            tp_delta = abs(plan.take_profit - plan.entry)
            sl_delta = abs(plan.entry - plan.stop_loss)
        if tp_delta <= 0 or sl_delta <= 0:
            logging.warning("Impossibile calcolare TP/SL validi, ordine ignorato")
            return

        entry_price = round(price, price_precision)
        if decision == "BUY":
            take_price = round(entry_price + tp_delta, price_precision)
            stop_price = round(entry_price - sl_delta, price_precision)
            action = "BUY"
        else:
            take_price = round(entry_price - tp_delta, price_precision)
            stop_price = round(entry_price + sl_delta, price_precision)
            action = "SELL"

        trade_logger.log_order_submission(
            symbol=symbol_key,
            action=decision,
            quantity=trade_quantity,
            price=entry_price,
            note=f"reason={reason} ATR={atr_value:.5f}",
        )

        if not auto_trade:
            logging.info("AUTO_TRADE disabilitato: segnale %s loggato ma non inviato.", decision)
            return

        if contract is None:
            logging.error("Contratto non disponibile, impossibile inviare ordini")
            return

        parent, take_profit_order, stop_order = util.bracketOrder(
            action=action,
            quantity=trade_quantity,
            limitPrice=entry_price,
            takeProfitPrice=take_price,
            stopLossPrice=stop_price,
        )
        orders = [parent, take_profit_order, stop_order]
        for order in orders:
            order.outsideRth = outside_rth
            if account:
                order.account = account
        logging.info(
            "Invio bracket %s qty=%.4f entry=%.5f tp=%.5f sl=%.5f (ATR=%.5f)",
            action,
            trade_quantity,
            entry_price,
            take_price,
            stop_price,
            atr_value,
        )
        for order in orders:
            conn_manager.ib.placeOrder(contract, order)

    try:
        if not await conn_manager.connect():
            return
        logging.info("Connessione IB stabilita (paper=%s)", trading_env == "PAPER")
        try:
            conn_manager.ib.reqMarketDataType(1)
            logging.info("Market data type impostato su REAL-TIME")
        except Exception as exc:
            logging.warning("Real-time non disponibile (%s), fallback a delayed", exc)
            conn_manager.ib.reqMarketDataType(3)

        contracts = await qualify_contracts_async(
            conn_manager.ib,
            [symbol_key],
            instrument_specs={symbol_key: instrument_spec},
        )
        contract = contracts[symbol_key]
        logging.info("Contratto qualificato: %s", contract.localSymbol)
        ticker = conn_manager.ib.reqMktData(contract, "", False, False)
        _cancel_stale_orders(conn_manager.ib, [contract.conId], client_id)

        if not exec_handler_registered:
            conn_manager.ib.execDetailsEvent += _handle_execution
            exec_handler_registered = True

        # start a timeout watcher if requested: after test_duration seconds disable trading
        async def _test_timeout_watcher(sec: int):
            nonlocal auto_trade
            try:
                await asyncio.sleep(sec)
                if auto_trade:
                    auto_trade = False
                    logging.info("Test duration scaduta (%ss). Disabilito ulteriori invii di ordini ma mantengo la connessione.", sec)
            except asyncio.CancelledError:
                return

        if test_duration > 0:
            test_timeout_task = asyncio.create_task(_test_timeout_watcher(test_duration))

        async def handle_new_bar(symbol: str, bar_snapshot: Sequence) -> None:
            nonlocal last_trade_timestamp, active_trade_slots
            def _normalize_bar(bar) -> dict:
                # Try attribute access first
                def _get_attr(b, *names):
                    for n in names:
                        v = getattr(b, n, None)
                        if v is not None:
                            return v
                    return None

                open_v = _get_attr(bar, "open", "Open", "o", "O")
                high_v = _get_attr(bar, "high", "High", "h", "H")
                low_v = _get_attr(bar, "low", "Low", "l", "L")
                close_v = _get_attr(bar, "close", "Close", "c", "C", "price")

                # Fallback for sequence-like bars: [time, open, high, low, close, ...]
                if open_v is None or high_v is None or low_v is None or close_v is None:
                    try:
                        if isinstance(bar, (list, tuple)) and len(bar) >= 5:
                            # assume layout: [time, open, high, low, close, ...]
                            open_v = open_v or bar[1]
                            high_v = high_v or bar[2]
                            low_v = low_v or bar[3]
                            close_v = close_v or bar[4]
                    except Exception:
                        pass

                # Final numeric coercion with safe defaults
                def _to_float(x):
                    try:
                        return float(x)
                    except Exception:
                        return 0.0

                return {
                    "open": _to_float(open_v),
                    "high": _to_float(high_v),
                    "low": _to_float(low_v),
                    "close": _to_float(close_v),
                }

            last_bar_raw = bar_snapshot[-1]
            last = _normalize_bar(last_bar_raw)
            logging.info(
                "Nuova barra %s | O=%.5f H=%.5f L=%.5f C=%.5f",
                symbol,
                last["open"],
                last["high"],
                last["low"],
                last["close"],
            )
            decision, reason = await ai_analyst.get_trading_decision(bar_snapshot)
            logging.info("Decisione AI per %s: %s (%s)", symbol, decision, reason)
            metrics = dict(getattr(ai_analyst, "last_metrics", {}))

            if decision not in {"BUY", "SELL"}:
                return
            qty = trade_quantity
            if qty <= 0:
                logging.warning("Quantità di strategia non valida (<=0), segnale ignorato")
                return
            atr_value = float(metrics.get("atr", 0.0) or 0.0)
            momentum_value = float(metrics.get("momentum", 0.0) or 0.0)
            loop = asyncio.get_running_loop()
            now = loop.time()
            if atr_value < min_atr_threshold:
                logging.info("Segnale %s ignorato: ATR %.5f < soglia %.5f", decision, atr_value, min_atr_threshold)
                return
            if abs(momentum_value) < min_momentum_threshold:
                logging.info(
                    "Segnale %s ignorato: momentum %.5f < soglia %.5f",
                    decision,
                    momentum_value,
                    min_momentum_threshold,
                )
                return
            if active_trade_slots >= max(1, max_concurrent_trades):
                logging.info(
                    "Segnale %s ignorato: slot occupati (%s/%s)",
                    decision,
                    active_trade_slots,
                    max_concurrent_trades,
                )
                return
            if (now - last_trade_timestamp) < cooldown_seconds:
                remaining = cooldown_seconds - (now - last_trade_timestamp)
                logging.info("Segnale %s ignorato: cooldown %.1fs", decision, remaining)
                return

            place_bracket(decision, float(last["close"]), metrics, reason)
            last_trade_timestamp = now
            active_trade_slots += 1
            asyncio.create_task(release_trade_slot(max_hold_seconds))

        def on_bar_update(bars, has_new_bar: bool) -> None:
            if not has_new_bar:
                return
            snapshot = list(bars)
            symbol = getattr(bars.contract, "symbol", "UNKNOWN")
            asyncio.create_task(handle_new_bar(symbol, snapshot))

        bars_handle = conn_manager.ib.reqRealTimeBars(contract, 5, "MIDPOINT", False)
        bars_callback = on_bar_update
        bars_handle.updateEvent += bars_callback
        logging.info(
            "Agente avviato. Auto-trade=%s | quantity=%.4f | max_trades=%s",
            auto_trade,
            trade_quantity,
            max_concurrent_trades,
        )
        await asyncio.Event().wait()

    except (KeyboardInterrupt, asyncio.CancelledError):
        logging.info("Richiesta di arresto ricevuta (Ctrl+C)")
    finally:
        logging.info("Arresto dell'agente in corso...")
        if bars_handle is not None and bars_callback is not None:
            try:
                bars_handle.updateEvent -= bars_callback
                conn_manager.ib.cancelRealTimeBars(bars_handle)
            except Exception:
                pass
        if ticker is not None and contract is not None:
            try:
                conn_manager.ib.cancelMktData(contract)
            except Exception:
                pass
        if exec_handler_registered:
            try:
                conn_manager.ib.execDetailsEvent -= _handle_execution
            except Exception:
                pass
        if conn_manager.is_connected():
            conn_manager.ib.reqGlobalCancel()
            await asyncio.sleep(1)
            conn_manager.disconnect()
        logging.info("Agente arrestato correttamente.")


async def entrypoint(args: argparse.Namespace) -> None:
    api_keys = {
        "NEWSAPI_KEY": os.getenv("NEWSAPI_KEY"),
        "MARKETAUX_API_KEY": os.getenv("MARKETAUX_API_KEY"),
    }
    if args.intel_test:
        await run_intel_test(args.intel_query, api_keys)
        return
    await run_agent(args)


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    if args.env_file and args.env_file.exists():
        load_dotenv(args.env_file)
    else:
        load_dotenv()
    if os.name == "nt" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    nest_asyncio.apply()
    configure_logging(args.log_level, args.log_file)
    try:
        asyncio.run(entrypoint(args))
    except (KeyboardInterrupt, SystemExit):
        logging.info("Programma terminato dall'utente")


if __name__ == "__main__":
    main()
