# Graph Report - /home/simon/HelmRig/agents  (2026-07-22)

## Corpus Check
- Corpus is ~11,939 words - fits in a single context window. You may not need a graph.

## Summary
- 205 nodes · 314 edges · 22 communities (15 shown, 7 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 13 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- CLI Harness Commands
- AgentKit Utilities
- Harness Tests
- Overlord & Config Merge
- Dashboard (Flask + htmx)
- Alerting & Runtime
- AgentKit API
- Overlord Tests
- Cron Matching
- Secrets & Logging
- Test Failure Agent
- Documentation
- Git Hooks
- CI Configuration
- Serena Config
- Agent HTML Template
- Dashboard HTML Template
- Test Agent Config
- Package Metadata

## God Nodes (most connected - your core abstractions)
1. `main()` - 17 edges
2. `cmd_run()` - 13 edges
3. `_run()` - 11 edges
4. `main()` - 10 edges
5. `_read_config()` - 10 edges
6. `TestCronMatching` - 9 edges
7. `load_env()` - 7 edges
8. `_list_agents()` - 7 edges
9. `cmd_install()` - 7 edges
10. `cmd_env()` - 7 edges

## Surprising Connections (you probably didn't know these)
- `cmd_env()` --calls--> `mask_secrets()`  [EXTRACTED]
  harness.py → agentkit/utils.py
- `cmd_run()` --calls--> `headroom_memory()`  [EXTRACTED]
  harness.py → agentkit/utils.py
- `cmd_env()` --calls--> `read_env_file()`  [EXTRACTED]
  harness.py → agentkit/utils.py
- `cmd_env()` --calls--> `write_env_file()`  [EXTRACTED]
  harness.py → agentkit/utils.py
- `main()` --calls--> `_list_agents()`  [EXTRACTED]
  .overlord/overlord.py → harness.py

## Import Cycles
- None detected.

## Communities (22 total, 7 thin omitted)

### Community 0 - "CLI Harness Commands"
Cohesion: 0.10
Nodes (37): cmd_cron_list(), cmd_cron_run(), cmd_doctor(), cmd_env(), cmd_install(), cmd_list(), cmd_log(), cmd_overlord_logs() (+29 more)

### Community 1 - "AgentKit Utilities"
Cohesion: 0.11
Nodes (22): call_skill(), create_model(), headroom_memory(), load_env(), Path, Delade verktyg för HelmRig — en gång, importerad överallt., Ladda .env från projektroten., Läs .env-fil som dict, exklusive kommentarer. (+14 more)

### Community 2 - "Harness Tests"
Cohesion: 0.12
Nodes (14): CompletedProcess, Tester för harness CLI-kommandon., Kör harness med givna argument., harness list' visar meddelande om inga agenter., harness --help' visar hjälp., harness scaffold' med ogiltigt namn ska misslyckas., harness scaffold' med giltigt namn skapar mappstruktur., harness scaffold --react' skapar ReAct-agent. (+6 more)

### Community 3 - "Overlord & Config Merge"
Cohesion: 0.16
Nodes (17): _list_agents(), _load_overlord_config(), Path, Läs och validera agent.yaml., Läs central config från .overlord/config.yaml. Tom dict om ingen config finns., Hitta alla agentkataloger med agent.yaml., _read_config(), health_check() (+9 more)

### Community 4 - "Dashboard (Flask + htmx)"
Cohesion: 0.14
Nodes (17): agent_history(), dashboard(), health(), _load_jsonl_safe(), _load_logs(), _log_audit(), metrics(), Path (+9 more)

### Community 5 - "Alerting & Runtime"
Cohesion: 0.12
Nodes (15): Alerting — skicka e-post vid misslyckade agentkörningar via Composio Gmail., Skicka e-post om en agent misslyckades.      Använder composio Gmail (samma conn, send_email_alert(), Komprimera text genom rtk pipe — sparar tokens i LLM-kontext.      Fallerar tyst, rtk_compress(), _alert_on_failure(), _check_deps(), cmd_run() (+7 more)

### Community 6 - "AgentKit API"
Cohesion: 0.14
Nodes (14): get_agent(), get_logs(), list_agents(), Path, _python(), Programmatiskt API för HelmRig — skapa, kör och hantera agenter i kod., Skapa en ny agent programmatiskt (motsvarar 'harness scaffold')., Hitta rätt python för en agent (per-agent venv > huvud-venv > system). (+6 more)

### Community 7 - "Overlord Tests"
Cohesion: 0.20
Nodes (6): Ta bort JSONL-loggar äldre än retention_days., _rotate_logs(), Tester för overlord daemon — cron-matching, log rotation, concurrency., TestConcurrencyLocks, TestLogRotation, TestReadAgentConfig

### Community 8 - "Cron Matching"
Cohesion: 0.29
Nodes (4): _cron_field_matches(), _cron_matches(), _cron_field_matches och _cron_matches., TestCronMatching

### Community 9 - "Secrets & Logging"
Cohesion: 0.33
Nodes (6): mask_secrets(), Maska API-nycklar, tokens och lösenord i en sträng.      Ex: "KEY=sk-abc123...", _mask_secrets_in_dict(), Maska känslig data i en dict via JSON-roundtrip., Skriv en loggpost till JSONL (maskar API-nycklar)., _write_log_entry()

### Community 10 - "Test Failure Agent"
Cohesion: 0.50
Nodes (3): Exempelskills — ersätt med faktisk implementation., Kör skillets logik. Motta parametrar från agentens pipeline., run()

### Community 11 - "Documentation"
Cohesion: 0.67
Nodes (3): config.yaml - Overlord Central Configuration, CONTEXT.md - HelmRig Context & Architecture, README.md - HelmRig Harness README

## Knowledge Gaps
- **1 isolated node(s):** `helmrig`
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_cron_field_matches()` connect `Cron Matching` to `Overlord & Config Merge`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Why does `_rotate_logs()` connect `Overlord Tests` to `Overlord & Config Merge`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **What connects `helmrig` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CLI Harness Commands` be split into smaller, more focused modules?**
  _Cohesion score 0.10241820768136557 - nodes in this community are weakly interconnected._
- **Should `AgentKit Utilities` be split into smaller, more focused modules?**
  _Cohesion score 0.1111111111111111 - nodes in this community are weakly interconnected._
- **Should `Harness Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.11857707509881422 - nodes in this community are weakly interconnected._
- **Should `Dashboard (Flask + htmx)` be split into smaller, more focused modules?**
  _Cohesion score 0.1437908496732026 - nodes in this community are weakly interconnected._