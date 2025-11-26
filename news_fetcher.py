import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx


@dataclass
class NewsArticle:
    """Rappresenta un articolo di news normalizzato."""

    title: str
    description: str
    source: str
    published_at: str
    url: str

    def short_line(self, max_chars: int = 160) -> str:
        snippet = (self.description or "").strip()
        if len(snippet) > max_chars:
            snippet = snippet[: max_chars - 3] + "..."
        return f"[{self.published_at}] {self.title} ({self.source}) - {snippet}"


class NewsFetcher:
    """Gestisce il download e la cache di news finanziarie/geopolitiche."""

    _NEWSAPI_URL = "https://newsapi.org/v2/everything"
    _MARKETAUX_URL = "https://api.marketaux.com/v1/news/all"

    def __init__(
        self,
        *,
        enabled: bool,
        api_key_env: str,
        provider: str = "newsapi",
        query: str,
        language: str,
        max_articles: int,
        refresh_minutes: int,
        lookback_minutes: int,
    ) -> None:
        self._enabled = enabled
        self._api_key_env = api_key_env or "NEWSAPI_KEY"
        self._query = query or "forex"
        self._language = language or "en"
        self._max_articles = max(1, min(max_articles, 20))
        self._refresh = max(1, refresh_minutes)
        self._lookback = max(15, lookback_minutes)
        self._cache: List[NewsArticle] = []
        self._cache_ts: Optional[datetime] = None
        provider_name = (provider or "newsapi").strip().lower()
        if provider_name not in {"newsapi", "marketaux"}:
            logging.warning("Provider news '%s' non supportato, fallback a NewsAPI.", provider)
            provider_name = "newsapi"
        self._provider = provider_name

    def _load_api_key(self) -> Optional[str]:
        api_key = os.getenv(self._api_key_env, "").strip()
        if not api_key:
            logging.debug("NEWSAPI_KEY non presente in ambiente: %s", self._api_key_env)
            return None
        return api_key

    def _cache_fresh(self) -> bool:
        if not self._cache_ts:
            return False
        return datetime.now(timezone.utc) - self._cache_ts < timedelta(minutes=self._refresh)

    async def get_recent_headlines(self) -> List[NewsArticle]:
        """Restituisce una lista di articoli recenti (usa cache quando possibile)."""

        if not self._enabled:
            return []
        api_key = self._load_api_key()
        if not api_key:
            logging.warning("NewsFetcher attivo ma nessuna chiave API '%s' trovata.", self._api_key_env)
            return []
        if self._cache_fresh():
            return self._cache

        try:
            normalized = await self._fetch_articles(api_key)
        except httpx.HTTPError as exc:
            logging.error("Errore durante il download delle news: %s", exc)
            return []

        self._cache = normalized
        self._cache_ts = datetime.now(timezone.utc)
        logging.info("NewsFetcher ha recuperato %s articoli.", len(normalized))
        return normalized

    async def _fetch_articles(self, api_key: str) -> List[NewsArticle]:
        if self._provider == "marketaux":
            return await self._fetch_marketaux(api_key)
        return await self._fetch_newsapi(api_key)

    async def _fetch_newsapi(self, api_key: str) -> List[NewsArticle]:
        params = {
            "q": self._query,
            "language": self._language,
            "pageSize": self._max_articles,
            "sortBy": "publishedAt",
            "from": (datetime.now(timezone.utc) - timedelta(minutes=self._lookback)).isoformat(),
        }
        headers = {"X-Api-Key": api_key}
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(self._NEWSAPI_URL, params=params, headers=headers)
            response.raise_for_status()
        data = response.json()
        articles = data.get("articles", []) if isinstance(data, dict) else []
        normalized: List[NewsArticle] = []
        for raw in articles:
            normalized.append(
                NewsArticle(
                    title=raw.get("title", "Senza titolo"),
                    description=raw.get("description") or raw.get("content", ""),
                    source=(raw.get("source") or {}).get("name", ""),
                    published_at=raw.get("publishedAt", ""),
                    url=raw.get("url", ""),
                )
            )
        return normalized

    async def _fetch_marketaux(self, api_key: str) -> List[NewsArticle]:
        params = {
            "api_token": api_key,
            "language": self._language,
            "limit": self._max_articles,
            "filter_entities": "true",
            "published_after": (datetime.now(timezone.utc) - timedelta(minutes=self._lookback)).isoformat(),
        }
        if self._query:
            params["search"] = self._query
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(self._MARKETAUX_URL, params=params)
            response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            data = {}
        articles = data.get("data", [])
        normalized: List[NewsArticle] = []
        for raw in articles:
            normalized.append(
                NewsArticle(
                    title=raw.get("title", "Senza titolo"),
                    description=raw.get("description") or raw.get("snippet") or raw.get("summary", ""),
                    source=raw.get("source") or raw.get("source_name", "MarketAux"),
                    published_at=raw.get("published_at", raw.get("publishedAt", "")),
                    url=raw.get("url", ""),
                )
            )
        return normalized

    def build_prompt_section(self, articles: List[NewsArticle]) -> str:
        if not articles:
            return ""
        lines = ["--- ULTIME NEWS FINANZIARIE ---"]
        for art in articles:
            lines.append(f"- {art.short_line()}")
        return "\n".join(lines)