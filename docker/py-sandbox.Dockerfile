# Isolated Python sandbox for coder_agent (doc 10, S4).
#
#   docker build -f docker/py-sandbox.Dockerfile -t mas-py-sandbox:latest .
#   PY_SANDBOX_BACKEND=docker   (in .env)
#
# Only the scientific stack — the worker imports nothing else from the application.
# The container is started per delegation by src/mas/execution/py_sandbox.py with
# --network none --read-only --memory --cpus --pids-limit, the source mounted read-only
# at /app/src and a per-session scratch directory at /work.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    MPLBACKEND=Agg \
    PYTHONPATH=/app/src

RUN pip install --no-cache-dir \
        "numpy>=1.26,<3" "pandas>=2.1,<3" "scipy>=1.11,<2" \
        "scikit-learn>=1.3,<2" "matplotlib>=3.8,<4" \
    && useradd --create-home --uid 10001 sandbox

USER sandbox
WORKDIR /work
