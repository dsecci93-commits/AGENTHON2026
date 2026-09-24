"""
Hook: syntax_check.py
Eseguito dopo ogni Edit/Write su file Python.
Esegue py_compile per intercettare errori di sintassi prima che il codice venga testato.
"""
import sys
import json
import py_compile
import os

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    file_path = data.get("tool_input", {}).get("file_path", "")

    if not file_path or not file_path.endswith(".py"):
        sys.exit(0)

    if not os.path.exists(file_path):
        sys.exit(0)

    try:
        py_compile.compile(file_path, doraise=True)
    except py_compile.PyCompileError as e:
        print(f"🐛  SYNTAX ERROR in {file_path}:")
        print(f"  {e}")
        print("Correggi l'errore di sintassi prima di continuare.")
        sys.exit(2)

    sys.exit(0)

if __name__ == "__main__":
    main()
