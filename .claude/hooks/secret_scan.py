"""
Hook: secret_scan.py
Eseguito dopo ogni Edit/Write.
Rileva API key, password o token hardcodati nel file modificato.
"""
import sys
import json
import re

SECRET_PATTERNS = [
    (re.compile(r'\bsk-ant-[A-Za-z0-9\-_]{20,}'), "Anthropic API key"),
    (re.compile(r'\bsk_(?:test|live)_[A-Za-z0-9]{20,}'), "Stripe secret key"),
    (re.compile(r'\bghp_[A-Za-z0-9]{36}'), "GitHub personal access token"),
    (re.compile(r'password\s*=\s*["\'][^"\']{6,}["\']', re.IGNORECASE), "Password hardcodata"),
    (re.compile(r'(?:api_key|apikey|secret_key)\s*=\s*["\'][A-Za-z0-9\-_]{16,}["\']', re.IGNORECASE), "API key generica"),
    (re.compile(r'JWT_SECRET\s*=\s*["\'][^"\']{8,}["\']', re.IGNORECASE), "JWT secret hardcodato"),
]

SAFE_PATTERNS = [
    re.compile(r'sk-ant-\.\.\.'),           # placeholder esemplificativo
    re.compile(r'cambia-con-valore'),        # placeholder nel .env.example
    re.compile(r'your[-_]?(api[-_]?key|secret)'),
    re.compile(r'<your[-_\w]+>'),
    re.compile(r'\$\{[A-Z_]+\}'),           # variabile di template
    re.compile(r'os\.environ|os\.getenv|dotenv'),
]

def is_safe_context(match_str: str, full_content: str) -> bool:
    for safe in SAFE_PATTERNS:
        if safe.search(match_str) or safe.search(full_content[:200]):
            return True
    return False

def check_file(path: str) -> list[str]:
    if path.endswith(".env.example") or path.endswith(".md"):
        return []
    try:
        content = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        return []

    issues = []
    for pattern, label in SECRET_PATTERNS:
        for m in pattern.finditer(content):
            if not is_safe_context(m.group(), content):
                issues.append(f"{label} potenzialmente hardcodato (riga ~{content[:m.start()].count(chr(10)) + 1})")
    return issues

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    issues = check_file(file_path)
    if issues:
        print("🔒  SECRET SCAN — possibili segreti rilevati:")
        for i in issues:
            print(f"  • {i}")
        print("Usa variabili d'ambiente (os.environ) o il secret manager. Mai hardcodare credenziali.")
        sys.exit(2)

    sys.exit(0)

if __name__ == "__main__":
    main()
