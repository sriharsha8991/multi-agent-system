"""Make `mas` importable, export `.env`, and fix console encoding.

Imported for its side effects by every script in this directory. The project is run
from source with no packaging step, so this is what puts ``src/`` on the path.

It also exports ``.env`` into ``os.environ``. Settings reads ``.env`` into its own
object, not into the process environment, so without this LangSmith sees no
configuration and every run started from a script is **silently untraced** — while the
same graph under ``langgraph dev`` traces fine, because the CLI exports ``.env`` itself.

Finally it forces UTF-8 on stdout/stderr: the reports print box-drawing characters and
Windows consoles default to cp1252, which raises ``UnicodeEncodeError`` mid-report.
"""

import pathlib
import sys

_SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
if _SRC.exists() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:  # non-reconfigurable stream (pipe, notebook, older Python)
        pass

try:
    from mas.config import load_env_file

    load_env_file()
except Exception:  # dependencies not installed yet (e.g. scripts/setup.py preflight)
    pass
