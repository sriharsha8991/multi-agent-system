"""Run the golden-dataset evaluation against the live orchestrator.

Executes each golden query through the real agents, scores routing/value/determinism, and
writes eval/report.md + eval/report.json.

    python scripts/run_eval.py

Makes live Gemini calls and hits Postgres/Neo4j. Determinism = each query run twice; the
second run replays the recorded trajectory (no supervisor LLM) for the cached cases.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from mas.eval import golden as G          # noqa: E402
from mas.orchestrator import run          # noqa: E402


def main() -> int:
    # the agent writes fresh queries each run; determinism is measured on answer values
    data = G.load_golden(ROOT / "eval" / "golden_dataset.json")

    def _safe_run(q: str):
        try:
            return run(q), None
        except Exception as e:  # a single hard failure must not abort the eval
            return None, str(e)[:140]

    results = []
    for case in data["cases"]:
        q = case["query"]
        print(f"[{case['id']}] {q[:70]}...")
        first, err = _safe_run(q)
        if first is None:
            results.append({
                "id": case["id"], "kind": case["kind"], "route": [],
                "expected_tools": sorted(G.expected_tools(case)), "route_ok": False,
                "value_ok": False, "value_detail": f"run error: {err}", "det_ok": None,
                "steps": 0,
            })
            print(f"    ERROR: {err}")
            continue
        second, _ = _safe_run(q)  # determinism: cached cases replay with no supervisor LLM
        r = G.score_case(case, first, second)
        results.append(r)
        print(f"    route={'ok' if r['route_ok'] else 'X '} "
              f"value={'ok' if r['value_ok'] else 'X '} "
              f"det={'ok' if r['det_ok'] else 'X '}  ({r['value_detail']})")

    report_md = G.format_report(results, data.get("meta"))
    (ROOT / "eval" / "report.md").write_text(report_md, encoding="utf-8")
    (ROOT / "eval" / "report.json").write_text(
        json.dumps({"summary": G.summarize(results), "results": results}, indent=2),
        encoding="utf-8",
    )
    print("\n" + report_md)
    print("\nwrote eval/report.md and eval/report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
