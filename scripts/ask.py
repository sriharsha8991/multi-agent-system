#!/usr/bin/env python
"""Ask the agent team one question from the command line.

    python scripts/ask.py "Which BFP ran hotter over the last 7 days?"

Add --trace to print every delegation, tool call and generated SQL/Cypher/Python
alongside the answer.
"""

from __future__ import annotations

import _bootstrap  # noqa: F401 - side-effect import: puts src/ on sys.path
import sys

from mas.orchestrator import answer_of, format_events, run

_DEFAULT = "Which BFP ran hotter over the last 7 days?"


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--trace"]
    query = args[0] if args else _DEFAULT
    print(f"QUERY: {query}\n")

    result = run(query)

    if "--trace" in sys.argv[1:]:
        print(format_events(result))
        print()
    print(answer_of(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
