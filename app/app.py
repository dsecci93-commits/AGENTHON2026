"""
Tool Educativo: Lettura Estratto Conto
VIETATO fornire raccomandazioni d'investimento o consulenza finanziaria personalizzata.
"""

import hashlib
import io
import json
import os
import pathlib
import re
import time
from collections import defaultdict
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    import pdfplumber
    PDF_OK = True
except ImportError:
    PDF_OK = False

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = pathlib.Path(__file__).parent
USERS_DIR  = BASE_DIR / "data" / "users"
SAMPLE_DIR = BASE_DIR / "data" / "samples"
USERS_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_OPTIONS = {
    "— nessuno —": None,
    "Gennaio 2024 (esempio)": SAMPLE_DIR / "sample_gennaio_2024.csv",
    "Febbraio 2024 (esempio)": SAMPLE_DIR / "sample_febbraio_2024.csv",
    "Marzo 2024 (esempio)": SAMPLE_DIR / "sample_marzo_2024.csv",
}

# ── Palette ───────────────────────────────────────────────────────────────────
INCOME_COLOR = "#00C49A"
CATEGORY_COLORS = {
    "Stipendio & Entrate":       "#00C49A",
    "Alimentari & Supermercati": "#4361EE",
    "Trasporti":                 "#3A0CA3",
    "Salute & Farmacia":         "#7209B7",
    "Svago & Ristorazione":      "#F72585",
    "Shopping & Abbigliamento":  "#FF9F1C",
    "Casa & Utenze":             "#2EC4B6",
    "Abbonamenti & Servizi":     "#E9C46A",
    "Prelievi ATM":              "#6D6875",
    "Commissioni & Spese":       "#B5838D",
    "Altro":                     "#ADB5BD",
}

# ── Categorization rules ───────────────────────────────────────────────────────
KEYWORD_RULES = [
    ("Stipendio & Entrate",       ["stipendio", "accredito", "rimborso", "pensione", "cedolino"]),
    ("Alimentari & Supermercati", ["supermercati", "supermercato", "coop", "esselunga", "lidl",
                                   "aldi", "conad", "eurospin", "carrefour", "penny", "tigros",
                                   "pam ", "iper", "ipercoop", "simply", "bennet"]),
    ("Casa & Utenze",             ["enel", "eni gas", "a2a ", "hera ", "iren ", "sorgenia",
                                   "tim ", "vodafone", "windtre", "iliad", "fastweb",
                                   "affitto", "mutuo", "condominio", "bolletta"]),
    ("Abbonamenti & Servizi",     ["netflix", "spotify", "disney", "apple.com", "google play",
                                   "dazn", "sky ", "adobe", "dropbox", "icloud", "abbonamento",
                                   "amazon prime", "youtube premium", "paramount"]),
    ("Trasporti",                 ["trenitalia", "italo ", "flixbus", "frecciarossa",
                                   "autogrill", "autobus", "atm milan", "atac ",
                                   "carburante", "benzina", "q8 ", "eni staz",
                                   "ip staz", "esso ", "tamoil", "parcheggio",
                                   "taxi", "uber ", "bolt ", "telepass", "autostrad"]),
    ("Salute & Farmacia",         ["farmacia", "medico", "dottore", "ottico", "dentista",
                                   "clinica", "ospedale", "sanitari", "parafarmacia",
                                   "analisi", "fisioterapia", "laboratorio", "specialista"]),
    ("Svago & Ristorazione",      ["ristorante", "trattoria", "osteria", "pizzeria", "sushi",
                                   "bar ", "caffe ", "mc donald", "burger", "pizza",
                                   "cinema", "teatro", "concerti", "ticketmaster",
                                   "deliveroo", "just eat", "glovo", "ubereats",
                                   "palestra", "piscina", "sport club", "fitness",
                                   "museo", "parco divertiment", "escape room"]),
    ("Shopping & Abbigliamento",  ["amazon", "zara", "h&m", "primark", "pull&bear",
                                   "mango ", "massimo dutti", "ikea", "leroy merlin",
                                   "decathlon", "zalando", "asos", "shein",
                                   "mediaworld", "unieuro", "euronics", "apple store",
                                   "booking", "airbnb", "expedia"]),
    ("Prelievi ATM",              ["prelievo", "sportello atm", "bancomat", "prelievo contante"]),
    ("Commissioni & Spese",       ["canone", "commissione", "imposta", "bollo", "costo servizio",
                                   "spese tenuta"]),
]


def categorize(df: pd.DataFrame) -> pd.DataFrame:
    def _cat(desc: str, amt: float) -> str:
        desc_lower = desc.lower()
        for cat, keywords in KEYWORD_RULES:
            if any(k in desc_lower for k in keywords):
                if cat == "Stipendio & Entrate" and amt < 0:
                    continue
                return cat
        return "Altro"

    df = df.copy()
    df["Categoria"] = df.apply(lambda r: _cat(r["Descrizione"], r["Importo"]), axis=1)
    return df


# ── CSV/TXT Parsing ────────────────────────────────────────────────────────────
def _normalize_amount(s: str) -> float | None:
    s = s.strip()
    if not s:
        return None
    try:
        clean = s.replace(" ", "")
        if re.search(r"\d\.\d{3}(?:,|$)", clean):
            clean = clean.replace(".", "").replace(",", ".")
        elif "," in clean and "." in clean:
            clean = clean.replace(",", "")
        elif "," in clean:
            clean = clean.replace(",", ".")
        return float(clean)
    except ValueError:
        return None


def _parse_dates(series: pd.Series) -> pd.Series:
    # Try without dayfirst (handles ISO YYYY-MM-DD correctly)
    result = pd.to_datetime(series, errors="coerce", dayfirst=False)
    if result.isna().mean() > 0.3:
        # Fallback: European format DD/MM/YYYY
        result2 = pd.to_datetime(series, errors="coerce", dayfirst=True)
        if result2.isna().mean() < result.isna().mean():
            return result2
    return result


def _detect_columns(df: pd.DataFrame) -> pd.DataFrame | None:
    col_map: dict[str, str] = {}
    for c in df.columns:
        cl = str(c).lower()
        if any(k in cl for k in ["data", "date"]) and "Data" not in col_map.values():
            col_map[c] = "Data"
        elif any(k in cl for k in ["descr", "causale", "dicitura", "movim"]):
            col_map[c] = "Descrizione"
        elif any(k in cl for k in ["import", "amount", "valore", "entrate", "uscite"]):
            if "Importo" not in col_map.values():
                col_map[c] = "Importo"
    if "Data" not in col_map.values() or "Descrizione" not in col_map.values() or "Importo" not in col_map.values():
        return None
    df = df.rename(columns=col_map)[["Data", "Descrizione", "Importo"]]
    df["Importo"] = df["Importo"].apply(lambda x: _normalize_amount(str(x)))
    df = df.dropna(subset=["Importo"])
    df["Data"] = _parse_dates(df["Data"])
    df = df.dropna(subset=["Data"])
    return df


def parse_csv_txt(content: str) -> pd.DataFrame | None:
    for sep in [",", ";", "\t", "|"]:
        try:
            df = pd.read_csv(io.StringIO(content), sep=sep, dtype=str)
            if len(df.columns) >= 3:
                result = _detect_columns(df)
                if result is not None and len(result) > 0:
                    return result
        except Exception:
            continue
    return None


def _parse_text_regex(text: str) -> pd.DataFrame | None:
    date_pat   = r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})"
    amount_pat = r"([+-]?\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)"
    rows = []
    for line in text.splitlines():
        dm = re.search(date_pat, line)
        am = re.findall(amount_pat, line)
        if dm and am:
            desc = re.sub(date_pat, "", line)
            desc = re.sub(amount_pat, "", desc).strip(" |;,-\t")
            amt  = _normalize_amount(am[-1])
            if amt is not None:
                rows.append({"Data": dm.group(1), "Descrizione": desc, "Importo": amt})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["Data"] = _parse_dates(df["Data"])
    return df.dropna(subset=["Data"]) if len(df) else None


def parse_pdf(file_bytes: bytes) -> pd.DataFrame | None:
    if not PDF_OK:
        return None
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        tables = []
        all_text = ""
        for page in pdf.pages:
            for tbl in page.extract_tables():
                if tbl:
                    tables.append(tbl)
            all_text += (page.extract_text() or "") + "\n"
        for tbl in tables:
            try:
                df = pd.DataFrame(tbl[1:], columns=tbl[0], dtype=str)
                result = _detect_columns(df)
                if result is not None and len(result) > 0:
                    return result
            except Exception:
                continue
        return _parse_text_regex(all_text)


# ── Month name lookup (needed before load_user_data) ──────────────────────────
_MONTH_IT_INV = {
    1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
    5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
    9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre",
}

def _sort_statements(stmts: list[dict]) -> list[dict]:
    _mnum = {v.lower(): k for k, v in _MONTH_IT_INV.items()}
    def _key(s):
        parts = s.get("period_label", "").split()
        try:
            return (int(parts[1]), _mnum.get(parts[0].lower(), 0))
        except Exception:
            return (0, 0)
    return sorted(stmts, key=_key)


def _df_from_stmt(stmt: dict) -> pd.DataFrame:
    rows = stmt.get("transactions", [])
    if not rows:
        return pd.DataFrame(columns=["Data", "Descrizione", "Importo", "Categoria"])
    df = pd.DataFrame(rows).rename(columns={
        "data": "Data", "descrizione": "Descrizione",
        "importo": "Importo", "categoria": "Categoria",
    })
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    return df


# ── Data persistence ───────────────────────────────────────────────────────────
def _user_file(username: str) -> pathlib.Path:
    return USERS_DIR / f"{username.lower().strip()}.json"


def _fix_period_labels(data: dict) -> tuple[dict, bool]:
    changed = False
    for stmt in data.get("statements", []):
        if stmt.get("period_label", "") not in ("", "Estratto senza data"):
            continue
        txs = stmt.get("transactions", [])
        if not txs:
            continue
        dates = pd.to_datetime(
            [t["data"] for t in txs if t.get("data")], errors="coerce"
        ).dropna()
        if dates.empty:
            continue
        dominant = dates.to_period("M").value_counts().idxmax()
        label = f"{_MONTH_IT_INV.get(dominant.month, str(dominant.month))} {dominant.year}"
        stmt["period_label"] = label
        changed = True
    return data, changed


def load_user_data(username: str) -> dict:
    fp = _user_file(username)
    if fp.exists():
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
            data, changed = _fix_period_labels(data)
            sorted_stmts = _sort_statements(data.get("statements", []))
            if sorted_stmts != data.get("statements", []):
                data["statements"] = sorted_stmts
                changed = True
            if changed:
                fp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            return data
        except Exception:
            pass
    return {"username": username, "statements": []}


def save_statement(username: str, df: pd.DataFrame, label: str, habit_notes: dict) -> dict:
    data     = load_user_data(username)
    expenses = df[df["Importo"] < 0].copy()
    income   = float(df[df["Categoria"] == "Stipendio & Entrate"]["Importo"].sum())
    cat_totals = (
        expenses[expenses["Categoria"] != "Stipendio & Entrate"]
        .groupby("Categoria")["Importo"]
        .sum()
        .abs()
        .to_dict()
    )
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "data":       r["Data"].strftime("%Y-%m-%d") if pd.notna(r["Data"]) else "",
            "descrizione": str(r["Descrizione"]),
            "importo":    float(r["Importo"]),
            "categoria":  str(r["Categoria"]),
        })
    stmt = {
        "id":             datetime.now().strftime("%Y%m%d_%H%M%S"),
        "upload_date":    datetime.now().strftime("%Y-%m-%d"),
        "period_label":   label,
        "income":         income,
        "total_expenses": float(sum(cat_totals.values())),
        "n_transactions": len(df),
        "category_totals": cat_totals,
        "habit_notes":    habit_notes,
        "transactions":   rows,
    }
    data["statements"].append(stmt)
    _user_file(username).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return stmt


# ── Auth ──────────────────────────────────────────────────────────────────────
def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def user_exists(username: str) -> bool:
    return _user_file(username).exists()


def register_user(username: str, password: str) -> None:
    data = {"username": username, "password_hash": _hash_pw(password), "statements": []}
    _user_file(username).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def authenticate(username: str, password: str) -> bool:
    data = load_user_data(username)
    stored = data.get("password_hash")
    if not stored:
        return False
    return stored == _hash_pw(password)


def set_password(username: str, password: str) -> None:
    data = load_user_data(username)
    data["password_hash"] = _hash_pw(password)
    _user_file(username).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _login_success(username: str):
    udata = load_user_data(username)
    stmts = udata.get("statements", [])
    st.session_state["user"]           = username
    st.session_state["all_statements"] = stmts
    st.session_state["page"]           = "dashboard"
    st.session_state.pop("login_mode", None)
    if stmts:
        last = stmts[-1]
        st.session_state["current_stmt"]  = last
        st.session_state["current_df"]    = _df_from_stmt(last)
        st.session_state["current_label"] = last["period_label"]
        st.session_state["chat_history"]  = []
        st.session_state["habit_notes"]   = last.get("habit_notes", {})


# ── Comparison ─────────────────────────────────────────────────────────────────
SIGNIFICANT_PCT = 20.0
SIGNIFICANT_ABS = 10.0


def _history_summary(all_stmts: list[dict]) -> dict:
    if not all_stmts:
        return {}
    labels   = [s["period_label"]   for s in all_stmts]
    incomes  = [s["income"]         for s in all_stmts]
    expenses = [s["total_expenses"] for s in all_stmts]
    balances = [i - e for i, e in zip(incomes, expenses)]
    best_idx  = balances.index(max(balances))
    worst_idx = balances.index(min(balances))
    cat_sums: dict[str, float] = defaultdict(float)
    cat_cnt:  dict[str, int]   = defaultdict(int)
    for s in all_stmts:
        for cat, val in s["category_totals"].items():
            cat_sums[cat] += val
            cat_cnt[cat]  += 1
    cat_avgs = {cat: cat_sums[cat] / cat_cnt[cat] for cat in cat_sums}
    return {
        "labels":   labels,
        "incomes":  incomes,
        "expenses": expenses,
        "balances": balances,
        "best":     (labels[best_idx],  balances[best_idx]),
        "worst":    (labels[worst_idx], balances[worst_idx]),
        "cat_avgs": cat_avgs,
        "n_months": len(all_stmts),
    }


def compare_statements(current: dict, previous: dict) -> list[dict]:
    all_cats = set(current["category_totals"]) | set(previous["category_totals"])
    results = []
    for cat in all_cats:
        prev_v = previous["category_totals"].get(cat, 0.0)
        curr_v = current["category_totals"].get(cat, 0.0)
        delta  = curr_v - prev_v
        pct    = ((curr_v - prev_v) / prev_v * 100) if prev_v else (100.0 if curr_v else 0.0)
        sig    = abs(pct) >= SIGNIFICANT_PCT and abs(delta) >= SIGNIFICANT_ABS
        results.append({
            "categoria":   cat,
            "previous":    prev_v,
            "current":     curr_v,
            "delta":       delta,
            "pct":         pct,
            "significant": sig,
        })
    results.sort(key=lambda x: abs(x["delta"]), reverse=True)
    return results


# ── Educational content ────────────────────────────────────────────────────────
CAT_EDU = {
    "Alimentari & Supermercati": (
        "La spesa alimentare è spesso il costo variabile più gestibile. "
        "Pianificare la lista prima di andare al supermercato riduce acquisti impulsivi. "
        "Confrontare i prezzi tra insegne diverse e sfruttare i prodotti a marchio privato "
        "sono tecniche consolidate per contenere questa voce."
    ),
    "Casa & Utenze": (
        "Le utenze domestiche (luce, gas, telefono) hanno tariffe regolamentate o di mercato libero. "
        "Confrontare periodicamente i fornitori e scegliere offerte a tariffa fissa può ridurre "
        "la variabilità mensile. Piccoli comportamenti — spegnere le luci, regolare il termostato — "
        "hanno impatto cumulativo nel tempo."
    ),
    "Trasporti": (
        "Il costo dei trasporti dipende dalla modalità scelta. L'auto privata comporta "
        "carburante, assicurazione, manutenzione e parcheggio. I mezzi pubblici o la bici, "
        "quando accessibili, hanno costi sensibilmente inferiori. "
        "L'abbonamento annuale ai mezzi pubblici conviene se usato regolarmente."
    ),
    "Svago & Ristorazione": (
        "Questa categoria è spesso la prima a crescere in modo non pianificato. "
        "Distinguere tra svago programmato (biglietti teatro, vacanze) e spese impulsive "
        "aiuta a mantenere il controllo. I servizi di food delivery tendono ad avere "
        "costi unitari superiori rispetto a mangiare al ristorante o cucinare in casa."
    ),
    "Shopping & Abbigliamento": (
        "Gli acquisti online facilitano la comparazione prezzi ma rendono più semplice "
        "la spesa impulsiva. Tecniche come la 'regola delle 24 ore' (aspettare prima di "
        "completare un acquisto) aiutano a distinguere i bisogni reali dagli impulsi. "
        "Le stagioni di saldi sono un'opportunità ma solo per ciò che era già pianificato."
    ),
    "Salute & Farmacia": (
        "Le spese sanitarie hanno carattere parzialmente imprevedibile. "
        "Distinguere tra spese ricorrenti (farmaci cronici, visite periodiche) e straordinarie "
        "aiuta la pianificazione. I farmaci equivalenti (generici) hanno lo stesso principio "
        "attivo dei branded a costo inferiore — verifica con il medico se sono adatti."
    ),
    "Abbonamenti & Servizi": (
        "Gli abbonamenti sono spese fisse spesso dimenticate. Fare periodicamente una "
        "revisione di tutti gli abbonamenti attivi — streaming, cloud, app, palestre — "
        "e valutare quali sono effettivamente usati è una pratica di igiene finanziaria. "
        "L'accumulo di piccoli abbonamenti può raggiungere cifre significative mensili."
    ),
    "Prelievi ATM": (
        "Il contante è difficile da tracciare perché le singole uscite non vengono registrate. "
        "Se i prelievi ATM sono frequenti, considera di sostituirli con pagamenti elettronici "
        "così da avere visibilità completa su tutte le spese nel tuo estratto conto."
    ),
    "Commissioni & Spese": (
        "Le commissioni bancarie sono spese fisse che variano molto tra istituti e conti. "
        "Verificare periodicamente il canone del conto e le commissioni di operazione "
        "permette di valutare se ci sono offerte più convenienti sul mercato."
    ),
    "Stipendio & Entrate": (
        "Le entrate sono il punto di partenza della gestione finanziaria personale. "
        "Avere chiarezza sulle entrate nette mensili — stipendio, rimborsi, altri redditi — "
        "è il primo passo per costruire un budget realistico."
    ),
    "Altro": (
        "Alcune transazioni non rientrano facilmente in una categoria standard. "
        "Classificarle manualmente nel tempo aiuta a costruire una mappa più precisa "
        "delle proprie abitudini di spesa."
    ),
}

GLOSSARY = {
    "IBAN": "Identificativo Bancario Internazionale — codice alfanumerico che identifica univocamente un conto corrente.",
    "Saldo": "Differenza tra entrate e uscite su un conto in un dato momento.",
    "Estratto conto": "Documento che riepiloga tutte le transazioni su un conto in un periodo.",
    "RID / SDD": "Addebito diretto autorizzato — il creditore preleva automaticamente l'importo dal conto.",
    "Bonifico": "Trasferimento di denaro da un conto all'altro tramite circuito bancario.",
    "SWIFT/BIC": "Codice internazionale che identifica la banca in un bonifico estero.",
    "Valuta": "Data da cui gli interessi decorrono su una transazione (può differire dalla data contabile).",
    "Commissione": "Costo addebitato dalla banca per un servizio specifico.",
    "Canone": "Costo fisso ricorrente per il mantenimento del conto corrente.",
    "Fido": "Linea di credito revolving legata al conto corrente.",
}

QUIZ_ITEMS = [
    ("Cosa indica il 'saldo' di un conto?",
     ["Il totale delle spese del mese", "La differenza tra entrate e uscite in un dato momento",
      "Il numero di transazioni effettuate", "L'importo massimo prelevabile"],
     1),
    ("Cos'è un RID/SDD?",
     ["Un tipo di bonifico urgente", "Un addebito diretto autorizzato dal titolare",
      "Un prelievo ATM internazionale", "Un'imposta bancaria obbligatoria"],
     1),
    ("Quale dato NON compare tipicamente in un estratto conto?",
     ["Data della transazione", "Descrizione della causale",
      "Codice fiscale del beneficiario", "Importo della transazione"],
     2),
    ("Cosa distingue la 'data valuta' dalla 'data contabile'?",
     ["Nessuna differenza, sono sinonimi",
      "La data valuta è quando il denaro è disponibile, la contabile quando appare nel registro",
      "La contabile è sempre successiva alla valuta",
      "La valuta riguarda solo i bonifici esteri"],
     1),
    ("Un farmaco equivalente (generico) rispetto al branded:",
     ["Ha meno efficacia clinica", "Contiene lo stesso principio attivo a costo inferiore",
      "È disponibile solo su prescrizione medica", "Ha una scadenza più breve"],
     1),
]


def stream_sentences(text: str, delay: float = 0.18):
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    buffer = ""
    for sent in sentences:
        buffer += sent + " "
        yield buffer
        time.sleep(delay)


def build_educational_text(df: pd.DataFrame) -> str:
    cats_present = df["Categoria"].unique()
    lines = ["## Cosa ci racconta il tuo estratto conto\n"]
    for cat, text in CAT_EDU.items():
        if cat in cats_present and cat != "Stipendio & Entrate":
            lines.append(f"### {cat}\n{text}\n")
    return "\n".join(lines) if len(lines) > 1 else (
        "Carica un estratto conto per ricevere contenuti educativi personalizzati."
    )


# ── Chat agent ─────────────────────────────────────────────────────────────────
HABIT_SUGGESTIONS = {
    "Alimentari & Supermercati": {
        "up":   ["Ospiti a casa", "Cambio supermercato", "Prezzi aumentati", "Più pasti a casa"],
        "down": ["Meno spesa settimanale", "Più pasti fuori", "Cambio supermercato"],
    },
    "Trasporti": {
        "up":   ["Cambio lavoro/percorso", "Vacanza in auto", "Prezzo carburante", "Manutenzione"],
        "down": ["Smart working", "Cambio mezzo", "Meno spostamenti"],
    },
    "Svago & Ristorazione": {
        "up":   ["Evento speciale", "Ospiti", "Vacanza", "Più uscite sociali"],
        "down": ["Meno uscite", "Più cucina in casa", "Budget ridotto"],
    },
    "Shopping & Abbigliamento": {
        "up":   ["Acquisto straordinario", "Nuova stagione", "Necessità imprevista"],
        "down": ["Nessun acquisto straordinario", "Fine stagione"],
    },
    "Casa & Utenze": {
        "up":   ["Stagione invernale/estiva", "Nuova utenza", "Nuova tariffa"],
        "down": ["Cambio fornitore", "Meno presenza in casa"],
    },
    "Salute & Farmacia": {
        "up":   ["Influenza/malattia", "Visita specialistica", "Stagione influenzale"],
        "down": ["Fine terapia", "Meno acciacchi"],
    },
    "Abbonamenti & Servizi": {
        "up":   ["Nuovo abbonamento", "Rinnovo annuale"],
        "down": ["Disdetto abbonamento", "Promozione scaduta"],
    },
    "Prelievi ATM": {
        "up":   ["Più spese in contante", "Esigenza specifica"],
        "down": ["Più pagamenti digitali"],
    },
}


_MONTH_IT = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4,
    "maggio": 5, "giugno": 6, "luglio": 7, "agosto": 8,
    "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}

def _detect_period_label(df: pd.DataFrame) -> str:
    if "Data" not in df.columns:
        return ""
    dates = pd.to_datetime(df["Data"], errors="coerce").dropna()
    if dates.empty:
        return ""
    dominant = dates.dt.to_period("M").value_counts().idxmax()
    return f"{_MONTH_IT_INV.get(dominant.month, str(dominant.month))} {dominant.year}"


def get_chat_response(question: str, df: pd.DataFrame | None) -> str:
    q        = question.lower()
    all_stmts: list[dict] = st.session_state.get("all_statements", [])
    hist      = _history_summary(all_stmts) if all_stmts else {}
    n_months  = hist.get("n_months", 0)

    # ── Saluto ────────────────────────────────────────────────────────────────
    if any(k in q for k in ["ciao", "salve", "buongiorno", "buonasera", "hey"]):
        return (
            "Ciao! Sono il tuo assistente educativo finanziario. "
            "Puoi chiedermi spiegazioni sulle categorie di spesa, sui termini bancari, "
            "sui tuoi dati storici o consigli generali su come leggere l'estratto conto. "
            "Cosa vuoi sapere?"
        )

    # ── Aiuto ─────────────────────────────────────────────────────────────────
    if any(k in q for k in ["aiuto", "cosa sai", "cosa puoi", "cosa fai"]):
        extra = f" Ho accesso a **{n_months} mesi** di storico." if n_months > 1 else ""
        return (
            f"Posso aiutarti a capire:{extra}\n"
            "- Le categorie di spesa nel tuo estratto conto\n"
            "- Termini bancari (saldo, IBAN, RID...)\n"
            "- Confronto con il mese precedente o con la media storica\n"
            "- Trend e andamento delle spese nel tempo\n"
            "- Il mese migliore e peggiore del tuo storico\n"
            "- Media mensile per categoria\n\n"
            "*Non fornisco consigli di investimento o raccomandazioni finanziarie personalizzate.*"
        )

    # ── Quanti mesi / storico completo ────────────────────────────────────────
    if any(k in q for k in ["quanti mesi", "quanti estratti", "storico completo", "storico disponibile"]):
        if n_months == 0:
            return "Non hai ancora caricato nessun estratto conto. Caricane uno per iniziare."
        labels = hist["labels"]
        return (
            f"Ho **{n_months} {"mese" if n_months == 1 else "mesi"}** di storico:\n"
            + "\n".join(f"- {l}" for l in labels)
        )

    # ── Mese migliore ─────────────────────────────────────────────────────────
    if any(k in q for k in ["migliore mese", "mese migliore", "speso meno", "risparmio maggiore"]):
        if n_months < 2:
            return "Ho bisogno di almeno 2 mesi di storico per trovare il mese migliore. Carica un altro estratto."
        lbl, bal = hist["best"]
        return f"Il mese con il **saldo migliore** è **{lbl}**, con un saldo positivo di €{bal:.0f}."

    # ── Mese peggiore ─────────────────────────────────────────────────────────
    if any(k in q for k in ["peggiore mese", "mese peggiore", "speso di più", "spese maggiori", "speso tanto"]):
        if n_months < 2:
            return "Ho bisogno di almeno 2 mesi di storico per trovare il mese peggiore. Carica un altro estratto."
        lbl, bal = hist["worst"]
        return f"Il mese con il **saldo peggiore** è **{lbl}**, con un saldo di €{bal:.0f}."

    # ── Trend / storico ───────────────────────────────────────────────────────
    if any(k in q for k in ["trend", "andamento storico", "negli ultimi mesi", "storico", "evoluzione"]):
        if n_months < 2:
            return "Ho bisogno di almeno 2 mesi di storico per mostrare il trend. Carica un altro estratto."
        lines = [f"**Andamento su {n_months} mesi:**\n"]
        for i, lbl in enumerate(hist["labels"]):
            inc = hist["incomes"][i]
            exp = hist["expenses"][i]
            bal = hist["balances"][i]
            sign = "+" if bal >= 0 else ""
            lines.append(f"📅 **{lbl}**: entrate €{inc:.0f} | uscite €{exp:.0f} | saldo {sign}€{bal:.0f}")
        return "\n".join(lines)

    # ── Media storica per categoria ───────────────────────────────────────────
    if any(k in q for k in ["media", "mediamente", "in media", "spendo mediamente"]):
        if n_months < 2:
            return "Ho bisogno di almeno 2 mesi di storico per calcolare le medie. Carica un altro estratto."
        cat_avgs = hist["cat_avgs"]
        top = sorted(cat_avgs.items(), key=lambda x: x[1], reverse=True)[:6]
        lines = [f"**Spesa media mensile su {n_months} mesi:**\n"]
        for cat, avg in top:
            lines.append(f"- **{cat}**: €{avg:.0f}/mese")
        lines.append("\n*Dati educativi, non consulenza finanziaria.*")
        return "\n".join(lines)

    # ── Lookup mese specifico ─────────────────────────────────────────────────
    for month_it, month_num in _MONTH_IT.items():
        if month_it in q and n_months > 0:
            match = next((s for s in all_stmts if month_it in s["period_label"].lower()), None)
            if match:
                bal = match["income"] - match["total_expenses"]
                sign = "+" if bal >= 0 else ""
                cats = sorted(match["category_totals"].items(), key=lambda x: x[1], reverse=True)[:4]
                lines = [f"**{match['period_label']}**:\n",
                         f"Entrate: €{match['income']:.0f} | Uscite: €{match['total_expenses']:.0f} | Saldo: {sign}€{bal:.0f}\n",
                         "Categorie principali:"]
                for cat, val in cats:
                    lines.append(f"- {cat}: €{val:.0f}")
                return "\n".join(lines)
            else:
                return f"Non ho dati per {month_it} nel tuo storico."

    # ── Confronto vs precedente / media ──────────────────────────────────────
    if any(k in q for k in ["confronto", "mese scorso", "precedente", "cambiato", "come va", "andamento"]):
        comparison = st.session_state.get("comparison")
        if comparison:
            sig = [c for c in comparison if c["significant"]]
            lines = []
            if sig:
                lines = ["Rispetto al **periodo precedente**, le variazioni più rilevanti sono:\n"]
                for c in sig[:5]:
                    arrow = "📈" if c["delta"] > 0 else "📉"
                    direction = "aumentate" if c["delta"] > 0 else "diminuite"
                    lines.append(f"{arrow} **{c['categoria']}**: {direction} di €{abs(c['delta']):.0f} ({c['pct']:+.0f}%)")
            else:
                lines = ["Rispetto al periodo precedente nessuna variazione significativa — andamento stabile."]
            if n_months >= 3:
                curr_exp = st.session_state.get("pending_stmt_data", {}).get("total_expenses", 0)
                if curr_exp and hist.get("cat_avgs"):
                    avg_exp = sum(hist["expenses"][:-1]) / (n_months - 1)
                    delta_avg = curr_exp - avg_exp
                    sign = "+" if delta_avg >= 0 else ""
                    lines.append(f"\nVs **media storica ({n_months-1} mesi)**: {sign}€{delta_avg:.0f} ({'sopra' if delta_avg > 0 else 'sotto'} la media).")
            return "\n".join(lines)
        return "Non ho dati di confronto disponibili. Carica almeno due estratti conto per vedere l'andamento."

    # ── Consigli risparmio ────────────────────────────────────────────────────
    if any(k in q for k in ["risparmia", "spendo troppo", "risparmiare", "spese alte"]) and df is not None:
        exp_df = df[df["Importo"] < 0].copy()
        exp_df = exp_df[exp_df["Categoria"] != "Stipendio & Entrate"]
        top = exp_df.groupby("Categoria")["Importo"].sum().abs().sort_values(ascending=False).head(3)
        lines = ["Le tre categorie con la spesa maggiore sono:\n"]
        for cat, val in top.items():
            edu = CAT_EDU.get(cat, "")
            tip = edu[:120] + "..." if len(edu) > 120 else edu
            avg_str = ""
            if cat in hist.get("cat_avgs", {}):
                avg = hist["cat_avgs"][cat]
                avg_str = f" (media storica: €{avg:.0f})"
            lines.append(f"**{cat}** — €{val:.0f}{avg_str}\n{tip}\n")
        lines.append("*Informazioni educative, non consigli finanziari personalizzati.*")
        return "\n".join(lines)

    # ── Categoria specifica ───────────────────────────────────────────────────
    if df is not None:
        for cat in CATEGORY_COLORS:
            cat_key = cat.lower().replace("&", "").replace("  ", " ")
            if cat_key in q or any(w in q for w in cat_key.split() if len(w) > 4):
                cat_data = df[df["Categoria"] == cat]
                if len(cat_data):
                    total = abs(cat_data["Importo"].sum())
                    n     = len(cat_data)
                    edu   = CAT_EDU.get(cat, "")
                    avg_str = ""
                    if cat in hist.get("cat_avgs", {}) and n_months >= 2:
                        avg = hist["cat_avgs"][cat]
                        delta = total - avg
                        avg_str = f"\n\nRispetto alla media storica (€{avg:.0f}/mese): **{'sopra' if delta > 0 else 'sotto'} di €{abs(delta):.0f}**."
                    return (
                        f"In **{cat}** hai registrato **{n} transazioni** per €{total:.2f} questo mese."
                        f"{avg_str}\n\n{edu}\n\n*Informazione educativa, non consulenza finanziaria.*"
                    )

    # ── Glossario ─────────────────────────────────────────────────────────────
    for term, defn in GLOSSARY.items():
        if term.lower() in q:
            return f"**{term}**: {defn}"

    # ── Riepilogo generico ────────────────────────────────────────────────────
    if any(k in q for k in ["totale", "quanto", "speso", "entrat"]) and df is not None:
        income  = df[df["Categoria"] == "Stipendio & Entrate"]["Importo"].sum()
        out_exp = df[df["Importo"] < 0]["Importo"].sum()
        balance = income + out_exp
        return (
            f"**Riepilogo estratto conto:**\n"
            f"- Entrate: €{income:.2f}\n"
            f"- Uscite totali: €{abs(out_exp):.2f}\n"
            f"- Saldo del periodo: €{balance:+.2f}"
        )

    return (
        "Non ho capito la domanda. Prova a chiedermi:\n"
        "- 'Quanto ho speso in Alimentari?'\n"
        "- 'Qual è il mese in cui ho speso di più?'\n"
        "- 'Qual è la mia spesa media mensile?'\n"
        "- 'Mostrami il trend degli ultimi mesi'\n"
        "- 'Come va rispetto al mese scorso?'\n"
        "- 'Cosa significa IBAN?'"
    )


# ── Charts ─────────────────────────────────────────────────────────────────────
def make_donut(cat_totals: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=cat_totals["Categoria"],
        values=cat_totals["Importo (€)"],
        hole=0.48,
        marker_colors=[CATEGORY_COLORS.get(c, "#ADB5BD") for c in cat_totals["Categoria"]],
        textinfo="label+percent",
        textfont_size=12,
    ))
    fig.update_layout(
        showlegend=False,
        margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=360,
    )
    return fig


def make_bar(cat_totals: pd.DataFrame, income: float) -> go.Figure:
    exp_sorted = cat_totals.sort_values("Importo (€)", ascending=False)
    cats   = ["Stipendio & Entrate"] + list(exp_sorted["Categoria"])
    values = [income]               + list(exp_sorted["Importo (€)"])
    colors = [INCOME_COLOR]         + [CATEGORY_COLORS.get(c, "#ADB5BD") for c in exp_sorted["Categoria"]]
    fig = go.Figure(go.Bar(
        x=values,
        y=cats,
        orientation="h",
        marker_color=colors,
        text=[f"€{v:,.0f}" for v in values],
        textposition="outside",
        textfont_size=11,
    ))
    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        xaxis=dict(showgrid=False, showticklabels=False),
        margin=dict(t=10, b=10, l=10, r=80),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=max(320, 36 * len(cats)),
    )
    return fig


def make_compare_chart(comparison: list[dict]) -> go.Figure:
    items   = comparison[:10]
    cats    = [c["categoria"] for c in items]
    prev_v  = [c["previous"]  for c in items]
    curr_v  = [c["current"]   for c in items]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Periodo precedente", x=cats, y=prev_v,
                         marker_color="#B5C0D0",
                         text=[f"€{v:.0f}" for v in prev_v],
                         textposition="outside", textfont_size=10))
    fig.add_trace(go.Bar(name="Periodo corrente", x=cats, y=curr_v,
                         marker_color="#4361EE",
                         text=[f"€{v:.0f}" for v in curr_v],
                         textposition="outside", textfont_size=10))
    fig.update_layout(
        barmode="group",
        xaxis=dict(tickangle=-30),
        yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.08)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=40, b=60, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=380,
    )
    return fig


def make_trend_chart(statements: list[dict]) -> go.Figure | None:
    if len(statements) < 2:
        return None
    labels  = [s["period_label"]   for s in statements]
    totals  = [s["total_expenses"] for s in statements]
    incomes = [s["income"]         for s in statements]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=labels, y=incomes, name="Entrate", mode="lines+markers",
                             line=dict(color=INCOME_COLOR, width=2.5), marker=dict(size=8)))
    fig.add_trace(go.Scatter(x=labels, y=totals, name="Uscite", mode="lines+markers",
                             line=dict(color="#F72585", width=2.5), marker=dict(size=8)))
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.08)"),
        margin=dict(t=40, b=30, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=300,
    )
    return fig


def make_category_trend_chart(all_stmts: list[dict], categories: list[str]) -> go.Figure:
    labels = [s["period_label"] for s in all_stmts]
    fig = go.Figure()
    for cat in categories:
        values = [s["category_totals"].get(cat, 0.0) for s in all_stmts]
        fig.add_trace(go.Scatter(
            x=labels, y=values, name=cat, mode="lines+markers",
            line=dict(color=CATEGORY_COLORS.get(cat, "#ADB5BD"), width=2.5),
            marker=dict(size=8),
            hovertemplate="<b>%{fullData.name}</b><br>%{x}<br>€%{y:.0f}<extra></extra>",
        ))
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(tickangle=-30, tickfont_size=11),
        yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.08)", title="€", tickprefix="€"),
        margin=dict(t=50, b=60, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=420,
    )
    return fig


# ── CSS ────────────────────────────────────────────────────────────────────────
CSS = """
<style>
[data-testid="stAppViewContainer"] { background: #F0F2F8; }
[data-testid="stSidebar"] { background: #1A1A2E; }
[data-testid="stSidebar"] * { color: #E8E0F0 !important; }
[data-testid="stSidebar"] hr { border-color: #333 !important; }
h1,h2,h3 { font-family: 'Segoe UI', sans-serif; }

.card {
    background: white;
    border-radius: 14px;
    padding: 20px 22px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    margin-bottom: 16px;
}
.stmt-card {
    background: white;
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
    margin-bottom: 12px;
    border-left: 4px solid #4361EE;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
}
.stmt-label  { font-weight: 600; font-size: 15px; color: #1A1A2E; }
.stmt-detail { font-size: 13px; color: #666; margin-top: 2px; }

.wizard-card {
    background: white;
    border-radius: 14px;
    padding: 24px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.08);
    margin-bottom: 20px;
}
.progress-bar {
    background: #E8E0F0;
    border-radius: 8px;
    height: 8px;
    margin-bottom: 18px;
    overflow: hidden;
}
.progress-fill {
    background: linear-gradient(90deg, #A100FF, #4361EE);
    height: 100%;
    border-radius: 8px;
}
.delta-up   { color: #F72585; font-weight: 700; }
.delta-down { color: #00C49A; font-weight: 700; }
.compare-up   { color: #F72585; }
.compare-down { color: #00C49A; }
</style>
"""


# ── Sidebar ────────────────────────────────────────────────────────────────────
def render_sidebar():
    with st.sidebar:
        st.markdown("### 💳 Estratto Conto")
        st.markdown("Strumento educativo")
        st.divider()
        user = st.session_state.get("user")
        if user:
            st.markdown(f"**Utente:** {user}")
            page = st.session_state.get("page", "dashboard")
            nav = {"🏠 Dashboard": "dashboard", "📂 Carica estratto": "upload"}
            if "current_df" in st.session_state:
                nav["📊 Analisi corrente"] = "analysis"
            if "comparison" in st.session_state:
                nav["🔄 Confronto"] = "compare"
            for lbl, pg in nav.items():
                btn_type = "primary" if page == pg else "secondary"
                if st.button(lbl, key=f"nav_{pg}", use_container_width=True, type=btn_type):
                    st.session_state["page"] = pg
                    st.rerun()
            st.divider()
            if st.button("🚪 Esci", use_container_width=True):
                for k in ["user", "page", "current_df", "current_label",
                          "comparison", "habit_idx", "habit_notes",
                          "sig_changes", "chat_history", "current_stmt",
                          "pending_stmt_data", "prev_label", "all_statements",
                          "login_mode", "legacy_user"]:
                    st.session_state.pop(k, None)
                st.rerun()
        st.divider()
        st.caption("⚠️ Strumento esclusivamente educativo. Non fornisce raccomandazioni di investimento né consulenza finanziaria.")


# ── Page: Login ────────────────────────────────────────────────────────────────
def _validate_username(u: str) -> str | None:
    if not u:
        return "Inserisci un nome utente."
    if not re.match(r"^[a-zA-Z0-9_.\-]{2,40}$", u):
        return "Usa solo lettere, numeri, punto, trattino o underscore (2–40 caratteri)."
    return None


def page_login():
    mode = st.session_state.get("login_mode", "login")
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("## 💳 Estratto Conto Educativo")
        st.markdown("**Analizza i tuoi movimenti bancari in modo semplice e consapevole.**")
        st.markdown("---")

        if mode == "login":
            st.markdown("#### Accedi")
            username = st.text_input("Nome utente", placeholder="mario", key="li_user")
            password = st.text_input("Password", type="password", key="li_pw")
            if st.button("▶ Accedi", type="primary", use_container_width=True):
                u = username.strip()
                err = _validate_username(u)
                if err:
                    st.warning(err)
                elif not user_exists(u):
                    st.error("Utente non trovato.")
                    if st.button("Crea nuovo account", key="to_reg_err"):
                        st.session_state["login_mode"] = "register"
                        st.rerun()
                else:
                    data = load_user_data(u)
                    if not data.get("password_hash"):
                        st.session_state["login_mode"] = "set_password"
                        st.session_state["legacy_user"] = u
                        st.rerun()
                    elif authenticate(u, password):
                        _login_success(u)
                        st.rerun()
                    else:
                        st.error("Password errata. Riprova.")
            st.markdown("---")
            if st.button("Nuovo utente? Crea account", use_container_width=True):
                st.session_state["login_mode"] = "register"
                st.rerun()

        elif mode == "register":
            st.markdown("#### Crea nuovo account")
            username = st.text_input("Nome utente", placeholder="mario", key="reg_user")
            password = st.text_input("Password", type="password", key="reg_pw")
            confirm  = st.text_input("Conferma password", type="password", key="reg_pw2")
            if st.button("✅ Crea account", type="primary", use_container_width=True):
                u = username.strip()
                err = _validate_username(u)
                if err:
                    st.warning(err)
                elif user_exists(u):
                    st.error("Questo nome utente è già in uso. Scegline un altro.")
                elif not password:
                    st.warning("La password non può essere vuota.")
                elif password != confirm:
                    st.error("Le password non coincidono.")
                else:
                    register_user(u, password)
                    _login_success(u)
                    st.rerun()
            st.markdown("---")
            if st.button("← Torna al login", use_container_width=True):
                st.session_state["login_mode"] = "login"
                st.rerun()

        elif mode == "set_password":
            u = st.session_state.get("legacy_user", "")
            st.info(f"Benvenuto **{u}**! Questa versione dell'app richiede una password. Impostane una ora.")
            password = st.text_input("Nuova password", type="password", key="sp_pw")
            confirm  = st.text_input("Conferma password", type="password", key="sp_pw2")
            if st.button("✅ Imposta password", type="primary", use_container_width=True):
                if not password:
                    st.warning("La password non può essere vuota.")
                elif password != confirm:
                    st.error("Le password non coincidono.")
                else:
                    set_password(u, password)
                    _login_success(u)
                    st.rerun()
            if st.button("← Annulla", use_container_width=True):
                st.session_state["login_mode"] = "login"
                st.session_state.pop("legacy_user", None)
                st.rerun()

        st.markdown("---")
        st.caption("I dati vengono salvati localmente sul tuo dispositivo. Nessun dato viene inviato a server esterni.")
        st.caption("⚠️ Strumento esclusivamente educativo. Non fornisce consulenza finanziaria personalizzata.")


# ── Page: Dashboard ────────────────────────────────────────────────────────────
def page_dashboard():
    user  = st.session_state["user"]
    data  = load_user_data(user)
    stmts = data.get("statements", [])

    st.markdown(f"## Benvenuto, **{user}**")

    col_new, _ = st.columns([1, 3])
    with col_new:
        if st.button("➕ Carica nuovo estratto", type="primary"):
            st.session_state["page"] = "upload"
            st.rerun()

    if not stmts:
        st.info("Nessun estratto conto ancora salvato. Caricane uno per iniziare.")
        return

    trend_fig = make_trend_chart(stmts)
    if trend_fig:
        with st.expander("📈 Andamento mensile", expanded=True):
            st.plotly_chart(trend_fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("### Estratti salvati")
    for stmt in reversed(stmts):
        income   = stmt.get("income", 0)
        expenses = stmt.get("total_expenses", 0)
        balance  = income - expenses
        bal_color = "#00C49A" if balance >= 0 else "#F72585"
        bal_sign  = "+" if balance >= 0 else ""
        col_card, col_btn = st.columns([5, 1])
        with col_card:
            st.markdown(
                f'<div class="stmt-card">'
                f'<div><div class="stmt-label">{stmt["period_label"]}</div>'
                f'<div class="stmt-detail">Caricato il {stmt["upload_date"]} &nbsp;·&nbsp; {stmt["n_transactions"]} transazioni</div></div>'
                f'<div style="text-align:right; white-space:nowrap;">'
                f'<span style="color:#00C49A;font-weight:700;">+€{income:.0f}</span> &nbsp;|&nbsp; '
                f'<span style="color:#F72585;font-weight:700;">-€{expenses:.0f}</span> &nbsp;|&nbsp; '
                f'<span style="color:{bal_color};font-weight:700;">{bal_sign}€{balance:.0f}</span>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("📂 Apri", key=f"open_{stmt['id']}"):
                st.session_state["current_stmt"]  = stmt
                st.session_state["current_df"]    = _df_from_stmt(stmt)
                st.session_state["current_label"] = stmt["period_label"]
                st.session_state["chat_history"]  = []
                st.session_state["habit_notes"]   = stmt.get("habit_notes", {})
                for k in ["comparison", "sig_changes", "pending_stmt_data", "prev_label", "habit_idx"]:
                    st.session_state.pop(k, None)
                st.session_state["page"] = "analysis"
                st.rerun()


# ── Page: Upload ───────────────────────────────────────────────────────────────
def page_upload():
    st.markdown("## 📂 Carica estratto conto")
    st.caption("Formati supportati: CSV, TXT, PDF")

    sample_key  = st.selectbox("File di esempio:", list(SAMPLE_OPTIONS.keys()), key="sample_sel")
    sample_path = SAMPLE_OPTIONS[sample_key]

    uploaded = st.file_uploader(
        "Oppure carica il tuo file:", type=["csv", "txt", "pdf"], key="file_up"
    )
    default_label = sample_key.replace(" (esempio)", "") if sample_key != "— nessuno —" else ""
    label = st.text_input(
        "Etichetta periodo (es. Gennaio 2024):",
        key="period_label",
        value=default_label,
    )

    if st.button("🔍 Analizza", type="primary"):
        df          = None
        if uploaded is not None:
            raw = uploaded.read()
            if uploaded.name.lower().endswith(".pdf"):
                df = parse_pdf(raw)
            else:
                df = parse_csv_txt(raw.decode("utf-8", errors="replace"))
        elif sample_path is not None:
            try:
                df = parse_csv_txt(sample_path.read_text(encoding="utf-8"))
            except Exception:
                st.error("Errore nella lettura del file di esempio.")
                return
        else:
            st.warning("Seleziona un file da caricare o scegli un esempio.")
            return

        if df is None or len(df) == 0:
            st.error("Non è stato possibile estrarre transazioni. Verifica il formato del file.")
            return

        df = categorize(df)
        effective_label = label.strip() or _detect_period_label(df) or "Estratto senza data"
        st.session_state["current_df"]    = df
        st.session_state["current_label"] = effective_label
        st.session_state["chat_history"]  = []
        for k in ["comparison", "habit_idx", "habit_notes", "sig_changes",
                  "current_stmt", "pending_stmt_data", "prev_label"]:
            st.session_state.pop(k, None)

        user  = st.session_state["user"]
        udata = load_user_data(user)
        stmts = udata.get("statements", [])

        cat_totals_dict = (
            df[(df["Importo"] < 0) & (df["Categoria"] != "Stipendio & Entrate")]
            .groupby("Categoria")["Importo"]
            .sum().abs().to_dict()
        )
        income    = float(df[df["Categoria"] == "Stipendio & Entrate"]["Importo"].sum())
        total_exp = float(sum(cat_totals_dict.values()))

        pending = {
            "period_label":    effective_label,
            "income":          income,
            "total_expenses":  total_exp,
            "n_transactions":  len(df),
            "category_totals": cat_totals_dict,
        }
        st.session_state["pending_stmt_data"] = pending

        if stmts:
            comparison = compare_statements(pending, stmts[-1])
            st.session_state["comparison"] = comparison
            st.session_state["prev_label"] = stmts[-1]["period_label"]
            sig = [c for c in comparison if c["significant"]]
            st.session_state["sig_changes"] = sig
            st.session_state["page"] = "compare"
        else:
            saved = save_statement(user, df, label or "Estratto senza data", {})
            st.session_state["current_stmt"]   = saved
            st.session_state["all_statements"] = load_user_data(user)["statements"]
            st.session_state["page"] = "analysis"

        st.rerun()


# ── Page: Compare ──────────────────────────────────────────────────────────────
def page_compare():
    comparison  = st.session_state.get("comparison", [])
    prev_label  = st.session_state.get("prev_label", "Periodo precedente")
    curr_label  = st.session_state.get("current_label", "Periodo corrente")
    pending     = st.session_state.get("pending_stmt_data", {})

    st.markdown(f"## 🔄 Confronto: {curr_label} vs {prev_label}")

    user_data = load_user_data(st.session_state["user"])
    prev_inc  = user_data["statements"][-1].get("income", 0) if user_data["statements"] else 0
    curr_inc  = pending.get("income", 0)
    curr_exp  = pending.get("total_expenses", 0)
    prev_exp  = user_data["statements"][-1].get("total_expenses", 0) if user_data["statements"] else 0
    delta_inc = curr_inc - prev_inc
    delta_exp = curr_exp - prev_exp

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Entrate", f"€{curr_inc:.0f}", delta=f"€{delta_inc:+.0f}" if delta_inc != 0 else None)
    c2.metric("Uscite totali", f"€{curr_exp:.0f}",
              delta=f"€{delta_exp:+.0f}" if delta_exp != 0 else None, delta_color="inverse")
    c3.metric("Saldo periodo", f"€{curr_inc - curr_exp:.0f}")
    n_sig = len([c for c in comparison if c["significant"]])
    c4.metric("Variazioni significative", n_sig)

    st.markdown("---")

    # Storico completo = salvati + quello in arrivo (pending)
    all_stmts_hist = st.session_state.get("all_statements", [])
    pending_as_stmt = {
        "period_label":    curr_label,
        "income":          curr_inc,
        "total_expenses":  curr_exp,
        "category_totals": pending.get("category_totals", {}),
    }
    full_stmts = list(all_stmts_hist) + [pending_as_stmt]

    if comparison:
        st.markdown("**Andamento per categoria — vs mese precedente**")
        st.plotly_chart(make_compare_chart(comparison), use_container_width=True,
                        config={"displayModeBar": False})

    # Se ci sono almeno 3 mesi nel totale: aggiunge evoluzione storica + media
    if len(full_stmts) >= 3:
        hist_data = _history_summary(full_stmts)
        avg_exp_prev = sum(hist_data["expenses"][:-1]) / (len(hist_data["expenses"]) - 1)
        delta_vs_avg = curr_exp - avg_exp_prev
        avg_bal_prev = sum(hist_data["balances"][:-1]) / (len(hist_data["balances"]) - 1)
        curr_balance = curr_inc - curr_exp
        delta_bal_avg = curr_balance - avg_bal_prev

        st.markdown(f"**Vs media storica ({len(full_stmts)-1} mesi precedenti)**")
        ca1, ca2, ca3 = st.columns(3)
        ca1.metric("Uscite medie", f"€{avg_exp_prev:.0f}",
                   delta=f"€{delta_vs_avg:+.0f}", delta_color="inverse")
        ca2.metric("Saldo medio", f"€{avg_bal_prev:.0f}",
                   delta=f"€{delta_bal_avg:+.0f}")
        ca3.metric("Mesi in storico", len(full_stmts))

        sig_cats = list({c["categoria"] for c in comparison if c["significant"]})
        if sig_cats:
            with st.expander("📈 Evoluzione storica delle categorie significative", expanded=False):
                st.plotly_chart(
                    make_category_trend_chart(full_stmts, sig_cats),
                    use_container_width=True, config={"displayModeBar": False}
                )

    incr = [c for c in comparison if c["significant"] and c["delta"] > 0]
    decr = [c for c in comparison if c["significant"] and c["delta"] < 0]

    col_a, col_b = st.columns(2)
    with col_a:
        if decr:
            st.markdown("### 📉 Andamento positivo")
            for c in decr:
                st.markdown(
                    f'<div class="card">'
                    f'<b>{c["categoria"]}</b><br>'
                    f'<span class="compare-down">▼ €{abs(c["delta"]):.0f} ({c["pct"]:+.0f}%)</span> '
                    f'da €{c["previous"]:.0f} a €{c["current"]:.0f}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    with col_b:
        if incr:
            st.markdown("### 📈 Da monitorare")
            for c in incr:
                st.markdown(
                    f'<div class="card">'
                    f'<b>{c["categoria"]}</b><br>'
                    f'<span class="compare-up">▲ €{abs(c["delta"]):.0f} ({c["pct"]:+.0f}%)</span> '
                    f'da €{c["previous"]:.0f} a €{c["current"]:.0f}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    st.markdown("---")
    sig = st.session_state.get("sig_changes", [])
    if sig:
        st.info(f"Ci sono **{len(sig)} variazioni significative**. Vuoi raccontarci cosa è successo? (facoltativo)")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✍️ Racconta le variazioni", type="primary"):
                st.session_state["habit_idx"]   = 0
                st.session_state["habit_notes"] = {}
                st.session_state["page"]        = "habits"
                st.rerun()
        with col2:
            if st.button("⏭️ Salta — vai all'analisi"):
                _save_and_go_analysis({})
    else:
        if st.button("➡️ Vai all'analisi completa", type="primary"):
            _save_and_go_analysis({})


def _save_and_go_analysis(habit_notes: dict):
    user  = st.session_state["user"]
    df    = st.session_state["current_df"]
    label = st.session_state.get("current_label", "Estratto")
    saved = save_statement(user, df, label, habit_notes)
    st.session_state["current_stmt"]   = saved
    st.session_state["all_statements"] = load_user_data(user)["statements"]
    st.session_state["habit_notes"]    = habit_notes
    st.session_state["page"] = "analysis"
    st.rerun()


# ── Page: Habits wizard ────────────────────────────────────────────────────────
def page_habits():
    sig   = st.session_state.get("sig_changes", [])
    idx   = st.session_state.get("habit_idx", 0)
    notes = st.session_state.get("habit_notes", {})

    if idx >= len(sig):
        _save_and_go_analysis(notes)
        return

    total = len(sig)
    pct   = int((idx / total) * 100)

    st.markdown("## ✍️ Raccontaci le variazioni")
    st.caption("Capire perché le spese cambiano è il primo passo per gestirle consapevolmente. Rispondi o salta liberamente.")
    st.markdown(
        f'<div class="progress-bar"><div class="progress-fill" style="width:{pct}%"></div></div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Variazione {idx + 1} di {total}")

    change    = sig[idx]
    cat       = change["categoria"]
    delta     = change["delta"]
    pct_v     = change["pct"]
    direction = "aumentate" if delta > 0 else "diminuite"
    arrow     = "📈" if delta > 0 else "📉"
    color_cls = "delta-up" if delta > 0 else "delta-down"

    st.markdown(
        f'<div class="wizard-card">'
        f'<div style="font-size:22px;margin-bottom:8px;">{arrow} <b>{cat}</b></div>'
        f'<div>Spese <span class="{color_cls}">{direction} del {abs(pct_v):.0f}%</span> '
        f'(da €{change["previous"]:.0f} a €{change["current"]:.0f})</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    st.markdown(f"**Perché le spese in {cat} sono {direction}?**")

    dir_key     = "up" if delta > 0 else "down"
    suggestions = HABIT_SUGGESTIONS.get(cat, {}).get(dir_key, [])

    if suggestions:
        st.markdown("Selezione rapida:")
        cols = st.columns(min(len(suggestions), 4))
        for i, sugg in enumerate(suggestions):
            with cols[i % len(cols)]:
                if st.button(sugg, key=f"sugg_{idx}_{i}"):
                    notes[cat] = sugg
                    st.session_state["habit_notes"] = notes
                    st.session_state["habit_idx"]   = idx + 1
                    st.rerun()

    free_text = st.text_input(
        "Oppure scrivi la motivazione:", key=f"free_{idx}",
        placeholder="Vacanza, ospiti, evento particolare..."
    )
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("➡️ Prossimo", type="primary"):
            if free_text.strip():
                notes[cat] = free_text.strip()
            st.session_state["habit_notes"] = notes
            st.session_state["habit_idx"]   = idx + 1
            st.rerun()
    with col2:
        if st.button("⏭️ Salta"):
            st.session_state["habit_idx"] = idx + 1
            st.rerun()


# ── Page: Analysis ─────────────────────────────────────────────────────────────
def page_analysis():
    df    = st.session_state.get("current_df")
    label = st.session_state.get("current_label", "Estratto conto")

    if df is None:
        st.warning("Nessun estratto conto caricato.")
        if st.button("🏠 Vai alla Dashboard"):
            st.session_state["page"] = "dashboard"
            st.rerun()
        return

    st.markdown(f"## 📊 Analisi — {label}")

    income   = df[df["Categoria"] == "Stipendio & Entrate"]["Importo"].sum()
    expenses = df[df["Importo"] < 0]["Importo"].sum()
    balance  = income + expenses
    n_tx     = len(df)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Entrate", f"€{income:,.2f}")
    c2.metric("Uscite totali", f"€{abs(expenses):,.2f}")
    c3.metric("Saldo periodo", f"€{balance:+,.2f}")
    c4.metric("Transazioni", n_tx)

    comparison = st.session_state.get("comparison")
    if comparison:
        prev_label  = st.session_state.get("prev_label", "periodo precedente")
        habit_notes = st.session_state.get("habit_notes", {})
        with st.expander(f"🔄 Riepilogo confronto vs {prev_label}", expanded=False):
            sig = [c for c in comparison if c["significant"]]
            if sig:
                for c in sig:
                    arrow = "📈" if c["delta"] > 0 else "📉"
                    color = "compare-up" if c["delta"] > 0 else "compare-down"
                    note  = habit_notes.get(c["categoria"], "")
                    note_str = f" — *{note}*" if note else ""
                    st.markdown(
                        f'{arrow} **{c["categoria"]}**: '
                        f'<span class="{color}">{c["pct"]:+.0f}% (€{c["delta"]:+.0f})</span>{note_str}',
                        unsafe_allow_html=True,
                    )
            else:
                st.success("Nessuna variazione significativa rispetto al periodo precedente.")

    st.markdown("---")

    exp_df = df[(df["Importo"] < 0) & (df["Categoria"] != "Stipendio & Entrate")].copy()
    cat_totals = (
        exp_df.groupby("Categoria")["Importo"]
        .sum().abs().reset_index()
        .rename(columns={"Importo": "Importo (€)"})
    )

    all_stmts = st.session_state.get("all_statements", [])
    has_history = len(all_stmts) >= 2

    tab_labels = ["📈 Grafici", "📋 Movimenti", "📚 Educazione", "💬 Chat", "📖 Glossario", "🎯 Quiz"]
    if has_history:
        tab_labels.append("📊 Storico")
    tabs = st.tabs(tab_labels)
    tab1, tab2, tab3, tab4, tab5, tab6 = tabs[:6]
    tab7 = tabs[6] if has_history else None

    with tab1:
        if len(cat_totals) == 0:
            st.info("Nessuna spesa rilevata.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Distribuzione spese**")
                st.plotly_chart(make_donut(cat_totals), use_container_width=True,
                                config={"displayModeBar": False})
            with c2:
                st.markdown("**Spese per categoria**")
                st.plotly_chart(make_bar(cat_totals, income), use_container_width=True,
                                config={"displayModeBar": False})

    with tab2:
        disp = df.copy()
        disp["Data"]    = disp["Data"].dt.strftime("%d/%m/%Y")
        disp["Importo"] = disp["Importo"].apply(lambda x: f"€ {x:+,.2f}")
        st.dataframe(disp[["Data", "Descrizione", "Importo", "Categoria"]],
                     use_container_width=True, hide_index=True)

    with tab3:
        edu_text = build_educational_text(df)
        with st.spinner("Preparazione contenuto educativo..."):
            ph = st.empty()
            for chunk in stream_sentences(edu_text, delay=0.06):
                ph.markdown(chunk)

    with tab4:
        st.markdown("### Chiedi all\'Agente Educativo")
        st.caption("Spiegazioni sulle categorie, lettura dell'estratto, termini bancari. Non fornisco consulenza finanziaria.")
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []
        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
        if question := st.chat_input("Scrivi una domanda..."):
            st.session_state["chat_history"].append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                response = get_chat_response(question, df)
                ph = st.empty()
                for chunk in stream_sentences(response, delay=0.04):
                    ph.markdown(chunk)
            st.session_state["chat_history"].append({"role": "assistant", "content": response})

    with tab5:
        st.markdown("### Glossario bancario")
        for term, defn in GLOSSARY.items():
            with st.expander(f"**{term}**"):
                st.write(defn)

    with tab6:
        st.markdown("### Quiz — Conosci il tuo estratto conto?")
        if "quiz_score" not in st.session_state:
            st.session_state["quiz_score"]    = 0
            st.session_state["quiz_answered"] = [False] * len(QUIZ_ITEMS)
        for i, (question, options, correct) in enumerate(QUIZ_ITEMS):
            st.markdown(f"**{i+1}. {question}**")
            choice = st.radio("", options, index=None, key=f"q{i}", label_visibility="collapsed")
            if choice is not None and not st.session_state["quiz_answered"][i]:
                st.session_state["quiz_answered"][i] = True
                if options.index(choice) == correct:
                    st.session_state["quiz_score"] += 1
                    st.success("Corretto!")
                else:
                    st.error(f"La risposta corretta era: **{options[correct]}**")
            st.markdown("---")
        if all(st.session_state["quiz_answered"]):
            score = st.session_state["quiz_score"]
            st.balloons()
            st.success(f"Quiz completato: **{score}/{len(QUIZ_ITEMS)}** risposte corrette!")
            if st.button("🔄 Ricomincia quiz"):
                st.session_state.pop("quiz_score")
                st.session_state.pop("quiz_answered")
                st.rerun()

    if tab7 is not None:
        with tab7:
            st.markdown("### Andamento storico per categoria")
            st.caption(f"{len(all_stmts)} mesi in archivio")
            all_cats_hist = sorted({
                cat for s in all_stmts for cat in s["category_totals"]
            })
            avg_by_cat = {
                cat: sum(s["category_totals"].get(cat, 0) for s in all_stmts) / len(all_stmts)
                for cat in all_cats_hist
            }
            top5_default = sorted(all_cats_hist, key=lambda c: avg_by_cat.get(c, 0), reverse=True)[:5]
            selected_cats = st.multiselect(
                "Seleziona categorie da visualizzare:",
                options=all_cats_hist,
                default=top5_default,
                key="hist_cats",
            )
            if selected_cats:
                fig_hist = make_category_trend_chart(all_stmts, selected_cats)
                st.plotly_chart(fig_hist, use_container_width=True, config={"displayModeBar": False})

            # Tabella riepilogativa
            st.markdown("#### Riepilogo mesi")
            rows = []
            for s in all_stmts:
                row = {"Periodo": s["period_label"],
                       "Entrate (€)": s["income"],
                       "Uscite (€)": s["total_expenses"],
                       "Saldo (€)": round(s["income"] - s["total_expenses"], 2)}
                for cat in all_cats_hist:
                    row[cat] = s["category_totals"].get(cat, 0.0)
                rows.append(row)
            hist_df = pd.DataFrame(rows)
            st.dataframe(hist_df, use_container_width=True, hide_index=True)

    st.markdown("---")
    if st.button("🏠 Torna alla Dashboard"):
        st.session_state["page"] = "dashboard"
        st.rerun()


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="Estratto Conto Educativo",
        page_icon="💳",
        layout="wide",
    )
    st.markdown(CSS, unsafe_allow_html=True)

    if "page" not in st.session_state:
        st.session_state["page"] = "login"

    page = st.session_state["page"]
    if page != "login":
        render_sidebar()

    if page == "login":
        page_login()
    elif page == "dashboard":
        page_dashboard()
    elif page == "upload":
        page_upload()
    elif page == "compare":
        page_compare()
    elif page == "habits":
        page_habits()
    elif page == "analysis":
        page_analysis()
    else:
        st.session_state["page"] = "login"
        st.rerun()


if __name__ == "__main__":
    main()
