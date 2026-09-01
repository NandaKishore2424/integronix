"""
This is a utility that we use to wrap all of our agent nodes.
It's a decorator that adds important features to each node automatically:
  - It logs when a node starts and finishes.
  - It measures how long each node takes to run.
  - It catches any errors, so that one failing node doesn't crash the whole process.
"""
import functools
from typing import Callable, Awaitable
from agents.graph import CodingState
from exceptions import NodeExecutionError
from logger import get_logger, Timer

log = get_logger(__name__)


def safe_node(node_name: str):
    # This is a decorator function. We can apply it to any of our agent nodes
    # by putting `@safe_node("node_name")` above the function definition.
    def decorator(func: Callable[[CodingState], Awaitable[CodingState]]):
        @functools.wraps(func)
        async def wrapper(state: CodingState) -> CodingState:
            session_id = str(state.get("session_id", "unknown"))

            # Fail-closed short-circuit: once any node has recorded a failure,
            # downstream nodes must not run — they would compute on partial
            # state and dress a failed run up as a plausible result. The graph
            # still drains to END, but every remaining node becomes a no-op.
            if state.get("error_at"):
                log.warning(
                    "node_skipped_due_to_upstream_error",
                    node_name=node_name,
                    session_id=session_id,
                    failed_at=state["error_at"],
                )
                return state

            log.info(
                "node_started",
                node_name=node_name,
                session_id=session_id,
            )

            # We'll time how long the node takes to execute.
            with Timer() as timer:
                try:
                    # This is where the actual node function gets called.
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
                    raise  # Don't re-wrap our custom errors.

                except Exception as exc:
                    # If any other error happens, we log it and mark it in the state.
                    # This allows the graph to potentially recover or handle the error gracefully.
                    log.error(
                        "node_failed",
                        node_name=node_name,
                        session_id=session_id,
                        latency_ms=timer.elapsed_ms,
                        status="failed",
                        error=str(exc),
                    )
                    # By adding the error to the state, subsequent nodes can see that something went wrong.
                    state["error_at"] = node_name
                    state["error_detail"] = str(exc)
                    return state

        return wrapper
    return decorator
