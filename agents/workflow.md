# FinEdu — Workflow Multi-Agente Completo

## Come è stato costruito FinEdu

Questo documento descrive il processo di sviluppo multi-agente usato per FinEdu durante Hagenthon 2026.

---

## Architettura degli agenti

```
[Utente / Team Lead]
        │
        ▼
  [Orchestrator]  ◄─── unico punto di contatto esterno
   ╔═══╧════════════════════════════════════════╗
   ║                                             ║
   ▼         ▼          ▼          ▼          ▼
[Backend] [Frontend] [GenAI]  [Security]  [Testing]
```

- **Orchestrator**: riceve la feature request, la scompone, assegna task ai sub-agenti
- **Sub-agenti**: scope chiaro e non sovrapposto; producono output strutturato
- **Security**: agente trasversale con diritto di veto; non aspettare la fine per coinvolgerlo
- **Testing**: agente trasversale; ogni feature deve avere i test scritti dallo stesso agente che la implementa (backend → backend scrive il test, testing lo rivede)

---

## Workflow per una nuova feature

### Step 1 — Feature Brief (Orchestrator)

Il team lead descrive la feature. L'orchestratore produce:

```markdown
## Feature: [nome]
**Obiettivo**: [cosa fa e perché è necessaria]
**Sub-agenti coinvolti**: [lista]
**Dipendenze**: [feature o API esistenti da non rompere]
**Vincoli**: [performance, privacy, compliance]
**Definition of Done**: [criteri verificabili]
```

### Step 2 — Task Delegation (Orchestrator → sub-agenti)

L'orchestratore assegna task specifici con output format definito. Esempio:

```
Backend agent: crea endpoint POST /statements/upload
  - Accetta: CSV, PDF, TXT, max 10MB
  - Risponde: statement_id, period_label, n_transactions, category_totals
  - NON restituire raw transactions nell'API response
  - Output atteso: codice FastAPI + schema Pydantic + docstring + test pytest
```

### Step 3 — Parallel Execution

I sub-agenti lavorano in parallelo dove possibile:
- Backend e Frontend lavorano contemporaneamente sulla stessa feature
- Security e Testing lavorano in parallelo, non aspettano la fine dell'implementazione
- GenAI agent viene coinvolto solo se la feature tocca la chat AI

### Step 4 — Integration Check (Orchestrator)

Prima di chiudere la feature:
1. Verifica che backend e frontend concordino sul contratto API
2. Verifica che il security agent abbia firmato il sign-off
3. Verifica che il testing agent abbia coverage ≥ 80% sul nuovo codice
4. Verifica che nessun raw banking data stia uscendo dal backend

### Step 5 — Known Issues Catalog (Testing agent)

Ogni bug trovato durante il development va catalogato in `testing.md` sotto "Bug pattern catalog" con:
- ID univoco (BUG-NNN)
- Descrizione
- Regression test corrispondente

---

## Come sono stati usati gli agenti nel prototipo (Hagenthon)

### Feature 1 — Parser e categorizzatore (Sprint 1)

```
Orchestrator → Backend: implementa parser CSV/TXT con categorizzazione keyword
Backend → Testing: PASS su 15 casi di test, 2 bug trovati e corretti
  BUG-001: "bonif" keyword troppo ampia
  BUG-002: "atm" senza spazio trailing
Orchestrator → merge con patch
```

### Feature 2 — Storico multi-mese (Sprint 2)

```
Orchestrator → Backend: aggiunge campo period_label e ordinamento cronologico
Orchestrator → Frontend: aggiunge grafico line chart (mesi su X, euro su Y)
Backend: BUG-003 trovato: period_label non veniva rilevato automaticamente da CSV
Backend: FIX _detect_period_label + _fix_period_labels retroattivo
Testing: test aggiunto per BUG-003, BUG-004 (ordinamento errato)
Security: verifica che le transazioni salvate nel JSON non vengano mai esposte in API esterne → OK
Orchestrator → merge
```

### Feature 3 — Dashboard interattiva (Sprint 3)

```
Orchestrator → Frontend: card cliccabili, auto-load mese più recente al login
Backend: aggiunge _df_from_stmt per ricostruire DataFrame da transazioni salvate
Testing: BUG-005 (dashboard vuota al login) → test E2E aggiunto
Orchestrator → merge
```

### Feature 4 — Integrazione GenAI API (pianificata, non nel prototipo Hagenthon)

```
Orchestrator → GenAI: definisce payload privacy-safe (solo aggregati)
Orchestrator → Security: sign-off obbligatorio prima del deploy
GenAI → Testing: 5 test critici (payload, rate limit, fallback, prompt injection, risposta consulenza)
Security: checklist GDPR + AI Act completata
Orchestrator → merge solo dopo security sign-off
```

---

## Decisioni architetturali prese dagli agenti

| Decisione | Agente | Motivazione |
|---|---|---|
| Streamlit per il prototipo | Orchestrator | Velocità > ergonomia; prototipo, non produzione |
| SHA-256 per demo, bcrypt per prod | Security | SHA-256 solo per non richiedere dipendenza pesante nella demo; ha documentato l'upgrade path |
| Privacy-safe payload come vincolo architetturale | Security + GenAI | Immutabile: ha precedenza su qualsiasi ottimizzazione della qualità delle risposte AI |
| Fallback deterministico obbligatorio prima dell'integrazione API | GenAI | Il sistema deve funzionare anche offline; l'AI è enhancement, non dipendenza |
| Ordine cronologico persistito su disco | Backend | Evita resorting in ogni query; fonte di verità sempre ordinata |
| `dayfirst=True` nel parser date | Backend | Date italiane sono GG/MM/AAAA; il fallback ISO gestisce i CSV bancari moderni |

---

## Cosa non è stato fatto (open points per la produzione)

1. **Claude API reale**: il prototipo usa risposte simulate; l'integrazione vera è definita in `genai-integration.md`
2. **Parser PDF avanzato**: il prototipo usa layout tabulari standard; formati bancari non-standard non sono supportati
3. **bcrypt in produzione**: il prototipo usa SHA-256 per semplicità — vedi `security.md` per l'upgrade path
4. **Mobile Flutter**: fuori scope Hagenthon; roadmap in `../presentation/index.html`
5. **PostgreSQL**: il prototipo usa file JSON per utente; lo schema SQL è definito in `backend.md`
6. **OAuth Google/Apple**: non implementato nel prototipo
7. **Export PDF report**: backend e template definiti, non integrati

---

## Legenda documenti

| File | Chi lo usa | Quando |
|---|---|---|
| `CLAUDE.md` | Tutti gli agenti | Regole trasversali, sempre |
| `orchestrator.md` | Orchestrator | Coordination, conflict resolution |
| `backend.md` | Backend agent | API, DB, parser, categorizzatore |
| `frontend.md` | Frontend agent | UI, grafici, routing |
| `genai-integration.md` | GenAI agent | Claude API, payload, prompt |
| `security.md` | Security agent | GDPR, auth, veto |
| `testing.md` | Testing agent | Test suite, bug catalog |
| `workflow.md` | Tutti (reference) | Come lavoriamo insieme |
