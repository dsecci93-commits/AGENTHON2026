# FinEdu — Hagenthon 2026

Strumento educativo per l'analisi degli estratti conto bancari, con agente AI integrato.

## Struttura repository

```
hagenthon-finedu/
├── app/                        # Prototipo Streamlit (MVP funzionante)
│   ├── app.py                  # Applicazione principale
│   ├── requirements.txt        # Dipendenze Python
│   └── data/
│       └── samples/            # CSV di esempio per la demo
├── agents/                     # Agenti Claude Code multi-agente
│   ├── CLAUDE.md               # Istruzioni di progetto per l'orchestratore
│   ├── orchestrator.md         # Agente lead (coordina tutti i sub-agenti)
│   ├── backend.md              # Agente backend (FastAPI, PostgreSQL, parser)
│   ├── frontend.md             # Agente frontend (React, Plotly.js, UI/UX)
│   ├── genai-integration.md    # Agente GenAI (Claude API, privacy-safe payload)
│   ├── security.md             # Agente security (GDPR, JWT, bcrypt)
│   ├── testing.md              # Agente testing (pytest, Jest, Playwright)
│   └── workflow.md             # Workflow completo di sviluppo multi-agente
└── presentation/
    └── index.html              # Presentazione sales-oriented con mock interattivo
```

## Come eseguire il prototipo

```bash
cd app
pip install -r requirements.txt
streamlit run app.py
```

Accedi a `http://localhost:8501`. Usa le credenziali demo: `dani / dani123`.

Per caricare un estratto di test usa uno dei CSV in `data/samples/`.

## Come visualizzare la presentazione

Apri `presentation/index.html` direttamente nel browser.  
La presentazione include un mock interattivo con dati reali dei 3 mesi campione.

## Architettura agentica

Il progetto è stato sviluppato con **Claude Code in modalità multi-agente**:

- **Orchestrator**: coordina backend, frontend, genai-integration, security, testing
- Ogni sub-agente ha scope definito, output format strutturato e vincoli espliciti di non-sovrapposizione
- Il security agent ha diritto di veto su qualsiasi decision che tocchi dati bancari o credenziali
- Il workflow completo è documentato in `agents/workflow.md`

## Vincoli di sicurezza e compliance

- **MAI** dati bancari raw all'API GenAI — solo aggregati per categoria
- **MAI** IBAN, descrizioni transazioni singole o importi individuali verso l'esterno
- Password hashed bcrypt (SHA-256 solo nella demo, non in produzione)
- System prompt fisso e versionato — non modificabile dall'utente
- Nessuna consulenza finanziaria: solo analisi educativa e descrittiva

## Team

**Hagenthon 2026 — Accenture Application Engineering**  
Daniele Secci — daniele.secci@accenture.com
