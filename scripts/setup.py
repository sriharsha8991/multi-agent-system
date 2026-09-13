#!/usr/bin/env python
"""One-command setup: env file, dependencies, databases, seeding, verification.

    python scripts/setup.py

Brings a clean clone to a fully seeded, verified, ready-to-query state. Every step is
idempotent, so it is safe to re-run after a partial or failed setup.

Standard library only, on purpose: this runs *before* requirements are installed.

Options:
    --skip-deps     don't run pip install (you manage the environment yourself)
    --skip-seed     set up schemas but don't generate data (fast, no agents to run)
    --force-seed    re-seed even if the databases already hold data
    --no-input      never prompt; warn about a missing API key and carry on
    --reset         destroy the database volumes first, then set up from scratch
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIN_PYTHON = (3, 11)
DB_SERVICES = ("postgres", "neo4j")
HEALTH_TIMEOUT_S = 180

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ── output ───────────────────────────────────────────────────────────────────
_STEP = 0
_TOTAL = 6

# Bold only when a terminal will actually render it: piping to a file, or a Windows
# console without VT processing, would otherwise print literal "[1m" noise.
_BOLD, _RESET = ("\033[1m", "\033[0m") if (
    sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
) else ("", "")


def step(title: str) -> None:
    global _STEP
    _STEP += 1
    print(f"\n{_BOLD}[{_STEP}/{_TOTAL}] {title}{_RESET}", flush=True)


def ok(msg: str) -> None:
    print(f"   OK    {msg}", flush=True)


def info(msg: str) -> None:
    print(f"   ...   {msg}", flush=True)


def warn(msg: str) -> None:
    print(f"   WARN  {msg}", flush=True)


def die(msg: str, fix: str = "") -> "NoReturn":  # type: ignore[valid-type]
    print(f"\n   FAIL  {msg}", file=sys.stderr)
    if fix:
        print(f"         -> {fix}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str], *, capture: bool = False, check: bool = True,
        cwd: Path = ROOT) -> subprocess.CompletedProcess:
    """Run a command, streaming its output unless we need to read it."""
    return subprocess.run(
        cmd, cwd=cwd, check=check, text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


# ── steps ────────────────────────────────────────────────────────────────────
def check_prerequisites() -> list[str]:
    """Verify Python and Docker before we change anything on disk."""
    step("Checking prerequisites")

    if sys.version_info < MIN_PYTHON:
        die(f"Python {'.'.join(map(str, MIN_PYTHON))}+ required, "
            f"found {sys.version.split()[0]}")
    ok(f"Python {sys.version.split()[0]}")

    if not shutil.which("docker"):
        die("Docker not found on PATH",
            "install Docker Desktop: https://docs.docker.com/get-docker/")

    try:
        run(["docker", "info"], capture=True)
    except subprocess.CalledProcessError:
        die("Docker is installed but the daemon is not responding",
            "start Docker Desktop and re-run this script")
    ok("Docker daemon is running")

    # `docker compose` (v2 plugin) with a fallback to legacy `docker-compose`.
    for candidate in (["docker", "compose"], ["docker-compose"]):
        try:
            run(candidate + ["version"], capture=True)
            ok(f"Compose available ({' '.join(candidate)})")
            return candidate
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    die("Docker Compose not found",
        "install Compose v2: https://docs.docker.com/compose/install/")


def ensure_env(interactive: bool) -> None:
    """Create .env from the template and make sure the Gemini key is set."""
    step("Setting up .env")

    env, example = ROOT / ".env", ROOT / ".env.example"
    if not env.exists():
        if not example.exists():
            die(".env.example is missing, cannot create .env")
        shutil.copyfile(example, env)
        ok("created .env from .env.example")
    else:
        ok(".env already exists (left untouched)")

    lines = env.read_text(encoding="utf-8").splitlines()
    key = ""
    for line in lines:
        if line.strip().startswith("GEMINI_API_KEY="):
            key = line.split("=", 1)[1].strip()
            break

    if key:
        ok("GEMINI_API_KEY is set")
        return

    print("\n   The data layer works without it, but the agents need a Gemini API key.")
    print("   Get one free at https://aistudio.google.com/apikey")

    entered = ""
    if interactive and sys.stdin.isatty():
        try:
            entered = input("\n   Paste your GEMINI_API_KEY (or press Enter to skip): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()

    if entered:
        # Replace the existing empty assignment if present, else append.
        for i, line in enumerate(lines):
            if line.strip().startswith("GEMINI_API_KEY="):
                lines[i] = f"GEMINI_API_KEY={entered}"
                break
        else:
            lines += ["", "# Gemini API key - https://aistudio.google.com/apikey",
                      f"GEMINI_API_KEY={entered}"]
        env.write_text("\n".join(lines) + "\n", encoding="utf-8")
        ok("GEMINI_API_KEY written to .env")
    else:
        warn("no GEMINI_API_KEY - setup continues, but the agents will not run.")
        warn("add this line to .env when you have one:  GEMINI_API_KEY=your-key-here")


def install_dependencies(skip: bool) -> None:
    step("Installing Python dependencies")
    if skip:
        ok("skipped (--skip-deps)")
        return
    info("pip install -r requirements.txt (a few minutes on a cold cache)")
    try:
        run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
    except subprocess.CalledProcessError:
        die("dependency installation failed",
            "check the pip output above; a virtualenv is recommended")
    ok("dependencies installed")


def start_databases(compose: list[str], reset: bool) -> None:
    step("Starting PostgreSQL and Neo4j")

    if reset:
        info("--reset: removing existing containers and data volumes")
        run(compose + ["down", "-v"], check=False)

    run(compose + ["up", "-d", *DB_SERVICES])
    info("waiting for both databases to report healthy")

    deadline = time.time() + HEALTH_TIMEOUT_S
    pending = set(DB_SERVICES)
    while pending and time.time() < deadline:
        for service in sorted(pending):
            if _is_healthy(compose, service):
                ok(f"{service} is healthy")
                pending.discard(service)
        if pending:
            time.sleep(2)

    if pending:
        die(f"timed out after {HEALTH_TIMEOUT_S}s waiting for: {', '.join(sorted(pending))}",
            f"inspect with: {' '.join(compose)} logs {' '.join(sorted(pending))}")


def _is_healthy(compose: list[str], service: str) -> bool:
    """True once the container's healthcheck passes (compose defines one for both)."""
    try:
        cid = run(compose + ["ps", "-q", service], capture=True).stdout.strip()
        if not cid:
            return False
        out = run(["docker", "inspect", "--format", "{{json .State}}", cid.splitlines()[0]],
                  capture=True).stdout
        state = json.loads(out)
    except (subprocess.CalledProcessError, json.JSONDecodeError, IndexError):
        return False
    if state.get("Status") != "running":
        return False
    health = (state.get("Health") or {}).get("Status")
    return health in (None, "healthy")


def seed(skip: bool, force: bool) -> bool:
    step("Creating schemas and seeding data")

    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}

    def script(name: str) -> None:
        try:
            subprocess.run([sys.executable, str(ROOT / "scripts" / name)],
                           cwd=ROOT, env=env, check=True)
        except subprocess.CalledProcessError:
            die(f"scripts/{name} failed", "see the output above")

    # Check BEFORE touching the schema. init_databases.py runs DROP ... CASCADE on every
    # table, so asking this question afterwards is always answered "empty" — which would
    # both force a needless 27M-value regeneration and make --skip-seed silently destroy
    # an existing database.
    if _already_seeded(env) and not force:
        ok("databases already hold data - nothing to do")
        info("re-seed from scratch with:  python scripts/setup.py --force-seed")
        return True

    info("initialising schemas, roles and constraints")
    script("init_databases.py")
    ok("schemas ready")

    if skip:
        ok("seeding skipped (--skip-seed)")
        return False

    info("generating ~27.5M telemetry values across 5 systems (a few minutes)")
    script("seed_all.py")
    ok("both databases seeded")
    return True


def _already_seeded(env: dict) -> bool:
    """Cheap check so a re-run doesn't regenerate 27M values needlessly."""
    probe = (
        "import sys; sys.path.insert(0, 'src');"
        "from mas.db import postgres;"
        "c = postgres.connect();"
        "print(postgres.fetchall(c, 'SELECT count(*) FROM run_metadata')[0][0])"
    )
    try:
        out = subprocess.run([sys.executable, "-c", probe], cwd=ROOT, env=env,
                             capture_output=True, text=True, timeout=60)
        return out.returncode == 0 and int(out.stdout.strip().splitlines()[-1]) > 0
    except Exception:
        return False


def verify(has_data: bool) -> bool:
    step("Verifying with the 22 quality gates")
    if not has_data:
        ok("skipped - the gates need seeded data")
        return True

    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate.py")],
                            cwd=ROOT, env=env)
    if result.returncode != 0:
        warn("some gates are red - see the report above")
        return False
    ok("22/22 gates green")
    return True


def summary(gates_green: bool, seeded: bool) -> None:
    print("\n" + "=" * 74)
    print("  Setup complete" if gates_green else "  Setup finished with warnings")
    print("=" * 74)
    print("\n  Try it:")
    if seeded:
        print('    python scripts/ask.py "Which BFP ran hotter over the last 7 days?"')
        print("    langgraph dev --port 2025        # step through every agent in Studio")
    print("    python -m pytest -q              # run the test suite")
    print("    docker compose down              # stop the databases (-v wipes data)")
    print()


def main() -> int:
    p = argparse.ArgumentParser(
        description="One-command setup for the multi-agent analytics stack.")
    p.add_argument("--skip-deps", action="store_true", help="don't run pip install")
    p.add_argument("--skip-seed", action="store_true", help="schemas only, no data")
    p.add_argument("--force-seed", action="store_true", help="re-seed even if data exists")
    p.add_argument("--no-input", action="store_true", help="never prompt")
    p.add_argument("--reset", action="store_true", help="destroy data volumes first")
    args = p.parse_args()

    print("=" * 74)
    print("  Multi-Agent Industrial Asset Analytics - setup")
    print("=" * 74)

    compose = check_prerequisites()
    ensure_env(interactive=not args.no_input)
    install_dependencies(args.skip_deps)
    start_databases(compose, args.reset)
    has_data = seed(args.skip_seed, args.force_seed)
    gates_green = verify(has_data)

    summary(gates_green, seeded=has_data)
    return 0 if gates_green else 1


if __name__ == "__main__":
    raise SystemExit(main())
