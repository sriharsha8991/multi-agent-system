"""Notebook helpers: ask the team a question and look inside the run.

    from mas.notebook import ask, show_plan, show_tool_calls, show_figures, show_data

    result = ask("Why is the turbine vibrating?")   # runs + shows everything
    show_tool_calls(result)                         # every SQL / Cypher / Python call again
    show_figures(result)                            # the images this run produced
    show_data(result, "t4")                         # the rows behind an artifact

Everything is read from the final state ``run()`` returns — the ledger, the ``tool_events``
trail every tool writes, and the blackboard of artifact digests — so nothing here calls a
model. Outside Jupyter the same functions print plain text.
"""
from __future__ import annotations

import html
import time
from pathlib import Path

import pandas as pd

from .memory import store
from .memory.artifacts import RecordsArtifact, TableArtifact
from .orchestrator import answer_of, run
from .orchestrator.ledger import ledger_view

__all__ = ["ask", "show_answer", "show_plan", "show_tool_calls", "show_figures", "show_data",
           "run_summary", "figures_of"]

_LANG = {"sql": "sql", "cypher": "cypher", "code": "python"}


# ── display plumbing ─────────────────────────────────────────────────────────────
def _in_notebook() -> bool:
    try:
        from IPython import get_ipython
        return get_ipython() is not None and "IPKernelApp" in get_ipython().config
    except Exception:  # noqa: BLE001 — IPython missing or not a kernel
        return False


def _markdown(text: str) -> None:
    if _in_notebook():
        from IPython.display import Markdown, display
        display(Markdown(text))
    else:
        print(text)


def _fence(body: str, lang: str = "") -> str:
    body = str(body).rstrip()
    fence = "````" if "```" in body else "```"
    return f"{fence}{lang}\n{body}\n{fence}"


def _seconds(ms) -> str:
    return f"{(ms or 0) / 1000:.1f} s"


# ── what happened ────────────────────────────────────────────────────────────────
def figures_of(result: dict) -> list[dict]:
    """Figures this run produced: ``[{artifact_id, title, path}]`` in the order drawn."""
    out = []
    for art_id, digest in (result.get("blackboard") or {}).items():
        if isinstance(digest, dict) and digest.get("kind") == "figure":
            out.append({"artifact_id": art_id, "title": digest.get("caption") or "",
                        "path": digest.get("path")})
    return out


def run_summary(result: dict) -> dict:
    """Headline numbers for a run: delegations, tool calls, model calls, tokens, time."""
    events = result.get("tool_events") or []
    delegations = [e for e in events if str(e.get("tool", "")).startswith("delegate:")]
    inner = [e for e in events if not str(e.get("tool", "")).startswith("delegate:")]
    orch_usage = [getattr(m, "usage_metadata", None) or {} for m in result.get("messages") or []]
    return {
        "delegations": len(delegations),
        "rejected_delegations": sum(1 for e in delegations if str(e.get("error", "")).startswith("rejected")),
        "tool_calls": len(inner),
        "failed_tool_calls": sum(1 for e in inner if e.get("error")),
        "orchestrator_model_calls": sum(1 for u in orch_usage if u),
        "specialist_model_calls": sum(e.get("model_calls") or 0 for e in delegations),
        "input_tokens": sum(u.get("input_tokens", 0) for u in orch_usage)
                        + sum(e.get("input_tokens") or 0 for e in delegations),
        "output_tokens": sum(u.get("output_tokens", 0) for u in orch_usage)
                         + sum(e.get("output_tokens") or 0 for e in delegations),
        "figures": len(figures_of(result)),
        "specialist_seconds": round(sum(e.get("ms") or 0 for e in delegations) / 1000, 1),
    }


# ── views ────────────────────────────────────────────────────────────────────────
def show_answer(result: dict) -> None:
    """The final answer, with the Evidence / Gaps lines code appended."""
    _markdown("## Answer\n\n" + (answer_of(result) or "_(no answer produced)_"))


def show_plan(result: dict) -> None:
    """The ledger: the facts the answer needed, the plan steps, their status, the artifacts."""
    view = ledger_view(result)
    _markdown("## Plan and ledger\n\n" + (_fence(view) if view else
                                          "_No plan — the orchestrator answered directly._"))


def show_tool_calls(result: dict, *, briefs: bool = True, max_chars: int = 4000) -> None:
    """Every delegation and, under it, every tool call the specialist made — the exact SQL,
    Cypher or Python, rows returned, artifacts, timing and errors."""
    events = result.get("tool_events") or []
    if not events:
        _markdown("## Tool calls\n\n_No tool calls recorded._")
        return
    parts = ["## Tool calls"]
    n = 0
    for e in events:
        tool = str(e.get("tool", "?"))
        if tool.startswith("delegate:"):
            agent = tool.split(":", 1)[1]
            status = "REJECTED" if str(e.get("error", "")).startswith("rejected") else e.get("status", "?")
            head = (f"### {e.get('step_id', '?')} · {agent} → **{status}**  \n"
                    f"slots {', '.join(e.get('slots') or [])} · {e.get('inner_calls', 0)} tool calls · "
                    f"{e.get('model_calls', 0)} model calls · "
                    f"{(e.get('input_tokens') or 0) + (e.get('output_tokens') or 0):,} tokens · "
                    f"{_seconds(e.get('ms'))}")
            parts.append(head)
            if e.get("error"):
                parts.append(f"> ⚠️ {e['error']}")
            if briefs and e.get("brief"):
                parts.append("<details><summary>brief written by code</summary>\n\n"
                             + _fence(e["brief"]) + "\n\n</details>")
            if e.get("artifacts_created"):
                parts.append(f"artifacts created: `{'`, `'.join(e['artifacts_created'])}`")
            if e.get("code_notes"):
                parts.append("code checks: " + "; ".join(e["code_notes"]))
            continue

        n += 1
        bits = [f"**{n}. {tool}**", f"`{e.get('agent', '?')}`", _seconds(e.get("ms"))]
        if e.get("rows") is not None:
            bits.append(f"{e['rows']:,} rows")
        if e.get("figures"):
            bits.append("figures " + ", ".join(f"`{f}`" for f in e["figures"]))
        elif e.get("artifact_id"):
            bits.append(f"→ `{e['artifact_id']}`")
        if e.get("searches"):
            bits.append(f"searched {e['searches']} ({e.get('matches', 0)} matches)")
        parts.append(" · ".join(bits))
        if e.get("error"):
            parts.append(f"> ❌ {html.escape(str(e['error']))}")
        for key, lang in _LANG.items():
            if e.get(key):
                body = str(e[key])
                parts.append(_fence(body[:max_chars] + (" …" if len(body) > max_chars else ""), lang))
                break
    _markdown("\n\n".join(parts))


def show_figures(result: dict, *, width: int = 900) -> list[dict]:
    """Display every figure the run produced, titled, with its file path. Returns the list."""
    figs = figures_of(result)
    if not figs:
        _markdown("## Figures\n\n_This run produced no figures._")
        return figs
    _markdown(f"## Figures ({len(figs)})")
    for f in figs:
        path = Path(f["path"] or "")
        _markdown(f"**{f['artifact_id']} — {f['title'] or 'untitled'}**  \n`{path}`")
        if not path.exists():
            _markdown(f"_file not found: {path}_")
        elif _in_notebook():
            from IPython.display import Image, display
            display(Image(filename=str(path), width=width))
    return figs


def show_data(result: dict, artifact_id: str, rows: int = 20) -> pd.DataFrame | None:
    """The rows behind a table or record artifact (payloads live in the in-process store,
    so this works in the same kernel that ran the question)."""
    art = store.get(artifact_id)
    if isinstance(art, TableArtifact):
        df = art.df
    elif isinstance(art, RecordsArtifact):
        df = pd.DataFrame(art.rows)
    else:
        known = ", ".join(k for k, d in (result.get("blackboard") or {}).items()
                          if isinstance(d, dict) and d.get("kind") in ("table", "records"))
        _markdown(f"_`{artifact_id}` is not a table or record artifact in this kernel. "
                  f"Data artifacts from this run: {known or 'none'}._")
        return None
    _markdown(f"**{artifact_id}** — {len(df):,} rows × {df.shape[1]} columns")
    if _in_notebook():
        from IPython.display import display
        display(df.head(rows))
    else:
        print(df.head(rows).to_string())
    return df


# ── one call does it all ─────────────────────────────────────────────────────────
def ask(question: str, *, plan: bool = True, tool_calls: bool = True, figures: bool = True,
        thread_id: str | None = None) -> dict:
    """Run one question through the team and show the answer, plan, tool calls and figures.

    Returns the final state, so any view can be shown again later.
    """
    _markdown(f"# {question}")
    t0 = time.perf_counter()
    result = run(question, thread_id=thread_id)
    elapsed = time.perf_counter() - t0
    if result.get("budget_exhausted"):
        _markdown("> ⚠️ Step budget exhausted — partial work shown.")

    show_answer(result)
    if figures:
        show_figures(result)
    if plan:
        show_plan(result)
    if tool_calls:
        show_tool_calls(result)
    s = run_summary(result)
    _markdown(f"_{elapsed:.0f} s · {s['delegations']} delegations · {s['tool_calls']} tool calls "
              f"({s['failed_tool_calls']} failed) · "
              f"{s['orchestrator_model_calls'] + s['specialist_model_calls']} model calls · "
              f"{s['input_tokens'] + s['output_tokens']:,} tokens · {s['figures']} figures_")
    return result
