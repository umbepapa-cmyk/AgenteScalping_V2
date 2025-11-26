"""Utility per descrivere gli orari di apertura dei mercati rilevanti."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Iterable, List, Sequence

from zoneinfo import ZoneInfo


@dataclass
class MarketSession:
    name: str
    timezone: str
    open_time: time
    close_time: time
    days: Sequence[int]
    always_open: bool = False
    notes: str = ""

    def describe(self, now_utc: datetime) -> str:
        tz = ZoneInfo(self.timezone)
        local_now = now_utc.astimezone(tz)
        if self.always_open:
            return f"{self.name}: OPEN 24/7 ({local_now:%H:%M %Z}) {self.notes}".strip()

        status, next_event = self._status_and_next(local_now)
        appendix = f" | Next {next_event}" if next_event else ""
        return f"{self.name}: {status} ({local_now:%H:%M %Z}){appendix} {self.notes}".strip()

    def _status_and_next(self, local_now):
        weekday = local_now.weekday()
        tz = local_now.tzinfo
        open_dt = datetime.combine(local_now.date(), self.open_time, tzinfo=tz)
        close_dt = self._compute_close(open_dt)

        if weekday in self.days and open_dt <= local_now <= close_dt:
            return "OPEN", f"close {close_dt:%H:%M}"
        next_open = self._next_open_datetime(local_now)
        if next_open:
            return "CLOSED", f"open {next_open:%a %H:%M}"
        return "CLOSED", None

    def _next_open_datetime(self, local_now: datetime) -> datetime | None:
        tz = local_now.tzinfo
        for offset in range(0, 8):
            candidate = local_now + timedelta(days=offset)
            if candidate.weekday() not in self.days:
                continue
            open_dt = datetime.combine(candidate.date(), self.open_time, tzinfo=tz)
            if open_dt > local_now:
                return open_dt
        return None

    def _compute_close(self, open_dt: datetime) -> datetime:
        close_dt = datetime.combine(open_dt.date(), self.close_time, tzinfo=open_dt.tzinfo)
        if close_dt <= open_dt:
            close_dt += timedelta(days=1)
        return close_dt


def _weekday_range(start: int, end: int) -> List[int]:
    return list(range(start, end + 1))


MARKET_SESSIONS: Sequence[MarketSession] = [
    MarketSession(
        name="FX Sydney",
        timezone="Australia/Sydney",
        open_time=time(8, 0),
        close_time=time(17, 0),
        days=_weekday_range(0, 4),
        notes="(AUD/NZD focus)",
    ),
    MarketSession(
        name="FX Tokyo",
        timezone="Asia/Tokyo",
        open_time=time(9, 0),
        close_time=time(18, 0),
        days=_weekday_range(0, 4),
        notes="(JPY session)",
    ),
    MarketSession(
        name="FX London",
        timezone="Europe/London",
        open_time=time(8, 0),
        close_time=time(17, 0),
        days=_weekday_range(0, 4),
        notes="(EUR/GBP peak liquidity)",
    ),
    MarketSession(
        name="FX New York",
        timezone="America/New_York",
        open_time=time(8, 0),
        close_time=time(17, 0),
        days=_weekday_range(0, 4),
        notes="(USD macro releases)",
    ),
    MarketSession(
        name="CME FX Futures",
        timezone="America/Chicago",
        open_time=time(7, 0),
        close_time=time(16, 0),
        days=_weekday_range(0, 4),
    ),
    MarketSession(
        name="IB PAXOS Crypto",
        timezone="America/New_York",
        open_time=time(0, 0),
        close_time=time(23, 59),
        days=_weekday_range(0, 6),
        always_open=True,
    ),
    MarketSession(
        name="Binance Spot",
        timezone="UTC",
        open_time=time(0, 0),
        close_time=time(23, 59),
        days=_weekday_range(0, 6),
        always_open=True,
    ),
]


def build_market_hours_context(now_utc: datetime | None = None) -> str:
    """Restituisce una stringa pronta per il prompt con gli status dei mercati."""
    reference = now_utc or datetime.now(timezone.utc)
    lines = [session.describe(reference) for session in MARKET_SESSIONS]
    header = "--- MARKET HOURS STATUS ---"
    return f"{header}\n" + "\n".join(f"- {line}" for line in lines)
