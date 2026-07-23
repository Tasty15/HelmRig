# HelmRig

CLI, runtime och övervakning för LangGraph-baserade AI-agenter.

Skapa agenter med pluggbara skills, schemalägg med cron, övervaka via Overlord-daemon,
kolla dashboarden, kör agentkedjor (chain) — allt från terminalen.

All kod ligger under [`agents/`](agents/).

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

## Arkitektur

```
harness.py                ← CLI: allt börjar här
├── agentkit/utils.py     ← Delade verktyg (rtk, env, call_skill, headroom)
├── agentkit/api.py       ← Programmatiskt API (skapa, kör, logga agenter i kod)
├── agentkit/alert.py     ← E-postnotifikation via Composio Gmail
├── agentkit/crawler.py   ← [T1] Crawl4AI webbcrawler med SQLite-cache
├── agentkit/memory.py    ← [T1] Chroma vector store (max 3 resultat)
├── agentkit/mcp.py       ← [T1] MCP-klient för externa tool-servrar
├── agentkit/knowledge.py ← [T2] Auto-index av agent-resultat i Chroma
├── agentkit/webhook.py   ← [T2] Webhook listener (POST → agent)
├── agentkit/tracer.py    ← [T2] Langfuse tracing (token/tool/latency)
├── agentkit/file_reader.py← [T3] PDF/DOCX/text-läsning
├── agentkit/api_gateway.py← [T3] REST API (POST /api/run/<agent>)
├── agentkit/slack_bot.py ← [T3] Slack-bot (lyssna → dispatchera)
├── .overlord/overlord.py ← Daemon: watchdog, health, jobbkö, cron
├── dashboard/app.py      ← Flask + htmx (port 5050) + blueprints
└── agents/<name>/        ← Agentkataloger med LangGraph-pipelines
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
pytest tests/ -v                     # Kör tester (25 st i 3 filer)
```

## Docker

```bash
docker compose up --build
```
