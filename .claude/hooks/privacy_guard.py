"""
Hook: privacy_guard.py
Eseguito dopo ogni Edit/Write.
Blocca se un file modificato contiene pattern che sembrano inviare
raw transactions (IBAN, descrizioni singole) verso endpoint esterni.
"""
import sys
import json
import re

# Pattern sospetti: combinazione di IBAN o descrizioni grezze + URL/request
IBAN_PATTERN = re.compile(r'\bIT\d{2}[A-Z]\d{10}[0-9A-Z]{12}\b', re.IGNORECASE)
RAW_TX_SEND  = re.compile(
    r'(requests\.(post|get)|httpx\.(post|get)|fetch\(|axios\.(post|get))'
    r'.{0,500}'
    r'(descrizione|description|raw_transactions|iban)',
    re.IGNORECASE | re.DOTALL
)

def check_file(path: str) -> list[str]:
    try:
        content = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return []

    issues = []
    if IBAN_PATTERN.search(content):
        issues.append(f"IBAN trovato in chiaro in {path}")
    if RAW_TX_SEND.search(content):
        issues.append(
            f"Possibile invio di raw transactions verso endpoint esterno in {path}. "
            "Verifica che il payload contenga solo aggregati per categoria."
        )
    return issues

def main():
    # Claude Code passa l'input del tool come JSON su stdin
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    issues = check_file(file_path)
    if issues:
        print("⚠️  PRIVACY GUARD — problemi rilevati:")
        for i in issues:
            print(f"  • {i}")
        print("Correggi prima di continuare. Nessun dato bancario raw deve raggiungere API esterne.")
        sys.exit(2)  # exit 2 = blocca il tool use

    sys.exit(0)

if __name__ == "__main__":
    main()
