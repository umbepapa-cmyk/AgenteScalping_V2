import os
import shutil
import logging
from typing import List
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader  # type: ignore
from langchain_google_genai import GoogleGenerativeAIEmbeddings  # type: ignore
from langchain_text_splitters import RecursiveCharacterTextSplitter  # type: ignore
from langchain_community.vectorstores import Chroma  # type: ignore
from langchain_core.documents import Document  # type: ignore
# NOTA: Potrebbe essere necessario installare 'chromadb' se non già presente
# pip install chromadb

# --- CONFIGURAZIONE E CARICAMENTO CHIAVI ---
load_dotenv() 
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- NOMI DEI PERCORSI ---
EBOOKS_DIR = "ebooks"       
VECTOR_DB_DIR = "chroma_db" 
# --- CONFIGURAZIONE SPLITTER ---
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 150

def load_and_split_documents(directory: str) -> List[Document]:
    """Carica tutti i PDF dalla directory e li divide in frammenti (chunks)."""
    
    logging.info(f"Caricamento documenti dalla directory: {directory}...")
    documents: List[Document] = []
    
    pdf_files = [f for f in os.listdir(directory) if f.lower().endswith(".pdf")]
    if not pdf_files:
        logging.warning(f"Nessun file PDF trovato in '{directory}'.")
        return []

    for filename in pdf_files:
        filepath = os.path.join(directory, filename)
        try:
            loader = PyPDFLoader(filepath)
            docs = loader.load()
            logging.info(f"Caricato {filename} ({len(docs)} pagine).")
            documents.extend(docs)
        except Exception as e:
            logging.error(f"Errore nel caricamento di {filename}: {e}")

    if not documents:
        logging.error("Nessun documento è stato caricato. Interruzione.")
        return []

    # Configurazione dello splitter
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    
    chunks = text_splitter.split_documents(documents)
    logging.info(f"Documenti divisi in {len(chunks)} 'chunks' (frammenti).")
    return chunks

def build_vector_store():
    """Crea e salva il database vettoriale (Chroma) dagli 'chunks'."""
    
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logging.error("GEMINI_API_KEY non trovata nel file .env. Interruzione.")
        raise ValueError("GEMINI_API_KEY non trovata. Controlla che sia nel file .env.")

    # --- CORREZIONE ERRORE RUNTIME ---
    # Controlla se il DB esiste. Se sì, non fa nulla per evitare corruzioni.
    # Per ricreare il DB, l'utente deve cancellare manualmente la cartella 'chroma_db'.
    if os.path.exists(VECTOR_DB_DIR):
        logging.warning(f"Database vettoriale '{VECTOR_DB_DIR}' esistente. Si assume sia aggiornato.")
        logging.warning("Per forzare una rigenerazione, cancella la cartella 'chroma_db' e riesegui lo script.")
        return

    # 1. Carica e dividi i documenti
    chunks = load_and_split_documents(EBOOKS_DIR)
    if not chunks:
        logging.error("Nessun frammento (chunk) da indicizzare. Il database non sarà creato.")
        return

    # 2. Definizione del modello di embedding (Gemini)
    try:
        logging.info("Inizializzazione modello di embedding (text-embedding-004)...")
        # Istanzia embeddings lasciando che la libreria legga le env internamente
        embeddings = GoogleGenerativeAIEmbeddings()  # type: ignore[call-arg]
    except Exception as e:
        logging.error(f"ERRORE CRITICO nella creazione di GoogleGenerativeAIEmbeddings: {e}")
        logging.error("Ciò potrebbe indicare una chiave API non valida o una versione obsoleta di 'langchain-google-genai'.")
        return

    # 3. Creazione dell'indice e salvataggio
    try:
        logging.info(f"Creazione database vettoriale in '{VECTOR_DB_DIR}' (potrebbe richiedere tempo)...")
        
        # --- CORREZIONE ERRORE RUNTIME ---
        # Metodo alternativo per la creazione del DB che aggira l'errore 'AttributeError: V'
        
        # 1. Inizializza un DB Chroma vuoto che punta alla directory
        db = Chroma(
            persist_directory=VECTOR_DB_DIR,
            embedding_function=embeddings
        )
        
        # 2. Aggiungi i documenti al DB
        logging.info(f"Aggiunta di {len(chunks)} frammenti al database...")
        db.add_documents(chunks)
        
        # 3. Salva (persisti) i dati su disco
        db.persist()
        
        logging.info("✅ Indicizzazione completata con successo!")
        logging.info(f"Database salvato in: {VECTOR_DB_DIR}")

    except Exception as e:
        logging.error(f"ERRORE CRITICO durante l'indicizzazione: {e}", exc_info=True)
        # Se fallisce, pulisce la cartella per evitare DB corrotti
        if os.path.exists(VECTOR_DB_DIR):
            shutil.rmtree(VECTOR_DB_DIR)
            logging.error(f"Pulizia di '{VECTOR_DB_DIR}' fallita a causa dell'errore.")


if __name__ == "__main__":
    if not os.path.exists(EBOOKS_DIR):
        os.makedirs(EBOOKS_DIR)
        logging.warning(f"La cartella '{EBOOKS_DIR}' è stata creata.")
        logging.warning(f"Per favore, aggiungi i tuoi file PDF in '{EBOOKS_DIR}' e riesegui lo script.")
    elif not any(f.lower().endswith('.pdf') for f in os.listdir(EBOOKS_DIR)):
        logging.warning(f"La cartella '{EBOOKS_DIR}' è vuota. Aggiungi i PDF per l'analisi.")
    else:
        build_vector_store()

