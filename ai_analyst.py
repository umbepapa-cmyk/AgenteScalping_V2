import json
import logging
import os
from pathlib import Path
from statistics import mean, pstdev
from typing import List, Mapping, Optional, Sequence, Tuple

# Disabilita la telemetria di Chroma prima del relativo import per evitare chiamate HTTPS esterne
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
os.environ.setdefault("CHROMA_TELEMETRY_ENABLED", "False")

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import chromadb
except ImportError:
    chromadb = None

try:
    from langchain.prompts import PromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.runnables import RunnableLambda, RunnableParallel
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    PromptTemplate = None
    StrOutputParser = None
    RunnableLambda = None
    RunnableParallel = None
    ChatGoogleGenerativeAI = None

from news_fetcher import NewsFetcher
from search_fetcher import SearchInsightFetcher
from crypto_feed import CryptoFeed
from market_hours import build_market_hours_context


class AiAnalyst:
    """
    Classe responsabile dell'analisi dei dati di mercato e della generazione
    di decisioni di trading (BUY, SELL, HOLD).
    """
    def __init__(
        self,
        strategy_version: str = "v1",
        model_name: str = "gemini-1.5-pro",
        news_config: Optional[Mapping[str, str]] = None,
        instrument: Optional[Mapping[str, str]] = None,
        crypto_feed_config: Optional[Mapping[str, str]] = None,
        forex_feed_config: Optional[Mapping[str, str]] = None,
    ):
        """
        Inizializza l'analista.
        
        Args:
            strategy_version (str): La versione della strategia da utilizzare,
                                    caricata dalla configurazione.
        """
        if load_dotenv:
            load_dotenv()
        self.strategy_version = strategy_version
        self.model_name = model_name
        self.vector_store = None
        self.knowledge_status = "Vector store non disponibile"
        self._init_vector_store()
        self._init_llm_chain()
        self.instrument = dict(instrument) if instrument else {}
        self.news_fetcher = self._init_news_fetcher(news_config, self.instrument)
        self.search_fetcher = SearchInsightFetcher(self.instrument)
        self.crypto_feed = self._init_market_feed(crypto_feed_config, default_label="CRYPTO FEED")
        self.forex_feed = self._init_market_feed(forex_feed_config, default_label="FOREX FEED")
        self.last_metrics: Mapping[str, float] = {}
        logging.info("Analista AI inizializzato (strategy=%s, llm=%s)",
                     self.strategy_version,
                     "ON" if self.llm_chain else "OFF")

    async def get_trading_decision(self, bars: Sequence) -> Tuple[str, str]:
        """
        Analizza i dati delle barre e restituisce una decisione di trading.
        
        Questa è la funzione principale che verrà estesa con la logica AI.
        Per ora, implementa una logica di fallback di base.

        Args:
            bars (list): Una lista di barre di dati di mercato.

        Returns:
            tuple: Una tupla contenente la decisione ('BUY', 'SELL', 'HOLD')
                   e una breve motivazione.
        """
        closes = self._extract_closes(bars)
        if len(closes) < 5:
            return "HOLD", "Serie di barre insufficiente (<5)."
        base_decision, base_reason, metrics = self._technical_signal(bars, closes)
        self.last_metrics = metrics
        if not self.llm_chain:
            return base_decision, base_reason

        technical_context = self._build_context(bars, closes, base_reason, metrics)
        knowledge_payload = self._fetch_knowledge(base_reason)
        knowledge_context = self._decorate_knowledge(knowledge_payload)
        news_context = await self._build_news_context()
        search_context = await self._build_search_context()
        crypto_context = await self._build_crypto_context()
        forex_context = await self._build_forex_context()
        market_hours_context = self._build_market_hours_context()
        try:
            llm_payload = {
                "strategy_version": self.strategy_version,
                "signal_context": technical_context,
                "knowledge": knowledge_context or "N/A",
                "news_context": news_context or "N/A",
                "search_context": search_context or "N/A",
                "crypto_context": crypto_context or "N/A",
                "forex_context": forex_context or "N/A",
                "market_hours": market_hours_context or "N/A",
            }
            response = await self.llm_chain.ainvoke(llm_payload)
            parsed = self._parse_llm_response(response)
            if parsed:
                return parsed["decision"], parsed["reason"]
        except Exception as exc:
            logging.warning("LLM non disponibile, uso fallback. Dettagli: %s", exc)
        return base_decision, base_reason

    def _extract_closes(self, bars: Sequence) -> List[float]:
        closes: List[float] = []
        for bar in bars:
            close = getattr(bar, "close", None)
            if close is not None:
                closes.append(close)
        return closes

    def _technical_signal(self, bars: Sequence, closes: Sequence[float]) -> Tuple[str, str, Mapping[str, float]]:
        short_ma = mean(closes[-5:])
        micro_ma = mean(closes[-3:]) if len(closes) >= 3 else closes[-1]
        long_ma = mean(closes[-20:]) if len(closes) >= 20 else short_ma
        momentum = closes[-1] - closes[-2]
        micro_trend = closes[-1] - closes[-3] if len(closes) >= 3 else momentum
        spread = short_ma - long_ma
        atr = self._average_true_range(bars)
        volatility = pstdev(closes[-10:]) if len(closes) >= 10 else abs(momentum)
        score = (spread * 2) + (momentum * 3) + (micro_trend * 3)

        decision = "HOLD"
        reason = f"Bias neutro | ΔMA={spread:.5f} Momentum={momentum:.5f} ATR={atr:.5f}"
        if spread > 0 and momentum > 0 and micro_trend > 0:
            decision = "BUY"
            reason = (
                f"Bias rialzista: shortMA {short_ma:.5f} > longMA {long_ma:.5f}, "
                f"momentum {momentum:.5f}, micro trend {micro_trend:.5f}, ATR {atr:.5f}."
            )
        elif spread < 0 and momentum < 0 and micro_trend < 0:
            decision = "SELL"
            reason = (
                f"Bias ribassista: shortMA {short_ma:.5f} < longMA {long_ma:.5f}, "
                f"momentum {momentum:.5f}, micro trend {micro_trend:.5f}, ATR {atr:.5f}."
            )

        metrics = {
            "short_ma": short_ma,
            "micro_ma": micro_ma,
            "long_ma": long_ma,
            "momentum": momentum,
            "micro_trend": micro_trend,
            "atr": atr,
            "volatility": volatility,
            "score": score,
        }
        return decision, reason, metrics

    def _build_context(self, bars: Sequence, closes: Sequence[float], reason: str, metrics: Mapping[str, float]) -> str:
        last_bar = bars[-1]
        high = getattr(last_bar, "high", None)
        low = getattr(last_bar, "low", None)
        volume = getattr(last_bar, "volume", None)
        return (
            f"Ultima chiusura: {closes[-1]:.5f}\n"
            f"Motivazione tecnica: {reason}\n"
            f"ATR: {metrics.get('atr', 0.0):.5f} | Momentum: {metrics.get('momentum', 0.0):.5f}\n"
            f"High/Low: {high}, {low} | Volume: {volume}\n"
            f"Numero barre disponibili: {len(closes)}"
        )

    def _average_true_range(self, bars: Sequence, period: int = 14) -> float:
        period = min(period, len(bars))
        if period <= 1:
            return 0.0
        trs = []
        previous_close = getattr(bars[-period], "close", None)
        for bar in bars[-period:]:
            high = getattr(bar, "high", None)
            low = getattr(bar, "low", None)
            close = getattr(bar, "close", None)
            if high is None or low is None or close is None:
                continue
            tr_components = [high - low]
            if previous_close is not None:
                tr_components.append(abs(high - previous_close))
                tr_components.append(abs(low - previous_close))
            tr = max(tr_components)
            trs.append(tr)
            previous_close = close
        return mean(trs) if trs else 0.0

    def _init_vector_store(self) -> None:
        db_path = Path(__file__).parent / "chroma_db"
        if not chromadb:
            self.knowledge_status = "ChromaDB non installato"
            return
        # Ensure the directory exists; create it if missing to avoid noisy warnings
        try:
            if not db_path.exists():
                db_path.mkdir(parents=True, exist_ok=True)
                logging.info("Creata directory knowledge base: %s", db_path)
        except Exception as exc:
            self.knowledge_status = f"Impossibile creare directory KB: {exc}"
            logging.warning("Impossibile creare directory knowledge base %s: %s", db_path, exc)
            return
        try:
            client = chromadb.PersistentClient(path=str(db_path))
            self.vector_store = client.get_or_create_collection("ebooks_knowledge")
            count = self.vector_store.count() if hasattr(self.vector_store, "count") else 0
            self.knowledge_status = f"Knowledge base attiva ({count} chunk)"
            logging.info("Vector store inizializzato da %s (records=%s)", db_path, count)
        except Exception as exc:
            self.vector_store = None
            self.knowledge_status = f"Errore inizializzazione KB: {exc}"
            logging.warning("Impossibile inizializzare Chroma DB: %s", exc)

    def _fetch_knowledge(self, query: str) -> str:
        if not self.vector_store:
            self.knowledge_status = "Knowledge base non disponibile"
            return ""
        try:
            result = self.vector_store.query(query_texts=[query], n_results=2)
            documents = result.get("documents") if isinstance(result, dict) else None
            if not documents:
                self.knowledge_status = "Knowledge base attiva ma nessun documento rilevante"
                return ""
            docs = documents[0]
            self.knowledge_status = f"Knowledge base attiva, match {len(docs)} documenti"
            return "\n".join(docs)
        except Exception as exc:
            self.knowledge_status = f"Errore query KB: {exc}"
            logging.warning("Errore durante la query al vector store: %s", exc)
            return ""

    def _init_llm_chain(self) -> None:
        self.llm_chain = None
        if not (ChatGoogleGenerativeAI and PromptTemplate and RunnableParallel and RunnableLambda and StrOutputParser):
            return
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return
        llm = ChatGoogleGenerativeAI(model=self.model_name, google_api_key=api_key, temperature=0.15)
        prompt = PromptTemplate(
            input_variables=[
                "strategy_version",
                "signal_context",
                "knowledge",
                "news_context",
                "search_context",
                "crypto_context",
                "forex_context",
                "market_hours",
            ],
            template=(
                "Strategia: {strategy_version}\n"
                "Contesto tecnico:\n{signal_context}\n"
                "Conoscenza aggiuntiva:\n{knowledge}\n"
                "News rilevanti:\n{news_context}\n"
                "Web intelligence:\n{search_context}\n"
                "Feed crypto esterno:\n{crypto_context}\n"
                "Feed forex esterno:\n{forex_context}\n"
                "Orari mercati:\n{market_hours}\n\n"
                "Restituisci SOLO JSON nel formato "
                '{"decision":"BUY|SELL|HOLD","reason":"spiega in una frase"}'
            ),
        )
        self.llm_chain = (
            RunnableParallel(prompt=prompt)
            | RunnableLambda(lambda x: x["prompt"])
            | llm
            | StrOutputParser()
        )

    def _parse_llm_response(self, response: str):
        try:
            parsed = json.loads(response)
            decision = parsed.get("decision", "").upper()
            if decision in {"BUY", "SELL", "HOLD"}:
                return {"decision": decision, "reason": parsed.get("reason", "").strip()}
        except (json.JSONDecodeError, AttributeError):
            logging.warning("Formato risposta LLM non valido: %s", response)
        return None

    def _init_news_fetcher(
        self,
        news_config: Optional[Mapping[str, str]],
        instrument: Optional[Mapping[str, str]],
    ):
        if not news_config:
            return None
        try:
            config_dict = dict(news_config.items())  # type: ignore[attr-defined]
        except AttributeError:
            config_dict = dict(news_config)

        enabled = self._to_bool(config_dict.get("enabled", "false"))
        if not enabled:
            return None
        query_value = self._resolve_news_query(config_dict.get("query"), instrument)
        try:
            return NewsFetcher(
                enabled=enabled,
                api_key_env=config_dict.get("api_key_env", "NEWSAPI_KEY"),
                provider=config_dict.get("provider", "newsapi"),
                query=query_value,
                language=config_dict.get("language", "en"),
                max_articles=self._to_int(config_dict.get("max_articles", 5), default=5, min_value=1),
                refresh_minutes=self._to_int(config_dict.get("refresh_minutes", 15), default=15, min_value=1),
                lookback_minutes=self._to_int(config_dict.get("lookback_minutes", 120), default=120, min_value=15),
            )
        except Exception as exc:
            logging.warning("Impossibile inizializzare NewsFetcher: %s", exc)
            return None

    async def _build_news_context(self) -> str:
        if not self.news_fetcher:
            return ""
        articles = await self.news_fetcher.get_recent_headlines()
        if not articles:
            return ""
        return self.news_fetcher.build_prompt_section(articles)

    async def _build_search_context(self) -> str:
        if not self.search_fetcher:
            return ""
        insights = await self.search_fetcher.fetch_insights()
        if not insights:
            return ""
        return self.search_fetcher.build_prompt_section(insights)

    def _decorate_knowledge(self, knowledge_text: str) -> str:
        status_line = f"[KB status: {self.knowledge_status}]"
        if knowledge_text:
            return f"{knowledge_text}\n{status_line}"
        return status_line

    async def _build_crypto_context(self) -> str:
        return await self._build_feed_context(self.crypto_feed)

    async def _build_forex_context(self) -> str:
        return await self._build_feed_context(self.forex_feed)

    async def _build_feed_context(self, feed) -> str:
        if not feed:
            return ""
        snapshots = await feed.get_snapshots()
        return feed.build_prompt_section(snapshots)

    def _build_market_hours_context(self) -> str:
        try:
            return build_market_hours_context()
        except Exception as exc:
            logging.warning("Impossibile costruire il contesto market hours: %s", exc)
            return ""

    @staticmethod
    def _to_bool(value, default: bool = False) -> bool:
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _to_int(value, default: int, min_value: int = 1) -> int:
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            numeric = default
        return max(min_value, numeric)

    def _resolve_news_query(
        self,
        raw_query: Optional[str],
        instrument: Optional[Mapping[str, str]],
    ) -> str:
        symbol = (instrument or {}).get("symbol", "")
        currency = (instrument or {}).get("currency", "")
        sec_type = (instrument or {}).get("sec_type", "")
        pair = f"{symbol}{currency}" if symbol and currency else ""

        default_terms = ["forex"]
        if pair:
            default_terms.append(pair)
        if symbol and currency:
            default_terms.append(f"{symbol}/{currency}")
        if currency:
            default_terms.append(f"{currency} macro")
        if sec_type:
            default_terms.append(sec_type)
        default_query = ",".join(filter(None, default_terms))

        if not raw_query or raw_query.strip().lower() == "auto":
            return default_query

        template = raw_query.strip()
        try:
            resolved = template.format(
                symbol=symbol,
                currency=currency,
                pair=pair,
                sec_type=sec_type,
            )
        except KeyError:
            resolved = template
        return resolved or default_query

    def _init_market_feed(self, feed_config: Optional[Mapping[str, str]], default_label: str):
        if not feed_config:
            return None
        try:
            config_dict = dict(feed_config.items())  # type: ignore[attr-defined]
        except AttributeError:
            config_dict = dict(feed_config)
        config_dict.setdefault("label", default_label)
        try:
            return CryptoFeed(config_dict)
        except Exception as exc:
            logging.warning("Impossibile inizializzare %s: %s", default_label, exc)
            return None

