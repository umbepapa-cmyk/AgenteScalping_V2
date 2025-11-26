import os
import sys
import socket
import configparser
from pathlib import Path

# helper per versioni pacchetti
try:
    import importlib.metadata as _ilm
except Exception:
    import importlib_metadata as _ilm  # type: ignore

def _pkg_version(name: str):
    try:
        return _ilm.version(name)
    except Exception:
        return None

def check_tws_ports():
    """Verifica le porte comuni TWS/Gateway."""
    ports = {
        7496: "TWS Live Trading",
        7497: "TWS Paper Trading",
        4001: "Gateway Live Trading", 
        4002: "Gateway Paper Trading"
    }
    results = {}
    for port, desc in ports.items():
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2.0):
                results[port] = f"✅ {desc} ({port}): RAGGIUNGIBILE"
        except Exception:
            results[port] = f"❌ {desc} ({port}): NON RAGGIUNGIBILE"
    return results

def check_dependencies():
    """Verifica dipendenze Python e mostra versioni se presenti."""
    deps = {
        "ib_async": "Richiesto per TWS/Gateway API",
        "python-dotenv": "Richiesto per .env",
        "langchain": "Opzionale per AI",
        "langchain-google-genai": "Opzionale per Gemini (nome pacchetto possibile diverso)",
        "chromadb": "Opzionale per RAG"
    }
    results = {}
    for pkg, desc in deps.items():
        ver = _pkg_version(pkg)
        if ver:
            results[pkg] = f"✅ {desc}: INSTALLATO (versione {ver})"
        else:
            # tenta alternative comuni per genai
            alt = None
            if pkg == "langchain-google-genai":
                alt = _pkg_version("google-genai") or _pkg_version("langchain_google_genai")
            # tenta ib_insync come alternativa per ib_async (backward compatibility)
            # ib_insync è il vecchio nome del pacchetto, ora rinominato in ib_async
            if pkg == "ib_async":
                alt = _pkg_version("ib_insync")
            if alt:
                results[pkg] = f"✅ {desc}: INSTALLATO (versione {alt})"
            else:
                results[pkg] = f"{'❌' if pkg in ['ib_async', 'python-dotenv'] else '⚠️'} {desc}: NON INSTALLATO"
    # aggiungi versione Python
    try:
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        results['python'] = f"✅ Python: {py_ver}"
    except Exception:
        pass
    return results

def check_config_ini():
    """Verifica config.ini."""
    config_path = Path("config.ini")
    if not config_path.exists():
        return "❌ config.ini non trovato"
    
    try:
        config = configparser.ConfigParser()
        config.read(config_path)
        # Leggi dalla sezione [IB] invece di DEFAULT
        ib_section = config['IB'] if 'IB' in config else config['DEFAULT']
        host = ib_section.get('host', 'NON TROVATO')
        port = ib_section.get('port', 'NON TROVATO')
        client_id = ib_section.get('client_id', 'NON TROVATO')
        environment = ib_section.get('environment', 'NON SPECIFICATO')
        return f"""✅ config.ini trovato:
- host: {host}
- port: {port}
- client_id: {client_id}
- environment: {environment}"""
    except Exception as e:
        return f"❌ Errore lettura config.ini: {e}"

def check_env_keys():
    """Verifica chiavi in .env."""
    try:
        from dotenv import load_dotenv
    except Exception:
        # Non fermiamo la diagnostica se python-dotenv non è presente
        def load_dotenv(*args, **kwargs):
            print("WARNING: python-dotenv non installato. Le chiavi in .env non saranno caricate automaticamente.")
            return False

    load_dotenv()
    keys = {
        "GEMINI_API_KEY": "Chiave Gemini",
        "GOOGLE_API_KEY": "Chiave Google AI",
        "OPENAI_API_KEY": "Chiave OpenAI (opzionale)"
    }
    results = {}
    for key, desc in keys.items():
        val = os.getenv(key)
        if val:
            # Mostra solo primi/ultimi 4 caratteri della chiave
            masked = f"{val[:4]}...{val[-4:]}"
            results[key] = f"✅ {desc}: TROVATA ({masked})"
        else:
            results[key] = f"{'❌' if key == 'GEMINI_API_KEY' else '⚠️'} {desc}: NON TROVATA"
    return results

def check_folders():
    """Verifica cartelle e permessi."""
    folders = {
        ".": "Directory principale",
        "chroma_db": "Database vettoriale (opzionale)",
        "ebooks": "PDF per RAG (opzionale)"
    }
    results = {}
    for folder, desc in folders.items():
        path = Path(folder)
        if not path.exists():
            results[folder] = f"⚠️ {desc}: NON ESISTE"
            continue
        try:
            # Verifica permessi creando/eliminando file test
            test_file = path / ".test_write"
            test_file.touch()
            test_file.unlink()
            results[folder] = f"✅ {desc}: OK (lettura/scrittura)"
        except Exception as e:
            results[folder] = f"❌ {desc}: ERRORE PERMESSI ({e})"
    return results

def suggest_install_commands(results: dict) -> list:
    """Ritorna comandi pip suggeriti per i pacchetti mancanti (richiesti)."""
    cmds = []
    required = ['ib_async', 'python-dotenv']
    for pkg in required:
        entry = results.get(pkg)
        if entry and ('NON INSTALLATO' in entry or '⚠️' in entry):
            cmds.append(f"pip install {pkg}")
    # suggerimenti opzionali
    optional = []
    if results.get('langchain', '').startswith('⚠️') or 'NON INSTALLATO' in results.get('langchain', ''):
        optional.append("pip install langchain")
    if results.get('langchain-google-genai', '').startswith('⚠️') or 'NON INSTALLATO' in results.get('langchain-google-genai', ''):
        optional.append("pip install langchain-google-genai")
    if results.get('chromadb', '').startswith('⚠️') or 'NON INSTALLATO' in results.get('chromadb', ''):
        optional.append("pip install chromadb")
    return cmds + optional

def analyze_firewall_file(path: str = "porte.txt", ports: list = None) -> dict:
    """Cerca nel file firewall (porte.txt) regole che menzionano le porte indicate."""
    if ports is None:
        ports = [7496, 7497, 4001, 4002]
    results = {}
    if not os.path.exists(path):
        return results
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
    except Exception:
        return results
    lines = text.splitlines()
    for p in ports:
        matches = []
        for ln in lines:
            if str(p) in ln:
                state = "UNKNOWN"
                if "Consenti" in ln or "Allow" in ln:
                    state = "CONSENTITO"
                if "Blocca" in ln or "Bloccare" in ln or "Deny" in ln or "Bloccato" in ln:
                    state = "BLOCCATO"
                matches.append((state, ln.strip()))
        results[p] = matches
    return results

def main():
    """Esegue tutti i controlli e stampa report."""
    print("\n=== 🔍 DIAGNOSTICA AGENTE TRADING V3 ===\n")
    
    # 1. TWS/Gateway
    print("\n--- 📡 Porte TWS/Gateway ---")
    for msg in check_tws_ports().values():
        print(msg)

    # Analisi file firewall (se presente)
    print("\n--- 🔐 Analisi file porte (porte.txt) ---")
    fw_report = analyze_firewall_file("porte.txt")
    if not fw_report:
        print("Nessun file 'porte.txt' trovato o file non leggibile.")
    else:
        for port, entries in fw_report.items():
            if not entries:
                print(f"{port}: Nessuna regola trovata in 'porte.txt'")
            else:
                # mostra solo le prime 2 occorrenze per porta per compattezza
                shown = 0
                for state, ln in entries:
                    print(f"{port}: {state} -> {ln[:200]}")
                    shown += 1
                    if shown >= 2:
                        break

    # 2. Dipendenze Python
    print("\n--- 📦 Dipendenze Python ---")
    deps = check_dependencies()
    for msg in deps.values():
        print(msg)
    # suggerimenti di installazione rapida
    suggestions = suggest_install_commands(deps)
    if suggestions:
        print("\n--- COMANDI SUGGERITI PER INSTALLARE I PACCHETTI MANCANTI ---")
        for c in suggestions:
            print(c)
    
    # 3. Configurazione
    print("\n--- ⚙️ Configurazione ---")
    print(check_config_ini())
    
    # 4. API Keys
    print("\n--- 🔑 Chiavi API ---")
    for msg in check_env_keys().values():
        print(msg)
    
    # 5. Cartelle
    print("\n--- 📁 Cartelle e Permessi ---")
    for msg in check_folders().values():
        print(msg)

    print("\n=== SUGGERIMENTI ===")
    print("""
1. Se le porte TWS non sono raggiungibili:
   - Avvia TWS/Gateway
   - Abilita API: Configure > API > Settings > Enable ActiveX and Socket Clients
   - Verifica firewall/antivirus
   - Se IB Gateway è su un server remoto, apri un tunnel SSH:
     ssh -L 4002:localhost:4002 user@server

2. Se mancano dipendenze richieste:
   pip install ib_async python-dotenv

3. Se config.ini non è corretto:
   - Verifica host (default: 127.0.0.1)
   - Verifica porta (TWS Live: 7496, TWS Paper: 7497, Gateway Live: 4001, Gateway Paper: 4002)
   - Assegna un client_id univoco

4. Se manca GEMINI_API_KEY:
   - Crea file .env nella directory principale
   - Aggiungi: GEMINI_API_KEY=your_key_here
""")

if __name__ == "__main__":
    main()
# (file aggiornato per stampare versioni pacchetti e controlli; nessuna ulteriore modifica richiesta)
