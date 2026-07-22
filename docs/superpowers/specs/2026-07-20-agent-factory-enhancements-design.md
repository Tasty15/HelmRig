# HelmRig — Förbättringsdesign

**Datum:** 2026-07-20
**Status:** Specifikation (godkänd av användare)

## Översikt

Fem additiva förbättringar till HelmRig-systemet (`ai/agents/`). Alla ändringar är additiva — ingen befintlig kod ändras, endast ny kod läggs till.

**Arkitektur:** Hybrid — loggning/dry-run/kedjor centralt i harness, headroom-minne i delad modul, webb-panel som fristående app.

---

## 1. Run-loggar (`harness log`)

### Logg-format
JSONL — en JSON-rad per körning i `.overlord/logs/<agent>.jsonl`.

```
{"agent":"svt-sarcastic","ts":"2026-07-20T12:00:00","status":"ok","code":0,"duration_s":4.2,"dry_run":false,"stdout":"📰...\n✍️  ...\n📧 ...","result":null,"error":null}
```

Fält:
- `agent` — agentnamn från agent.yaml
- `ts` — ISO 8601-timestamp
- `status` — `"ok"`, `"error"`, `"dry_run"`
- `code` — exit code
- `duration_s` — körningstid i sekunder
- `dry_run` — boolean
- `stdout` — full stdout från agenten (för visning i webb-panel)
- `result` — JSON-parsad output om agenten skickar CHAIN_OUTPUT (annars null)
- `error` — felmeddelande vid crash

### `harness log` subcommand

```
harness log                         # senaste status per agent
harness log <agent>                 # senaste 5 körningarna (tabell)
harness log <agent> --tail          # följ live (tail -f)
harness log <agent> --json          # rå JSONL-rader
harness log <agent> -n 20           # antal rader (default 5)
```

### Implementation (harness.py)
- `cmd_run`: efter subprocess, logga resultatet till `.overlord/logs/<agent>.jsonl`. Capture stdout via `subprocess.PIPE`.
- `cmd_log`: läs JSONL-filen, visa tabell eller JSON.
- Hantera trasiga JSONL-rader (crash mitt i skrivning).

### Inga agent-ändringar
All loggning sker i harness. Agentens stdout sparas oavsett.

---

## 2. Dry-run mode (`harness run --dry-run`)

### agent.yaml — nytt fält
```yaml
skills:
  - name: send_email
    side_effect: true
```

### Protokoll
Harness sätter env-variabler när `--dry-run` används:
```
HARNESS_DRY_RUN=true
HARNESS_DRY_RUN_SKILLS=send_email,slack_post,some_other_side_effect
```

### Agent-ändring
Varje skill med `side_effect: true` kollar env-variabeln före anrop:

```python
def send_email(state):
    if os.environ.get("HARNESS_DRY_RUN"):
        print("[DRY-RUN] skulle maila: <subject> | <body[:200]>")
        return {"email_result": {"status": "dry-run"}}
    # ... riktig sändning ...
```

### Implementering (harness.py)
- Ny flagga `--dry-run` till `run` subcommand
- Läs agent.yaml, komma-separera skills med `side_effect: true`
- Sätt env, kör agent normalt, logga med `"dry_run": true`

### Scaffold-uppdatering
Mallen `AGENT_YAML_TEMPLATE` uppdateras med `side_effect: false` som default på skills.

---

## 3. Headroom-minne (`agentkit/memory.py`)

### Ny modul
`ai/agents/agentkit/__init__.py` (tom)
`ai/agents/agentkit/memory.py`

```python
def save_run(agent: str, summary: str, tags: list[str] | None = None) -> dict:
    """Spara en minnes-post under topic 'helmrig/<agent>'."""
    # anropar: headroom memory write helmrig/<agent> --content <summary> --tags <tags>

def get_recent(agent: str, days: int = 7) -> list[dict]:
    """Hämta minnen från topic 'helmrig/<agent>'."""
    # anropar: headroom memory list helmrig/<agent>

def get_context(agent: str) -> str:
    """Bygg en prompt-sträng: 'Tidigare körningar:\n- <date>: <summary>\n...'"""
```

### Användning i agent (ex. stock-watcher)
```python
from agentkit.memory import save_run, get_context

# Före analys
prev = get_context("stock-watcher")
if prev:
    instructions += f"\n\n{prev}"

# Efter analys
save_run("stock-watcher", summary=f"5 tickers: ... Trender: ...", tags=["daily"])
```

### Inga nya beroenden
Headroom CLI är redan installerad (`/home/simon/.local/bin/headroom`). Modulen anropar den via subprocess.

### Scaffold-uppdatering
`MAIN_PY_TEMPLATE` lägger till `from agentkit.memory import save_run, get_context`.

---

## 4. Agentkedjor (chain)

### agent.yaml — nytt fält
```yaml
# svt-sarcastic/agent.yaml
chain:
  next_agent: stock-watcher
  mapping:
    comment: news_context
```

- `next_agent`: agentmappnamn att trigga efter att denna agent slutförts
- `mapping`: output-nyckel → nästa agents CHAIN_INPUT_*-variabel

### Protokoll
Agentens `run()` returnerar en dict. För att kedjan ska fungera måste agenten skriva sin output som JSON på en egen rad med prefix `CHAIN_OUTPUT:`.

```python
# main.py — nederst
if __name__ == "__main__":
    result = run()
    print("CHAIN_OUTPUT:" + json.dumps(result))
```

### Implementering (harness.py)
I `cmd_run`, efter agent körts:
1. Sök stdout efter `CHAIN_OUTPUT:` — plocka sista förekomsten
2. Om hittad, JSON-parsea raden
3. Läs agent.yaml: om `chain.next_agent` finns, bygg env med `CHAIN_INPUT_<key>=<value>` från chain.mapping
4. Kör nästa agent via samma subprocess-logik
5. Kedjade agenter loggas som separata logg-rader (med `"chained_from": "svt-sarcastic"`)

### Flagga
`harness run svt-sarcastic` — med chain om agent.yaml har chain-konfig
`harness run svt-sarcastic --no-chain` — disable kedja explicit

---

## 5. Webb-panel (`dashboard/app.py`)

### Ny app
`ai/agents/dashboard/app.py` — Flask + Jinja2 + htmx.

### Routes

| Metod | Route | Beskrivning |
|---|---|---|
| GET | `/` | Dashboard — alla agenter, senaste körning, statusindikator |
| GET | `/agent/<name>` | Historik för en agent — lista körningar |
| GET | `/agent/<name>/<ts>` | En specifik körning — full stdout |
| POST | `/run/<name>` | Trigga en agent manuellt (anropar `harness.py run <name>` via subprocess) |
| GET | `/cron` | Lista alla cron-scheman från agent.yaml-filer |

### Teknisk stack
- Flask (enda nya dependency)
- Jinja2 templates (medföljer Flask)
- htmx via CDN (laddas från `<script src="https://unpkg.com/htmx.org">`)
- Inget npm, inga bygg-verktyg

### Design
En sida. Topp: statuskort per agent (grön=rullen, röd=error, grå=aldrig körts). Klicka på en agent → expandera senaste stdout. Klicka "Visa historik" → full lista. Klicka "Kör nu" → POST → spinner → uppdaterad status.

### Start
```bash
python ai/agents/dashboard/app.py
# → http://localhost:5050
```

---

## Filstruktur (ändringar)

```
ai/agents/
├── harness.py              # +~130 rader (log, dry-run, chain)
├── agentkit/               # NY mapp
│   ├── __init__.py
│   └── memory.py           # ~60 rader
├── dashboard/              # NY mapp
│   ├── app.py              # ~200 rader
│   └── templates/
│       ├── dashboard.html  # ~80 rader
│       └── agent.html      # ~70 rader
├── stock-watcher/
│   ├── agent.yaml          # + side_effect
│   ├── main.py             # + memory-anrop, CHAIN_OUTPUT
│   ├── skills/
│   │   ├── fetch_price.py  # oförändrad
│   │   └── analyze.py      # oförändrad
├── svt-sarcastic/
│   ├── agent.yaml          # + side_effect, chain
│   ├── main.py             # + dry-run guard, CHAIN_OUTPUT
│   ├── skills/
│       ├── fetch_top_news.py
│       ├── generate_comment.py
│       └── send_email.py   # + dry-run guard
└── .overlord/
    └── logs/               # NY — auto-skapad
        ├── stock-watcher.jsonl
        └── svt-sarcastic.jsonl
```

---

## Ordning

1. **harness.py** — loggning + dry-run (grunden för allt annat)
2. **Befintliga agenter** — dry-run guards i skills
3. **agentkit/memory.py** — headroom-minne
4. **Agenter med memory** — stock-watcher + svt-sarcastic
5. **Agentkedjor** — chain-protokoll i harness + main.py
6. **dashboard/** — webb-panel

Varje steg fungerar isolerat. Kan byggas och testas steg för steg.
