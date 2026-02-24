"""
agents/node_runner.py — Safe node execution wrapper for LangGraph.

Wraps any node function with:
  1. Structured logging (entry + exit)
  2. Latency measurement
  3. Exception catching → NodeExecutionError
  4. State error_at field marking (graph continues, not crashes)

Usage:
    from agents.node_runner import safe_node
    
    @safe_node("snomed_resolve")
    async def snomed_resolver_node(state: CodingState) -> CodingState:
        ...
"""
import functools
from typing import Callable, Awaitable
from agents.graph import CodingState
from exceptions import NodeExecutionError
from logger import get_logger, Timer

log = get_logger(__name__)


def safe_node(node_name: str):
    """
    Decorator for LangGraph node functions.
    Adds logging, latency tracking, and exception safety.
    """
    def decorator(func: Callable[[CodingState], Awaitable[CodingState]]):
        @functools.wraps(func)
        async def wrapper(state: CodingState) -> CodingState:
            session_id = str(state.get("session_id", "unknown"))

            log.info(
                "node_started",
                node_name=node_name,
                session_id=session_id,
            )

            with Timer() as timer:
                try:
                    result_state = await func(state)
                    log.info(
                        "node_completed",
                        node_name=node_name,
                        session_id=session_id,
                        latency_ms=timer.elapsed_ms,
                        status="success",
                    )
                    return result_state

                except NodeExecutionError:
                    raise  # Don't double-wrap

                except Exception as exc:
                    log.error(
                        "node_failed",
                        node_name=node_name,
                        session_id=session_id,
                        latency_ms=timer.elapsed_ms,
                        status="failed",
                        error=str(exc),
                    )
                    # Mark error in state — graph CAN continue with fallback routing
                    state["error_at"] = node_name
                    state["error_detail"] = str(exc)
                    return state

        return wrapper
    return decorator
