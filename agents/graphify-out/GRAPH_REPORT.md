# Graph Report - .  (2026-07-23)

## Corpus Check
- Corpus is ~19,967 words - fits in a single context window. You may not need a graph.

## Summary
- 370 nodes · 512 edges · 35 communities (20 shown, 15 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 23 edges (avg confidence: 0.7)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- CLI & Översikt
- Overlord Cron & Journal
- AgentKit Alert, API Gateway & Webhook
- AgentKit Utilities (utils)
- Cron Journal Tester
- AgentKit API (programmatiskt)
- Harness CLI Tester
- MCP-klient (Model Context Protocol)
- Knowledge Base & Memory (Chroma)
- Overlord Tester
- Dashboard Templates & Design
- File Reader (PDF/DOCX)
- Webbcrawler (Crawl4AI)
- Tracing (Langfuse)
- CI Workflow
- Overlord Konfiguration
- Slack-bot
- Konfig & Dokumentation
- Git Hooks
- Mindre noder
- Mindre noder
- Mindre noder
- Mindre noder
- Mindre noder
- Mindre noder
- Mindre noder
- Mindre noder
- Mindre noder
- Mindre noder
- Mindre noder
- Mindre noder
- Mindre noder
- Mindre noder

## God Nodes (most connected - your core abstractions)
1. `main()` - 19 edges
2. `cmd_run()` - 13 edges
3. `_read_config()` - 12 edges
4. `_run()` - 11 edges
5. `main()` - 11 edges
6. `_catch_up()` - 10 edges
7. `McpClient` - 10 edges
8. `TestCronMatching` - 9 edges
9. `TestGetMissedSlots` - 9 edges
10. `Dashboard Template` - 8 edges

## Surprising Connections (you probably didn't know these)
- `Context & Architecture` --references--> `load_env()`  [EXTRACTED]
  CONTEXT.md → agentkit/utils.py
- `Context & Architecture` --references--> `cmd_run()`  [EXTRACTED]
  CONTEXT.md → harness.py
- `Context & Architecture` --references--> `_read_config()`  [EXTRACTED]
  CONTEXT.md → harness.py
- `README - HelmRig Harness` --references--> `cmd_env()`  [EXTRACTED]
  README.md → harness.py
- `README - HelmRig Harness` --references--> `cmd_log()`  [EXTRACTED]
  README.md → harness.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Community 0: CLI Harness Commands** — harness_cmd_run, harness_cmd_cron_list, harness_cmd_cron_run, harness_cmd_doctor, harness_cmd_env, harness_cmd_install, harness_cmd_list, harness_cmd_log, harness_cmd_overlord_logs, harness_cmd_overlord_start, harness_cmd_overlord_status, harness_cmd_overlord_stop, harness_cmd_remove, harness_cmd_scaffold, harness_cmd_setup [EXTRACTED 0.80]
- **Community 1: AgentKit Utilities** — agentkit_utils_call_skill, agentkit_utils_create_model, agentkit_utils_headroom_memory, agentkit_utils_load_env, agentkit_utils_read_env_file [EXTRACTED 0.80]
- **Community 3: Overlord & Config Merge** — overlord_overlord_health_check, harness_read_config, harness_load_overlord_config [EXTRACTED 0.80]

## Communities (35 total, 15 thin omitted)

### Community 0 - "CLI & Översikt"
Cohesion: 0.06
Nodes (65): Context & Architecture, README - HelmRig Harness, Overlord, _alert_on_failure(), _check_deps(), cmd_cron_list(), cmd_cron_run(), cmd_dashboard() (+57 more)

### Community 1 - "Overlord Cron & Journal"
Cohesion: 0.09
Nodes (32): Lock, _cron_field_matches(), _cron_matches(), get_missed_slots(), load_journal(), datetime, Persistent cron journal + missed slot calculation., Load cron journal. Returns {agent_name: {last_run, cron, status}}. (+24 more)

### Community 2 - "AgentKit Alert, API Gateway & Webhook"
Cohesion: 0.07
Nodes (30): Alerting — skicka e-post vid misslyckade agentkörningar via Composio Gmail., Skicka e-post om en agent misslyckades.      Använder composio Gmail (samma conn, send_email_alert(), get_agent_status(), API Gateway — exponera agenter som REST-endpoints.  Används som Flask Blueprint, Hämta status för en specifik agent., Kör en agent och returnera resultatet som JSON.      Body (valfritt):         {", run_agent_api() (+22 more)

### Community 3 - "AgentKit Utilities (utils)"
Cohesion: 0.09
Nodes (26): call_skill(), create_model(), headroom_memory(), load_env(), mask_secrets(), Path, Delade verktyg för HelmRig — en gång, importerad överallt., Ladda .env från projektroten. (+18 more)

### Community 4 - "Cron Journal Tester"
Cohesion: 0.07
Nodes (15): Tester för cron-journal — missed slot detection + journal persistence., Kontorscron 09-17 vardagar. Hela dagen avstängd → 9 slots., Lördag — inga vardagsslots.         Obs: cron DOW använder Python weekday() (0=M, 4-fälts cron → tom lista, ingen krasch., Slot precis vid now-gränsen ska inte räknas som missad., Ingen journal-fil → tom dict., Korrupt JSON → tom dict, ingen krasch., Save → Load ska returnera samma data. (+7 more)

### Community 5 - "AgentKit API (programmatiskt)"
Cohesion: 0.11
Nodes (20): get_agent(), get_logs(), list_agents(), Path, _python(), Programmatiskt API för HelmRig — skapa, kör och hantera agenter i kod., Skapa en ny agent programmatiskt (motsvarar 'harness scaffold')., Hitta rätt python för en agent (per-agent venv > huvud-venv > system). (+12 more)

### Community 6 - "Harness CLI Tester"
Cohesion: 0.12
Nodes (14): CompletedProcess, Tester för harness CLI-kommandon., Kör harness med givna argument., harness list' visar meddelande om inga agenter., harness --help' visar hjälp., harness scaffold' med ogiltigt namn ska misslyckas., harness scaffold' med giltigt namn skapar mappstruktur., harness scaffold --react' skapar ReAct-agent. (+6 more)

### Community 7 - "MCP-klient (Model Context Protocol)"
Cohesion: 0.13
Nodes (13): _async_call(), create_tools(), _list_tools_from_server(), mcp_tools_to_langchain(), McpClient, MCP-klient — anslut till MCP-servrar via stdio och exponera tools.  Användning i, Skapa LangChain-tools från MCP-serverkonfiguration.      Args:         servers:, Anslut till en MCP-server via stdio-transport.      Startar servern som subproce (+5 more)

### Community 8 - "Knowledge Base & Memory (Chroma)"
Cohesion: 0.18
Nodes (14): Knowledge base — auto-index agent-resultat i Chroma.  Används av harness.py efte, Spara en agentkörning i knowledge base.      Anropas automatiskt efter varje age, Sök i knowledge base över agentkörningar.      Args:         agent: Agentnamn (N, search(), store_result(), forget(), _get_collection(), Agentminne — Chroma vector store med token-snål recall.  Användning:     from ag (+6 more)

### Community 9 - "Overlord Tester"
Cohesion: 0.13
Nodes (5): Tester för overlord daemon — cron-matching, log rotation, concurrency., _cron_field_matches och _cron_matches., TestConcurrencyLocks, TestCronMatching, TestReadAgentConfig

### Community 10 - "Dashboard Templates & Design"
Cohesion: 0.17
Nodes (12): Agent History Template, Dashboard Template, Design System: HelmRig Dashboard, Agent Card, Chart Bar, Cron Timeline, Empty State, KPI Card (+4 more)

### Community 11 - "File Reader (PDF/DOCX)"
Cohesion: 0.33
Nodes (9): Path, File reader — läs PDF, DOCX, och textfiler.  Används som skill i agent.yaml:, Läs en fil och returnera textinnehållet.      Args:         path: Absolut eller, Extrahera text från PDF., Extrahera text från DOCX., _read_docx(), _read_pdf(), _read_text() (+1 more)

### Community 12 - "Webbcrawler (Crawl4AI)"
Cohesion: 0.48
Nodes (6): _cache_get(), _cache_set(), crawl(), _init_cache(), Webbcrawler — Crawl4AI wrapper med SQLite-cache.  Användning i agent-skill:, Hämta och extrahera text från en URL.      Args:         url: Full URL (https://

### Community 13 - "Tracing (Langfuse)"
Cohesion: 0.40
Nodes (5): get_langfuse_handler(), Tracing — Langfuse callback för token/tool/latency-spårning.  Används i agent-pi, Skapa en Langfuse callback handler för spårning.      Args:         agent_name:, Logga en agentkörning till Langfuse (anropas efter completion).      För agenter, trace_run()

### Community 14 - "CI Workflow"
Cohesion: 0.40
Nodes (5): CI Workflow, Install dependencies, Lint, Set up Python, Test

### Community 15 - "Overlord Konfiguration"
Cohesion: 0.40
Nodes (5): Overlord Config, Defaults, Health, Overrides, Watchdog

### Community 16 - "Slack-bot"
Cohesion: 0.50
Nodes (3): listen(), Slack-bot — lyssna på Slack-meddelanden och dispatchera till agenter.  Användnin, Poll Slack-kanal och dispatchera meddelanden till agent.      Args:         agen

### Community 17 - "Konfig & Dokumentation"
Cohesion: 0.67
Nodes (3): config.yaml - Overlord Central Configuration, CONTEXT.md - HelmRig Context & Architecture, README.md - HelmRig Harness README

## Knowledge Gaps
- **26 isolated node(s):** `Serena Project Config`, `Agent Card`, `Status Badge`, `KPI Card`, `Chart Bar` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `load_env()` connect `AgentKit Utilities (utils)` to `CLI & Översikt`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **What connects `Serena Project Config`, `Agent Card`, `Status Badge` to the rest of the system?**
  _26 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CLI & Översikt` be split into smaller, more focused modules?**
  _Cohesion score 0.06060606060606061 - nodes in this community are weakly interconnected._
- **Should `Overlord Cron & Journal` be split into smaller, more focused modules?**
  _Cohesion score 0.09041835357624832 - nodes in this community are weakly interconnected._
- **Should `AgentKit Alert, API Gateway & Webhook` be split into smaller, more focused modules?**
  _Cohesion score 0.07357357357357357 - nodes in this community are weakly interconnected._
- **Should `AgentKit Utilities (utils)` be split into smaller, more focused modules?**
  _Cohesion score 0.09274193548387097 - nodes in this community are weakly interconnected._
- **Should `Cron Journal Tester` be split into smaller, more focused modules?**
  _Cohesion score 0.07142857142857142 - nodes in this community are weakly interconnected._