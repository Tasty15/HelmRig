# HelmRig — Context & Arkitektur

> Genererad från graphify-graf: 370 noder · 512 edges · 35 communities
> Commit: `332f2c9` · Uppdaterad: 2026-07-23

---

## 1. Projektöversikt

HelmRig är ett CLI-ramverk för att skapa, köra och övervaka AI-agenter.
Varje agent är en LangGraph-pipeline med pluggbara skills, cron-schemaläggning,
och central övervakning via Overlord-daemonen + dashboard.

```
HelmRig/
├── .env                          # API-nycklar (maskade i loggar)
└── agents/                       # 🎯 Projektrot
    ├── harness.py                # CLI: scaffold, run, cron, log, env, queue
    ├── agentkit/                 # Delade moduler
    │   ├── utils.py              # rtk_run, headroom_memory, load_env, call_skill, mask_secrets
    │   ├── alert.py              # E-postnotifikation vid fel
    │   ├── api.py                # Programmatiskt API (get_agent, run_agent, scaffold)
    │   ├── sub_agent.py          # Sub-agent dispatch (anropa agent som tool)
    │   ├── parallel.py           # Parallel fan-out (flera agenter samtidigt)
    │   ├── crawler.py            # [T1] Webbcrawler — Crawl4AI wrapper med SQLite-cache
    │   ├── memory.py             # [T1] Agentminne — Chroma vector store, max 3 resultat
    │   ├── mcp.py                # [T1] MCP-klient — anslut till MCP-servrar via stdio
    │   ├── knowledge.py          # [T2] Knowledge base — auto-index av agent-resultat
    │   ├── webhook.py            # [T2] Webhook listener — POST /webhook/<agent>
    │   ├── tracer.py             # [T2] Langfuse tracing — token/tool/latency-spårning
    │   ├── file_reader.py        # [T3] File reader — PDF, DOCX, text-filer
    │   ├── api_gateway.py        # [T3] API Gateway — POST /api/run/<agent>
    │   └── slack_bot.py          # [T3] Slack-bot — lyssna och dispatchera till agent
    ├── .overlord/                # Central övervakning
    │   ├── config.yaml           # Defaults, overrides, watchdog, queue
    │   ├── overlord.py           # Daemon: watchdog + health + queue consumer
    │   └── logs/                 # JSONL-runloggar per agent
    ├── dashboard/                # Flask + htmx (port 5050)
    │   ├── app.py
    │   └── templates/            # agent.html, dashboard.html
    ├── .serena/                  # Serena IDE projektkonfiguration
    ├── design.md                 # UI-design guidelines för dashboard
    ├── tests/                    # pytest-tester (25 st i 3 filer)
    ├── test-fail/                # Test-agent (används i tester)
    ├── graphify-out/             # Knowledge graph (graph.html, GRAPH_REPORT.md)
    ├── .githooks/pre-commit      # ruff + pytest vid commit
    └── .github/workflows/ci.yml  # GitHub Actions
```

---

## 2. Arkitektur (från graph communities)

Grafen identifierade 35 communities med följande kärnområden (19 visas, 16 tunna utelämnade):

### Community 0 — AgentKit Utilities (18 noder)
- `agentkit/utils.py`: call_skill, create_model, headroom_memory, load_env
- Delade verktyg som importeras överallt i systemet

### Community 1 — Dashboard + Alerting + Cron (20 noder)
- `dashboard/app.py`: agent_history, dashboard, health, metrics, _compute_stats
- `agentkit/alert.py`: send_email_alert (Composio Gmail)
- `agentkit/utils.py`: rtk_compress
- `overlord.py`: _cron_field_matches, _cron_matches

### Community 2 — Harness Tests (14 noder)
- `tests/test_harness.py`: tester för CLI-kommandon
- `tests/test_utils.py`: tester för utility-funktioner
- CompletedProcess-hantering, argumenttestning

### Community 3 — Overlord Daemon (17 noder)
- `overlord.py`: health_check, _list_agents, main, watchdog, config-loading
- Övervakning och processhantering

### Community 4 — CLI Commands (20 noder)
- `harness.py`: cmd_cron_list, cmd_cron_run, cmd_list, cmd_log, cmd_overlord_logs, cmd_overlord_start, cmd_overlord_status, cmd_overlord_stop
- README, Context & Architecture — dokumentation kopplad till CLI

### Community 5 — Runtime & Alerting (18 noder)
- `harness.py`: cmd_run, _alert_on_failure, send_email_alert
- `agentkit/utils.py`: rtk_compress
- Agentexekvering, timeout, chain, felnotifikation

### Community 6 — AgentKit API (14 noder)
- `agentkit/api.py`: get_agent, get_logs, list_agents, run_agent, scaffold_agent
- Programmatiskt API för HelmRig

### Community 7 — Overlord Tests (5 noder)
- `tests/test_overlord.py`: TestConcurrencyLocks, TestCronMatching, TestReadAgentConfig
- Log rotation, concurrency-lås, cron-matching

### Community 8 — Environment & CLI (14 noder)
- `harness.py`: cmd_dashboard, cmd_env, cmd_setup, cmd_tunnel
- `agentkit/utils.py`: read_env_file, write_env_file
- .env-hantering, dashboard start, SSH-tunnel

### Community 9 — Dashboard Templates (12 noder)
- `dashboard/templates/agent.html`: Agent History, Status Badge, Cron Timeline
- `dashboard/templates/dashboard.html`: KPI Card, Chart Bar, Empty State
- Design System tokens i `design.md`

### Community 7 — MCP Client (21 noder)
- `agentkit/mcp.py`: McpClient, create_tools, list_tools_from_server
- MCP stdio-klient för externa tool-servrar

### Community 8 — Knowledge Base & Memory (16 noder)
- `agentkit/knowledge.py`: store_result, search
- `agentkit/memory.py`: store, recall, forget (Chroma vector store)
- Auto-index agent-resultat, token-snål recall (max 3)

### Community 11 — File Reader (10 noder)
- `agentkit/file_reader.py`: _read_pdf, _read_docx, _read_text
- PDF (PyMuPDF), DOCX (python-docx) och text-filer

### Community 12 — Webbcrawler (7 noder)
- `agentkit/crawler.py`: crawl, _cache_get, _cache_set
- Crawl4AI wrapper med SQLite-cache

### Community 13 — Tracing (6 noder)
- `agentkit/tracer.py`: get_langfuse_handler, trace_run
- Langfuse callback för token/latency-spårning

### Community 16 — Slack-bot (4 noder)
- `agentkit/slack_bot.py`: listen
- Poll Slack-kanaler och dispatchera till agenter

### Community 10 — Agent Management (10 noder)
- `harness.py`: cmd_install, cmd_remove, cmd_validate
- Per-agent virtualenv, dependency-installation

### Community 11 — Dependency Check (7 noder)
- `harness.py`: _check_deps, cmd_doctor, _resolve_agent_dir
- PATH-hantering, beroendekontroll

### Community 12 — CI Workflow (5 noder)
- `.github/workflows/ci.yml`: lint, test, setup
- GitHub Actions pipeline

### Community 13 — Overlord Config (5 noder)
- `.overlord/config.yaml`: Defaults, Health, Overrides, Watchdog, Queue
- Central konfiguration för overlord-daemon

### Community 14 — Secrets & Logging (4 noder)
- `agentkit/utils.py`: mask_secrets
- `harness.py`: _mask_secrets_in_dict, _write_log_entry
- API-nyckel-maskering i loggar och env-visning

### Community 15 — Documentation (3 noder)
- CONTEXT.md, README.md, config.yaml
- Projekt-dokumentation och arkitekturbeskrivning

---

## 3. Kärnabstraktioner (God Nodes)

| Nod | Grad | Roll |
|---|---|---|
| `harness.py:main()` | 19 edges | CLI-dispatch, alla kommandon |
| `cmd_run()` | 15 edges | Agentexekvering, timeout, chain, alerting |
| `_read_config()` | 11 edges | Config-merge (agent.yaml → overlord → defaults) |
| `_run()` | 11 edges | Subprocess-run (används av cmd_run, chain) |
| `overlord.py:main()` | 10 edges | Overlord daemon entry |
| `load_env()` | 8 edges | Miljövariabler från .env |
| `read_env_file()` | 8 edges | Läs/skriv .env-filer |
| `cmd_env()` | 8 edges | CLI-hantering av miljövariabler |
| `_list_agents()` | 7 edges | Agent-discovery (används av list, cmd_run) |

---

## 4. Hur man skapar en ny agent

### 4.1 Snabbstart

```bash
# Skapa agent (hårdkodad LangGraph-pipeline)
harness scaffold min-agent

# Eller ReAct-agent (LLM väljer tools)
harness scaffold min-agent --react

# Installera beroenden
harness install min-agent

# Validera konfiguration
harness validate min-agent

# Kör manuellt
harness run min-agent

# Lägg till cron-schema (redigera agent.yaml)
cron: "0 9 * * 1-5"  # vardagar 09:00

# Se loggar
harness log min-agent
```

### 4.2 Agentstruktur

```
agents/min-agent/
├── agent.yaml           # <-- Redigera först
├── main.py              # <-- LangGraph pipeline (redigera)
├── requirements.txt     # <-- Lägg till pip-beroenden
└── skills/
    ├── __init__.py
    └── example_skill.py # <-- Ersätt med egna skills
```

### 4.3 agent.yaml — referens

```yaml
name: "min-agent"
description: "Beskrivning av vad agenten gör"
instructions: |
  System-prompt till AI-modellen. Var konkret.
  Tala om vad agenten ska fokusera på.
model:
  provider: deepseek          # eller openai
  name: deepseek-chat         # eller gpt-4o
  api_base: https://api.deepseek.com/v1
skills:
  - name: my_skill
    module: skills.my_skill
    description: "Vad denna skill gör"
    side_effect: false         # true = kräver --dry-run-respekt
    sandbox: false             # true = rensad miljö före anrop
cron: null                     # "0 9 * * 1-5" för schemaläggning
timeout: 300                   # max sekunder (default 300)
chain:                         # agentkedjor (valfritt)
  next_agent: stock-watcher
  mapping:
    output_key: input_key
```

### 4.4 Skill-kontrakt

Varje skill exporterar en `run(**kwargs)`-funktion som returnerar en dict:

```python
"""skills/my_skill.py — exempel"""

def run(**kwargs) -> dict:
    """Kör skillets logik. Motta parametrar från agentens pipeline."""
    input_data = kwargs.get("input_field")
    # ... logik ...
    return {"result": "något", "status": "ok"}
```

### 4.5 LangGraph-pipeline (standard)

```python
"""Agent: min-agent"""
from agentkit.utils import call_skill, load_env

AGENT_CONFIG = ...  # läses från agent.yaml
load_env(AGENT_DIR)

class AgentState(TypedDict):
    result: dict

def step_one(state: AgentState) -> AgentState:
    data = call_skill(AGENT_CONFIG, "my_skill", param="value")
    return {"result": data}

# Bygg graph
builder = StateGraph(AgentState)
builder.add_node("step_one", step_one)
builder.add_edge(START, "step_one")
builder.add_edge("step_one", END)
graph = builder.compile()
```

### 4.6 ReAct-agent (--react)

LLM får skills som `@tool`-dekorerade funktioner och väljer själv när de ska anropas.

```python
from agentkit.utils import load_env
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

# Skills blir automatiskt tools via agent.yaml-scanning
agent = create_react_agent(model, tools)
```

### 4.7 Miljövariabler

```bash
# Lägg till i ai/.env:
DEEPSEEK_API_KEY=sk-...
ALERT_EMAIL_TO=dig@example.com   # felnotifikationer
DASHBOARD_TOKEN=hemligt           # dashboard auth
```

---

## 5. Config Merge-ordning

Värden slås samman i denna ordning (senare vinner):

1. **`agentkit/defaults`** — hårdkodade defaults
2. **`.overlord/config.yaml → defaults`** — centrala projekt-defaults
3. **`agent.yaml`** — per-agent-konfig
4. **`.overlord/config.yaml → overrides/<agent>`** — centrala overrides

---

## 6. Viktiga koncept

| Koncept | Förklaring |
|---|---|---|
| **Skill** | Python-modul med `run(**kwargs) → dict`. Importeras dynamiskt av agenten. |
| **Chain** | Agentkedjor: output från agent A → input till agent B via `CHAIN_OUTPUT: JSON`. |
| **Dry-run** | `--dry-run` flagga + env `HARNESS_DRY_RUN=true`. Skills med `side_effect: true` kollas innan körning. |
| **Sandbox** | `sandbox: true` på en skill rensar miljövariabler (behåller PATH + ALLOWED_*). |
| **Sub-agent dispatch** | `agentkit.sub_agent.dispatch()` — anropa en annan agent programmatiskt, få svar. Används som tool i ReAct-agent. |
| **Parallel fan-out** | `agentkit.parallel.fan_out()` — kör flera instanser av samma agent parallellt med ThreadPoolExecutor. |
| **Overlord** | Daemon som watchar loggar, startar om crashade agenter, kör hälsokoller och konsumerar jobbkö. Kan köra cron-jobb parallellt via `max_concurrent_cron`. |
| **Jobbkö** | Om max_concurrent=1 och en agent körs, hamnar nästa i kön (JSON-filer i `.overlord/queue/`). |
| **Agentkit** | Gemensamma moduler: utils (rtk, headroom, env, secrets), api, alert, sub_agent, parallel, crawler, memory, mcp, knowledge, webhook, tracer, file_reader, api_gateway, slack_bot. |

---

## 7. CLI-referens

```bash
harness scaffold <name> [--react]    # Skapa agent
harness list / ls                    # Lista alla
harness install [name]               # Installera deps
harness remove / rm <name>           # Ta bort agent
harness validate <name>              # Validera konfig
harness run <name> [--dry-run] [--timeout N] [--no-chain]
harness log [name] [-n N] [--since] [--until] [--level] [--tail] [--json]
harness env [key] [value]            # Visa/editera .env
harness cron list / run <name>       # Cron-scheman
harness overlord start|stop|status|logs [-n N] [--tail]
harness queue list|flush             # Jobbkö
```

---

## 8. Graf-översikt

En interaktiv graf över kodbasen finns i:

```
agents/graphify-out/graph.html
```

Öppna i webbläsaren för att navigera:
- **Noder** = filer, funktioner, klasser, koncept
- **Edges** = imports, anrop, referenser
- **Communities** = färgkodade kluster av relaterad kod

### Tvärcommunity-bryggor

1. `load_env()` — binder Community 0 (AgentKit Utilities) ↔ 5 (Runtime & Alerting)
2. `_cron_field_matches()` — binder Community 1 (Dashboard + Cron) ↔ 3 (Overlord Daemon)
3. `_cron_matches()` — binder Community 1 (Dashboard + Cron) ↔ 7 (Overlord Tests)
4. `cmd_env()` → `mask_secrets()` — binder Community 8 (Environment & CLI) ↔ 14 (Secrets)
5. `cmd_env()` → `read_env_file()` — binder Community 8 (Environment & CLI) ↔ 0 (AgentKit)
6. `cmd_run()` → `headroom_memory()` — binder Community 5 (Runtime) ↔ 0 (AgentKit)
7. `main()` → `_list_agents()` — Overlord (Community 3) anropar harness CLI (Community 4)

---

## 9. Utvecklingsflöde

```bash
# 1. Skapa ny agent
harness scaffold my-agent
# 2. Redigera agent.yaml + main.py + skills
vim my-agent/agent.yaml
vim my-agent/main.py
# 3. Validera
harness validate my-agent
# 4. Testa
harness run my-agent --dry-run
harness run my-agent
# 5. Logga
harness log my-agent --tail
# 6. Committa (pre-commit hook kör tester)
git add -A && git commit -m "feat: my-agent"
```

Pre-commit hooken kör automatiskt `ruff check` + `pytest tests/` (37 tester i 4 filer) före varje commit.
