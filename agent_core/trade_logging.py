"""CSV-based trade logging utilities shared by the agent."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, Tuple

_NUMBER_FORMAT = "{:.5f}"


class TradeLogger:
    """Persists order submissions and fills to a CSV log."""

    def __init__(self, log_path: Path | str) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._positions: Dict[str, Tuple[float, float]] = {}
        if not self.log_path.exists():
            self._write_header()

    def log_order_submission(
        self,
        *,
        symbol: str,
        action: str,
        quantity: float,
        price: float | None,
        note: str = "",
    ) -> None:
        self._write_row(
            event="ORDER",
            symbol=symbol,
            action=action,
            quantity=quantity,
            price=price,
            pnl=None,
            note=note,
        )

    def log_execution(
        self,
        *,
        symbol: str,
        action: str,
        quantity: float,
        price: float,
        note: str = "",
    ) -> float:
        normalized_action = self._normalize_action(action)
        with self._lock:
            pnl = self._update_positions(symbol, normalized_action, quantity, price)
            self._write_row_unlocked(
                event="FILL",
                symbol=symbol,
                action=normalized_action,
                quantity=quantity,
                price=price,
                pnl=pnl,
                note=note,
            )
        return pnl

    def _write_header(self) -> None:
        header = ["timestamp", "event", "symbol", "action", "quantity", "price", "pnl", "notes"]
        with self.log_path.open("w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(header)

    def _write_row(
        self,
        *,
        event: str,
        symbol: str,
        action: str,
        quantity: float,
        price: float | None,
        pnl: float | None,
        note: str,
    ) -> None:
        with self._lock:
            self._write_row_unlocked(
                event=event,
                symbol=symbol,
                action=action,
                quantity=quantity,
                price=price,
                pnl=pnl,
                note=note,
            )

    def _write_row_unlocked(
        self,
        *,
        event: str,
        symbol: str,
        action: str,
        quantity: float,
        price: float | None,
        pnl: float | None,
        note: str,
    ) -> None:
        timestamp = datetime.utcnow().isoformat()
        formatted_price = "" if price is None else _NUMBER_FORMAT.format(price)
        formatted_pnl = "" if pnl is None else _NUMBER_FORMAT.format(pnl)
        row = [
            timestamp,
            event,
            symbol,
            action,
            _NUMBER_FORMAT.format(quantity),
            formatted_price,
            formatted_pnl,
            note,
        ]
        with self.log_path.open("a", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(row)

    def _update_positions(self, symbol: str, action: str, quantity: float, price: float) -> float:
        qty, avg_price = self._positions.get(symbol, (0.0, 0.0))
        if action == "BUY":
            new_qty = qty + quantity
            if new_qty <= 0:
                avg_price = 0.0
            else:
                avg_price = ((qty * avg_price) + (quantity * price)) / new_qty
            self._positions[symbol] = (new_qty, avg_price)
            return 0.0
        if action == "SELL":
            pnl = 0.0 if qty <= 0 else (price - avg_price) * quantity
            new_qty = qty - quantity
            if new_qty <= 0:
                self._positions[symbol] = (0.0, 0.0)
            else:
                self._positions[symbol] = (new_qty, avg_price)
            return pnl
        return 0.0

    @staticmethod
    def _normalize_action(action: str) -> str:
        value = action.upper()
        if value in {"BOT", "BUY"}:
            return "BUY"
        if value in {"SLD", "SELL"}:
            return "SELL"
        return value
