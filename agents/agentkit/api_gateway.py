"""API Gateway — exponera agenter som REST-endpoints.

Används som Flask Blueprint i dashboarden:
    from agentkit.api_gateway import api_bp
    app.register_blueprint(api_bp)

Endpoints:
    POST /api/run/<agent>   — Kör agent, returnera JSON
    GET  /api/agents        — Lista alla agenter
    GET  /api/agents/<name> — Hämta agent-status
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Blueprint, jsonify, request

api_bp = Blueprint("api", __name__)

AGENTS_DIR = Path(__file__).parent.parent
VENV_PYTHON = AGENTS_DIR.parent / ".venv" / "bin" / "python3"
HARNESS = AGENTS_DIR / "harness.py"
DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN")


def _require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if DASHBOARD_TOKEN:
            token = request.headers.get("Authorization", "").replace("Bearer ", "")
            if not token or token != DASHBOARD_TOKEN:
                return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


@api_bp.route("/api/agents", methods=["GET"])
@_require_auth
def list_agents():
    """Lista alla agenter."""
    from agentkit.api import list_agents
    return jsonify(list_agents())


@api_bp.route("/api/agents/<name>", methods=["GET"])
@_require_auth
def get_agent_status(name: str):
    """Hämta status för en specifik agent."""
    cfg_path = AGENTS_DIR / name / "agent.yaml"
    if not cfg_path.exists():
        return jsonify({"error": "not found"}), 404

    import yaml
    cfg = yaml.safe_load(cfg_path.read_text())

    # Senaste logg
    log_dir = AGENTS_DIR / ".overlord" / "logs"
    last_run = None
    log_file = log_dir / f"{name}.jsonl"
    if log_file.exists():
        for line in log_file.read_text().splitlines():
            if line.strip():
                try:
                    last_run = json.loads(line)
                except json.JSONDecodeError:
                    pass

    return jsonify({
        "name": cfg.get("name", name),
        "description": cfg.get("description", ""),
        "cron": cfg.get("cron"),
        "model": cfg.get("model", {}),
        "skills": len(cfg.get("skills", [])),
        "last_run": last_run,
    })


@api_bp.route("/api/run/<name>", methods=["POST"])
@_require_auth
def run_agent_api(name: str):
    """Kör en agent och returnera resultatet som JSON.

    Body (valfritt):
        {"input": {"key": "value"}, "timeout": 120, "dry_run": false}
    """
    agent_dir = AGENTS_DIR / name
    if not (agent_dir / "main.py").exists():
        return jsonify({"error": f"agent '{name}' not found"}), 404

    data = request.get_json(silent=True) or {}
    inp = data.get("input", {})
    timeout = min(int(data.get("timeout", 120)), 600)  # max 10 min
    dry_run = bool(data.get("dry_run", False))

    # Sätt CHAIN_INPUT_* om input finns
    env = os.environ.copy()
    for key, val in inp.items():
        env[f"CHAIN_INPUT_{key.upper()}"] = str(val)
    if dry_run:
        env["HARNESS_DRY_RUN"] = "true"

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"
    try:
        r = subprocess.run(
            [python, str(HARNESS), "run", name],
            env=env, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": f"timeout ({timeout}s)", "status": "error"}), 504
    except Exception as e:
        return jsonify({"error": str(e)[:300], "status": "error"}), 500

    return jsonify({
        "agent": name,
        "status": "ok" if r.returncode == 0 else "error",
        "returncode": r.returncode,
        "stdout": r.stdout,
        "stderr": r.stderr,
    })
