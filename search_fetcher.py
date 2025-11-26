import logging
import os
from dataclasses import dataclass
from typing import List, Mapping, Optional

import httpx


@dataclass
class SearchInsight:
    """Informazione sintetica derivata da un motore di ricerca."""

    title: str
    snippet: str
    link: str
    source: str

    def to_line(self, max_chars: int = 200) -> str:
        snippet = (self.snippet or "").strip()
        if len(snippet) > max_chars:
            snippet = snippet[: max_chars - 3] + "..."
        return f"{self.source}: {self.title} -> {snippet} ({self.link})"


class SearchInsightFetcher:
    """Raccoglie insight macro/FX da SERPAPI, SERPER o Google CSE."""

    SERPAPI_URL = "https://serpapi.com/search"
    SERPER_URL = "https://google.serper.dev/news"
    GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, instrument: Optional[Mapping[str, str]] = None) -> None:
        self.instrument = dict(instrument or {})
        self.serpapi_key = os.getenv("SERPAPI_API_KEY", "").strip()
        self.serper_key = os.getenv("SERPER_API_KEY", "").strip()
        self.google_api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        self.google_cse_id = os.getenv("GOOGLE_CSE_ID", "").strip()

    def _compose_query(self) -> str:
        symbol = self.instrument.get("symbol", "")
        currency = self.instrument.get("currency", "")
        pair = f"{symbol}{currency}" if symbol and currency else ""
        pieces = [
            pair,
            f"{symbol}/{currency}" if symbol and currency else "",
            f"{symbol} forex" if symbol else "",
            f"{currency} macro" if currency else "",
            "central bank outlook",
        ]
        return " ".join(filter(None, pieces)) or "forex market"

    async def fetch_insights(self, limit: int = 5) -> List[SearchInsight]:
        query = self._compose_query()
        providers = [self._fetch_serpapi, self._fetch_serper, self._fetch_google_cse]
        for provider in providers:
            try:
                results = await provider(query, limit)
            except Exception as exc:  # pragma: no cover - log per debug, non critico
                logging.warning("Search provider %s fallito: %s", provider.__name__, exc)
                continue
            if results:
                logging.info("SearchInsights/%s ha restituito %s risultati.", provider.__name__, len(results))
                return results
        return []

    async def _fetch_serpapi(self, query: str, limit: int) -> List[SearchInsight]:
        if not self.serpapi_key:
            return []
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.serpapi_key,
            "tbm": "nws",
            "num": min(limit, 10),
            "hl": "en",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(self.SERPAPI_URL, params=params)
            response.raise_for_status()
        data = response.json()
        news = data.get("news_results") or data.get("organic_results") or []
        insights: List[SearchInsight] = []
        for item in news[:limit]:
            insights.append(
                SearchInsight(
                    title=item.get("title", ""),
                    snippet=item.get("snippet") or item.get("body", ""),
                    link=item.get("link", ""),
                    source=item.get("source") or item.get("source_url", "SERP"),
                )
            )
        return insights

    async def _fetch_serper(self, query: str, limit: int) -> List[SearchInsight]:
        if not self.serper_key:
            return []
        headers = {"X-API-KEY": self.serper_key}
        payload = {"q": query, "num": min(limit, 10)}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(self.SERPER_URL, json=payload, headers=headers)
            response.raise_for_status()
        data = response.json()
        news = data.get("news") or []
        insights: List[SearchInsight] = []
        for item in news[:limit]:
            insights.append(
                SearchInsight(
                    title=item.get("title", ""),
                    snippet=item.get("snippet") or item.get("summary", ""),
                    link=item.get("link", ""),
                    source=item.get("source") or item.get("date", "SERPER"),
                )
            )
        return insights

    async def _fetch_google_cse(self, query: str, limit: int) -> List[SearchInsight]:
        if not (self.google_api_key and self.google_cse_id):
            return []
        params = {
            "key": self.google_api_key,
            "cx": self.google_cse_id,
            "q": query,
            "num": min(limit, 10),
        }
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(self.GOOGLE_CSE_URL, params=params)
            response.raise_for_status()
        data = response.json()
        items = data.get("items") or []
        insights: List[SearchInsight] = []
        for item in items[:limit]:
            insights.append(
                SearchInsight(
                    title=item.get("title", ""),
                    snippet=item.get("snippet", ""),
                    link=item.get("link", ""),
                    source=item.get("displayLink", "GoogleCSE"),
                )
            )
        return insights

    def build_prompt_section(self, insights: List[SearchInsight]) -> str:
        if not insights:
            return ""
        lines = ["--- WEB INTEL (SEARCH) ---"]
        for insight in insights:
            lines.append(f"- {insight.to_line()}")
        return "\n".join(lines)