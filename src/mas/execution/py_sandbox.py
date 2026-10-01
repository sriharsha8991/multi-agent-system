"""Out-of-process Python execution for the coder (doc 10, S4).

The previous executor ran generated code with ``exec`` inside the application process: no
timeout (an infinite loop hung the run), no isolation, no exception classes in scope, and a
fresh namespace on every call. This module runs ``mas.execution.py_worker`` instead:

* ``subprocess`` backend — a separate interpreter per delegation, ``PYTHONHASHSEED=0``, a
  hard per-call timeout (the process is killed and the session reset), and CPU/memory
  rlimits where the OS supports them (POSIX). Works on any machine with the venv.
* ``docker`` backend — the same worker inside ``--network none --read-only`` with memory,
  CPU and PID limits, source mounted read-only and a per-session scratch directory. This is
  the isolation boundary for untrusted code; build the image from
  ``docker/py-sandbox.Dockerfile``.

A session lives for one delegation (keyed by the delegation id the orchestrator puts in the
specialist's run config) and is closed when the delegation ends.
"""
from __future__ import annotations

import atexit
import itertools
import json
import os
import pickle
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from ..config import get_settings

SRC = Path(__file__).resolve().parents[2]


class SandboxError(RuntimeError):
    """The sandbox could not run the code (timeout, crash, protocol failure)."""


class SandboxSession:
    def __init__(self, backend: str | None = None, timeout_s: int | None = None):
        s = get_settings()
        self.backend = backend or s.py_sandbox_backend
        self.timeout_s = timeout_s or s.py_sandbox_timeout_s
        self.workdir = Path(tempfile.mkdtemp(prefix="mas-py-"))
        self.loaded: set[str] = set()
        self._counter = itertools.count(1)
        self._lines: queue.Queue[str | None] = queue.Queue()
        self.proc = self._spawn()
        threading.Thread(target=self._pump, daemon=True).start()

    # ── process ──────────────────────────────────────────────────────────────
    def _spawn(self) -> subprocess.Popen:
        s = get_settings()
        env = {**os.environ, "PYTHONHASHSEED": "0", "MPLBACKEND": "Agg",
               "PYTHONPATH": str(SRC), "MAS_SANDBOX_WORKDIR": str(self.workdir)}
        if self.backend == "docker":
            cmd = ["docker", "run", "--rm", "-i", "--network", "none", "--read-only",
                   "--memory", s.py_sandbox_memory, "--cpus", "1", "--pids-limit", "128",
                   "--tmpfs", "/tmp", "-e", "PYTHONHASHSEED=0", "-e", "MPLBACKEND=Agg",
                   "-e", "PYTHONPATH=/app/src", "-e", "MAS_SANDBOX_WORKDIR=/work",
                   "-e", "MPLCONFIGDIR=/tmp",
                   "-v", f"{SRC}:/app/src:ro", "-v", f"{self.workdir}:/work", "-w", "/work",
                   # By path, not ``-m mas.execution.py_worker``: running it as a module
                   # executes ``mas/__init__.py`` and ``mas/execution/__init__.py`` first,
                   # and the latter imports timewin -> config -> pydantic_settings, which
                   # the image deliberately does not carry. The worker itself imports
                   # nothing from ``mas``, so the file runs standalone.
                   s.py_sandbox_image, "python", "-u", "/app/src/mas/execution/py_worker.py"]
            preexec = None
        elif self.backend == "subprocess":
            cmd = [sys.executable, "-u", "-m", "mas.execution.py_worker"]
            preexec = _posix_limits if os.name == "posix" else None
        else:
            raise SandboxError(f"unknown sandbox backend {self.backend!r}")
        try:
            return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                    env=env, cwd=str(self.workdir), preexec_fn=preexec)
        except OSError as e:
            raise SandboxError(f"could not start the {self.backend} sandbox: {e}") from e

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self._lines.put(line)
        self._lines.put(None)

    # ── api ──────────────────────────────────────────────────────────────────
    def run(self, code: str, frames: dict, figure_name: str) -> dict:
        """Run ``code`` with ``frames`` ({artifact_id: DataFrame}) in scope.

        Returns ``{"ok", "stdout", "error", "figures": [{"path", "title"}]}`` — every figure
        the code drew, saved or not; raises ``SandboxError`` on a timeout (after killing the
        worker) or if the worker died.
        """
        if self.proc.poll() is not None:
            raise SandboxError("the sandbox process is no longer running")
        new = {k: v for k, v in frames.items() if k not in self.loaded}
        frames_file = None
        if new:
            frames_file = f"frames_{next(self._counter)}.pkl"
            with open(self.workdir / frames_file, "wb") as fh:
                pickle.dump(new, fh)
        request = {"op": "run", "code": code, "frames_file": frames_file,
                   "use": list(frames), "out": figure_name}
        assert self.proc.stdin is not None
        try:
            self.proc.stdin.write(json.dumps(request) + "\n")
            self.proc.stdin.flush()
            line = self._lines.get(timeout=self.timeout_s)
        except queue.Empty:
            self.close(force=True)
            raise SandboxError(f"timed out after {self.timeout_s}s — the session was reset, so "
                               "variables from earlier calls are gone") from None
        except (BrokenPipeError, OSError) as e:
            self.close(force=True)
            raise SandboxError(f"sandbox pipe failed: {e}") from e
        if line is None:
            self.close(force=True)
            raise SandboxError("the sandbox process exited (out of memory or crashed)")
        resp = json.loads(line)
        if resp.get("ok"):
            self.loaded |= set(new)
        resp["figures"] = [{"path": str(self.workdir / f["file"]), "title": f.get("title") or ""}
                           for f in resp.get("figures") or []
                           if (self.workdir / f["file"]).exists()]
        return resp

    def close(self, force: bool = False) -> None:
        try:
            if not force and self.proc.poll() is None and self.proc.stdin:
                self.proc.stdin.write(json.dumps({"op": "exit"}) + "\n")
                self.proc.stdin.flush()
                self.proc.wait(timeout=3)
        except Exception:  # noqa: BLE001
            pass
        if self.proc.poll() is None:
            self.proc.kill()
        shutil.rmtree(self.workdir, ignore_errors=True)


def _posix_limits() -> None:  # pragma: no cover — POSIX only
    import resource

    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024 ** 3, 2 * 1024 ** 3))
    resource.setrlimit(resource.RLIMIT_CPU, (300, 300))


_SESSIONS: dict[str, SandboxSession] = {}
_LOCK = threading.Lock()


def session(key: str | None) -> tuple[SandboxSession, bool]:
    """The session for a delegation, created on first use. Returns (session, ephemeral)."""
    if key is None:
        return SandboxSession(), True
    with _LOCK:
        s = _SESSIONS.get(key)
        if s is None or s.proc.poll() is not None:
            s = _SESSIONS[key] = SandboxSession()
        return s, False


def close_session(key: str) -> None:
    with _LOCK:
        s = _SESSIONS.pop(key, None)
    if s is not None:
        s.close()


@atexit.register
def _close_all() -> None:
    for key in list(_SESSIONS):
        close_session(key)
