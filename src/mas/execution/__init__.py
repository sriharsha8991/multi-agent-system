"""Execution layer (L3): validators and read-only executors. **Nothing here calls an LLM.**

Not to be confused with ``mas.agents.tools`` — the two are stacked, not parallel:

* ``mas.agents.tools`` (L4) holds the seven LangChain ``@tool`` functions the *model*
  calls by name — ``sql_query``, ``graph_query``, ``python_analysis`` and friends. Their
  docstrings are prompt text, and they return ``Command`` updates to graph state.
* ``mas.execution`` (this package, L3) is what those tools call *underneath*. Plain
  Python: validate the generated SQL/Cypher/code, then run it against the read-only
  Postgres role or the Neo4j read session or the AST-restricted sandbox.

The split is the safety boundary (doc 06 §4): nothing a model generates reaches a driver
or the sandbox until it has passed a validator here, and no agent code opens its own
connection — the executors wrap ``mas.db``. ``timewin`` keeps relative-date arithmetic in
code, against the frozen anchor, rather than trusting the model to do date maths.
"""

from .timewin import resolve_window
from .sql_guard import SqlValidationError, default_allowed_tables, validate_sql
from .cypher_guard import CypherValidationError, validate_cypher
from .py_guard import PyValidationError, validate_python

__all__ = [
    "resolve_window",
    "validate_sql", "default_allowed_tables", "SqlValidationError",
    "validate_cypher", "CypherValidationError",
    "validate_python", "PyValidationError",
]
