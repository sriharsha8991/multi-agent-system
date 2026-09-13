"""Graph entrypoints for `langgraph dev` (LangGraph Studio).

Exposes the orchestrator **and** each specialist as its own assistant, so you can step
through the team end-to-end or drive a single agent in isolation to see exactly what it
does. Referenced from ``langgraph.json``.

Absolute imports on purpose: the LangGraph CLI loads this file directly (not as part of
the package), so relative imports would fail. The project is run from source with no
packaging step, so this file also puts ``src/`` on the path itself rather than assuming
``mas`` was pip-installed.
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mas.agents import specialists
from mas.orchestrator.agent import build_agent

# The full team: orchestrator delegating to graph/sql/coder specialists.
orchestrator = build_agent()

# Individual specialists — useful for inspecting one agent's tool loop on its own.
sql_agent = specialists.sql_agent()
graph_agent = specialists.graph_agent()
coder_agent = specialists.coder_agent()
