"""Optional LangGraph research loop over Schola's existing safe interfaces.

The transport owns credentials, JSON/native compatibility and daily accounting.
The tool callback owns scope, URL policy and provenance. No provider clients,
parallel tools, retries, checkpoints or fallback model calls live here.
"""
import asyncio
import copy
import json
import math
import time
from typing import TypedDict


class ResearchLimit(ValueError):
    """A research run exhausted an explicit local limit."""


def budget_message(*, remaining_tools, remaining_rounds):
    """Give each model reply its actual remaining local budget."""
    if remaining_tools <= 0 or remaining_rounds <= 0:
        return {"role": "user", "content": "Research budget reached. Answer now using collected evidence, cite sources, and mark unresolved facts UNKNOWN. Do not request more tools."}
    return {"role": "user", "content": (
        f"Research budget: {remaining_tools} tool calls and {remaining_rounds} further model replies remain after this reply. "
        "Use focused source queries and continuation offsets; avoid rereading whole pages. "
        "Reserve the final reply for synthesis. If evidence remains incomplete, explain the gaps and mark unresolved facts UNKNOWN."
    )}


def prepare_reply(reply, tool_names, *, allow_tools, remaining_tools):
    """Validate a complete batch before execution, marking over-budget calls.

    Every requested call keeps its ID and receives a result, including skipped
    calls. Unknown tools and malformed arguments remain errors, not executions.
    """
    if not isinstance(reply, dict):
        raise ValueError("The model returned an invalid research reply. Retry explicitly.")
    raw_calls = reply.get("tool_calls")
    if raw_calls is None:
        raw_calls = []
    if not isinstance(raw_calls, list) or len(raw_calls) > 32:
        raise ValueError("The model returned invalid research tool calls. Retry explicitly.")
    if raw_calls and not allow_tools:
        raise ResearchLimit("The final research reply requested tools despite the synthesis-only limit. Retry explicitly.")
    calls, normalized_calls, seen = [], [], set()
    for call in raw_calls:
        try:
            call_id, function = call["id"], call["function"]
            name, encoded = function["name"], function["arguments"]
            if (not isinstance(call_id, str) or not call_id.strip() or len(call_id) > 200
                    or call_id in seen or not isinstance(name, str) or name not in tool_names
                    or not isinstance(encoded, str)):
                raise ValueError()
            arguments = json.loads(encoded)
            if not isinstance(arguments, dict):
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise ValueError("The model requested an unavailable research tool or malformed arguments.") from None
        seen.add(call_id)
        calls.append((call_id, name, arguments, len(calls) < remaining_tools))
        normalized_calls.append({"id": call_id, "type": "function", "function": {"name": name, "arguments": encoded}})
    content = reply.get("content") or ""
    if not isinstance(content, str) or (not content.strip() and not calls):
        raise ValueError("The model returned no usable research reply. Retry explicitly.")
    normalized = {"role": "assistant", "content": content}
    if normalized_calls:
        normalized["tool_calls"] = normalized_calls
    return normalized, calls


def skipped_tool_result():
    return {"state": "BUDGET_EXHAUSTED", "error": "This tool call was not executed because the research tool budget is exhausted. Use collected evidence and mark unresolved facts UNKNOWN."}


def run_agent(messages, tool_specs, complete, execute_tool, *, max_rounds=6,
              max_tools=12, max_seconds=600):
    """Return a normalized final reply; both callbacks run on this thread.

    ``complete(messages, allow_tools=...)`` reserves its own model-call budget.
    ``execute_tool(name, args)`` returns scrubbed JSON data and records evidence.
    Exceptions stop the run; the owner must explicitly retry saved work.
    Time is checked between operations; the transport owns request timeouts.
    """
    try:
        from langgraph.graph import END, START, StateGraph
        from langsmith import tracing_context
    except ImportError:
        raise ValueError("Schola's research runtime is unavailable. Install requirements-research.txt in the worker environment.") from None

    if not messages or type(max_rounds) is not int or not 1 <= max_rounds <= 12:
        raise ValueError("Research needs saved messages and between 1 and 12 model rounds.")
    if type(max_tools) is not int or not 1 <= max_tools <= 12:
        raise ValueError("Research allows between 1 and 12 tool calls.")
    if type(max_seconds) not in (int, float) or not math.isfinite(max_seconds) or not 0 < max_seconds <= 600:
        raise ValueError("Research allows at most 600 seconds.")
    deadline = time.monotonic() + max_seconds
    counts = {"model": 0, "tools": 0}
    names = {spec["function"]["name"] for spec in tool_specs}
    if len(names) != len(tool_specs) or not names:
        raise ValueError("Research needs a nonempty, unique tool allowlist.")

    def check_time():
        if time.monotonic() >= deadline:
            raise ResearchLimit("Research time limit reached. Saved evidence is preserved; retry explicitly.")

    class State(TypedDict):
        messages: list
        reply: dict
        calls: list

    # Async nodes deliberately call callbacks inline. Sync LangGraph nodes and
    # ToolNode can use executors, moving SQLite access off its owning thread.
    async def model_step(state):
        check_time()
        if counts["model"] >= max_rounds:
            raise ResearchLimit("Research model-round limit reached. Retry explicitly.")
        counts["model"] += 1
        allow_tools = counts["model"] < max_rounds and counts["tools"] < max_tools
        history = [*state["messages"], budget_message(
            remaining_tools=max_tools - counts["tools"], remaining_rounds=max_rounds - counts["model"])]
        reply = complete(history, allow_tools=allow_tools)
        check_time()
        normalized, calls = prepare_reply(reply, names, allow_tools=allow_tools,
                                          remaining_tools=max_tools - counts["tools"])
        return {"messages": [*state["messages"], normalized], "reply": normalized, "calls": calls}

    async def tool_step(state):
        results = []
        for call_id, name, arguments, admitted in state["calls"]:
            check_time()
            if admitted:
                counts["tools"] += 1
                result = execute_tool(name, arguments)
            else:
                result = skipped_tool_result()
            check_time()
            results.append({"role": "tool", "tool_call_id": call_id,
                            "content": json.dumps(result, ensure_ascii=False)})
        return {"messages": [*state["messages"], *results], "calls": []}

    builder = StateGraph(State)
    builder.add_node("model", model_step)
    builder.add_node("tools", tool_step)
    builder.add_edge(START, "model")
    builder.add_conditional_edges("model", lambda state: "tools" if state["calls"] else END)
    builder.add_edge("tools", "model")
    graph = builder.compile()

    async def invoke():
        # Never let ambient LANGSMITH_TRACING export private Schola history.
        with tracing_context(enabled=False):
            return await graph.ainvoke({"messages": copy.deepcopy(messages), "reply": {}, "calls": []},
                                       {"callbacks": [], "recursion_limit": max_rounds * 2 + 2})

    result = asyncio.run(invoke())
    check_time()
    return {"role": "assistant", "content": result["reply"]["content"]}
