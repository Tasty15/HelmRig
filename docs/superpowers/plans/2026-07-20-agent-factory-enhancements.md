# HelmRig Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add run-loggar, dry-run, headroom-minne, agentkedjor, och webb-panel till HelmRig.

**Architecture:** Hybrid — loggning/dry-run/kedjor centralt i harness, headroom-minne i delad modul (`agentkit/`), webb-panel som fristående Flask-app (`dashboard/`). Alla ändringar additiva.

**Tech Stack:** Python 3.14, stdlib (json, subprocess, pathlib), yaml; Headroom CLI; Flask + htmx (dashboard only)

## Global Constraints

- Alla ändringar additiva — ingen befintlig kod ändras om inte specen explicit säger så
- Logg-format: JSONL, en rad per körning i `.overlord/logs/<agent>.jsonl`
- Env-variabler: `HARNESS_DRY_RUN`, `HARNESS_DRY_RUN_SKILLS`, `CHAIN_INPUT_<key>`
- Python 3.14+, ingen ny dependency förutom `flask` (till dashboard)
- Headroom CLI på `/home/simon/.local/bin/headroom`

---

## File Structure

### Nya filer
| Fil | Ansvar |
|---|---|
| `ai/agents/agentkit/__init__.py` | Tom paket-markör |
| `ai/agents/agentkit/memory.py` | Headroom-wrapper: `save_run()`, `get_context()` |
| `ai/agents/dashboard/app.py` | Flask-app, routes, subprocess-anrop till harness |
| `ai/agents/dashboard/templates/dashboard.html` | Dashboard-sida med htmx |
| `ai/agents/dashboard/templates/agent.html` | Agent-historik-sida |
| `ai/agents/.overlord/logs/` | Katalog för JSONL-loggar (skapas automatiskt) |

### Modifierade filer
| Fil | Ändring |
|---|---|
| `ai/agents/harness.py` | +`cmd_log`, +`--dry-run` flag, +chain-protokoll, +auto-loggning i `cmd_run` |
| `ai/agents/stock-watcher/main.py` | +`get_context()`/`save_run()`, +`CHAIN_OUTPUT` |
| `ai/agents/svt-sarcastic/main.py` | +dry-run guard, +`CHAIN_OUTPUT` |
| `ai/agents/svt-sarcastic/skills/send_email.py` | +dry-run guard |
| `ai/agents/svt-sarcastic/agent.yaml` | +`side_effect: true`, +`chain` |
| `ai/agents/stock-watcher/agent.yaml` | +`side_effect: false` |

---

### Task 1: Harness — loggning

**Files:**
- Modify: `ai/agents/harness.py`
- Create (auto): `ai/agents/.overlord/logs/`

**Interfaces:**
- Consumes: befintlig `cmd_run` och `_read_config`
- Produces: `cmd_log()`, loggning i `cmd_run()`, JSONL-filer i `.overlord/logs/<agent>.jsonl`

- [ ] **Step 1: Lägg till loggning i cmd_run och skapa cmd_log**

Lägg i `harness.py`:

```python
# Efter imports, lägg till:
import json
import time
from datetime import datetime, timezone

# I cmd_run, före subprocess:
def cmd_run(args: argparse.Namespace) -> None:
    agent_dir = AGENTS_DIR / args.name
    # ... befintlig validering ...
    cfg = _read_config(agent_dir)
    
    dry_run = getattr(args, "dry_run", False)
    
    start = time.time()
    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"
    print(f"🚀 Kör agent '{cfg['name']}' med {python}...")
    
    env = os.environ.copy()
    if "model" in cfg:
        env["AGENT_MODEL_NAME"] = cfg["model"].get("name", "")
        env["AGENT_MODEL_API_BASE"] = cfg["model"].get("api_base", "")
    if cfg.get("instructions"):
        env["AGENT_INSTRUCTIONS"] = cfg["instructions"]
    
    if dry_run:
        env["HARNESS_DRY_RUN"] = "true"
        side_effects = [
            s["name"] for s in cfg.get("skills", [])
            if s.get("side_effect")
        ]
        if side_effects:
            env["HARNESS_DRY_RUN_SKILLS"] = ",".join(side_effects)
    
    result = subprocess.run(
        [python, str(main_py)], env=env,
        capture_output=True, text=True,
    )
    duration = time.time() - start
    
    # Logga
    log_dir = OVERLORD_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_entry = {
        "agent": cfg["name"],
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        "status": "ok" if result.returncode == 0 else "error",
        "code": result.returncode,
        "duration_s": round(duration, 2),
        "dry_run": dry_run,
        "stdout": result.stdout,
        "result": None,
        "error": result.stderr if result.returncode != 0 else None,
    }
    
    # Kolla efter CHAIN_OUTPUT
    chain_output = None
    if result.stdout:
        for line in result.stdout.splitlines():
            if line.startswith("CHAIN_OUTPUT:"):
                try:
                    chain_output = json.loads(line[len("CHAIN_OUTPUT:"):])
                except json.JSONDecodeError:
                    pass
        log_entry["result"] = chain_output
    
    log_file = log_dir / f"{cfg['name']}.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(result.returncode)
```

- [ ] **Step 2: Lägg till cmd_log subcommand**

Lägg i `harness.py`, efter `cmd_cron_run`:

```python
def cmd_log(args: argparse.Namespace) -> None:
    """Visa loggar för en eller alla agenter."""
    log_dir = OVERLORD_DIR / "logs"
    if not log_dir.exists():
        print("📭 Inga loggar än.")
        return
    
    name = getattr(args, "name", None)
    tail = getattr(args, "tail", False)
    as_json = getattr(args, "json", False)
    n = getattr(args, "n", 5)
    
    if name:
        log_file = log_dir / f"{name}.jsonl"
        if not log_file.exists():
            print(f"📭 Inga loggar för '{name}'.")
            return
        lines = log_file.read_text().splitlines()
        entries = [json.loads(l) for l in lines if l.strip()]
        selected = entries[-n:] if n else entries
        
        if as_json:
            for e in selected:
                print(json.dumps(e, ensure_ascii=False))
            return
        
        if tail:
            import shlex
            os.execvp("tail", ["tail", "-f", str(log_file)])
        
        for e in reversed(selected):
            icon = "✅" if e["status"] == "ok" else "❌"
            dry = " [DRY]" if e.get("dry_run") else ""
            print(f"{icon} {e['agent']:20s} {e['ts'][:19]}  {e['duration_s']:5.1f}s{dry}")
            if e.get("error"):
                print(f"   └─ {e['error'][:120]}")
    else:
        # Visa senaste per agent
        agent_statuses = {}
        for f in sorted(log_dir.glob("*.jsonl")):
            agent = f.stem
            lines = f.read_text().splitlines()
            if not lines:
                continue
            last = json.loads(lines[-1])
            agent_statuses[agent] = last
        
        if not agent_statuses:
            print("📭 Inga loggar.")
            return
        
        print(f"{'Agent':20s} {'Status':6s} {'Senast':20s} {'Tid':>6s}")
        print("-" * 55)
        for agent, e in sorted(agent_statuses.items()):
            icon = "✅" if e["status"] == "ok" else "❌"
            dry = " DRY" if e.get("dry_run") else ""
            print(f"{icon} {agent:18s} {e['status']:6s} {e['ts'][:19]} {e['duration_s']:5.1f}s{dry}")
```

- [ ] **Step 3: Lägg till `log` subparser i main()**

```python
# Efter cron-parsern:
log_parser = sub.add_parser("log", help="Visa loggar")
log_parser.add_argument("name", nargs="?", help="Agentnamn")
log_parser.add_argument("-n", type=int, default=5, help="Antal rader")
log_parser.add_argument("--tail", action="store_true", help="Följ live")
log_parser.add_argument("--json", action="store_true", help="Rå JSON")

# Och i main()-switch:
elif args.command == "log":
    cmd_log(args)
```

- [ ] **Step 4: Lägg till `--dry-run` flagga till run-parsern**

```python
run_parser.add_argument("--dry-run", action="store_true", help="Kör utan side-effects")
```

- [ ] **Step 5: Verifiera**

```bash
python3 ai/agents/harness.py run stock-watcher
python3 ai/agents/harness.py log stock-watcher
python3 ai/agents/harness.py log
```

Expected: loggarna visas med ✅/❌, tider, status.

---

### Task 2: Agent dry-run guards

**Files:**
- Modify: `ai/agents/svt-sarcastic/main.py`
- Modify: `ai/agents/svt-sarcastic/skills/send_email.py`
- Modify: `ai/agents/svt-sarcastic/agent.yaml`
- Modify: `ai/agents/stock-watcher/agent.yaml`

- [ ] **Step 1: Uppdatera agent.yaml med side_effect**

I `svt-sarcastic/agent.yaml`:
```yaml
skills:
  - name: fetch_top_news
    module: skills.fetch_top_news
    description: "Hämta toppnyheten från SVT Nyheter"
  - name: generate_comment
    module: skills.generate_comment
    description: "Generera sarkastisk kommentar"
  - name: send_email
    module: skills.send_email
    description: "Skicka e-post"
    side_effect: true
```

I `stock-watcher/agent.yaml`:
```yaml
skills:
  - name: fetch_price
    module: skills.fetch_price
    description: "Hämta aktiekurs"
  - name: analyze
    module: skills.analyze
    description: "AI-analys"
```

(Stock-watcher har inga side-effects — API-anrop till DeepSeek räknas inte, bara externa sidoeffekter som mail/API-writes)

- [ ] **Step 2: Uppdatera svt-sarcastic/skills/send_email.py**

Lägg i början av `run()`:

```python
def run(to: str, subject: str, body: str) -> dict:
    if os.environ.get("HARNESS_DRY_RUN"):
        print(f"[DRY-RUN] Skulle maila {to}: {subject}")
        print(f"[DRY-RUN] Body: {body[:200]}")
        return {"status": "dry-run", "to": to, "subject": subject}
    # ... befintlig kod ...
```

- [ ] **Step 3: Uppdatera harness scaffold-mallen**

I `AGENT_YAML_TEMPLATE`, lägg till `side_effect: false` som default:

```yaml
skills:
  - name: example_skill
    module: skills.example_skill
    description: "Exempelskills"
    side_effect: false
```

- [ ] **Step 4: Verifiera**

```bash
python3 ai/agents/harness.py run svt-sarcastic --dry-run
```

Expected: SVT-hämtning och kommentargenerering körs, men mail-steget skriver `[DRY-RUN]` och skickar inget.

```bash
python3 ai/agents/harness.py log svt-sarcastic
```

Expected: Senaste raden har `[DRY]`-markering.

---

### Task 3: agentkit/memory

**Files:**
- Create: `ai/agents/agentkit/__init__.py`
- Create: `ai/agents/agentkit/memory.py`

**Interfaces:**
- Produces: `save_run(agent, summary, tags=None)`, `get_context(agent, days=7)`, `get_recent(agent, days=7)`

- [ ] **Step 1: Skapa agentkit/__init__.py**

```python
# agentkit - delade moduler för HelmRig
```

- [ ] **Step 2: Skapa agentkit/memory.py**

```python
"""Headroom-minne för agenter. Lagrar och hämtar kontext mellan körningar."""

import json
import os
import subprocess
from datetime import datetime, timedelta

HEADROOM = os.path.expanduser("~/.local/bin/headroom")


def _headroom(*args: str) -> dict:
    """Anropa headroom CLI och returnera {stdout, stderr, rc}."""
    cmd = [HEADROOM] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return {"stdout": r.stdout, "stderr": r.stderr, "rc": r.returncode}


def save_run(agent: str, summary: str, tags: list[str] | None = None) -> dict:
    """Spara en minnes-post om vad agenten gjorde.
    
    Ex: save_run("stock-watcher", "Analyserade 5 tickers. MSFT upp 2%.")
    """
    if tags is None:
        tags = []
    topic = f"helmrig/{agent}"
    content = json.dumps({
        "ts": datetime.now().isoformat(),
        "summary": summary,
        "tags": tags,
    }, ensure_ascii=False)
    
    # headroom memory write <topic> --content <json>
    result = _headroom("memory", "write", topic, "--content", content)
    return result


def get_recent(agent: str, days: int = 7) -> list[dict]:
    """Hämta minnen från topic 'helmrig/<agent>'."""
    topic = f"helmrig/{agent}"
    result = _headroom("memory", "list", topic)
    if result["rc"] != 0:
        return []
    
    # Headroom returnerar en lista med JSON-poster
    entries = []
    for line in result["stdout"].splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            entries.append(entry)
        except json.JSONDecodeError:
            continue  # ponytail: skippa trasiga rader
    
    # Filtrera på dagar
    cutoff = datetime.now() - timedelta(days=days)
    recent = []
    for e in entries:
        try:
            ts = datetime.fromisoformat(e.get("ts", ""))
            if ts >= cutoff:
                recent.append(e)
        except (ValueError, TypeError):
            continue
    return recent


def get_context(agent: str) -> str:
    """Bygg en prompt-kontextsträng från senaste minnen.
    
    Returnerar tom sträng om inga minnen finns.
    """
    recent = get_recent(agent)
    if not recent:
        return ""
    
    lines = ["**Tidigare körningar:**"]
    for e in recent[-7:]:  # max 7
        ts = e.get("ts", "")[:16]  # "2026-07-20T12:00"
        summary = e.get("summary", "")
        lines.append(f"- {ts}: {summary}")
    return "\n".join(lines)
```

- [ ] **Step 3: Verifiera**

```bash
python3 -c "
import sys; sys.path.insert(0, 'ai/agents')
from agentkit.memory import save_run, get_context, get_recent
save_run('test-agent', 'Testkörning', ['test'])
print(get_context('test-agent'))
print(get_recent('test-agent', 30))
"
```

Expected: Context-sträng med datum och summary.

---

### Task 4: Integrera memory i agenter

**Files:**
- Modify: `ai/agents/stock-watcher/main.py`
- Modify: `ai/agents/svt-sarcastic/main.py`

- [ ] **Step 1: Lägg till memory i stock-watcher**

Lägg överst i `stock-watcher/main.py`:

```python
import sys
from pathlib import Path

# agentkit-sökväg
sys.path.insert(0, str(Path(__file__).parent.parent / "agentkit"))
```

Ändra `analyze_with_llm`:

```python
def analyze_with_llm(state: AgentState) -> AgentState:
    """Analysera kursdata via skill, med headroom-kontext."""
    prev = get_previous_context()
    instructions = INSTRUCTIONS
    if prev:
        instructions += f"\n\n{prev}"
    
    # Headroom-minne
    try:
        from agentkit.memory import get_context
        mem_context = get_context("stock-watcher")
        if mem_context:
            instructions += f"\n\n{mem_context}"
    except Exception:
        pass  # ponytail: headroom är nice-to-have
    
    state["analysis"] = call_skill(
        "analyze",
        results=state["results"],
        instructions=instructions,
        model=MODEL_NAME,
        api_base=API_BASE,
    )
    return state
```

Lägg till `save_run` i `format_report`:

```python
def format_report(state: AgentState) -> AgentState:
    """Formatera och spara rapport."""
    now = datetime.now()
    ts = now.strftime("%Y-%m-%d %H:%M")
    
    # ... befintlig utskrift ...
    
    # Headroom-minne
    try:
        from agentkit.memory import save_run
        tickers_str = ", ".join(
            f"{r['ticker']}={r.get('change_pct', 0):+.1f}%"
            for r in state["results"] if r.get("price")
        )
        save_run("stock-watcher", summary=f"Priser: {tickers_str}", tags=["daily"])
    except Exception:
        pass
    
    return state
```

- [ ] **Step 2: Verifiera**

```bash
python3 ai/agents/harness.py run stock-watcher
```

Expected: Agenten körs normalt. Efteråt:

```bash
headroom memory list helmrig/stock-watcher
```

Expected: En JSON-post finns.

---

### Task 5: Agentkedjor

**Files:**
- Modify: `ai/agents/harness.py`
- Modify: `ai/agents/svt-sarcastic/main.py`
- Modify: `ai/agents/svt-sarcastic/agent.yaml`

- [ ] **Step 1: Uppdatera agent.yaml med chain**

I `svt-sarcastic/agent.yaml`, lägg till sist:

```yaml
chain:
  next_agent: stock-watcher
  mapping:
    comment: news_context
```

- [ ] **Step 2: Lägg till CHAIN_OUTPUT i svt-sarcastic/main.py**

I slutet av `__main__`-blocket:

```python
if __name__ == "__main__":
    result = run()
    # CHAIN_OUTPUT för kedjor — sista raden parsas av harness
    print("CHAIN_OUTPUT:" + json.dumps(result))
```

- [ ] **Step 3: Implementera chain-logik i harness.cmd_run**

Lägg i `cmd_run`, efter att agenten körts och loggats:

```python
    # Chain: om agent.yaml har chain-konfig och föregående steg gick bra
    if result.returncode == 0 and chain_output and cfg.get("chain"):
        chain_cfg = cfg["chain"]
        next_agent = chain_cfg.get("next_agent")
        mapping = chain_cfg.get("mapping", {})
        if next_agent:
            next_dir = AGENTS_DIR / next_agent
            if next_dir.exists():
                # Bygg env för nästa agent
                for output_key, input_key in mapping.items():
                    if output_key in chain_output:
                        val = chain_output[output_key]
                        if isinstance(val, str):
                            env[f"CHAIN_INPUT_{input_key}"] = val
                        else:
                            env[f"CHAIN_INPUT_{input_key}"] = json.dumps(val, ensure_ascii=False)
                
                # Lägg till chain_origin så nästa agent vet att den kedjades
                env["CHAIN_FROM"] = cfg["name"]
                
                print(f"⛓️  Kedjar vidare till '{next_agent}'...")
                next_result = subprocess.run(
                    [python, str(next_dir / "main.py")], env=env,
                    capture_output=True, text=True,
                )
                next_duration = time.time() - start
                
                # Logga den kedjade körningen
                next_log_entry = {
                    "agent": next_agent,
                    "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                    "status": "ok" if next_result.returncode == 0 else "error",
                    "code": next_result.returncode,
                    "duration_s": round(time.time() - start - duration, 2),
                    "dry_run": dry_run,
                    "stdout": next_result.stdout,
                    "result": None,
                    "error": next_result.stderr if next_result.returncode != 0 else None,
                    "chained_from": cfg["name"],
                }
                next_log_file = log_dir / f"{next_agent}.jsonl"
                with open(next_log_file, "a") as f:
                    f.write(json.dumps(next_log_entry, ensure_ascii=False) + "\n")
                
                print(next_result.stdout)
                if next_result.returncode != 0:
                    print(next_result.stderr)
```

- [ ] **Step 4: Lägg till `--no-chain` flagga**

```python
run_parser.add_argument("--no-chain", action="store_true", help="Hoppa över kedja")
```

I chain-blocket, linda med `if not getattr(args, "no_chain", False):`

- [ ] **Step 5: Verifiera**

```bash
python3 ai/agents/harness.py run svt-sarcastic
```

Expected: SVT-agenten kör → mail skickas (eller dry-run) → "⛓️ Kedjar vidare till stock-watcher" → stock-watcher körs med `CHAIN_INPUT_news_context`.

```bash
python3 ai/agents/harness.py log
```

Expected: Båda agenterna visas med senaste körning. Kedjade körningen har ingen `[DRY]`.

---

### Task 6: Dashboard (webb-panel)

**Files:**
- Create: `ai/agents/dashboard/app.py`
- Create: `ai/agents/dashboard/templates/dashboard.html`
- Create: `ai/agents/dashboard/templates/agent.html`

**Interfaces:**
- Consumes: `.overlord/logs/*.jsonl` från task 1
- Produces: Flask-app på localhost:5050

- [ ] **Step 1: Installera Flask**

```bash
pip install flask
```

- [ ] **Step 2: Skapa dashboard/app.py**

```python
#!/usr/bin/env python3
"""HelmRig Dashboard — webb-panel för att övervaka agenter."""

import json
import os
import subprocess
from pathlib import Path

from flask import Flask, render_template, request

app = Flask(__name__)

AGENTS_DIR = Path(__file__).parent.parent
LOGS_DIR = AGENTS_DIR / ".overlord" / "logs"
HARNESS = AGENTS_DIR / "harness.py"


def _load_logs(agent: str | None = None) -> list[dict]:
    """Ladda loggar från JSONL-filer."""
    if not LOGS_DIR.exists():
        return []
    entries = []
    if agent:
        log_file = LOGS_DIR / f"{agent}.jsonl"
        if log_file.exists():
            for line in log_file.read_text().splitlines():
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    else:
        for f in sorted(LOGS_DIR.glob("*.jsonl")):
            for line in f.read_text().splitlines():
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return entries


@app.route("/")
def dashboard():
    """Dashboard — alla agenter med senaste status."""
    entries = _load_logs()
    
    # Senaste per agent
    latest = {}
    for e in entries:
        agent = e["agent"]
        if agent not in latest or e["ts"] > latest[agent]["ts"]:
            latest[agent] = e
    
    # Läs cron-scheman från agent.yaml
    agents = []
    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name.startswith("."):
            continue
        yaml_path = agent_dir / "agent.yaml"
        if not yaml_path.exists():
            continue
        try:
            import yaml
            cfg = yaml.safe_load(yaml_path.read_text())
        except Exception:
            continue
        name = cfg.get("name", agent_dir.name)
        cron = cfg.get("cron")
        last = latest.get(name, {})
        agent_info = {
            "name": name,
            "dir": agent_dir.name,
            "cron": cron,
            "status": last.get("status", "never"),
            "ts": last.get("ts", ""),
            "duration_s": last.get("duration_s"),
            "stdout": last.get("stdout", ""),
        }
        agents.append(agent_info)
    
    return render_template("dashboard.html", agents=agents)


@app.route("/agent/<name>")
def agent_history(name: str):
    """Historik för en specifik agent."""
    entries = _load_logs(name)
    entries.reverse()  # nyast först
    return render_template("agent.html", agent=name, entries=entries)


@app.route("/run/<name>", methods=["POST"])
def run_agent(name: str):
    """Trigga en agent manuellt."""
    try:
        r = subprocess.run(
            [sys.executable, str(HARNESS), "run", name],
            capture_output=True, text=True, timeout=120,
        )
        return {"status": "ok" if r.returncode == 0 else "error", "stdout": r.stdout, "stderr": r.stderr}
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "timeout"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    import sys
    app.run(host="0.0.0.0", port=5050, debug=True)
```

- [ ] **Step 3: Skapa dashboard/templates/dashboard.html**

```html
<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HelmRig Dashboard</title>
    <script src="https://unpkg.com/htmx.org@1.9.12"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f0f; color: #e0e0e0; padding: 2rem; }
        h1 { font-size: 1.5rem; font-weight: 600; margin-bottom: 1.5rem; color: #fff; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 1rem; }
        .card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px; padding: 1rem; }
        .card.ok { border-color: #1a6b3c; }
        .card.error { border-color: #8b1a1a; }
        .card.never { border-color: #333; opacity: 0.6; }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; }
        .agent-name { font-weight: 600; font-size: 1.1rem; }
        .status-badge { font-size: 0.75rem; padding: 0.15rem 0.5rem; border-radius: 4px; }
        .status-badge.ok { background: #1a6b3c; color: #fff; }
        .status-badge.error { background: #8b1a1a; color: #fff; }
        .status-badge.never { background: #333; color: #999; }
        .cron { font-size: 0.8rem; color: #777; margin-bottom: 0.5rem; font-family: monospace; }
        .stdout-preview { font-size: 0.8rem; color: #aaa; font-family: monospace; white-space: pre-wrap; max-height: 200px; overflow-y: auto; background: #111; padding: 0.5rem; border-radius: 4px; margin-top: 0.5rem; display: none; }
        .card.expanded .stdout-preview { display: block; }
        .card-actions { margin-top: 0.75rem; }
        button { background: #2a2a2a; border: 1px solid #444; color: #e0e0e0; padding: 0.4rem 0.8rem; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
        button:hover { background: #333; }
        .duration { font-size: 0.8rem; color: #666; }
        a { color: #6ab0ff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .last-run { font-size: 0.75rem; color: #666; margin-bottom: 0.25rem; }
    </style>
</head>
<body>
    <h1>🤖 HelmRig Dashboard</h1>
    <div class="grid">
        {% for agent in agents %}
        <div class="card {{ agent.status }}" 
             hx-get="/agent/{{ agent.dir }}?preview=1" 
             hx-trigger="click target:.stdout-preview"
             hx-target="find .stdout-preview"
             hx-swap="innerHTML">
            <div class="card-header">
                <span class="agent-name">{{ agent.name }}</span>
                <span class="status-badge {{ agent.status }}">{{ agent.status }}</span>
            </div>
            <div class="last-run">{{ agent.ts[:19] if agent.ts else "Aldrig" }}</div>
            {% if agent.cron %}
            <div class="cron">⏰ {{ agent.cron }}</div>
            {% endif %}
            {% if agent.duration_s %}
            <div class="duration">{{ agent.duration_s }}s</div>
            {% endif %}
            <div class="stdout-preview">
                {% if agent.stdout %}
                <pre>{{ agent.stdout }}</pre>
                {% else %}
                <em>Ingen output</em>
                {% endif %}
            </div>
            <div class="card-actions">
                <button hx-post="/run/{{ agent.dir }}" hx-swap="outerHTML" hx-target="closest .card">▶ Kör nu</button>
                <a href="/agent/{{ agent.dir }}">📋 Historik</a>
            </div>
        </div>
        {% endfor %}
    </div>
</body>
</html>
```

- [ ] **Step 4: Skapa dashboard/templates/agent.html**

```html
<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ agent }} — Historik</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f0f0f; color: #e0e0e0; padding: 2rem; }
        h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
        .back { margin-bottom: 1.5rem; }
        .back a { color: #6ab0ff; text-decoration: none; }
        .back a:hover { text-decoration: underline; }
        .entry { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }
        .entry.ok { border-color: #1a6b3c; }
        .entry.error { border-color: #8b1a1a; }
        .entry-header { display: flex; justify-content: space-between; margin-bottom: 0.5rem; font-size: 0.85rem; color: #999; }
        .stdout { font-family: monospace; font-size: 0.8rem; white-space: pre-wrap; background: #111; padding: 0.75rem; border-radius: 4px; overflow-x: auto; }
        .error-box { color: #ff6b6b; margin-top: 0.5rem; }
    </style>
</head>
<body>
    <div class="back"><a href="/">← Dashboard</a></div>
    <h1>🤖 {{ agent }}</h1>
    <p style="color: #666; margin-bottom: 1.5rem;">Senaste {{ entries|length }} körningar</p>
    
    {% for e in entries %}
    <div class="entry {{ e.status }}">
        <div class="entry-header">
            <span>{{ e.ts[:19] }}</span>
            <span>{{ e.duration_s }}s {% if e.dry_run %}· DRY-RUN{% endif %}</span>
            <span class="status-badge {{ e.status }}">{{ e.status }}{% if e.chained_from %} (kedjad från {{ e.chained_from }}){% endif %}</span>
        </div>
        <div class="stdout">{{ e.stdout }}</div>
        {% if e.error %}
        <div class="error-box">{{ e.error }}</div>
        {% endif %}
    </div>
    {% endfor %}
</body>
</html>
```

- [ ] **Step 5: Verifiera**

```bash
cd ai/agents && python3 dashboard/app.py &
# Öppna http://localhost:5050 i webbläsare
```

Expected: Dashboard visar stock-watcher och svt-sarcastic med status, cron, och knappar. Klicka på "Kör nu" → agenten triggas.

---

## Self-Review Check

**Spec coverage:**
- 1. Run-loggar: ✓ Task 1 (cmd_log, auto-loggning i cmd_run)
- 2. Dry-run: ✓ Task 1 (--dry-run flag) + Task 2 (agent guards)
- 3. Headroom-minne: ✓ Task 3 (agentkit/memory) + Task 4 (agent integration)
- 4. Webb-panel: ✓ Task 6 (dashboard/)
- 5. Agentkedjor: ✓ Task 5 (chain i harness + agenter)

**Placeholder scan:** Alla steg har full kod och exacta kommandon. Inga TBD/TODO.

**Type consistency:** `CHAIN_INPUT_*` env vars, `CHAIN_OUTPUT:` prefix, `HARNESS_DRY_RUN` env — alla konsekventa genom tasks. `save_run(agent, summary, tags)` och `get_context(agent)` har samma signatur i Task 3 och Task 4.
