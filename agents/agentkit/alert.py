"""Alerting — skicka e-post vid misslyckade agentkörningar via Composio Gmail."""

import json
import os
import subprocess
from datetime import datetime


def send_email_alert(agent: str, error: str, log_entry: dict) -> dict:
    """Skicka e-post om en agent misslyckades.

    Använder composio Gmail (samma connection som agenternas skills).
    Kräver: composio CLI installerat + `composio add gmail`.

    Fallerar tillbaka till utskrift om composio inte finns.
    """
    to = os.environ.get("ALERT_EMAIL_TO", "grahn.simon@outlook.com")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    subject = f"⚠️ Agent misslyckades: {agent}"
    body = (
        f"Agent: {agent}\n"
        f"Tid: {ts}\n"
        f"Fel: {error[:500]}\n\n"
        f"Logg: {json.dumps(log_entry, indent=2, ensure_ascii=False)[:1000]}"
    )

    try:
        r = subprocess.run(
            ["composio", "execute", "GMAIL_SEND_EMAIL", "-d",
             json.dumps({"recipient_email": to, "subject": subject, "body": body})],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0:
            return {"status": "ok", "detail": "notifikation skickad"}
        return {"status": "error", "detail": r.stderr[:200]}
    except FileNotFoundError:
        return {"status": "error", "detail": "composio CLI saknas — kör: curl -fsSL https://composio.dev/install | bash"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "detail": "timeout vid anrop till composio"}
