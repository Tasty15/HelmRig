"""Agent: nyheter — hämta RSS-flöden och sammanfatta dagens nyheter"""

import json, os, sys, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import yaml
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

from agentkit.utils import load_env, create_model

AGENT_DIR = Path(__file__).parent
AGENT_CONFIG = yaml.safe_load((AGENT_DIR / "agent.yaml").read_text())
AGENT_NAME = AGENT_CONFIG["name"]
load_env(AGENT_DIR)
TO = os.environ.get("ALERT_EMAIL_TO", "grahn.simon@outlook.com")


class AgentState(TypedDict):
    raa_text: str
    summary: str


def fetch_news(state: AgentState) -> AgentState:
    texts = []
    for url in [
        "https://www.svt.se/rss.xml",
        "https://www.dn.se/rss",
    ]:
        print(f"  📰 Hämtar {url}...")
        try:
            r = urllib.request.urlopen(url, timeout=15)
            xml = r.read().decode("utf-8", errors="replace")
            # Enkel RSS-parsing: extrahera <title> och <description>
            titles = []
            for line in xml.split("<item>")[1:4]:
                for part in line.split("</title>")[:1]:
                    t = part.split("<title>")[-1].split("<")[0].strip() if "<title>" in part else ""
                    desc = ""
                    if "<description>" in line:
                        desc = line.split("<description>")[-1].split("</description>")[0].strip()[:200]
                    if t:
                        titles.append(f"• {t}")
                        if desc:
                            titles.append(f"  {desc}")
            if titles:
                texts.append(f"=== {url}\n" + "\n".join(titles))
        except Exception as e:
            texts.append(f"=== {url}\nFel: {e}")
    return {"raa_text": "\n\n".join(texts) if texts else "Kunde inte hämta nyheter.", "summary": ""}


def summarize(state: AgentState) -> AgentState:
    llm = create_model(AGENT_CONFIG.get("model", {}))
    prompt = (
        "Sammanfatta dagens nyheter från nedanstående RSS-flöden. "
        "Kategorisera i: Ekonomi, Tech, Politik, Övrigt. "
        "Max en mening per kategori. Skriv på svenska.\n\n"
        f"{state['raa_text'][:6000]}"
    )
    summary = llm.invoke(prompt).content
    return {"raa_text": state["raa_text"], "summary": summary}


def send(state: AgentState) -> AgentState:
    body = f"📰 Dagens nyheter — {AGENT_NAME}\n{'='*40}\n\n{str(state['summary'])}"
    import subprocess
    subprocess.run(
        ["composio", "execute", "GMAIL_SEND_EMAIL", "-d",
         json.dumps({"recipient_email": TO, "subject": "📰 Dagens nyheter", "body": body})],
        capture_output=True, text=True, timeout=30,
    )
    return state


builder = StateGraph(AgentState)
builder.add_node("fetch", fetch_news)
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
