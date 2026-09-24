# FinEdu — Agenti Claude Code

## Contesto di progetto

**FinEdu** è uno strumento di educazione finanziaria B2C che analizza estratti conto bancari e offre supporto AI descrittivo. Sviluppato per Hagenthon 2026 — Accenture.

**Protipo funzionante**: `../app/app.py` (Streamlit, Python 3.12)  
**Target produzione**: FastAPI + React + PostgreSQL + Claude API

---

## Agenti disponibili

| Agente | File | Responsabilità |
|---|---|---|
| **Orchestrator** | `orchestrator.md` | Coordina tutti i sub-agenti; decision finale su conflitti |
| **Backend** | `backend.md` | FastAPI, PostgreSQL, parser CSV/PDF, categorizzatore |
| **Frontend** | `frontend.md` | React, Plotly.js, UI/UX, grafici (mesi su X, euro su Y) |
| **GenAI Integration** | `genai-integration.md` | Claude API, privacy-safe payload, system prompt |
| **Security** | `security.md` | GDPR, JWT, bcrypt, checklist compliance, veto sui dati |
| **Testing** | `testing.md` | pytest, Jest, Playwright, bug patterns noti |

---

## Regole trasversali (tutti gli agenti)

1. **Privacy non negoziabile**: all'API GenAI arrivano SOLO aggregati per categoria. Mai IBAN, mai descrizioni singole transazioni. Il Security agent ha diritto di veto.
2. **Nessuna consulenza finanziaria**: il sistema è educativo. Nessun agente deve implementare logiche che raccomandino acquisti, vendite, investimenti o scelte finanziarie specifiche.
3. **System prompt fisso**: il prompt dell'agente AI è versionato in `genai-integration.md` e non è modificabile dall'utente.
4. **Ordine cronologico**: gli estratti sono sempre ordinati per anno/mese, indipendentemente dall'ordine di caricamento.
5. **Fallback deterministico**: il sistema funziona anche senza Claude API (regole keyword). L'agente AI è un enhancement, non una dipendenza critica.

---

## Come usare gli agenti

Per nuove feature, partire sempre dall'**Orchestrator** che coordina gli altri sub-agenti.  
Per bug specifici, è possibile invocare direttamente il sub-agente responsabile.

Workflow documentato in `workflow.md`.
