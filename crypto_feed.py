"""Utility per ottenere snapshot di prezzo per crypto/forex da provider pubblici."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Mapping, Optional, Sequence

import httpx


@dataclass
class CryptoSnapshot:
    symbol: str
    last_price: float
    high_price: float
    low_price: float
    volume: float

    def to_context_line(self) -> str:
        return (
            f"{self.symbol}: last={self.last_price:.2f} high={self.high_price:.2f} "
            f"low={self.low_price:.2f} vol={self.volume:.2f}"
        )


class CryptoFeed:
    """Supporta provider pubblici per ottenere quote quasi real-time."""

    _BINANCE_URL = "https://api.binance.com/api/v3/ticker/24hr"

    def __init__(self, config: Mapping[str, str]):
        self.enabled = self._to_bool(config.get("enabled", "false"))
        self.provider = (config.get("provider", "binance") or "binance").strip().lower()
        default_symbol = (config.get("symbol", "BTCUSDT") or "BTCUSDT").strip().upper()
        self.symbols = self._parse_symbols(config.get("symbols"), default_symbol)
        self.label = (config.get("label", "CRYPTO FEED") or "CRYPTO FEED").strip().upper()

    @staticmethod
    def _to_bool(value: Optional[str], default: bool = False) -> bool:
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    async def get_snapshot(self) -> Optional[CryptoSnapshot]:
        snapshots = await self.get_snapshots()
        return snapshots[0] if snapshots else None

    async def get_snapshots(self) -> List[CryptoSnapshot]:
        if not self.enabled or not self.symbols:
            return []
        try:
            if self.provider == "binance":
                snapshots: List[CryptoSnapshot] = []
                for symbol in self.symbols:
                    snap = await self._fetch_binance(symbol)
                    if snap:
                        snapshots.append(snap)
                return snapshots
            logging.warning("Provider crypto '%s' non supportato.", self.provider)
        except httpx.HTTPError as exc:
            logging.warning("CryptoFeed/%s errore HTTP: %s", self.provider, exc)
        except Exception as exc:  # pragma: no cover - log difensivo
            logging.warning("CryptoFeed/%s errore inatteso: %s", self.provider, exc)
        return []

    async def _fetch_binance(self, symbol: str) -> Optional[CryptoSnapshot]:
        params = {"symbol": symbol}
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(self._BINANCE_URL, params=params)
            response.raise_for_status()
        data = response.json()
        return CryptoSnapshot(
            symbol=symbol,
            last_price=float(data.get("lastPrice", data.get("weightedAvgPrice", 0.0)) or 0.0),
            high_price=float(data.get("highPrice", 0.0) or 0.0),
            low_price=float(data.get("lowPrice", 0.0) or 0.0),
            volume=float(data.get("volume", 0.0) or 0.0),
        )

    def build_prompt_section(self, snapshots: Optional[Sequence[CryptoSnapshot]]) -> str:
        if not snapshots:
            return ""
        header = f"--- {self.label} (BINANCE) ---"
        lines = "\n".join(f"- {snap.to_context_line()}" for snap in snapshots)
        return f"{header}\n{lines}"

    @staticmethod
    def _parse_symbols(raw_value: Optional[str], fallback: str) -> List[str]:
        if raw_value:
            symbols = [token.strip().upper() for token in raw_value.split(",") if token.strip()]
            if symbols:
                return symbols
        return [fallback]
