"""Helpers for building and qualifying IB contracts (async-friendly)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, MutableMapping, Sequence, cast

from ib_async import Contract, Forex, IB, Stock


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    sec_type: str
    exchange: str
    currency: str


def stock_contract(symbol: str, exchange: str = "SMART", currency: str = "USD") -> Contract:
    normalized_symbol = symbol.upper()
    contract: Contract = Stock(normalized_symbol, exchange, currency)
    if normalized_symbol in {"AAPL", "MSFT", "GOOG", "META", "AMZN", "NVDA"}:
        contract.primaryExchange = "NASDAQ"
    else:
        contract.primaryExchange = "NYSE"
    return contract


def forex_contract(pair: str, exchange: str = "IDEALPRO") -> Contract:
    cleaned = pair.replace("/", "").replace(".", "").upper()
    if len(cleaned) != 6:
        raise ValueError(f"Formato coppia FX non valido: {pair}")
    return Forex(cleaned, exchange)


def crypto_contract(symbol: str, exchange: str = "PAXOS", currency: str = "USD") -> Contract:
    contract = Contract()
    contract.symbol = symbol.upper()
    contract.secType = "CRYPTO"
    contract.exchange = exchange
    contract.currency = currency
    return contract


def detect_instrument_type(symbol: str) -> str:
    normalized = symbol.replace("/", ".").upper()
    parts = normalized.split(".")
    if len(parts) == 2 and all(len(part) == 3 and part.isalpha() for part in parts):
        return "forex"
    if normalized in {"BTC", "ETH", "DOGE"}:
        return "crypto"
    return "stock"


def _contract_from_spec(symbol: str, spec: Mapping[str, str]) -> Contract:
    sec_type = spec.get("sec_type", "STK").upper()
    target_symbol = spec.get("symbol", symbol).upper()
    exchange = spec.get("exchange", "SMART")
    currency = spec.get("currency", "USD")
    if sec_type == "CRYPTO":
        return crypto_contract(target_symbol, exchange=exchange, currency=currency)
    if sec_type in {"CASH", "FX", "FOREX"}:
        return forex_contract(target_symbol, exchange=exchange)
    contract = Contract()
    contract.symbol = target_symbol
    contract.secType = sec_type
    contract.exchange = exchange
    contract.currency = currency
    primary = spec.get("primary_exchange")
    if primary:
        contract.primaryExchange = primary
    return contract


async def qualify_contracts_async(
    ib: IB,
    symbols: Sequence[str],
    *,
    instrument_specs: Mapping[str, Mapping[str, str]] | None = None,
) -> Dict[str, Contract]:
    instrument_specs = instrument_specs or {}
    qualified: Dict[str, Contract] = {}
    for raw_symbol in symbols:
        symbol = raw_symbol.upper()
        spec = instrument_specs.get(symbol)
        if spec:
            contract = _contract_from_spec(symbol, spec)
        else:
            instrument_type = detect_instrument_type(symbol)
            if instrument_type == "forex":
                contract = forex_contract(symbol)
            elif instrument_type == "crypto":
                contract = crypto_contract(symbol)
            else:
                contract = stock_contract(symbol)
        raw_response = await ib.qualifyContractsAsync(contract)
        if raw_response is None:
            qualified_list: list[Contract] = []
        elif isinstance(raw_response, Contract):
            qualified_list = [raw_response]
        else:
            normalized = cast(Sequence[Contract | None], raw_response)
            qualified_list = [c for c in normalized if c is not None]

        if not qualified_list:
            raise RuntimeError(f"IB non ha restituito dettagli per {symbol}")
        qualified[symbol] = qualified_list[0]
    return qualified
