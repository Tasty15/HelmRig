#!/usr/bin/env python3
"""Overlord daemon — cron scheduler + health checks + log rotation."""

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

OVERLORD_DIR = Path(__file__).parent
AGENTS_DIR = OVERLORD_DIR.parent
LOGS_DIR = OVERLORD_DIR / "logs"
LOG_FILE = OVERLORD_DIR / "watchdog.log"
PID_FILE = OVERLORD_DIR / "overlord.pid"
VENV_PYTHON = AGENTS_DIR.parent / ".venv" / "bin" / "python3"

sys.path.insert(0, str(AGENTS_DIR))
from harness import _list_agents, _read_config as _read_agent_config  # noqa: E402

RUNNING = True
AGENT_LOCKS: dict[str, float] = {}  # agent_name → timestamp när den startades


def _log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _rotate_logs(retention_days: int = 30):
    """Ta bort JSONL-loggar äldre än retention_days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_str = cutoff.isoformat()
    for f in LOGS_DIR.glob("*.jsonl"):
        try:
            lines = [l for l in f.read_text().splitlines() if l.strip()]
            if not lines:
                continue
            parsed = []
            for l in lines:
                try:
                    e = json.loads(l)
                    if e.get("ts", "") >= cutoff_str:
                        parsed.append(l)
                except json.JSONDecodeError:
                    parsed.append(l)
            # Behåll minst 10 rader — lägg till senaste från originalfilen om för få
            if len(parsed) < 10:
                seen = set(parsed)
                for l in reversed(lines):
                    if len(parsed) >= 10:
                        break
                    if l not in seen:
                        parsed.insert(0, l)
                        seen.add(l)
            f.write_text("\n".join(parsed) + "\n")
        except Exception:
            pass


def _cron_field_matches(pattern: str, value: int) -> bool:
    for part in pattern.split(","):
        part = part.strip()
        if part == "*":
            return True
        if "-" in part:
            lo, hi = part.split("-", 1)
            if lo.isdigit() and hi.isdigit() and int(lo) <= value <= int(hi):
                return True
        elif part.isdigit() and int(part) == value:
            return True
    return False


def _cron_matches(expr: str) -> bool:
    fields = expr.strip().split()
    if len(fields) != 5:
        return False
    now = datetime.now()
    minute, hour, dom, month, dow = fields
    if not _cron_field_matches(minute, now.minute):
        return False
    if not _cron_field_matches(hour, now.hour):
        return False
    if not _cron_field_matches(dom, now.day):
        return False
    if not _cron_field_matches(month, now.month):
        return False
    if not _cron_field_matches(dow, now.weekday()):
        return False
    return True


def _run_agent(agent_dir: Path) -> None:
    """Kör en agents main.py — skyddad av PID-lock mot dubbla körningar."""
    agent_name = agent_dir.name
    main_py = agent_dir / "main.py"
    if not main_py.exists():
        _log(f"CRON SKIP {agent_name} — ingen main.py")
        return

    # Concurrency-skydd: kolla om agenten redan körs
    lock_file = OVERLORD_DIR / "locks" / f"{agent_name}.pid"
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    if lock_file.exists():
        try:
            pid = int(lock_file.read_text().strip())
            os.kill(pid, 0)  # Lever PID?
            _log(f"CRON SKIP {agent_name} — körs redan (PID {pid})")
            return
        except (ProcessLookupError, ValueError, OSError):
            lock_file.unlink(missing_ok=True)  # Stale lock

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"
    lock_file.write_text(str(os.getpid()))
    AGENT_LOCKS[agent_name] = time.time()
    _log(f"CRON RUN {agent_name}")

    start = time.time()
    try:
        result = subprocess.run(
            [python, str(main_py)],
            capture_output=True, text=True, timeout=120,
        )
        duration = time.time() - start
        if result.returncode == 0:
            _log(f"CRON OK {agent_name} ({duration:.1f}s)")
        else:
            _log(f"CRON FAIL {agent_name} ({duration:.1f}s): {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        _log(f"CRON FAIL {agent_name} — timeout (120s)")
    finally:
        lock_file.unlink(missing_ok=True)
        AGENT_LOCKS.pop(agent_name, None)


def _load_config() -> dict:
    cfg_path = OVERLORD_DIR / "config.yaml"
    if not cfg_path.exists():
        return {}
    try:
        return yaml.safe_load(cfg_path.read_text()) or {}
    except Exception:
        return {}


def health_check(agent_dir: Path, cfg: dict) -> None:
    agent_name = agent_dir.name
    main_py = agent_dir / "main.py"
    if main_py.exists():
        try:
            compile(main_py.read_text(), str(main_py), "exec")
        except SyntaxError as e:
            _log(f"ERROR {agent_name} — syntaxfel i main.py: {e}")


def _stale_lock_cleanup():
    """Rensa PID-lockar äldre än 2 timmar (process dog utan att rensa)."""
    lock_dir = OVERLORD_DIR / "locks"
    if not lock_dir.exists():
        return
    cutoff = time.time() - 7200
    for f in lock_dir.glob("*.pid"):
        try:
            if f.stat().st_mtime < cutoff:
                pid = int(f.read_text().strip())
                try:
                    os.kill(pid, 0)
                except (ProcessLookupError, OSError):
                    f.unlink(missing_ok=True)
        except Exception:
            f.unlink(missing_ok=True)


def main():
    global RUNNING

    def handle_signal(sig, frame):
        global RUNNING
        _log("Overlord stoppar...")
        RUNNING = False

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    _log("Overlord startad")

    config = _load_config()
    interval = config.get("watchdog", {}).get("interval_s", 60)
    retention = config.get("log_retention_days", 30)
    cron_tracker: dict[str, str] = {}
    rotate_every = max(interval * 60, 3600)  # Rotera loggar max 1 gång/timme
    last_rotate = 0.0

    while RUNNING:
        now = datetime.now()
        now_ts = time.time()
        cron_minute = now.strftime("%Y%m%d%H%M")

        # Log rotation (en gång i timmen)
        if now_ts - last_rotate >= rotate_every:
            _rotate_logs(retention)
            _stale_lock_cleanup()
            last_rotate = now_ts

        # Schemalägg cron-jobb
        to_run = []
        for agent_dir in _list_agents():
            cfg = _read_agent_config(agent_dir) or {}
            agent_name = agent_dir.name
            cron = cfg.get("cron")
            if cron and cron_tracker.get(agent_name) != cron_minute and _cron_matches(cron):
                cron_tracker[agent_name] = cron_minute
                to_run.append(agent_dir)

        # Health checks
        for agent_dir in _list_agents():
            cfg = _read_agent_config(agent_dir) or {}
            health_check(agent_dir, cfg)

        # Kör cron-jobb
        for agent_dir in to_run:
            _run_agent(agent_dir)

        # Vänta
        for _ in range(interval):
            if not RUNNING:
                break
            time.sleep(1)

    _log("Overlord stoppad")


if __name__ == "__main__":
    main()
