"""Slack-bot — lyssna på Slack-meddelanden och dispatchera till agenter.

Användning:
    python -c "from agentkit.slack_bot import listen; listen(agent='research-agent')"

Kräver: composio CLI + Slack-anslutning (composio add slack)
"""

import json
import os
import subprocess
import time
from pathlib import Path

AGENTS_DIR = Path(__file__).parent.parent
HARNESS = AGENTS_DIR / "harness.py"
VENV_PYTHON = AGENTS_DIR.parent / ".venv" / "bin" / "python3"


def listen(agent: str = None, channel: str = None, poll_interval: int = 10):
    """Poll Slack-kanal och dispatchera meddelanden till agent.

    Args:
        agent: Agentnamn att köra (None = kräver @mention i Slack)
        channel: Slack-kanal-ID (None = alla kanaler)
        poll_interval: Poll-intervall i sekunder (default 10)

    Detta är en enkel polling-loop — i produktion, använd Slack Events API.
    """
    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else "python3"

    # Kolla att composio finns
    try:
        subprocess.run(["composio", "--version"], capture_output=True, timeout=5)
    except FileNotFoundError:
        print("❌ composio CLI saknas — kör: curl -fsSL https://composio.dev/install | bash")
        return

    seen = set()
    print(f"🤖 Slack-bot startar (agent={agent or 'auto'}, channel={channel or 'alla'})")

    while True:
        try:
            # Hämta Slack-meddelanden via composio execute
            cmd = ["composio", "execute", "SLACK_LIST_MESSAGES", "-d",
                   json.dumps({"channel": channel or "C...", "limit": 5})]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if r.returncode != 0:
                time.sleep(poll_interval * 6)
                continue

            messages = json.loads(r.stdout) if r.stdout.strip() else []

            for msg in messages:
                msg_id = msg.get("ts", "") or msg.get("client_msg_id", "")
                if not msg_id or msg_id in seen:
                    continue
                seen.add(msg_id)

                text = msg.get("text", "")
                user = msg.get("user", "unknown")
                channel_type = msg.get("channel_type", "channel")

                # Bestäm vilken agent som ska svara
                target_agent = agent
                if not target_agent:
                    # Kolla om någon agent nämns i meddelandet
                    for d in AGENTS_DIR.iterdir():
                        if d.is_dir() and not d.name.startswith("."):
                            if d.name in text:
                                target_agent = d.name
                                break

                if not target_agent:
                    continue  # Inget matchande agent för detta meddelande

                print(f"  📩 Dispatch till '{target_agent}': {text[:80]}...")
                env = os.environ.copy()
                env["CHAIN_INPUT_SLACK_MESSAGE"] = text
                env["CHAIN_INPUT_SLACK_USER"] = user
                env["CHAIN_INPUT_SLACK_CHANNEL"] = str(channel_type)

                subprocess.run(
                    [python, str(HARNESS), "run", target_agent],
                    env=env, capture_output=True, timeout=120,
                )

        except Exception as e:
            print(f"  ⚠ Slack-bot error: {e}")

        time.sleep(poll_interval)
