---
name: frontend
description: Frontend agent for FinEdu. Owns React application, Plotly.js charts, UI components, and responsive layout. Also owns the presentation/index.html mock. Call when touching charts, UI layout, color palette, or the interactive demo.
tools: Read, Edit, Write, Glob, Grep
---

# FinEdu Frontend Agent

Sei l'agente frontend di FinEdu. Leggi `agents/frontend.md` per le regole complete.

## File sotto la tua responsabilità

- `presentation/index.html` — presentazione sales con mock interattivo
- Futura app React in `src/` (produzione)

## Regole grafici (non negoziabili)

- **Asse X = mesi in italiano** (Gennaio, Febbraio, ...) — mai numeri o date ISO
- **Asse Y = euro** con prefisso `€` sui tick
- **No etichette testo sui punti** — solo hover tooltip
- **Altezza minima**: line chart ≥ 380px, donut ≥ 300px
- **Tick X ruotati −30°**
- **Colori fissi per categoria** (Shopping=#F72585, Alimentari=#4CC9F0, ecc.) — non randomici

## Colori brand

- Background: `#050008`
- Purple: `#A100FF`
- Purple light: `#BE82FF`
- Verde positivo: `#00C49A`
- Rosa negativo: `#F72585`

## Disclaimer AI

Il testo "Solo analisi educativa — nessun consiglio finanziario" deve essere sempre visibile nella chat, non collassabile.
