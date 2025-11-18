import json
import logging
import os
from pathlib import Path
from statistics import mean
from typing import List, Sequence, Tuple

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


class AiAnalyst:
    """
    Classe responsabile dell'analisi dei dati di mercato e della generazione
    di decisioni di trading (BUY, SELL, HOLD).
    """
    def __init__(self, strategy_version: str = "v1", model_name: str = "gemini-1.5-pro"):
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
        self._init_vector_store()
        self._init_llm_chain()
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
        base_decision, base_reason = self._technical_signal(closes)
        if not self.llm_chain:
            return base_decision, base_reason

        technical_context = self._build_context(bars, closes, base_reason)
        knowledge = self._fetch_knowledge(base_reason)
        try:
            llm_payload = {
                "strategy_version": self.strategy_version,
                "signal_context": technical_context,
                "knowledge": knowledge or "N/A"
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

    def _technical_signal(self, closes: Sequence[float]) -> Tuple[str, str]:
        short_ma = mean(closes[-5:])
        long_ma = mean(closes[-20:]) if len(closes) >= 20 else short_ma
        momentum = closes[-1] - closes[-2]
        spread = short_ma - long_ma
        if spread > 0 and momentum > 0:
            return "BUY", f"ShortMA ({short_ma:.5f}) sopra LongMA ({long_ma:.5f}) con momentum positivo ({momentum:.5f})."
        if spread < 0 and momentum < 0:
            return "SELL", f"ShortMA ({short_ma:.5f}) sotto LongMA ({long_ma:.5f}) con momentum negativo ({momentum:.5f})."
        return "HOLD", f"Segnali contrastanti (ΔMA={spread:.5f}, momentum={momentum:.5f})."

    def _build_context(self, bars: Sequence, closes: Sequence[float], reason: str) -> str:
        last_bar = bars[-1]
        high = getattr(last_bar, "high", None)
        low = getattr(last_bar, "low", None)
        volume = getattr(last_bar, "volume", None)
        return (
            f"Ultima chiusura: {closes[-1]:.5f}\n"
            f"Motivazione tecnica: {reason}\n"
            f"High/Low: {high}, {low} | Volume: {volume}\n"
            f"Numero barre disponibili: {len(closes)}"
        )

    def _init_vector_store(self) -> None:
        self.vector_store = None
        db_path = Path(__file__).parent / "chroma_db"
        if chromadb and db_path.exists():
            try:
                client = chromadb.PersistentClient(path=str(db_path))
                self.vector_store = client.get_or_create_collection("ebooks_knowledge")
                logging.info("Vector store inizializzato da %s", db_path)
            except Exception as exc:
                logging.warning("Impossibile inizializzare Chroma DB: %s", exc)

    def _fetch_knowledge(self, query: str) -> str:
        if not self.vector_store:
            return ""
        try:
            result = self.vector_store.query(query_texts=[query], n_results=2)
            docs = result.get("documents", [[]])[0]
            return "\n".join(docs)
        except Exception as exc:
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
            input_variables=["strategy_version", "signal_context", "knowledge"],
            template=(
                "Strategia: {strategy_version}\n"
                "Contesto tecnico:\n{signal_context}\n"
                "Conoscenza aggiuntiva:\n{knowledge}\n\n"
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

