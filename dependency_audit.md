Dependency audit and recommendations

Source: `requirements.txt` in the repository.

Current requirements (as provided):
- ibapi==9.81.1.post1
- ib_async>=1.0.0
- pandas
- python-dotenv
- langchain
- langchain-google-genai
- langchain-community
- chromadb
- pypdf
- configparser
- httpx
- nest_asyncio>=1.5.6
- tzdata>=2023.3

Findings & recommendations:

1) Optional vs mandatory: Several heavy dependencies are optional in code (LangChain, chromadb, langchain-google-genai). If you deploy to a server without LLM functionality, pin these as optional extras or document them in README. Example: create `requirements-llm.txt` for LLM/RAG features.

2) Pin versions for reproducibility: packages like `langchain`, `chromadb` and `ib_async` change fast. Recommend pinning explicit versions after verifying compatibility. E.g. `langchain==0.2x` (choose a tested version), `chromadb==0.3x`.

3) Security: remove API keys from source; use environment variables. Do not commit `Scalping_V2.txt` or any `.env` with keys. Rotate any keys that might have been exposed.

4) Platform specifics: `ibapi` and `ib_async` require specific Python versions and network access. Use Python 3.10+ as documented; ensure `tzdata` for timezones on minimal Linux images.

5) Performance: If you plan to run on a small VPS, consider removing/pinning heavy ML deps and running analysis remotely (LLM calls) or using a lighter fallback.

6) Testing/CI: add a `requirements-dev.txt` including `pytest`, `ruff`/`black` and `mypy` to run static checks and unit tests before deploy.

Suggested new files:
- `requirements-core.txt` (core runtime: ibapi, ib_async, httpx, python-dotenv, configparser, nest_asyncio)
- `requirements-llm.txt` (langchain, langchain-google-genai, chromadb, pypdf)
- `requirements-dev.txt` (pytest, ruff, black, mypy)

Actionable next steps I can perform now:
- Produce the split requirement files and a short script to install core or full stack (if you want).
- Run static checks (`ruff`/`mypy`) locally if you want me to add them and run them.
