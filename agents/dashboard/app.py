#!/usr/bin/env python3
"""HelmRig Dashboard — Analytics & Performance Dashboard."""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

import sys
import yaml
from flask import Flask, Response, abort, render_template, request, stream_with_context

# Se till att agents/-katalogen är i sys.path för agentkit-imports
_agents_dir = Path(__file__).parent.parent
if str(_agents_dir) not in sys.path:
    sys.path.insert(0, str(_agents_dir))

app = Flask(__name__)

# Registrera API Gateway + Webhook blueprints
from agentkit.api_gateway import api_bp
from agentkit.webhook import webhook_bp
app.register_blueprint(api_bp)
app.register_blueprint(webhook_bp)

AGENTS_DIR = Path(__file__).parent.parent
LOGS_DIR = AGENTS_DIR / ".overlord" / "logs"
AUDIT_LOG = AGENTS_DIR / ".overlord" / "audit.log"
HARNESS = AGENTS_DIR / "harness.py"
VENV_PYTHON = AGENTS_DIR.parent / ".venv" / "bin" / "python3"

# Ladda .env från projektroten om den inte redan är laddad
_env_path = AGENTS_DIR.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN")


def require_auth(f):
    """Decorator: kräver ?token=... om DASHBOARD_TOKEN är satt."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if DASHBOARD_TOKEN:
            token = request.args.get("token") or request.headers.get("X-Auth-Token")
            if token != DASHBOARD_TOKEN:
                abort(401, description="Unauthorized — ange ?token=...")
        return f(*args, **kwargs)
    return decorated


def _log_audit(action: str, detail: str = ""):
    """Skriv audit-log för dashboard-actions."""
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "detail": detail,
        "remote": request.remote_addr or "",
    }
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _load_jsonl_safe(path: Path) -> list[dict]:
    entries = []
    for line in path.read_text().splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def _load_logs(agent: str | None = None) -> list[dict]:
    if not LOGS_DIR.exists():
        return []
    entries = []
    if agent:
        log_file = LOGS_DIR / f"{agent}.jsonl"
        if log_file.exists():
            entries = _load_jsonl_safe(log_file)
    else:
        for f in sorted(LOGS_DIR.glob("*.jsonl")):
            entries.extend(_load_jsonl_safe(f))
    return entries


# ── Cron matching (samma logik som overlord.py) ──────────────────────

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


def _cron_matches(expr: str, dt: datetime) -> bool:
    fields = expr.strip().split()
    if len(fields) != 5:
        return False
    minute, hour, dom, month, dow = fields
    return (
        _cron_field_matches(minute, dt.minute)
        and _cron_field_matches(hour, dt.hour)
        and _cron_field_matches(dom, dt.day)
        and _cron_field_matches(month, dt.month)
        and _cron_field_matches(dow, dt.weekday())
    )


def _next_cron_run(expr: str, from_dt: datetime | None = None) -> datetime | None:
    """Hitta nästa datetime som matchar cron-uttryck (sök upp till 7 dagar)."""
    if not expr or not expr.strip():
        return None
    now = from_dt or datetime.now()
    for i in range(1, 10081):
        dt = now + timedelta(minutes=i)
        if _cron_matches(expr, dt):
            return dt
    return None


# ── Analytics engine ─────────────────────────────────────────────────

def _compute_stats():
    """Beräkna all analytics-data för dashboarden."""
    logs = _load_logs()
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    yesterday_dt = now - timedelta(hours=24)
    yesterday_str = yesterday_dt.strftime("%Y-%m-%dT%H:%M:%S")

    latest = {}  # agent → senaste entry
    tokens_total = 0
    tokens_today = 0
    tokens_yesterday = 0
    tokens_by_day: dict[str, int] = {}
    total_duration = 0.0
    total_runs = len(logs)
    active_24h: set[str] = set()

    for e in logs:
        agent = e["agent"]
        ts = e.get("ts", "")
        tokens = e.get("tokens") or 0
        dur = e.get("duration_s") or 0
        tokens_total += tokens
        total_duration += dur

        day = ts[:10] if len(ts) >= 10 else ""
        if day:
            tokens_by_day[day] = tokens_by_day.get(day, 0) + tokens
            if day == today:
                tokens_today += tokens
            elif day == (now - timedelta(days=1)).strftime("%Y-%m-%d"):
                tokens_yesterday += tokens

        if ts >= yesterday_str:
            active_24h.add(agent)

        if agent not in latest or ts > latest[agent]["ts"]:
            latest[agent] = e

    # Senaste 7 dagarna
    days_data = []
    for i in range(6, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        day_logs = [e for e in logs if e.get("ts", "")[:10] == d]
        days_data.append({
            "day": d[-5:],
            "tokens": tokens_by_day.get(d, 0),
            "runs": len(day_logs),
        })

    ok_runs = sum(1 for e in logs if e.get("status") == "ok")
    error_runs = sum(1 for e in logs if e.get("status") == "error")
    success_rate = round(ok_runs / total_runs * 100) if total_runs else 100

    # Samla agenter med config + analys
    agents = []
    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name.startswith("."):
            continue
        yaml_path = agent_dir / "agent.yaml"
        if not yaml_path.exists():
            continue
        try:
            cfg = yaml.safe_load(yaml_path.read_text())
        except Exception:
            continue
        name = cfg.get("name", agent_dir.name)
        cron = cfg.get("cron")
        model = cfg.get("model", {})
        last = latest.get(name, {})
        next_run = _next_cron_run(cron) if cron else None

        agent_logs = [e for e in logs if e.get("agent") == name]
        agent_tokens = sum(e.get("tokens") or 0 for e in agent_logs)
        agent_ok = sum(1 for e in agent_logs if e.get("status") == "ok")
        agent_total = len(agent_logs)
        agent_success = round(agent_ok / agent_total * 100) if agent_total else 0

        agents.append({
            "name": name,
            "dir": agent_dir.name,
            "status": last.get("status", "never"),
            "ts": last.get("ts", ""),
            "duration_s": last.get("duration_s"),
            "tokens": agent_tokens,
            "model": f"{model.get('provider', '?')}/{model.get('name', '?')}",
            "cron": cron,
            "next_run": next_run.strftime("%Y-%m-%dT%H:%M:%S") if next_run else None,
            "total_runs": agent_total,
            "success_rate": agent_success,
        })

    # Overlord-status
    overlord_pid = AGENTS_DIR / ".overlord" / "overlord.pid"
    overlord_alive = False
    if overlord_pid.exists():
        try:
            pid = int(overlord_pid.read_text().strip())
            os.kill(pid, 0)
            overlord_alive = True
        except (ProcessLookupError, ValueError, OSError):
            pass

    return {
        "tokens_today": tokens_today,
        "tokens_yesterday": tokens_yesterday,
        "tokens_total": tokens_total,
        "tokens_by_day": days_data,
        "total_runs": total_runs,
        "active_agents": len(active_24h),
        "agents": agents,
        "avg_duration": round(total_duration / total_runs, 1) if total_runs else 0,
        "ok_runs": ok_runs,
        "error_runs": error_runs,
        "success_rate": success_rate,
        "overlord_alive": overlord_alive,
        "agent_count": len(agents),
        "top_token_agent": max(agents, key=lambda a: a["tokens"])["name"] if agents else "-",
    }


# ── API endpoints ──────────────────────────────────────────────────────

@app.route("/health")
def health():
    stats = _compute_stats()
    return {
        "status": "ok",
        "overlord": "alive" if stats["overlord_alive"] else "stopped",
        "agents_count": stats["agent_count"],
        "total_runs": stats["total_runs"],
        "tokens_total": stats["tokens_total"],
    }


@app.route("/metrics")
def metrics():
    stats = _compute_stats()
    return Response(
        f"# HELP agent_runs_total Total agent runs\n"
        f"# TYPE agent_runs_total counter\n"
        f"agent_runs_total {stats['total_runs']}\n"
        f"# HELP agent_runs_ok Successful agent runs\n"
        f"agent_runs_ok {stats['ok_runs']}\n"
        f"# HELP agent_runs_error Failed agent runs\n"
        f"agent_runs_error {stats['error_runs']}\n"
        f"# HELP agent_tokens_total Total tokens consumed\n"
        f"agent_tokens_total {stats['tokens_total']}\n"
        f"# HELP agent_count Number of agents\n"
        f"agent_count {stats['agent_count']}\n",
        mimetype="text/plain",
    )


# ── SSE: realtidsström av loggar ──────────────────────────────────────

@app.route("/events")
@require_auth
def sse_events():
    def generate():
        known_lines: dict[str, str] = {}
        while True:
            for f in sorted(LOGS_DIR.glob("*.jsonl")):
                agent = f.stem
                lines = f.read_text().splitlines()
                last_line = lines[-1] if lines else ""
                if last_line and last_line != known_lines.get(agent):
                    known_lines[agent] = last_line
                    try:
                        e = json.loads(last_line)
                        yield f"data: {json.dumps(e)}\n\n"
                    except json.JSONDecodeError:
                        pass
            time.sleep(3)
    return Response(stream_with_context(generate()), mimetype="text/event-stream")


# ── Dashboard route ────────────────────────────────────────────────────

@app.route("/")
@require_auth
def dashboard():
    stats = _compute_stats()
    return render_template("dashboard.html", **stats)


@app.route("/agent/<name>")
@require_auth
def agent_history(name: str):
    entries = _load_logs(name)
    entries.reverse()
    return render_template("agent.html", agent=name, entries=entries)


@app.route("/run/<name>", methods=["POST"])
@require_auth
def run_agent(name: str):
    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"
    try:
        r = subprocess.run(
            [python, str(HARNESS), "run", name],
            capture_output=True, text=True, timeout=120,
        )
        _log_audit("run", f"agent={name}, exit={r.returncode}")
        return {"status": "ok" if r.returncode == 0 else "error", "stdout": r.stdout, "stderr": r.stderr}
    except subprocess.TimeoutExpired:
        _log_audit("run_timeout", f"agent={name}")
        return {"status": "error", "error": "timeout"}
    except Exception as e:
        _log_audit("run_error", f"agent={name}, error={e}")
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
