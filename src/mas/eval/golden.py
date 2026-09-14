"""Golden-dataset evaluation (L6) — correctness, reliability and information determinism.

Scored per case over k runs of the same question on the same pinned data (doc 10, §6):

* **routing** — did the specialists use the right tool families (graph / sql / python)?
* **value** — do the ground-truth checks (numbers, required strings, a figure, or no
  delegation for out-of-scope questions) hold in the final answer?
* **pass^k** — τ-bench's reliability metric: every one of the k runs passes value checks.
* **fact determinism** — the normalised set of accepted facts (entity, attribute, value,
  unit, time) is identical across runs. Wording and execution path may differ; the
  information may not.
* **answer-number determinism** — the numbers-with-units the user reads are identical.
* **window determinism** — the time windows the specialists' queries used are identical.

The old "numbers anywhere in the answer" determinism metric failed on any wording change
and is gone. Pure functions over final states, so everything unit-tests without live calls.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from langchain_core.messages import AIMessage

from ..catalog import glossary
from ..orchestrator.trace import content_text

#: Tool families: a golden case names families, and any tool in the family satisfies it.
_FAMILY_TOOLS = {
    "sql": {"sql_query"},
    "graph": {"graph_query"},
    "python": {"python_analysis"},
}


def load_golden(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _events(result: dict) -> list[dict]:
    return result.get("tool_events") or []


def tools_used(result: dict) -> list[str]:
    """Tools the specialists called, in order (from ``tool_events``, not messages)."""
    return [str(e.get("tool")) for e in _events(result)
            if not str(e.get("tool", "")).startswith("delegate:") and e.get("tool") != "set_plan"
            and not str(e.get("error", "")).startswith("refused")]


def expected_tools(case: dict) -> set[str]:
    """Tool families the case needs: a subset of {'sql', 'graph', 'python'}."""
    return {c.split(".")[0] for c in case.get("expected_route", []) if c.split(".")[0] in _FAMILY_TOOLS}


def answer_text(result: dict) -> str:
    finals = [content_text(m.content) for m in result.get("messages", [])
              if isinstance(m, AIMessage) and not m.tool_calls and content_text(m.content).strip()]
    return finals[-1] if finals else ""


def _answer_body(result: dict) -> str:
    """The answer without the code-written footers (they list ids, not the model's claims)."""
    return re.split(r"\n\n\*\*Evidence:\*\*|\n\n\*\*Gaps:\*\*", answer_text(result))[0]


def _has_figure(result: dict) -> bool:
    return any(isinstance(d, dict) and d.get("kind") == "figure"
               for d in (result.get("blackboard") or {}).values())


def _delegated(result: dict) -> bool:
    return any(str(e.get("tool", "")).startswith("delegate:") and not str(e.get("error", "")).startswith("rejected")
               for e in _events(result))


_NUM_TOKEN = re.compile(r"(-?\d[\d,]*\.?\d*)\s*(million|lakh|crore|k|K|M)?\b")
_SCALE = {None: 1, "k": 1e3, "K": 1e3, "M": 1e6, "million": 1e6, "lakh": 1e5, "crore": 1e7}


def _num_in_text(value, text: str, *, rel: float = 0.0005) -> bool:
    """True if `value` appears in the text at reporting precision.

    ±0.051 absorbs one-decimal rounding; 0.05% relative absorbs "9.75 million" for 9,749,780.
    A 1% tolerance used to let 66.1 pass for 65.8.
    """
    try:
        target = float(value)
    except (TypeError, ValueError):
        return str(value).lower() in text.lower()
    for raw, scale in _NUM_TOKEN.findall(text):
        try:
            found = float(raw.replace(",", "")) * _SCALE.get(scale or None, 1)
        except ValueError:
            continue
        tol = max(abs(target) * rel, 0.051)
        if scale:  # a scaled figure is rounded at its own precision
            decimals = len(raw.split(".")[1]) if "." in raw else 0
            tol = max(tol, 0.5 * 10 ** -decimals * _SCALE[scale])
        if abs(found - target) <= tol:
            return True
    return False


def check_value(case: dict, result: dict) -> tuple[bool, str]:
    """Evaluate a case's ``checks`` against one final state."""
    checks = case.get("checks") or {}
    text = _answer_body(result)
    failures = []
    if checks.get("no_delegation"):
        if _delegated(result):
            failures.append("delegated an out-of-scope question")
    elif not text:
        return False, "no final answer"
    for n in checks.get("numbers", []):
        if not _num_in_text(n, text):
            failures.append(f"missing {n}")
    for group in checks.get("any_of", []):
        if not any(s.lower() in text.lower() for s in group):
            failures.append(f"none of {group}")
    if checks.get("figure") and not _has_figure(result):
        failures.append("no figure")
    return (not failures), ("ok" if not failures else "; ".join(failures))


# ── determinism signatures ──────────────────────────────────────────────────────
def fact_signature(result: dict) -> list:
    """Accepted facts, normalised: slot ids and wording excluded, values at display precision."""
    sig = set()
    for f in (result.get("facts") or {}).values():
        value = f.get("value")
        sig.add((
            (f.get("entity") or "").strip().lower(),
            f.get("attribute_norm") or (f.get("attribute") or "").strip().lower(),
            None if value is None else round(float(value), 2),
            glossary.canonical_unit(f.get("unit")),
            (f.get("time") or "")[:16].replace(" ", "T"),
            tuple(f.get("items") or ()),
        ))
    return sorted(sig, key=json.dumps)


_NUM_UNIT = re.compile(r"(-?\d[\d,]*(?:\.\d+)?)\s*(°C|degC|µm|um|mm/s|mbara|mbar|bar|kW|MW|t/h|%|INR|₹|minutes|min|hours|h\b)")


def answer_numbers(result: dict) -> list:
    """Numbers with units the user reads, normalised (units canonical, values to 2 dp)."""
    out = set()
    for raw, unit in _NUM_UNIT.findall(_answer_body(result)):
        try:
            out.add((round(float(raw.replace(",", "")), 2), glossary.canonical_unit(unit)))
        except ValueError:
            continue
    return sorted(out, key=json.dumps)


def efficiency(result: dict) -> dict:
    """What answering cost, and how clean the handoffs were. Pure — reads final state."""
    delegations = [e for e in _events(result) if str(e.get("tool", "")).startswith("delegate:")]
    ran = [e for e in delegations if not str(e.get("error", "")).startswith("rejected")]
    ai = [m for m in result.get("messages", []) if isinstance(m, AIMessage)]
    orch_in = sum((m.usage_metadata or {}).get("input_tokens", 0) for m in ai)
    spec_in = sum(e.get("input_tokens", 0) for e in ran)
    return {
        "delegations": [e["tool"].split(":", 1)[1] for e in ran],
        "rejected_tasks": len(delegations) - len(ran),
        "orch_calls": len(ai),
        "inner_calls": sum(e.get("inner_calls", 0) for e in ran),
        "refused_tool_calls": sum(1 for e in _events(result) if str(e.get("error", "")).startswith("refused")),
        "input_tokens": orch_in + spec_in,
        "orch_input_tokens": orch_in,
        "report_chars": sum(e.get("report_chars", 0) for e in ran),
        "reports_with_code": sum(bool(e.get("report_has_code")) for e in ran),
        "exhausted": sum(1 for e in ran if e.get("error")),
        "windows": sorted({w for e in ran for w in (e.get("windows") or [])}),
        "slots": {sid: s.get("status") for sid, s in (result.get("slots") or {}).items()},
    }


def score_case(case: dict, results: list[dict]) -> dict:
    """Score one case over its k runs (k ≥ 1)."""
    want = expected_tools(case)
    per_run = []
    for r in results:
        used = tools_used(r)
        ok, detail = check_value(case, r)
        per_run.append({"route": used, "route_ok": all(_FAMILY_TOOLS[f] & set(used) for f in want),
                        "value_ok": ok, "value_detail": detail, "efficiency": efficiency(r)})
    k = len(results)
    same = (lambda sigs: len({json.dumps(s) for s in sigs}) == 1) if k > 1 else (lambda sigs: None)
    return {
        "id": case["id"], "kind": case.get("kind", ""), "query": case["query"], "k": k,
        "expected_tools": sorted(want),
        "route_ok": all(p["route_ok"] for p in per_run),
        "value_ok": per_run[0]["value_ok"],
        "value_detail": per_run[0]["value_detail"],
        "pass_k": all(p["value_ok"] for p in per_run),
        "value_rate": sum(p["value_ok"] for p in per_run) / k,
        "fact_det": same([fact_signature(r) for r in results]),
        "answer_det": same([answer_numbers(r) for r in results]),
        "window_det": same([efficiency(r)["windows"] for r in results]),
        "runs": per_run,
    }


def _mean(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def summarize(results: list[dict]) -> dict:
    n = len(results)
    effs = [p["efficiency"] for r in results for p in r.get("runs", [])]
    return {
        "cases": n,
        "k": max((r.get("k", 1) for r in results), default=1),
        "route_acc": _mean([r["route_ok"] for r in results]),
        "value_acc": _mean([r["value_rate"] for r in results]),
        "pass_k": _mean([r["pass_k"] for r in results]),
        "fact_determinism": _mean([r["fact_det"] for r in results]),
        "answer_determinism": _mean([r["answer_det"] for r in results]),
        "window_determinism": _mean([r["window_det"] for r in results]),
        "avg_input_tokens": _mean([e["input_tokens"] for e in effs]),
        "avg_orch_calls": _mean([e["orch_calls"] for e in effs]),
        "rejected_tasks": sum(e["rejected_tasks"] for e in effs),
        "refused_tool_calls": sum(e["refused_tool_calls"] for e in effs),
        "reports_with_code": sum(e["reports_with_code"] for e in effs),
        "exhausted": sum(e["exhausted"] for e in effs),
    }


def format_report(results: list[dict], meta: dict | None = None) -> str:
    s = summarize(results)

    def pct(v):
        return "n/a" if v is None else f"{v:.0%}"

    lines = ["# Golden-dataset evaluation", ""]
    if meta:
        lines += [f"- snapshot: {json.dumps(meta.get('snapshot', {}))}",
                  f"- model: {json.dumps(meta.get('model', {}))}", ""]
    lines += [
        f"**Routing {pct(s['route_acc'])} · Value {pct(s['value_acc'])} · pass^{s['k']} {pct(s['pass_k'])} · "
        f"Fact determinism {pct(s['fact_determinism'])} · Answer-number determinism "
        f"{pct(s['answer_determinism'])} · Window determinism {pct(s['window_determinism'])}** "
        f"({s['cases']} cases × {s['k']} runs)", "",
        f"avg input tokens {s['avg_input_tokens'] or 0:.0f} · avg orchestrator calls "
        f"{s['avg_orch_calls'] or 0:.1f} · rejected tasks {s['rejected_tasks']} · refused tool calls "
        f"{s['refused_tool_calls']} · reports with code {s['reports_with_code']} · exhausted {s['exhausted']}", "",
        "| case | route | value (rate) | pass^k | same facts | same answer numbers | same windows | detail |",
        "|---|---|---|---|---|---|---|---|",
    ]
    mark = {True: "yes", False: "NO", None: "-"}
    for r in results:
        lines.append(f"| {r['id']} | {'PASS' if r['route_ok'] else 'FAIL'} | {r['value_rate']:.0%} | "
                     f"{mark[r['pass_k']]} | {mark[r['fact_det']]} | {mark[r['answer_det']]} | "
                     f"{mark[r['window_det']]} | {r['value_detail']} |")
    return "\n".join(lines)
