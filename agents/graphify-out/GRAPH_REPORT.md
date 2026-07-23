# Graph Report - .  (2026-07-23)

## Corpus Check
- 16 files · ~16,260 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 294 nodes · 432 edges · 30 communities (16 shown, 14 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 23 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- CLI & Environment
- Config & Cron
- AgentKit Utilities
- AgentKit API
- Tests — CLI
- Dashboard Backend
- Tests — Overlord
- Utilities & Secrets
- Tests — Cron Journal
- Alerting
- Dashboard Templates
- CI Workflow
- Overlord Config
- Documentation
- Git Hooks
- AgentKit Concept
- Chain Concept
- LangGraph Concept
- Skill Concept
- Design Theme
- Output Preview
- CI YAML
- Serena Config
- Agent Template
- Dashboard HTML
- Test Agent Config
- HelmRig Project
- Serena Project

## God Nodes (most connected - your core abstractions)
1. `main()` - 19 edges
2. `cmd_run()` - 15 edges
3. `_read_config()` - 12 edges
4. `_run()` - 11 edges
5. `main()` - 11 edges
6. `_catch_up()` - 10 edges
7. `TestCronMatching` - 9 edges
8. `TestGetMissedSlots` - 9 edges
9. `Dashboard Template` - 8 edges
10. `_run_agent()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `Context & Architecture` --references--> `load_env()`  [EXTRACTED]
  CONTEXT.md → agentkit/utils.py
- `Context & Architecture` --references--> `_read_config()`  [EXTRACTED]
  CONTEXT.md → harness.py
- `README - HelmRig Harness` --references--> `cmd_run()`  [EXTRACTED]
  README.md → harness.py
- `Context & Architecture` --references--> `cmd_run()`  [EXTRACTED]
  CONTEXT.md → harness.py
- `README - HelmRig Harness` --references--> `cmd_env()`  [EXTRACTED]
  README.md → harness.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Community 0: CLI Harness Commands** — harness_cmd_run, harness_cmd_cron_list, harness_cmd_cron_run, harness_cmd_doctor, harness_cmd_env, harness_cmd_install, harness_cmd_list, harness_cmd_log, harness_cmd_overlord_logs, harness_cmd_overlord_start, harness_cmd_overlord_status, harness_cmd_overlord_stop, harness_cmd_remove, harness_cmd_scaffold, harness_cmd_setup [EXTRACTED 0.80]
- **Community 1: AgentKit Utilities** — agentkit_utils_call_skill, agentkit_utils_create_model, agentkit_utils_headroom_memory, agentkit_utils_load_env, agentkit_utils_read_env_file [EXTRACTED 0.80]
- **Community 3: Overlord & Config Merge** — overlord_overlord_health_check, harness_read_config, harness_load_overlord_config [EXTRACTED 0.80]

## Communities (30 total, 14 thin omitted)

### Community 0 - "CLI & Environment"
Cohesion: 0.08
Nodes (49): README - HelmRig Harness, Läs .env-fil som dict, exklusive kommentarer., Skriv .env-fil från dict, sorterad., read_env_file(), write_env_file(), cmd_cron_list(), cmd_cron_run(), cmd_dashboard() (+41 more)

### Community 1 - "Config & Cron"
Cohesion: 0.10
Nodes (33): _load_overlord_config(), Läs och validera agent.yaml., Läs central config från .overlord/config.yaml. Tom dict om ingen config finns., _read_config(), Lock, _cron_field_matches(), _cron_matches(), get_missed_slots() (+25 more)

### Community 2 - "AgentKit Utilities"
Cohesion: 0.13
Nodes (18): call_skill(), create_model(), headroom_memory(), load_env(), Path, Delade verktyg för HelmRig — en gång, importerad överallt., Ladda .env från projektroten., Skapa en LangChain-modell baserat på agent.yaml config.      Stödjer: openai, de (+10 more)

### Community 3 - "AgentKit API"
Cohesion: 0.11
Nodes (20): get_agent(), get_logs(), list_agents(), Path, _python(), Programmatiskt API för HelmRig — skapa, kör och hantera agenter i kod., Skapa en ny agent programmatiskt (motsvarar 'harness scaffold')., Hitta rätt python för en agent (per-agent venv > huvud-venv > system). (+12 more)

### Community 4 - "Tests — CLI"
Cohesion: 0.12
Nodes (14): CompletedProcess, Tester för harness CLI-kommandon., Kör harness med givna argument., harness list' visar meddelande om inga agenter., harness --help' visar hjälp., harness scaffold' med ogiltigt namn ska misslyckas., harness scaffold' med giltigt namn skapar mappstruktur., harness scaffold --react' skapar ReAct-agent. (+6 more)

### Community 5 - "Dashboard Backend"
Cohesion: 0.15
Nodes (19): agent_history(), _compute_stats(), _cron_field_matches(), _cron_matches(), dashboard(), health(), _load_jsonl_safe(), _load_logs() (+11 more)

### Community 6 - "Tests — Overlord"
Cohesion: 0.10
Nodes (8): Ta bort JSONL-loggar äldre än retention_days., _rotate_logs(), Tester för overlord daemon — cron-matching, log rotation, concurrency., _cron_field_matches och _cron_matches., TestConcurrencyLocks, TestCronMatching, TestLogRotation, TestReadAgentConfig

### Community 7 - "Utilities & Secrets"
Cohesion: 0.10
Nodes (20): Context & Architecture, mask_secrets(), Maska API-nycklar, tokens och lösenord i en sträng.      Ex: "KEY=sk-abc123...", Komprimera text genom rtk pipe — sparar tokens i LLM-kontext.      Fallerar tyst, rtk_compress(), Overlord, _alert_on_failure(), _check_deps() (+12 more)

### Community 8 - "Tests — Cron Journal"
Cohesion: 0.12
Nodes (9): Kontorscron 09-17 vardagar. Hela dagen avstängd → 9 slots., Lördag — inga vardagsslots.         Obs: cron DOW använder Python weekday() (0=M, 4-fälts cron → tom lista, ingen krasch., Slot precis vid now-gränsen ska inte räknas som missad., Agent körde nyss — inga missade slots., En missad slot (09:00) mellan 08:00-10:00., Två missade slots (09:00, 17:00) samma dag., Ogiltigt last_run-datum → tom lista. (+1 more)

### Community 9 - "Alerting"
Cohesion: 0.12
Nodes (10): Alerting — skicka e-post vid misslyckade agentkörningar via Composio Gmail., Skicka e-post om en agent misslyckades.      Använder composio Gmail (samma conn, send_email_alert(), datetime, Tester för cron-journal — missed slot detection + journal persistence., Ingen journal-fil → tom dict., Korrupt JSON → tom dict, ingen krasch., Save → Load ska returnera samma data. (+2 more)

### Community 10 - "Dashboard Templates"
Cohesion: 0.17
Nodes (12): Agent History Template, Dashboard Template, Design System: HelmRig Dashboard, Agent Card, Chart Bar, Cron Timeline, Empty State, KPI Card (+4 more)

### Community 11 - "CI Workflow"
Cohesion: 0.40
Nodes (5): CI Workflow, Install dependencies, Lint, Set up Python, Test

### Community 12 - "Overlord Config"
Cohesion: 0.40
Nodes (5): Overlord Config, Defaults, Health, Overrides, Watchdog

### Community 13 - "Documentation"
Cohesion: 0.67
Nodes (3): config.yaml - Overlord Central Configuration, CONTEXT.md - HelmRig Context & Architecture, README.md - HelmRig Harness README

## Knowledge Gaps
- **26 isolated node(s):** `Serena Project Config`, `Agent Card`, `Status Badge`, `KPI Card`, `Chart Bar` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **14 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TestGetMissedSlots` connect `Tests — Cron Journal` to `Alerting`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Why does `_rotate_logs()` connect `Tests — Overlord` to `Config & Cron`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `load_env()` connect `AgentKit Utilities` to `Utilities & Secrets`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **What connects `Serena Project Config`, `Agent Card`, `Status Badge` to the rest of the system?**
  _26 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CLI & Environment` be split into smaller, more focused modules?**
  _Cohesion score 0.08408163265306122 - nodes in this community are weakly interconnected._
- **Should `Config & Cron` be split into smaller, more focused modules?**
  _Cohesion score 0.0960960960960961 - nodes in this community are weakly interconnected._
- **Should `AgentKit Utilities` be split into smaller, more focused modules?**
  _Cohesion score 0.13043478260869565 - nodes in this community are weakly interconnected._