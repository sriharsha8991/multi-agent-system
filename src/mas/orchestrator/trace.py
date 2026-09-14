"""Human-readable trace of an agent run.

Walks the message history and renders each step the agent took: the tool it called, the
arguments it wrote (the actual SQL/Cypher/Python), and what came back — then the final
answer. This is the inspector view.
"""
from __future__ import annotations

import textwrap

from langchain_core.messages import AIMessage, ToolMessage


def content_text(content) -> str:
    """Message content may be a plain string or a list of content blocks (Gemini)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("text"):
                parts.append(block["text"])
        return "\n".join(parts)
    return str(content or "")


def _preview(value, width: int = 900) -> str:
    text = value if isinstance(value, str) else str(value)
    text = " ".join(text.split()) if len(text) > width else text
    return textwrap.shorten(text, width=width, placeholder=" …")


def format_trace(result: dict, *, arg_width: int = 900, out_width: int = 700) -> str:
    """Render tool calls + results + the final answer as readable text."""
    lines: list[str] = []
    step = 0
    for msg in result.get("messages", []):
        if isinstance(msg, AIMessage):
            for call in (msg.tool_calls or []):
                step += 1
                lines.append(f"\n─── step {step}: {call['name']} ───")
                for key, val in (call.get("args") or {}).items():
                    lines.append(f"  {key}: {_preview(val, arg_width)}")
        elif isinstance(msg, ToolMessage):
            lines.append(f"  → {_preview(content_text(msg.content), out_width)}")

    finals = [content_text(m.content) for m in result.get("messages", [])
              if isinstance(m, AIMessage) and not m.tool_calls and content_text(m.content).strip()]
    lines.append("\n" + "=" * 78)
    if result.get("budget_exhausted"):
        lines.append("[step budget exhausted — partial work shown above]")
    lines.append("ANSWER:\n")
    lines.append(finals[-1] if finals else "(no answer produced)")
    bb = result.get("blackboard") or {}
    if bb:
        lines.append(f"\nartifacts on blackboard: {', '.join(bb)}")
    return "\n".join(lines)


def format_events(result: dict, *, query_width: int = 220) -> str:
    """Render the full tool-level trail: every SQL/Cypher/Python call, in order.

    Reads the ``tool_events`` state channel, which the tools populate and ``_delegate``
    propagates up from each specialist. This is the minute-level view that the message
    history deliberately hides.
    """
    events = result.get("tool_events") or []
    if not events:
        return "(no tool events recorded)"

    lines = [f"TOOL-LEVEL TRAIL - {len(events)} events", "=" * 78]
    for i, e in enumerate(events, 1):
        agent = e.get("agent", "?")
        head = f"{i:>3}. [{e.get('ms', 0):>6}ms] {agent:<13} {e.get('tool', '?')}"
        bits = []
        for key in ("db", "rows", "artifact_id", "matches", "inner_calls", "stdout_chars"):
            if e.get(key) is not None:
                bits.append(f"{key}={e[key]}")
        if e.get("error"):
            bits.append(f"ERROR={e['error'][:80]}")
        lines.append(head + ("   " + " ".join(bits) if bits else ""))

        body = (e.get("sql") or e.get("cypher") or e.get("code")
                or e.get("task") or e.get("expression") or "")
        if body:
            text = " ".join(str(body).split())
            lines.append(f"       {text[:query_width]}{' ...' if len(text) > query_width else ''}")
        if e.get("artifacts_created"):
            lines.append(f"       -> artifacts: {', '.join(e['artifacts_created'])}")
    return "\n".join(lines)
