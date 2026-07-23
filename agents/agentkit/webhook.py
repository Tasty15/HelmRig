"""Webhook listener — trigga agentkörningar via HTTP.

Används som Flask Blueprint i dashboarden:
    from agentkit.webhook import webhook_bp
    app.register_blueprint(webhook_bp)

Endpoints:
    POST /webhook/<agent> — Kör agent med valfri JSON-body som input
"""

import json
import os
import subprocess
from pathlib import Path

from flask import Blueprint, jsonify, request

webhook_bp = Blueprint("webhook", __name__)

AGENTS_DIR = Path(__file__).parent.parent
VENV_PYTHON = AGENTS_DIR.parent / ".venv" / "bin" / "python3"
HARNESS = AGENTS_DIR / "harness.py"
DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN")


@webhook_bp.route("/webhook/<agent>", methods=["POST"])
def webhook_trigger(agent: str):
    """Ta emot webhook-anrop och kör agenten.

    POST /webhook/<agent>
    Body: {"input": {"key": "value"}, "timeout": 120}
    Headers: Authorization: Bearer <token> (om DASHBOARD_TOKEN satt)
    """
    # Auth
    if DASHBOARD_TOKEN:
        token = request.headers.get("Authorization", "").replace("Bearer ", "") or request.args.get("token")
        if token != DASHBOARD_TOKEN:
            return jsonify({"error": "unauthorized"}), 401

    # Validera agent
    agent_dir = AGENTS_DIR / agent
    if not (agent_dir / "agent.yaml").exists():
        return jsonify({"error": f"agent '{agent}' not found"}), 404

    data = request.get_json(silent=True) or {}
    inp = data.get("input", {})
    timeout = min(int(data.get("timeout", 120)), 600)

    # Sätt CHAIN_INPUT_* om input finns
    env = os.environ.copy()
    for key, val in inp.items():
        env[f"CHAIN_INPUT_{key.upper()}"] = str(val)

    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"
    try:
        r = subprocess.run(
            [python, str(HARNESS), "run", agent],
            env=env, capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"status": "timeout", "error": f"timeout ({timeout}s)"}), 504
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)[:300]}), 500

    return jsonify({
        "status": "ok" if r.returncode == 0 else "error",
        "agent": agent,
        "stdout": r.stdout,
        "stderr": r.stderr,
        "returncode": r.returncode,
    })
