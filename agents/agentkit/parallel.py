"""Parallel execution — kör flera agent-instanser samtidigt."""

from concurrent.futures import ThreadPoolExecutor

from agentkit.sub_agent import dispatch


def fan_out(
    agent_name: str,
    inputs: list[dict],
    timeout: int = 120,
    max_workers: int = 4,
) -> list[dict]:
    """Kör flera instanser av samma agent parallellt med olika input.

    Args:
        agent_name: Agentnamn att köra
        inputs: Lista med input-dicts — en agent per dict
        timeout: Max sekunder per agent
        max_workers: Max parallella agenter (minimum 1)

    Returns:
        Lista med resultat-dicts i samma ordning som inputs
    """
    if not inputs:
        return []

    max_workers = max(1, max_workers)
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(dispatch, agent_name, inp, timeout) for inp in inputs]
        for f in futures:
            try:
                results.append(f.result())
            except Exception as e:
                results.append({
                    "agent": agent_name,
                    "status": "error",
                    "error": str(e),
                })

    return results
