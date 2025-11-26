"""External intel helpers (NewsAPI, MarketAux) for quick diagnostics."""

from __future__ import annotations

import logging
from typing import Dict, List, Mapping, MutableMapping, Optional

import httpx

logger = logging.getLogger("agent_core.intel")


class ExternalIntelService:
    """Aggregates lightweight market headlines from third-party APIs."""

    def __init__(self, api_keys: Mapping[str, Optional[str]] | None = None) -> None:
        self.api_keys = dict(api_keys or {})

    async def snapshot(self, query: str = "stocks", limit: int = 3) -> Dict[str, List[str]]:
        summary: Dict[str, List[str]] = {}
        newsapi = await self._newsapi_headlines(query=query, limit=limit)
        if newsapi:
            summary["newsapi"] = newsapi
        marketaux = await self._marketaux_headlines(query=query, limit=limit)
        if marketaux:
            summary["marketaux"] = marketaux
        return summary

    async def _newsapi_headlines(self, query: str, limit: int) -> List[str]:
        api_key = self.api_keys.get("newsapi")
        if not api_key:
            return []
        params = {
            "q": query,
            "language": "en",
            "pageSize": limit,
            "sortBy": "publishedAt",
            "apiKey": api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get("https://newsapi.org/v2/top-headlines", params=params)
                response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            logger.warning("NewsAPI request failed: %s", exc)
            return []
        articles = payload.get("articles") or []
        return [article.get("title", "") for article in articles if article.get("title")]

    async def _marketaux_headlines(self, query: str, limit: int) -> List[str]:
        api_key = self.api_keys.get("marketaux")
        if not api_key:
            return []
        params = {
            "api_token": api_key,
            "language": "en",
            "limit": limit,
            "filter_entities": True,
        }
        if len(query) <= 6:
            params["symbols"] = query.upper()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get("https://api.marketaux.com/v1/news/all", params=params)
                response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            logger.warning("MarketAux request failed: %s", exc)
            return []
        data = payload.get("data") or []
        return [item.get("title", "") for item in data if item.get("title")]
