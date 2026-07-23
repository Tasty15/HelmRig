"""Tracing — Langfuse callback för token/tool/latency-spårning.

Används i agent-pipeline:
    from agentkit.tracer import get_langfuse_handler

    handler = get_langfuse_handler(agent_name="research-agent")
    # Använd i LangGraph: graph.invoke(inputs, config={"callbacks": [handler]})

Ingen token-påverkan i agent-prompten — data skickas till Langfuse-server.
"""

import os


def get_langfuse_handler(agent_name: str = "helmrig", session_id: str = None):
    """Skapa en Langfuse callback handler för spårning.

    Args:
        agent_name: Namn på agenten (blir trace name i Langfuse)
        session_id: Valfritt session-ID för att gruppera körningar

    Returns:
        Langfuse CallbackHandler eller None (om langfuse inte är installerat)
    """
    try:
        from langfuse.callback import CallbackHandler
    except ImportError:
        return None

    # ponytail: använd LANGFUSE_* env vars — standard från Langfuse docs
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY") or os.environ.get("LANGFUSE_SECRET_KEY")
    if not public_key:
        # Silent fallback — tracing är opt-in
        return None

    handler = CallbackHandler(
        public_key=os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
        secret_key=os.environ.get("LANGFUSE_SECRET_KEY", ""),
        host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        trace_name=agent_name,
        session_id=session_id,
    )
    return handler


def trace_run(agent: str, status: str, duration_s: float, tokens: int = 0, error: str = ""):
    """Logga en agentkörning till Langfuse (anropas efter completion).

    För agenter som inte använder LangGraph callbacks.
    """
    handler = get_langfuse_handler(agent_name=agent)
    if not handler:
        return {"status": "skipped", "reason": "langfuse inte konfigurerad"}

    try:
        # ponytail: grundläggande trace — nog för översikt
        handler.trace(
            name=agent,
            metadata={
                "status": status,
                "duration_s": duration_s,
                "tokens": tokens,
                "error": error[:500] if error else "",
            },
        )
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "error": str(e)[:200]}
