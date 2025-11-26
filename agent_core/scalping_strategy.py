"""Baseline scalping strategy utilities reused by the unified agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ib_async import Ticker


@dataclass(slots=True)
class StrategyPlan:
    entry: float
    take_profit: float
    stop_loss: float


@dataclass(slots=True)
class ScalpingStrategy:
    price_offset: float = 0.01
    take_profit: float = 0.03
    stop_loss: float = 0.02
    price_precision: int = 4

    def price_plan(self, ticker: Ticker) -> Optional[StrategyPlan]:
        bid = getattr(ticker, "bid", None)
        ask = getattr(ticker, "ask", None)
        if bid is None or ask is None:
            return None
        entry_price = max(0.01, round(bid - self.price_offset, self.price_precision))
        tp_price = round(entry_price + self.take_profit, self.price_precision)
        sl_price = round(max(0.001, entry_price - self.stop_loss), self.price_precision)
        if sl_price >= entry_price:
            sl_price = max(0.001, entry_price - 0.01)
        return StrategyPlan(entry=entry_price, take_profit=tp_price, stop_loss=sl_price)
