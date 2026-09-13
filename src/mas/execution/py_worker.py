"""Sandbox worker — runs inside a separate interpreter (or container), one per delegation.

Protocol: one JSON request per stdin line, one JSON response per stdout line.

    {"op": "run", "code": "...", "frames_file": "frames_1.pkl" | null, "use": ["t3"],
     "out": "figure_2.png"}
    → {"ok": true, "stdout": "...", "error": null,
       "figures": [{"file": "figure_2.png", "title": "..."}, ...]}
    {"op": "exit"}

The namespace persists across requests, so an analysis split over several calls keeps its
imports and variables (a traced run failed twice with ``name 'KMeans' is not defined``
because every call started empty). Seeds are fixed before any user code runs.

**Figures.** Every figure the code draws is kept: whatever it saves (to ``OUT`` or any
name — the path is redirected into the session directory) and any figure left open
unsaved. A figure was previously kept only when the code remembered ``plt.savefig(OUT)``,
so an analysis that drew a chart but saved it under another name returned nothing.
Presentation defaults (size, resolution, grid, palette, readable dates) are set once so a
plain ``df.plot()`` already renders legibly; the analysis code decides everything else.

Imports nothing from ``mas`` — the container image carries only the scientific stack.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import pickle
import random
import sys
from pathlib import Path

_MAX_STDOUT = 4000
#: Figures kept per call — a runaway loop of plt.figure() must not flood the store.
MAX_FIGURES = 8

PLOT_STYLE = {
    "figure.figsize": (12, 6),
    "figure.dpi": 110,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
    "axes.grid": True,
    "grid.alpha": 0.3,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.fontsize": 9,
    "legend.framealpha": 0.85,
    "lines.linewidth": 1.4,
    "date.converter": "concise",
}


def _title(fig) -> str:
    sup = getattr(fig, "_suptitle", None)
    if sup is not None and sup.get_text():
        return sup.get_text()[:160]
    for ax in fig.axes:
        if ax.get_title():
            return ax.get_title()[:160]
    return ""


def main() -> int:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    import pandas as pd
    from cycler import cycler
    from matplotlib.figure import Figure

    matplotlib.rcParams.update(PLOT_STYLE)
    matplotlib.rcParams["axes.prop_cycle"] = cycler(color=plt.get_cmap("tab10").colors)
    random.seed(0)
    np.random.seed(0)

    workdir = Path(os.environ.get("MAS_SANDBOX_WORKDIR", "."))
    proto = sys.stdout
    dfs: dict[str, pd.DataFrame] = {}
    ns: dict = {"pd": pd, "np": np, "plt": plt, "dfs": dfs}

    # Every save lands in the session directory under a managed name, whatever path the code
    # passed, and is recorded so unsaved figures can be told apart from saved ones.
    saved: dict[int, str] = {}
    state = {"stem": "figure", "n": 0}
    original_savefig = Figure.savefig

    def managed_savefig(self, fname=None, *args, **kwargs):
        if id(self) in saved:
            name = saved[id(self)]
        else:
            if len(saved) >= MAX_FIGURES:
                return None
            state["n"] += 1
            name = f"{state['stem']}.png" if state["n"] == 1 else f"{state['stem']}_{state['n']}.png"
            saved[id(self)] = name
        kwargs.pop("format", None)
        return original_savefig(self, workdir / name, *args, format="png", **kwargs)

    Figure.savefig = managed_savefig

    for line in sys.stdin:
        if not line.strip():
            continue
        req = json.loads(line)
        if req.get("op") == "exit":
            break
        buf = io.StringIO()
        out_name = Path(req.get("out", "figure.png")).name
        state.update(stem=Path(out_name).stem, n=0)
        saved.clear()
        figures: list[dict] = []
        try:
            if req.get("frames_file"):
                with open(workdir / req["frames_file"], "rb") as fh:
                    dfs.update(pickle.load(fh))
            use = req.get("use") or []
            ns["df"] = dfs[use[0]] if use else None
            ns["OUT"] = out_name
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                exec(compile(req["code"], "<analysis>", "exec"), ns)  # noqa: S102 — isolated worker
                for num in plt.get_fignums():
                    fig = plt.figure(num)
                    if id(fig) not in saved and fig.axes:
                        fig.savefig(out_name)
            resp = {"ok": True, "stdout": buf.getvalue()[-_MAX_STDOUT:], "error": None}
        except Exception as e:  # noqa: BLE001 — reported back to the agent
            resp = {"ok": False, "stdout": buf.getvalue()[-_MAX_STDOUT:],
                    "error": f"{type(e).__name__}: {e}"}
        finally:
            titles = {id(plt.figure(n)): _title(plt.figure(n)) for n in plt.get_fignums()}
            for fig_id, name in saved.items():
                if (workdir / name).exists():
                    figures.append({"file": name, "title": titles.get(fig_id, "")})
            plt.close("all")
        resp["figures"] = figures
        proto.write(json.dumps(resp) + "\n")
        proto.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
