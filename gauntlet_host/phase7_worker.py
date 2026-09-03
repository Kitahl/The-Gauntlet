"""FAST-P7 wrapper that injects one advisory FOIL route before model work."""

from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
import sys
from typing import Any

if __package__ in {None, ""}:
    _repo_bootstrap = Path(__file__).resolve().parent.parent
    if str(_repo_bootstrap) not in sys.path:
        sys.path.insert(0, str(_repo_bootstrap))

from gauntlet_host import foil_bridge
from gauntlet_host import worker_main as core
from gauntlet_host.ipc import RuntimeRequest, RuntimeResult

_ORIGINAL_EXECUTE = core._execute_agent_turn


def _execute_with_foil_route(
    request: RuntimeRequest,
    proof: Any,
) -> RuntimeResult:
    route_state: dict[str, Any] = {}

    with redirect_stdout(sys.stderr):
        from run_agent import AIAgent

    original_run_conversation = AIAgent.run_conversation

    def routed_run_conversation(
        agent: Any,
        prompt: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if route_state.get("applied") is True:
            return original_run_conversation(agent, prompt, *args, **kwargs)

        route_state["applied"] = True
        try:
            route = foil_bridge.build_advisory_route(
                task_id=request.task_id,
                tool_definitions=getattr(agent, "tools", ()),
            )
            routed_prompt = foil_bridge.inject_advisory_route(prompt, route)
        except foil_bridge.FoilRouteBridgeError as exc:
            raise core.RuntimeExecutionError(exc.code, exc.message) from exc

        route_state["route"] = route
        return original_run_conversation(
            agent,
            routed_prompt,
            *args,
            **kwargs,
        )

    AIAgent.run_conversation = routed_run_conversation
    try:
        result = _ORIGINAL_EXECUTE(request, proof)
    finally:
        if AIAgent.run_conversation is routed_run_conversation:
            AIAgent.run_conversation = original_run_conversation

    route = route_state.get("route")
    if isinstance(route, dict):
        payload = dict(result.payload)
        payload["foil_route"] = route
        result = replace(result, payload=payload)
    elif result.status.value == "OK":
        return core._error_result(
            request,
            status=core.WorkerStatus.UNAVAILABLE,
            event="worker.foil_route_unavailable",
            code="FOIL_ROUTE_NOT_APPLIED",
            message="runtime completed without the required FAST-P7 route",
            payload=proof.to_payload(),
        )
    return result


def main() -> int:
    core._execute_agent_turn = _execute_with_foil_route
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
