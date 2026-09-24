FinEdu — Istruzioni di progetto per Claude Code
Attivazione
Applica queste istruzioni quando la richiesta riguarda il progetto FinEdu: codice applicativo, agenti, parser, grafici, integrazione Claude API, sicurezza, test, documentazione.

Identità di progetto
Campo	Valore
Progetto	FinEdu — Strumento di educazione finanziaria
Prototipo	app/app.py (Streamlit, Python 3.12)
Target produzione	FastAPI + React + PostgreSQL + Claude API
Repository	https://github.com/dsecci93-commits/AGENTHON2026
Team	Daniele Secci — daniele.secci@accenture.com
Agenti disponibili
Invoca sempre l'orchestratore come punto di ingresso per nuove feature.
Per bug su un dominio specifico puoi invocare direttamente il sub-agente.

Agente	Scope
orchestrator	Coordina tutto; decision finale su conflitti
backend	FastAPI, PostgreSQL, parser CSV/PDF, categorizzatore
frontend	React, Plotly.js, UI/UX, routing, responsive
genai-integration	Claude API, payload privacy-safe, system prompt, rate limit, fallback
security	GDPR, JWT, bcrypt, input validation — ha diritto di veto
testing	pytest, Jest, Playwright, bug catalog
Dettagli completi in .claude/agents/ e documentazione in agents/.

Regole non negoziabili (tutti gli agenti)
Privacy: all'API Claude arrivano SOLO aggregati per categoria. Mai IBAN, mai descrizioni singole transazioni, mai importi individuali.
No consulenza finanziaria: il sistema è educativo. Nessun output deve raccomandare acquisti, vendite, investimenti o scelte finanziarie.
System prompt fisso: il prompt AI è versionato in .claude/agents/genai-integration.md — non modificabile dall'utente.
Fallback deterministico: il sistema funziona anche senza Claude API.
Secrets via env: API key, password DB e credenziali solo in variabili d'ambiente. Mai nel codice.
Security sign-off: qualsiasi modifica ad autenticazione, parser o payload verso l'API esterna richiede approvazione del security agent prima del merge.
Variabili d'ambiente richieste
Vedi .env.example per la lista completa.
In sviluppo: crea un file .env (già in .gitignore).
In produzione: usa il secret manager del provider cloud.

Hook attivi
Gli hook sono configurati in .claude/settings.json:

Privacy guard (PostToolUse su Edit/Write): blocca se un file contiene pattern che sembrano raw transactions diretti verso endpoint esterni
Syntax check (PostToolUse su Edit/Write su *.py): esegue python -m py_compile sul file modificato
Secret scan (PostToolUse su Edit/Write): cerca pattern di API key o password hardcodate
Struttura chiave
hagenthon-finedu/
├── CLAUDE.md                   ← questo file (letto automaticamente da Claude Code)
├── .claude/
│   ├── settings.json           ← permessi, hook
│   ├── agents/                 ← definizioni agenti Claude Code (con frontmatter)
│   └── hooks/                  ← script hook
├── agents/                     ← documentazione estesa degli agenti (reference)
├── app/                        ← prototipo Streamlit
├── presentation/               ← presentazione HTML
└── delivery/                   ← deliverable Hagenthon
