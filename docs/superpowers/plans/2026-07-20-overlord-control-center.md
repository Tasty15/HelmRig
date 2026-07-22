# Overlord Control Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bygg ut `.overlord/` till en kontrollcentral med central config, watchdog, hälsokoll och jobbkö.

**Architecture:** Hybrid — config merge i harness, daemon i separat overlord.py, jobbkö som filbaserad mekanism. Agenter är omedvetna om overlord.

**Tech Stack:** Python 3.14, stdlib (json, subprocess, pathlib, yaml, time, signal)

## Global Constraints

- Alla ändringar additiva — befintlig kod ändras minimalt
- config.yaml läses ENDAST av harness, aldrig av agenter
- Merge-regler: override > agent.yaml > defaults
- Watchdog daemon körs som subprocess, PID i `.overlord/overlord.pid`
- Job queue: filbaserad i `.overlord/queue/`, lock via PID-fil
- Inga nya beroenden

---

## File Structure

### Nya filer
| Fil | Ansvar |
|---|---|
| `ai/agents/.overlord/config.yaml` | Central config: defaults, overrides, watchdog/health/queue-inställningar |
| `ai/agents/.overlord/overlord.py` | Daemon: watchdog + health + queue consumer |
| `ai/agents/.overlord/queue/` | Katalog för jobb-filer (skapas automatiskt) |

### Modifierade filer
| Fil | Ändring |
|---|---|
| `ai/agents/harness.py` | +`_load_overlord_config()`, +`cmd_overlord_*`, +`cmd_queue_*`, +queue-koll i cmd_run |

---

### Task 1: Central config + `_load_overlord_config()`

**Files:**
- Create: `ai/agents/.overlord/config.yaml`
- Modify: `ai/agents/harness.py`

**Interfaces:**
- Produces: `_load_overlord_config() -> dict` — anropas av `_read_config()` för merge
- Produces: `.overlord/config.yaml` — YAML med defaults/overrides/watchdog/health/queue

- [ ] **Step 1: Skapa .overlord/config.yaml**

Path: `/home/simon/HelmRig/agents/.overlord/config.yaml`

```yaml
# Overlord central config — defaults och overrides för alla agenter
# Merge-regel: override > agent.yaml > defaults

defaults:
  model:
    provider: deepseek
    name: deepseek-chat
    api_base: https://api.deepseek.com/v1

overrides:
  stock-watcher:
    model:
      name: deepseek-v4-flash

  svt-sarcastic:
    email_to: "grahn.simon@outlook.com"

watchdog:
  enabled: true
  interval_s: 60
  max_restarts: 3

health:
  notify_on_missed_cron: true

queue:
  max_concurrent: 1
```

- [ ] **Step 2: Lägg till `_load_overlord_config()` i harness.py**

I `harness.py`, efter `def _read_config(...)`:

```python
def _load_overlord_config() -> dict:
    """Läs central config från .overlord/config.yaml. Tom dict om ingen config finns."""
    config_path = OVERLORD_DIR / "config.yaml"
    if not config_path.exists():
        return {}
    try:
        return yaml.safe_load(config_path.read_text()) or {}
    except Exception as e:
        print(f"⚠️  config.yaml parse-fel: {e}")
        return {}
```

- [ ] **Step 3: Uppdatera `_read_config` för merge av overlord-config**

Ändra slutet av `_read_config` så den mergar overlord-config:

```python
def _read_config(agent_dir: Path) -> dict | None:
    """Läs och validera agent.yaml, mergea med overlord config."""
    yaml_path = agent_dir / "agent.yaml"
    if not yaml_path.exists():
        print(f"❌ Ingen agent.yaml i {agent_dir}")
        return None
    try:
        cfg = yaml.safe_load(yaml_path.read_text())
    except Exception as e:
        print(f"❌ agent.yaml parse-fel: {e}")
        return None
    if "name" not in cfg:
        print(f"❌ agent.yaml saknar 'name'")
        return None

    # Merge overlord-config
    overlord = _load_overlord_config()
    agent_name = cfg.get("name", agent_dir.name)

    # Applicera defaults
    defaults = overlord.get("defaults", {})
    for key, val in defaults.items():
        if key not in cfg or cfg[key] is None:
            cfg[key] = val
        elif isinstance(val, dict) and isinstance(cfg.get(key), dict):
            # Merge dict-fält (t.ex. model)
            for sub_key, sub_val in val.items():
                if sub_key not in cfg[key]:
                    cfg[key][sub_key] = sub_val

    # Applicera overrides (specifika för denna agent)
    overrides = overlord.get("overrides", {}).get(agent_dir.name, {})
    for key, val in overrides.items():
        cfg[key] = val

    return cfg
```

- [ ] **Step 4: Verifiera**

```bash
python3 -c "
import sys; sys.path.insert(0, '/home/simon/HelmRig/agents')
from harness import _load_overlord_config
c = _load_overlord_config()
print('defaults:', c.get('defaults', {}).get('model', {}).get('name'))
print('watchdog:', c.get('watchdog', {}).get('interval_s'))
"
```

Expected: `deepseek-chat`, `60`.

```bash
python3 /home/simon/HelmRig/agents/harness.py run stock-watcher
```

Expected: Agenten körs som vanligt. Config mergen är transparent.

---

### Task 2: `harness overlord` subcommands

**Files:**
- Modify: `ai/agents/harness.py`

**Interfaces:**
- Consumes: `_load_overlord_config()` från Task 1
- Produces: `cmd_overlord_start()`, `cmd_overlord_stop()`, `cmd_overlord_status()`, `cmd_overlord_logs()`

- [ ] **Step 1: Lägg till `cmd_overlord_start`**

```python
def cmd_overlord_start(args: argparse.Namespace) -> None:
    """Starta overlord.py som bakgrundsprocess."""
    pid_path = OVERLORD_DIR / "overlord.pid"
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)  # Kolla om processen lever
            print(f"⚠️  Overlord körs redan (PID {pid})")
            return
        except (ProcessLookupError, ValueError):
            pid_path.unlink(missing_ok=True)  # Stale PID

    overlord_py = OVERLORD_DIR / "overlord.py"
    if not overlord_py.exists():
        print(f"❌ {overlord_py} finns inte. Skapa först.")
        return

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"
    proc = subprocess.Popen(
        [python, str(overlord_py)],
        stdout=open(OVERLORD_DIR / "watchdog.log", "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    pid_path.write_text(str(proc.pid))
    print(f"✅ Overlord startad (PID {proc.pid})")
```

- [ ] **Step 2: Lägg till `cmd_overlord_stop`**

```python
def cmd_overlord_stop(args: argparse.Namespace) -> None:
    """Stoppa overlord daemon."""
    pid_path = OVERLORD_DIR / "overlord.pid"
    if not pid_path.exists():
        print("⚠️  Overlord körs inte (ingen PID-fil)")
        return
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        pid_path.unlink()
        print(f"✅ Overlord stoppad (PID {pid})")
    except (ProcessLookupError, ValueError, OSError) as e:
        print(f"⚠️  Kunde inte stoppa: {e}")
        pid_path.unlink(missing_ok=True)
```

- [ ] **Step 3: Lägg till `cmd_overlord_status`**

```python
def cmd_overlord_status(args: argparse.Namespace) -> None:
    """Visa overlord-status."""
    pid_path = OVERLORD_DIR / "overlord.pid"
    if not pid_path.exists():
        print("💤 Overlord: stoppad")
        return
    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)
        # Kolla när den startades
        import stat
        mtime = datetime.fromtimestamp(pid_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"✅ Overlord: körs (PID {pid}, startad {mtime})")
    except (ProcessLookupError, ValueError):
        print("💤 Overlord: PID-fil finns men processen är död (stale)")
        pid_path.unlink(missing_ok=True)
```

- [ ] **Step 4: Lägg till `cmd_overlord_logs`**

```python
def cmd_overlord_logs(args: argparse.Namespace) -> None:
    """Visa watchdog.log."""
    log_path = OVERLORD_DIR / "watchdog.log"
    if not log_path.exists():
        print("📭 Inga watchdog-loggar än.")
        return
    tail = getattr(args, "tail", False)
    n = getattr(args, "n", 20)
    
    if tail:
        os.execvp("tail", ["tail", "-f", str(log_path)])
    
    lines = log_path.read_text().splitlines()
    for line in lines[-n:]:
        print(line)
```

- [ ] **Step 5: Lägg till subparser för `overlord` i main()**

I `main()`:

```python
    # overlord
    over_parser = sub.add_parser("overlord", help="Styr overlord daemon")
    over_sub = over_parser.add_subparsers(dest="overlord_command")
    over_sub.add_parser("start", help="Starta overlord")
    over_sub.add_parser("stop", help="Stoppa overlord")
    over_sub.add_parser("status", help="Visa status")
    over_logs = over_sub.add_parser("logs", help="Visa watchdog-loggar")
    over_logs.add_argument("-n", type=int, default=20, help="Antal rader")
    over_logs.add_argument("--tail", action="store_true", help="Följ live")
```

Lägg till i kommandoswitchen:

```python
    elif args.command == "overlord":
        if args.overlord_command == "start":
            cmd_overlord_start(args)
        elif args.overlord_command == "stop":
            cmd_overlord_stop(args)
        elif args.overlord_command == "status":
            cmd_overlord_status(args)
        elif args.overlord_command == "logs":
            cmd_overlord_logs(args)
        else:
            over_parser.print_help()
```

- [ ] **Step 6: Lägg till `import signal` i toppen av harness.py**

```python
import signal
```

- [ ] **Step 7: Verifiera**

```bash
python3 /home/simon/HelmRig/agents/harness.py overlord status
python3 /home/simon/HelmRig/agents/harness.py overlord start  # kommer faila (ingen overlord.py än)
python3 /home/simon/HelmRig/agents/harness.py overlord stop
```

Expected: visas rätt status, start försöker men failar (ingen overlord.py).

---

### Task 3: overlord.py — watchdog + health

**Files:**
- Create: `ai/agents/.overlord/overlord.py`

**Interfaces:**
- Consumes: `.overlord/config.yaml` (via `_load_overlord_config`-liknande funktion)
- Consumes: `.overlord/logs/*.jsonl` (befintlig logg från Task 1)
- Consumes: `*/agent.yaml` (cron-scheman)
- Produces: `.overlord/watchdog.log` (text-logg)
- Produces: `.overlord/queue/` konsumtion (plockar jobb)

- [ ] **Step 1: Skapa overlord.py**

Path: `/home/simon/HelmRig/agents/.overlord/overlord.py`

```python
#!/usr/bin/env python3
"""Overlord daemon — watchdog, health checks, job queue consumer."""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import yaml

OVERLORD_DIR = Path(__file__).parent
AGENTS_DIR = OVERLORD_DIR.parent
LOGS_DIR = OVERLORD_DIR / "logs"
QUEUE_DIR = OVERLORD_DIR / "queue"
LOG_FILE = OVERLORD_DIR / "watchdog.log"
PID_FILE = OVERLORD_DIR / "overlord.pid"
VENV_PYTHON = AGENTS_DIR.parent / ".venv" / "bin" / "python3"

running = True


def _log(msg: str):
    """Skriv tidsstämplad rad till watchdog.log."""
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def _load_config() -> dict:
    """Läs overlord config."""
    cfg_path = OVERLORD_DIR / "config.yaml"
    if not cfg_path.exists():
        return {}
    try:
        return yaml.safe_load(cfg_path.read_text()) or {}
    except Exception:
        return {}


def _list_agents() -> list[Path]:
    """Hitta alla agentkataloger med agent.yaml."""
    agents = []
    for d in sorted(AGENTS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("."):
            continue
        if (d / "agent.yaml").exists():
            agents.append(d)
    return agents


def _read_cfg(agent_dir: Path) -> dict:
    """Läs en agents agent.yaml."""
    try:
        return yaml.safe_load((agent_dir / "agent.yaml").read_text()) or {}
    except Exception:
        return {}


def watchdog_check(agent_dir: Path, cfg: dict, restart_counts: dict) -> None:
    """Kolla om agenten har crashat. Starta om vid behov."""
    agent_name = agent_dir.name
    log_file = LOGS_DIR / f"{agent_name}.jsonl"

    if not log_file.exists():
        return

    # Läs sista log-raden
    lines = log_file.read_text().splitlines()
    if not lines:
        return
    try:
        last = json.loads(lines[-1])
    except (json.JSONDecodeError, IndexError):
        return

    if last.get("status") != "error":
        return

    config = _load_config()
    max_restarts = config.get("watchdog", {}).get("max_restarts", 3)
    now = time.time()

    # Rensa gamla restart-räknare (äldre än 1 timme)
    restart_counts[agent_name] = [
        t for t in restart_counts.get(agent_name, [])
        if now - t < 3600
    ]

    if len(restart_counts[agent_name]) >= max_restarts:
        _log(f"SKIP {agent_name} — max restarts ({max_restarts}) nådd senaste timmen")
        return

    main_py = agent_dir / "main.py"
    if not main_py.exists():
        return

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"
    _log(f"RESTART {agent_name} — exit code {last.get('code', '?')}, restart {len(restart_counts[agent_name]) + 1}/{max_restarts}")
    restart_counts[agent_name].append(now)

    subprocess.run([python, str(main_py)], capture_output=True, text=True, timeout=120)


def health_check(agent_dir: Path, cfg: dict) -> None:
    """Kolla cron och syntax."""
    agent_name = agent_dir.name
    cron = cfg.get("cron")
    if cron:
        # Kolla om senaste körningen är inom cron-fönstret + 10 min
        # Enkel koll: finns det en logg från idag?
        log_file = LOGS_DIR / f"{agent_name}.jsonl"
        if not log_file.exists():
            _log(f"WARN {agent_name} — cron '{cron}' men aldrig körts")
            return
        lines = log_file.read_text().splitlines()
        if not lines:
            return
        try:
            last = json.loads(lines[-1])
            last_ts = last.get("ts", "")
            today = datetime.now().strftime("%Y-%m-%d")
            if not last_ts.startswith(today):
                _log(f"WARN {agent_name} — cron '{cron}' missad (senaste körning {last_ts[:10]})")
        except (json.JSONDecodeError, IndexError):
            pass

    # Syntax-koll
    main_py = agent_dir / "main.py"
    if main_py.exists():
        try:
            compile(main_py.read_text(), str(main_py), "exec")
        except SyntaxError as e:
            _log(f"ERROR {agent_name} — syntaxfel i main.py: {e}")


def process_queue() -> None:
    """Plocka och kör nästa jobb från kön."""
    if not QUEUE_DIR.exists():
        return
    lock_file = QUEUE_DIR / "lock"

    # Kolla om något redan körs
    if lock_file.exists():
        try:
            pid = int(lock_file.read_text().strip())
            os.kill(pid, 0)  # Lever PID?
            return  # Agent körs redan
        except (ProcessLookupError, ValueError):
            lock_file.unlink(missing_ok=True)  # Stale lock

    # Hitta äldsta jobbet
    jobs = sorted(QUEUE_DIR.glob("*.json"))
    if not jobs:
        return

    job = jobs[0]
    try:
        job_data = json.loads(job.read_text())
    except (json.JSONDecodeError, OSError):
        job.unlink(missing_ok=True)
        return

    agent = job_data.get("agent")
    dry_run = job_data.get("dry_run", False)
    agent_dir = AGENTS_DIR / agent

    if not agent_dir.exists():
        _log(f"QUEUE SKIP {agent} — agent finns inte")
        job.unlink()
        return

    main_py = agent_dir / "main.py"
    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"
    env = os.environ.copy()
    if dry_run:
        env["HARNESS_DRY_RUN"] = "true"

    # Sätt lock
    lock_file.write_text(str(os.getpid()))

    _log(f"QUEUE RUN {agent} {'(dry-run)' if dry_run else ''}")
    result = subprocess.run([python, str(main_py)], env=env, capture_output=True, text=True, timeout=120)
    _log(f"QUEUE DONE {agent} — exit {result.returncode}")

    # Rensa lock och jobb
    lock_file.unlink(missing_ok=True)
    job.unlink()


def main():
    global running

    def handle_signal(sig, frame):
        global running
        _log("Overlord stoppar...")
        running = False

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    _log("Overlord startad")

    config = _load_config()
    interval = config.get("watchdog", {}).get("interval_s", 60)
    restart_counts: dict[str, list[float]] = {}

    while running:
        for agent_dir in _list_agents():
            cfg = _read_cfg(agent_dir)
            watchdog_check(agent_dir, cfg, restart_counts)
            health_check(agent_dir, cfg)

        process_queue()

        # Vänta, men kolla running varje sekund
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    _log("Overlord stoppad")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verifiera**

```bash
python3 /home/simon/HelmRig/agents/harness.py overlord start
sleep 3
python3 /home/simon/HelmRig/agents/harness.py overlord status
python3 /home/simon/HelmRig/agents/harness.py overlord logs
python3 /home/simon/HelmRig/agents/harness.py overlord stop
```

Expected: Daemon startar, status visar PID, watchdog.log har "Overlord startad", daemon stoppas.

---

### Task 4: Jobbkö — queue-koll i cmd_run + queue subcommands

**Files:**
- Modify: `ai/agents/harness.py`

**Interfaces:**
- Consumes: `_load_overlord_config()` → `queue.max_concurrent`
- Consumes: `.overlord/queue/` katalog
- Produces: `cmd_queue_list()`, `cmd_queue_flush()`

- [ ] **Step 1: Lägg till queue-koll i cmd_run**

I `cmd_run`, efter validering men innan subprocess, lägg till:

```python
def cmd_run(args: argparse.Namespace) -> None:
    # ... befintlig validering ...
    
    # Kolla jobbkö
    overlord_cfg = _load_overlord_config()
    max_concurrent = overlord_cfg.get("queue", {}).get("max_concurrent", 1)
    if max_concurrent > 0:
        lock_file = OVERLORD_DIR / "queue" / "lock"
        if lock_file.exists():
            try:
                lock_pid = int(lock_file.read_text().strip())
                os.kill(lock_pid, 0)  # Lever PID?
                # Agent körs redan, lägg i kön
                queue_dir = OVERLORD_DIR / "queue"
                queue_dir.mkdir(parents=True, exist_ok=True)
                dry_run = getattr(args, "dry_run", False)
                job = {
                    "agent": cfg["name"],
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "dry_run": dry_run,
                }
                job_file = queue_dir / f"{cfg['name']}-{datetime.now().strftime('%Y%m%dT%H%M%S')}.json"
                job_file.write_text(json.dumps(job, ensure_ascii=False))
                print(f"⏳ Agent '{cfg['name']}' är i kön. Väntar på ledig plats.")
                return
            except (ProcessLookupError, ValueError):
                lock_file.unlink(missing_ok=True)  # Stale lock, kör direkt
    
    # ... resten av cmd_run ...
```

- [ ] **Step 2: Lägg till cmd_queue_list**

```python
def cmd_queue_list(args: argparse.Namespace) -> None:
    """Lista jobb i kön."""
    queue_dir = OVERLORD_DIR / "queue"
    if not queue_dir.exists():
        print("📭 Kön är tom.")
        return
    jobs = sorted(queue_dir.glob("*.json"))
    if not jobs:
        print("📭 Kön är tom.")
        return
    lock_file = queue_dir / "lock"
    running = None
    if lock_file.exists():
        try:
            pid = int(lock_file.read_text().strip())
            os.kill(pid, 0)
            running = pid
        except (ProcessLookupError, ValueError):
            pass
    
    print(f"{'Agent':20s} {'Tid':20s} {'Status':10s}")
    print("-" * 52)
    for j in jobs:
        if j.name == "lock":
            continue
        try:
            data = json.loads(j.read_text())
            agent = data.get("agent", j.stem)
            ts = data.get("ts", "")[:19]
            status = "⏳ väntar"
            if running:
                status = "▶ körs"
            print(f"{agent:20s} {ts:20s} {status}")
        except (json.JSONDecodeError, OSError):
            print(f"{j.stem:20s} {'?':20s} {'❌ trasig':10s}")
```

- [ ] **Step 3: Lägg till cmd_queue_flush**

```python
def cmd_queue_flush(args: argparse.Namespace) -> None:
    """Rensa kön."""
    queue_dir = OVERLORD_DIR / "queue"
    if not queue_dir.exists():
        print("✅ Kön är redan tom.")
        return
    count = 0
    for f in queue_dir.glob("*.json"):
        if f.name == "lock":
            continue
        f.unlink()
        count += 1
    # Rensa lock också om stale
    lock_file = queue_dir / "lock"
    if lock_file.exists():
        try:
            pid = int(lock_file.read_text().strip())
            os.kill(pid, 0)
        except (ProcessLookupError, ValueError):
            lock_file.unlink(missing_ok=True)
    print(f"✅ Kön rensad: {count} jobb borttagna.")
```

- [ ] **Step 4: Lägg till queue subparser i main()**

```python
    # queue
    queue_parser = sub.add_parser("queue", help="Hantera jobbkö")
    queue_sub = queue_parser.add_subparsers(dest="queue_command")
    queue_sub.add_parser("list", help="Lista jobb")
    queue_sub.add_parser("flush", help="Rensa kön")
```

Lägg till i switchen:

```python
    elif args.command == "queue":
        if args.queue_command == "list":
            cmd_queue_list(args)
        elif args.queue_command == "flush":
            cmd_queue_flush(args)
        else:
            queue_parser.print_help()
```

- [ ] **Step 5: Verifiera**

```bash
python3 /home/simon/HelmRig/agents/harness.py queue list
python3 /home/simon/HelmRig/agents/harness.py queue flush
```

Expected: Kön är tom. Skapa ett test-jobb:

```bash
mkdir -p /home/simon/HelmRig/agents/.overlord/queue
echo '{"agent":"stock-watcher","ts":"2026-07-20T12:00:00","dry_run":false}' > /home/simon/HelmRig/agents/.overlord/queue/test.json
python3 /home/simon/HelmRig/agents/harness.py queue list
python3 /home/simon/HelmRig/agents/harness.py queue flush
```

Expected: Jobbet syns i listan, flush rensar.

---

## Self-Review

**Spec coverage:**
1. Central config: ✓ Task 1 (config.yaml + _load_overlord_config + merge i _read_config)
2. Watchdog: ✓ Task 3 (overlord.py watchdog_check + restart)
3. Hälsoövervakning: ✓ Task 3 (health_check cron + syntax)
4. Jobbkö: ✓ Task 3 (process_queue) + Task 4 (queue-koll i cmd_run + commands)
5. harness overlord CLI: ✓ Task 2 (start/stop/status/logs)
6. harness queue CLI: ✓ Task 4 (list/flush)

**Placeholder scan:** All steps contain complete code. No TBD/TODO.

**Type consistency:**
- `_load_overlord_config()` definieras i Task 1, anropas i Task 2 och Task 4 ✓
- `watchdog_check(agent_dir, cfg, restart_counts)` i Task 3, restart_counts är `dict[str, list[float]]` ✓
- QUEUE_DIR, LOGS_DIR, PID_FILE alla konsekventa i Task 3 ✓
- Lock file: `.overlord/queue/lock` i Task 3 och Task 4 ✓
