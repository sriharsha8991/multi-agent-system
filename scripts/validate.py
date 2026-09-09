#!/usr/bin/env python
"""Run the 22 quality gates and print the report. Exits non-zero on any failure."""

from __future__ import annotations

import _bootstrap  # noqa: F401
import sys

from mas.config import get_settings
from mas.eval import consistency


def main() -> int:
    settings = get_settings()
    results = consistency.run_all(settings)
    print(consistency.format_report(results))
    return 0 if consistency.all_passed(results) else 1


if __name__ == "__main__":
    sys.exit(main())
