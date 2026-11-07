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
        history = state["messages"]
        if not allow_tools:
            history = [*history, {"role": "user", "content": "Research limit reached. Answer now using collected evidence, cite sources, and mark unresolved eligibility UNKNOWN. Do not request more tools."}]
        reply = complete(history, allow_tools=allow_tools)
        check_time()
        if not isinstance(reply, dict):
            raise ValueError("The model returned an invalid research reply. Retry explicitly.")
        calls = []
        for call in reply.get("tool_calls") or []:
            if not allow_tools or len(calls) + counts["tools"] >= max_tools:
                raise ResearchLimit("Research tool limit reached. Retry explicitly.")
            function = call["function"]
            args = json.loads(function["arguments"])
            if function["name"] not in names or not isinstance(args, dict):
                raise ValueError("The model requested an unavailable research tool.")
            calls.append((call["id"], function["name"], args))
        content = reply.get("content") or ""
        if not isinstance(content, str) or (not content.strip() and not calls):
            raise ValueError("The model returned no usable research reply. Retry explicitly.")
        normalized = {"role": "assistant", "content": content}
        if calls:
            normalized["tool_calls"] = reply["tool_calls"]
        return {"messages": [*state["messages"], normalized], "reply": normalized, "calls": calls}

    async def tool_step(state):
        results = []
        for call_id, name, arguments in state["calls"]:
            check_time()
            if counts["tools"] >= max_tools:
                raise ResearchLimit("Research tool limit reached. Retry explicitly.")
            counts["tools"] += 1
            result = execute_tool(name, arguments)
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
