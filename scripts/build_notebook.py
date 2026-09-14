"""Write notebooks/demonstration.ipynb — ask the team questions and look inside each run.

    python scripts/build_notebook.py            # write the notebook (no model calls)
    python scripts/build_notebook.py --execute  # also run it (live Gemini calls)

The notebook is deliberately thin: every view lives in ``mas.notebook`` so the same helpers
work from any script or kernel.
"""
import sys
from pathlib import Path

import nbformat as nbf

root = Path(__file__).resolve().parents[1]
cells = []


def md(s: str) -> None:
    cells.append(nbf.v4.new_markdown_cell(s.strip()))


def code(s: str) -> None:
    cells.append(nbf.v4.new_code_cell(s.strip()))


md("""
# Multi-agent plant analytics — demonstration

Ask a question; the team answers it and you see everything that happened inside.

```
question → orchestrator: intent, split into facts (slots), plan
             ├─ graph_agent   narrows: which tags, which alert window     (Neo4j, Cypher)
             ├─ sql_agent     retrieves exactly that data                 (PostgreSQL, SQL)
             └─ coder_agent   analyses it and draws the figures           (Python sandbox)
         → answer checked by code, with Evidence / Gaps and named figures
```

Architecture explained: `docs/agentic_design/11-agents-architecture-explained.md`.
""")

md("## Setup")
code("""
import os, sys
from pathlib import Path

root = Path.cwd()
while not (root / "langgraph.json").exists() and root != root.parent:
    root = root.parent
sys.path.insert(0, str(root / "src"))
os.chdir(root)                      # figures are written under outputs/figures

from mas.config import load_env_file
load_env_file()                     # the whole .env, so LangSmith tracing works too

from mas.notebook import (ask, show_answer, show_plan, show_tool_calls, show_figures,
                          show_data, run_summary, figures_of)

print("gemini key :", "set" if os.getenv("GEMINI_API_KEY") else "MISSING")
print("tracing    :", os.getenv("LANGSMITH_TRACING", "off"))
""")

md("""
## The helpers

| Function | Shows |
|---|---|
| `result = ask(question)` | runs the question, then shows the answer, figures, plan and every tool call; returns the final state |
| `show_answer(result)` | the final answer with the code-written Evidence / Gaps lines |
| `show_figures(result)` | every image the run produced, with its title and file path |
| `show_plan(result)` | the ledger: slots (facts needed), plan steps, status, artifacts |
| `show_tool_calls(result)` | each delegation (brief, status, tokens, time) and every SQL / Cypher / Python call under it |
| `show_data(result, "t4")` | the rows behind a table or record artifact |
| `run_summary(result)` | counts: delegations, tool calls, model calls, tokens, figures |
| `figures_of(result)` | the figure list `[{artifact_id, title, path}]` for your own use |

`ask(question, plan=False, tool_calls=False)` shows only the answer and figures.
""")

md("## Ask a question")
code("""
QUESTION = "What is the latest alert on BFP-A? Plot the bearing temperature during that alert window."

result = ask(QUESTION)
""")

md("## Look again at any part")
code("show_tool_calls(result)")
code("show_figures(result)")
code("run_summary(result)")
code("""
# The rows behind any table or record artifact listed in the plan / tool calls:
data_ids = [k for k, d in result["blackboard"].items() if d.get("kind") in ("table", "records")]
print(data_ids)
if data_ids:
    show_data(result, data_ids[0])
""")

md("""
## Your question

Some to try:
- *Why is the turbine vibrating?* — graph narrows the tags → sql pulls their series → coder analyses and plots
- *Which BFP ran hotter over the last 7 days?*
- *How many minutes was any BFP-A bearing above alarm_hi yesterday?*
- *What did maintenance on the turbine cost, and which part was used most?*
- *Cluster BFP-A's operating regions by load, efficiency and vibration and plot them.*
""")
code("""
my_result = ask("Why is the turbine vibrating?")
""")

nb = nbf.v4.new_notebook()
nb.cells = cells
nb.metadata = {"kernelspec": {"name": "python3", "display_name": "Python 3"},
               "language_info": {"name": "python"}}

nbpath = root / "notebooks" / "demonstration.ipynb"
nbpath.parent.mkdir(exist_ok=True)
if "--execute" in sys.argv[1:]:
    from nbclient import NotebookClient

    print("executing notebook (live Gemini calls)...")
    NotebookClient(nb, timeout=3600, kernel_name="python3",
                   resources={"metadata": {"path": str(root)}}).execute()
nbf.write(nb, str(nbpath))
print("wrote", nbpath)
