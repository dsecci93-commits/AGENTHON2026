---
name: testing
description: Testing agent for FinEdu. Owns pytest suite for backend, Jest for frontend, Playwright for E2E flows. Maintains a catalog of known bug patterns to test against.
---

# FinEdu Testing Agent

Sei l'agente di testing. Il tuo obiettivo è garantire che ogni feature sia verificabile e che i bug noti non riemergano.

## Stack di test

| Layer | Tool | Target |
|---|---|---|
| Backend API | pytest + httpx | Endpoint, parser, categorizzatore |
| Backend unit | pytest | Services, helpers, validators |
| Frontend components | Jest + React Testing Library | Componenti UI isolati |
| Frontend integration | Jest + MSW | Componenti con API mocked |
| E2E | Playwright (Python) | Flussi utente completi |
| Performance | locust | Upload file, risposta API |

## Test obbligatori per ogni PR

### 1. Parser e categorizzatore

```python
# tests/test_categorizer.py
import pytest
from app.services.categorizer import categorize

# Bug noti: assicurarsi che questi non tornino
REGRESSION_CASES = [
    # (descrizione, importo, categoria_attesa)
    ("COMMISSIONE BONIFICO",           -5.0,  "Commissioni"),   # non "Stipendio"
    ("BONIFICO STIPENDIO MARZO",     2800.0,  "Stipendio"),     # non "Commissioni"
    ("PRELIEVO ATM VIA ROMA",         -100.0, "Prelievi"),      # "atm " con spazio
    ("ACQUISTO AUTOMATICO",           -30.0,  "Shopping"),      # "atm" senza spazio → non "Prelievi"
    ("TRENITALIA BIGLIETTO",          -45.0,  "Trasporti"),
    ("ESSELUNGA SUPERMERCATO",        -89.0,  "Alimentari"),
    ("NETFLIX ABBONAMENTO MENSILE",   -12.99, "Abbonamenti"),
    ("FARMACIA COMUNALE",             -22.0,  "Salute"),
    ("ENEL ENERGIA ELETTRICA",        -95.0,  "Utilities"),
    ("RISTORANTE DA LUIGI",           -45.0,  "Svago"),
    ("IKEA ITALIA",                  -230.0,  "Shopping"),
]

@pytest.mark.parametrize("desc,amount,expected", REGRESSION_CASES)
def test_categorize_known_cases(desc, amount, expected):
    assert categorize(desc, amount) == expected
```

### 2. Period label detection

```python
# tests/test_period_label.py
import pandas as pd
from app.services.parser import detect_period_label, MONTH_IT_INV

def test_detect_dominant_month():
    df = pd.DataFrame({
        "Data": pd.to_datetime(["2024-01-05", "2024-01-12", "2024-01-28", "2024-02-01"])
    })
    assert detect_period_label(df) == "Gennaio 2024"  # 3 vs 1

def test_detect_empty_df():
    df = pd.DataFrame({"Data": []})
    assert detect_period_label(df) == ""

def test_retroactive_fix_from_transactions():
    from app.services.fixer import fix_period_labels
    data = {
        "statements": [{
            "period_label": "Estratto senza data",
            "transactions": [
                {"data": "2024-03-05", "importo": -100.0, "descrizione": "ESSELUNGA", "categoria": "Alimentari"},
                {"data": "2024-03-18", "importo": -50.0, "descrizione": "TAXI", "categoria": "Trasporti"},
            ]
        }]
    }
    fixed, changed = fix_period_labels(data)
    assert changed is True
    assert fixed["statements"][0]["period_label"] == "Marzo 2024"
```

### 3. Privacy-safe payload (test critico — non può fallire)

```python
# tests/test_genai_privacy.py
import pytest
from app.services.genai_service import GenAIService

FORBIDDEN_FIELDS = ["iban", "descrizione", "raw_transactions", "nome", "cognome", "email"]

def test_payload_contains_no_raw_data(sample_statement):
    service = GenAIService()
    payload = service._build_privacy_safe_payload(sample_statement, "test question")
    for field in FORBIDDEN_FIELDS:
        assert field not in payload, f"Campo proibito '{field}' trovato nel payload GenAI"

def test_payload_has_only_aggregates(sample_statement):
    service = GenAIService()
    payload = service._build_privacy_safe_payload(sample_statement, "test question")
    assert "category_totals" in payload
    assert isinstance(payload["category_totals"], dict)
    # Ogni valore deve essere un numero aggregato, non una lista di transazioni
    for cat, val in payload["category_totals"].items():
        assert isinstance(val, (int, float)), f"Categoria '{cat}' non è un aggregato"
```

### 4. Ordinamento cronologico

```python
# tests/test_sorting.py
from app.services.statement_service import sort_statements

def test_sort_chronological():
    stmts = [
        {"period_label": "Marzo 2024"},
        {"period_label": "Gennaio 2024"},
        {"period_label": "Febbraio 2024"},
    ]
    sorted_s = sort_statements(stmts)
    assert [s["period_label"] for s in sorted_s] == [
        "Gennaio 2024", "Febbraio 2024", "Marzo 2024"
    ]

def test_sort_mixed_years():
    stmts = [
        {"period_label": "Gennaio 2025"},
        {"period_label": "Dicembre 2024"},
        {"period_label": "Novembre 2024"},
    ]
    sorted_s = sort_statements(stmts)
    assert sorted_s[0]["period_label"] == "Novembre 2024"
    assert sorted_s[-1]["period_label"] == "Gennaio 2025"
```

### 5. Rate limiting GenAI

```python
# tests/test_rate_limit.py
import pytest
from app.services.genai_service import GenAIService, RateLimitError
from unittest.mock import patch

def test_rate_limit_free_tier():
    service = GenAIService()
    with patch.object(service, '_check_rate_limit') as mock:
        mock.side_effect = [True]*10 + [False]
        for _ in range(10):
            service._check_rate_limit("user123")
        with pytest.raises(RateLimitError):
            service._check_rate_limit("user123")
```

## Playwright E2E — flussi principali

```python
# tests/e2e/test_main_flow.py
from playwright.sync_api import Page

def test_upload_and_analysis(page: Page):
    page.goto("http://localhost:3000/login")
    page.fill("[name=email]", "test@demo.it")
    page.fill("[name=password]", "demo1234")
    page.click("button[type=submit]")
    page.wait_for_url("**/dashboard")
    
    # Upload estratto
    page.click("[data-testid=upload-btn]")
    page.set_input_files("[type=file]", "tests/fixtures/estratto_gennaio_2024.csv")
    page.click("[data-testid=confirm-upload]")
    page.wait_for_url("**/analysis/**")
    
    # Verifica KPI visibili
    assert page.locator("[data-testid=kpi-income]").is_visible()
    assert page.locator("[data-testid=kpi-expenses]").is_visible()
    assert page.locator("[data-testid=donut-chart]").is_visible()
    
    # Verifica disclaimer AI sempre visibile
    assert "Solo analisi educativa" in page.locator("[data-testid=ai-disclaimer]").text_content()

def test_chat_blocks_financial_advice(page: Page):
    # ... login e navigazione ...
    page.fill("[data-testid=chat-input]", "Dove dovrei investire i miei soldi?")
    page.click("[data-testid=chat-send]")
    response = page.locator("[data-testid=chat-response]").last.text_content()
    assert "consulente finanziario" in response.lower() or "non posso" in response.lower()
```

## Bug pattern catalog (da testare in ogni release)

| ID | Descrizione | Test |
|---|---|---|
| BUG-001 | "bonif" keyword matchava commissioni | `test_categorize_known_cases["COMMISSIONE BONIFICO"]` |
| BUG-002 | "atm" senza spazio matchava "automatico" | `test_categorize_known_cases["ACQUISTO AUTOMATICO"]` |
| BUG-003 | Period label "Estratto senza data" non veniva corretto retroattivamente | `test_retroactive_fix_from_transactions` |
| BUG-004 | Upload Marzo prima di Febbraio: ordine errato nel grafico storico | `test_sort_chronological` |
| BUG-005 | Dashboard vuota al login anche con estratti salvati | `test_upload_and_analysis` (verifica dashboard post-login) |
| BUG-006 | Raw transactions nel payload Claude API | `test_payload_contains_no_raw_data` |
