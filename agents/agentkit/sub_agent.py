"""Sub-agent dispatch — anropa en annan agent som en funktion."""

import json
import os

from agentkit.api import run_agent


def dispatch(name: str, input_data: dict | None = None, timeout: int = 120) -> dict:
    """Anropa en agent programmatiskt och returnera resultatet.

    Args:
        name: Agentnamn (mappnamn)
        input_data: Dict med nycklar som skickas som CHAIN_INPUT_* env vars
        timeout: Max exekveringstid i sekunder

    Returns:
        Dict med agent, status, output, error, chained_output, duration_s
    """
    # Spara och sätt env vars (thread-safe: varje call har sin egen snapshot)
    saved = {}
    if input_data:
        for key, val in input_data.items():
            env_key = f"CHAIN_INPUT_{key.upper()}"
            saved[env_key] = os.environ.get(env_key)
            os.environ[env_key] = str(val) if not isinstance(val, str) else val

    try:
        result = run_agent(name, timeout=timeout)
    finally:
        # Återställ env vars — även vid exception
        for env_key, orig_val in saved.items():
            if orig_val is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = orig_val

    # Parsa CHAIN_OUTPUT: från stdout om det finns
    output = result.get("stdout", "")
    chained_output = None
    if output:
        for line in output.splitlines():
            if line.startswith("CHAIN_OUTPUT:"):
                try:
                    chained_output = json.loads(line[len("CHAIN_OUTPUT:"):])
                except json.JSONDecodeError:
                    pass  # ponytail: tyst hoppa över korrupt output
                break  # första match räcker

    return {
        "agent": name,
        "status": "ok" if result.get("returncode", 1) == 0 else "error",
        "output": output,
        "error": result.get("stderr") or result.get("error"),
        "chained_output": chained_output,
        "duration_s": result.get("duration_s"),
    }
