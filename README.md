# HelmRig

CLI, runtime och övervakning för LangGraph-baserade AI-agenter.

All kod finns under [`agents/`](agents/README.md) — inklusive CLI (`harness.py`),
agentkit, Overlord-daemon och dashboard.

## Snabbstart

```bash
make setup          # Skapa venv + installera CLI-verktyg
make run            # Starta dashboard (port 5050)
make overlord       # Starta Overlord-daemon
make test           # Kör tester
make doctor         # Diagnostik
```

## Docker

```bash
make docker         # docker compose up --build
```

Se [`agents/README.md`](agents/README.md) för full dokumentation om agenter, skills och CLI.
