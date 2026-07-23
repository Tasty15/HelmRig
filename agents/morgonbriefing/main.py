"""Agent: morgonbriefing — sammanfatta olästa mejl"""

import json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import yaml
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

from agentkit.utils import load_env
from agentkit.alert import send_email_alert

AGENT_DIR = Path(__file__).parent
AGENT_CONFIG = yaml.safe_load((AGENT_DIR / "agent.yaml").read_text())
AGENT_NAME = AGENT_CONFIG["name"]
load_env(AGENT_DIR)

TO = os.environ.get("ALERT_EMAIL_TO", "grahn.simon@outlook.com")

class AgentState(TypedDict):
    emails: list
    summary: str

def fetch_emails(state: AgentState) -> AgentState:
    """Hämta olästa mejl via Composio Gmail."""
    import subprocess
    r = subprocess.run(
        ["composio", "execute", "GMAIL_FETCH_EMAILS", "-d",
         json.dumps({"query": "is:unread", "max_results": 10, "verbose": False})],
        capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        return {"emails": [], "summary": f"Gmail-fel: {r.stderr[:200]}"}
    try:
        data = json.loads(r.stdout)
        msgs = data.get("data", {}).get("messages", [])
    except (json.JSONDecodeError, AttributeError):
        msgs = []
    return {"emails": msgs, "summary": ""}

def summarize(state: AgentState) -> AgentState:
    """Summera mejlen med LLM."""
    if not state.get("emails"):
        return {"emails": state["emails"], "summary": "Inga olästa mejl."}
    lines = []
    for m in state["emails"][:10]:
        subj = m.get("subject", "(ingen ämne)")
        sender = m.get("from", "(okänd)")
        snippet = m.get("snippet", "")[:150]
        lines.append(f"Från: {sender}\nÄmne: {subj}\n{'' if not snippet else snippet}")
    email_text = "\n---\n".join(lines)
    from agentkit.utils import create_model
    llm = create_model(AGENT_CONFIG.get("model", {}))
    prompt = (
        "Summera följande mejl i 3-5 punkter. Markera deadlines med ⏰.\n\n"
        f"{email_text}"
    )
    summary = llm.invoke(prompt).content
    return {"emails": state["emails"], "summary": summary}

def send(state: AgentState) -> AgentState:
    """Skicka summeringen via e-post."""
    body = (
        f"☀️ Morgonbriefing — {AGENT_NAME}\n"
        f"{'='*40}\n\n{state['summary']}\n\n"
        f"---\n{len(state.get('emails',[]))} olästa mejl bearbetade"
    )
    import subprocess
    r = subprocess.run(
        ["composio", "execute", "GMAIL_SEND_EMAIL", "-d",
         json.dumps({"recipient_email": TO, "subject": "☀️ Morgonbriefing", "body": body})],
        capture_output=True, text=True, timeout=30,
    )
    return {"emails": state["emails"], "summary": state["summary"]}

builder = StateGraph(AgentState)
builder.add_node("fetch", fetch_emails)
builder.add_node("summarize", summarize)
builder.add_node("send", send)
builder.add_edge(START, "fetch")
builder.add_edge("fetch", "summarize")
builder.add_edge("summarize", "send")
builder.add_edge("send", END)
graph = builder.compile()

def run(inputs: dict | None = None) -> dict:
    return graph.invoke(inputs or {})

if __name__ == "__main__":
    result = run()
    print(result.get("summary", ""))
