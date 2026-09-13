"""Run the golden-dataset evaluation against the live orchestrator.

Executes each golden query k times through the real agents and scores routing, value,
pass^k and information determinism (facts, answer numbers, windows). Writes
eval/report[-label].md and .json.

    python scripts/run_eval.py [label] [--k 3] [--cases A1,A4]

Makes live Gemini calls (k × cases full runs) and hits Postgres/Neo4j. The report header pins
the data snapshot (run_metadata) and the model sampling config, so runs are comparable.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from mas.config import get_settings        # noqa: E402
from mas.db import postgres                 # noqa: E402
from mas.eval import golden as G            # noqa: E402
from mas.orchestrator import run            # noqa: E402


def snapshot() -> dict:
    conn = postgres.connect(reader=True)
    try:
        meta = dict(postgres.fetchall(conn, "SELECT key, value FROM run_metadata"))
    finally:
        conn.close()
    return {k: meta.get(k) for k in ("generator_version", "master_seed", "now_anchor",
                                     "window_start", "window_end")}


def model_config() -> dict:
    s = get_settings()
    return {"model": s.gemini_reasoning_model, "temperature": s.gemini_temperature,
            "seed": s.gemini_seed, "specialist_thinking_budget": s.specialist_thinking_budget,
            "sandbox": s.py_sandbox_backend}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("label", nargs="?", default="")
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--cases", default="", help="comma-separated case ids to run")
    args = ap.parse_args()

    data = G.load_golden(ROOT / "eval" / "golden_dataset.json")
    wanted = {c.strip() for c in args.cases.split(",") if c.strip()}
    cases = [c for c in data["cases"] if not wanted or c["id"] in wanted]
    meta = {"snapshot": snapshot(), "model": model_config()}
    if data.get("meta", {}).get("snapshot") and data["meta"]["snapshot"] != meta["snapshot"]:
        print("WARNING: the database snapshot differs from the one the golden set was built on")

    scored = []
    for case in cases:
        print(f"[{case['id']}] {case['query'][:80]}")
        runs = []
        for i in range(args.k):
            try:
                runs.append(run(case["query"]))
            except Exception as e:  # a single hard failure must not abort the eval
                print(f"    run {i + 1} ERROR: {str(e)[:160]}")
                runs.append({"messages": [], "tool_events": [{"tool": "run", "error": str(e)[:300]}]})
        r = G.score_case(case, runs)
        scored.append(r)
        print(f"    route={'ok' if r['route_ok'] else 'X'} value={r['value_rate']:.0%} "
              f"pass^k={r['pass_k']} facts_same={r['fact_det']} answer_same={r['answer_det']} "
              f"({r['value_detail']})")

    stem = f"report-{args.label}" if args.label else "report"
    md = G.format_report(scored, meta)
    (ROOT / "eval" / f"{stem}.md").write_text(md, encoding="utf-8")
    (ROOT / "eval" / f"{stem}.json").write_text(
        json.dumps({"meta": meta, "summary": G.summarize(scored), "results": scored}, indent=2,
                   default=str), encoding="utf-8")
    print("\n" + md)
    print(f"\nwrote eval/{stem}.md and eval/{stem}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
