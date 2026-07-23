# HelmRig

CLI, runtime och övervakning för LangGraph-baserade AI-agenter.

Skapa agenter med pluggbara skills, schemalägg med cron, övervaka via Overlord-daemon,
kolla dashboarden, kör agentkedjor (chain) — allt från terminalen.

## Kommandon

| Kommando | Funktion |
|---|---|
| `harness scaffold <name>` | Skapa ny agent |
| `harness scaffold <name> --react` | Skapa ReAct-agent (LLM väljer tools) |
| `harness list` / `ls` | Lista alla agenter |
| `harness run <name>` | Kör agent |
| `harness run <name> --timeout 600` | Kör med timeout |
| `harness run <name> --dry-run` | Kör utan side-effects |
| `harness install [name]` | Installera dependencies |
| `harness remove <name>` | Ta bort agent |
| `harness validate <name>` | Validera konfiguration |
| `harness log [name]` | Visa loggar |
| `harness log --since 2026-07-20 --level error` | Filtrera loggar |
| `harness env` | Visa alla miljövariabler |
| `harness env KEY value` | Sätt miljövariabel |
| `harness cron list` | Lista cron-scheman |
| `harness overlord start\|stop\|status\|logs` | Hantera daemon |
| `harness queue list\|flush` | Hantera jobbkö |

## Agentstruktur

```
agents/<name>/
├── agent.yaml           # Konfiguration (modell, skills, cron, chain)
├── main.py              # LangGraph-pipeline
├── requirements.txt     # Beroenden
└── skills/
    ├── __init__.py
    └── example_skill.py # Pluggable Python-moduler
```

## Nya features

### Sub-agent dispatch

En agent kan anropa en annan agent programmatiskt via `agentkit.sub_agent.dispatch()`.
Perfekt för orchestrator-agenter som delegerar till specialister:

```python
from agentkit.sub_agent import dispatch

result = dispatch("analyst", input_data={"query": "data"}, timeout=120)
print(result["output"])  # sub-agentens stdout
```

Används som tool i ReAct-agent genom att lägga till i `agent.yaml`:

```yaml
skills:
  - name: dispatch
    module: agentkit.sub_agent
    description: "Anropa specialist-agent. input_data skickas som CHAIN_INPUT_* env vars."
```

### Parallel fan-out

Kör flera instanser av samma agent parallellt:

```python
from agentkit.parallel import fan_out

results = fan_out("analyst", [
    {"query": "data1"},
    {"query": "data2"},
], max_workers=4)
```

### Overlord parallel cron

Overlord kan köra flera cron-jobb samtidigt. Styrs i `.overlord/config.yaml`:

```yaml
watchdog:
  interval_s: 60
  max_concurrent_cron: 4   # 0-1 = sekventiellt (default), >1 = parallellt
```

Thread-safe in-memory locks per agent ersätter gamla PID-filer.

---

## Arkitektur

```
harness.py               ← CLI: allt börjar här
├── agentkit/utils.py    ← Delade verktyg (rtk, env, call_skill, headroom)
├── agentkit/api.py      ← Programmatiskt API (skapa, kör, logga agenter i kod)
├── agentkit/alert.py    ← E-postnotifikation via Composio Gmail
├── agentkit/sub_agent.py← Sub-agent dispatch (anropa agent som tool)
├── agentkit/parallel.py ← Parallel fan-out (flera agenter samtidigt)
├── .overlord/overlord.py← Daemon: watchdog, health, jobbkö, cron, parallel cron
├── dashboard/app.py     ← Flask + htmx (port 5050)
└── agents/<name>/       ← Agentkataloger med LangGraph-pipelines
```

## Konfiguration

- `agent.yaml` per agent: model, skills, cron, chain
- `.overlord/config.yaml`: centrala defaults och overrides
- `.env`: API-nycklar och miljövariabler (maskeras automatiskt i loggar)

## Säkerhet

- API-nycklar maskas automatiskt i loggar och `harness env`
- Skills kan köras i sandbox (begränsad miljö) via `sandbox: true`
- `--dry-run` flagga för skills med side-effects

## Utveckling

```bash
git config core.hooksPath .githooks  # Aktivera pre-commit hook
pytest tests/ -v                     # Kör tester (37 st i 4 filer)
```
