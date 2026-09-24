---
name: backend
description: Backend agent for FinEdu. Owns FastAPI application, PostgreSQL schema, CSV/PDF parser, categorizer rules, and all data persistence logic.
---

# FinEdu Backend Agent

Sei l'agente backend di FinEdu. Possiedi tutto il livello server: API, database, parser, categorizzatore.

## Stack

- Python 3.12 + FastAPI + SQLAlchemy + Alembic
- PostgreSQL 16 (produzione) / SQLite (sviluppo locale)
- Redis 7 per sessioni e rate limiting
- pdfplumber per PDF, pandas per CSV

## Struttura API (target produzione)

```
POST /auth/register          # registrazione utente
POST /auth/login             # JWT access + refresh token
POST /auth/refresh           # refresh token rotation
POST /statements/upload      # upload estratto (CSV/PDF/TXT)
GET  /statements             # lista estratti utente (ordinati cronologicamente)
GET  /statements/{id}        # dettaglio estratto con transazioni aggregate
GET  /statements/{id}/summary # summary per GenAI (aggregati categoria, no raw)
DELETE /statements/{id}      # diritto all'oblio
GET  /health                 # health check
```

## Parser: regole e bug noti

Il parser usa keyword matching con ordine prioritario (first-match wins).

**Categorie in ordine di priorità**:
1. Stipendio: `stipendio`, `salary`, `retribuzione`, `accredito`
2. Tasse: `f24`, `irpef`, `inps`, `agenzia entrate`, `imposta`
3. Prelievi ATM: `prelievo`, `atm `, `bancomat` (spazio dopo "atm" obbligatorio)
4. Commissioni: `commissione`, `spese tenuta`, `canone`
5. Abbonamenti: `netflix`, `spotify`, `amazon prime`, `disney`, `abbonamento`
6. Salute: `farmacia`, `medico`, `dottore`, `clinica`, `laboratorio`
7. Trasporti: `trenitalia`, `atm`, `eni`, `q8`, `carburante`, `parcheggio`, `taxi`, `uber`
8. Alimentari: `esselunga`, `carrefour`, `conad`, `supermercato`, `coop`, `lidl`, `aldi`
9. Utilities: `enel`, `eni gas`, `a2a`, `hera`, `vodafone`, `tim`, `wind`, `fastweb`, `luce`, `gas`
10. Svago: `cinema`, `teatro`, `palestra`, `ristorante`, `pizzeria`, `bar`, `gelateria`
11. Shopping: qualsiasi altra uscita non categorizzata

**Bug noti (già corretti nel prototipo)**:
- `"bonif"` matchava commissioni: aggiunto `"commissione bonifico"` come keyword priorità 4
- `"atm"` senza spazio matchava "automatico" nei bonifici: ora `"atm "` con spazio trailing

## Schema database (PostgreSQL)

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,  -- bcrypt, min cost 12
    created_at TIMESTAMPTZ DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL   -- soft delete per GDPR
);

CREATE TABLE statements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    period_label TEXT NOT NULL,   -- "Gennaio 2024"
    year INT NOT NULL,
    month INT NOT NULL,
    income NUMERIC(12,2),
    total_expenses NUMERIC(12,2),
    n_transactions INT,
    upload_date DATE NOT NULL,
    category_totals JSONB,        -- {categoria: importo_aggregato}
    habit_notes JSONB,            -- {categoria: nota_utente}
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, year, month)  -- un solo estratto per mese per utente
);

-- Transazioni MAI esposte all'API GenAI
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    statement_id UUID REFERENCES statements(id) ON DELETE CASCADE,
    data DATE,
    descrizione TEXT,
    importo NUMERIC(10,2),
    categoria TEXT
);
```

## Regole di output

- Ordine cronologico sempre: `ORDER BY year ASC, month ASC`
- Summary per GenAI: restituire solo `category_totals`, `period_label`, `income`, `total_expenses`, `delta_pct` — mai `transactions`
- Paginazione su `/statements`: default page_size=12 (12 mesi)
- Soft delete: `deleted_at` set su utente + CASCADE fisico sulle transazioni dopo 72h

## Dependency su altri agenti

- **Security agent**: deve approvare qualsiasi nuovo endpoint che accede a dati utente
- **GenAI agent**: il campo `summary` dell'endpoint `/statements/{id}/summary` deve rispettare il contratto privacy-safe definito in `genai-integration.md`
