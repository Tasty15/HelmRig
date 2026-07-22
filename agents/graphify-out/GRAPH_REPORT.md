# Graph Report - /home/simon/HelmRig/agents  (2026-07-22)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 239 nodes · 359 edges · 32 communities (18 shown, 14 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 17 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- utils.py
- app.py
- _run
- overlord.py
- main
- harness.py
- api.py
- TestCronMatching
- read_env_file
- Dashboard Template
- cmd_install
- Path
- CI Workflow
- Overlord Config
- mask_secrets
- CONTEXT.md - HelmRig Context & Architecture
- pre-commit
- AgentKit
- Chain
- LangGraph Pipeline
- Skill
- Cockpit Dense Theme
- Stdout preview
- ci.yml - GitHub Actions CI
- project.yml - Serena Project Configuration
- Dashboard template: agent.html
- Dashboard template: dashboard.html
- test-fail/agent.yaml - Agent Configuration
- helmrig
- Serena Project Config

## God Nodes (most connected - your core abstractions)
1. `main()` - 19 edges
2. `cmd_run()` - 15 edges
3. `_read_config()` - 11 edges
4. `_run()` - 11 edges
5. `main()` - 10 edges
6. `TestCronMatching` - 9 edges
7. `load_env()` - 8 edges
8. `read_env_file()` - 8 edges
9. `write_env_file()` - 8 edges
10. `cmd_env()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `Context & Architecture` --references--> `load_env()`  [EXTRACTED]
  CONTEXT.md → agentkit/utils.py
- `README - HelmRig Harness` --references--> `cmd_env()`  [EXTRACTED]
  README.md → harness.py
- `README - HelmRig Harness` --references--> `cmd_run()`  [EXTRACTED]
  README.md → harness.py
- `Context & Architecture` --references--> `_read_config()`  [EXTRACTED]
  CONTEXT.md → harness.py
- `README - HelmRig Harness` --references--> `cmd_scaffold()`  [EXTRACTED]
  README.md → harness.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Community 0: CLI Harness Commands** — harness_cmd_run, harness_cmd_cron_list, harness_cmd_cron_run, harness_cmd_doctor, harness_cmd_env, harness_cmd_install, harness_cmd_list, harness_cmd_log, harness_cmd_overlord_logs, harness_cmd_overlord_start, harness_cmd_overlord_status, harness_cmd_overlord_stop, harness_cmd_remove, harness_cmd_scaffold, harness_cmd_setup [EXTRACTED 0.80]
- **Community 1: AgentKit Utilities** — agentkit_utils_call_skill, agentkit_utils_create_model, agentkit_utils_headroom_memory, agentkit_utils_load_env, agentkit_utils_read_env_file [EXTRACTED 0.80]
- **Community 3: Overlord & Config Merge** — overlord_overlord_health_check, harness_read_config, harness_load_overlord_config [EXTRACTED 0.80]

## Communities (32 total, 14 thin omitted)

### Community 0 - "utils.py"
Cohesion: 0.13
Nodes (18): call_skill(), create_model(), headroom_memory(), load_env(), Path, Delade verktyg för HelmRig — en gång, importerad överallt., Ladda .env från projektroten., Skapa en LangChain-modell baserat på agent.yaml config.      Stödjer: openai, de (+10 more)

### Community 1 - "app.py"
Cohesion: 0.13
Nodes (20): Alerting — skicka e-post vid misslyckade agentkörningar via Composio Gmail., agent_history(), _compute_stats(), _cron_field_matches(), _cron_matches(), dashboard(), health(), _load_jsonl_safe() (+12 more)

### Community 2 - "_run"
Cohesion: 0.12
Nodes (14): CompletedProcess, Tester för harness CLI-kommandon., Kör harness med givna argument., harness list' visar meddelande om inga agenter., harness --help' visar hjälp., harness scaffold' med ogiltigt namn ska misslyckas., harness scaffold' med giltigt namn skapar mappstruktur., harness scaffold --react' skapar ReAct-agent. (+6 more)

### Community 3 - "overlord.py"
Cohesion: 0.15
Nodes (17): _list_agents(), Hitta alla agentkataloger med agent.yaml., _cron_field_matches(), _cron_matches(), health_check(), _load_config(), _log(), main() (+9 more)

### Community 4 - "main"
Cohesion: 0.15
Nodes (20): README - HelmRig Harness, cmd_cron_list(), cmd_cron_run(), cmd_list(), cmd_log(), cmd_overlord_logs(), cmd_overlord_start(), cmd_overlord_status() (+12 more)

### Community 5 - "harness.py"
Cohesion: 0.15
Nodes (18): Context & Architecture, Skicka e-post om en agent misslyckades.      Använder composio Gmail (samma conn, send_email_alert(), Komprimera text genom rtk pipe — sparar tokens i LLM-kontext.      Fallerar tyst, rtk_compress(), Overlord, _alert_on_failure(), cmd_run() (+10 more)

### Community 6 - "api.py"
Cohesion: 0.14
Nodes (14): get_agent(), get_logs(), list_agents(), Path, _python(), Programmatiskt API för HelmRig — skapa, kör och hantera agenter i kod., Skapa en ny agent programmatiskt (motsvarar 'harness scaffold')., Hitta rätt python för en agent (per-agent venv > huvud-venv > system). (+6 more)

### Community 7 - "TestCronMatching"
Cohesion: 0.13
Nodes (5): Tester för overlord daemon — cron-matching, log rotation, concurrency., _cron_field_matches och _cron_matches., TestConcurrencyLocks, TestCronMatching, TestReadAgentConfig

### Community 8 - "read_env_file"
Cohesion: 0.18
Nodes (14): Läs .env-fil som dict, exklusive kommentarer., Skriv .env-fil från dict, sorterad., read_env_file(), write_env_file(), cmd_dashboard(), cmd_env(), cmd_setup(), cmd_tunnel() (+6 more)

### Community 9 - "Dashboard Template"
Cohesion: 0.17
Nodes (12): Agent History Template, Dashboard Template, Design System: HelmRig Dashboard, Agent Card, Chart Bar, Cron Timeline, Empty State, KPI Card (+4 more)

### Community 10 - "cmd_install"
Cohesion: 0.20
Nodes (10): cmd_install(), cmd_remove(), cmd_validate(), _ensure_agent_venv(), Validera agentnamn — endast [a-z0-9_-]. Höj vid ogiltigt., Skapa per-agent virtualenv om den inte finns. Returnera python-sökväg., Installera dependencies i per-agent virtualenv., Ta bort en agent (mapp, loggar, config-override). (+2 more)

### Community 11 - "Path"
Cohesion: 0.29
Nodes (7): _check_deps(), cmd_doctor(), Path, Kontrollera att alla beroenden finns installerade., Kontrollera att packages i requirements.txt finns installerade., Hitta agentkatalog — först AGENTS_DIR/name, sen cwd/name., _resolve_agent_dir()

### Community 12 - "CI Workflow"
Cohesion: 0.40
Nodes (5): CI Workflow, Install dependencies, Lint, Set up Python, Test

### Community 13 - "Overlord Config"
Cohesion: 0.40
Nodes (5): Overlord Config, Defaults, Health, Overrides, Watchdog

### Community 14 - "mask_secrets"
Cohesion: 0.50
Nodes (4): mask_secrets(), Maska API-nycklar, tokens och lösenord i en sträng.      Ex: "KEY=sk-abc123...", _mask_secrets_in_dict(), Maska känslig data i en dict via JSON-roundtrip.

### Community 15 - "CONTEXT.md - HelmRig Context & Architecture"
Cohesion: 0.67
Nodes (3): config.yaml - Overlord Central Configuration, CONTEXT.md - HelmRig Context & Architecture, README.md - HelmRig Harness README

## Knowledge Gaps
- **26 isolated node(s):** `helmrig`, `Serena Project Config`, `Agent Card`, `Status Badge`, `KPI Card` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `load_env()` connect `utils.py` to `harness.py`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **What connects `helmrig`, `Serena Project Config`, `Agent Card` to the rest of the system?**
  _26 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `utils.py` be split into smaller, more focused modules?**
  _Cohesion score 0.13043478260869565 - nodes in this community are weakly interconnected._
- **Should `app.py` be split into smaller, more focused modules?**
  _Cohesion score 0.13438735177865613 - nodes in this community are weakly interconnected._
- **Should `_run` be split into smaller, more focused modules?**
  _Cohesion score 0.11857707509881422 - nodes in this community are weakly interconnected._
- **Should `overlord.py` be split into smaller, more focused modules?**
  _Cohesion score 0.14624505928853754 - nodes in this community are weakly interconnected._
- **Should `main` be split into smaller, more focused modules?**
  _Cohesion score 0.14736842105263157 - nodes in this community are weakly interconnected._