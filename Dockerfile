# Runner image for the scripts (seed / validate / eval / ask).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONIOENCODING=utf-8

# The project is run from source with no packaging step, so `mas` is imported off
# PYTHONPATH rather than being pip-installed. scripts/_bootstrap.py does the same
# thing for direct script runs; this covers `python -m pytest` and `python -c`.
ENV PYTHONPATH=/app/src

WORKDIR /app

# Install deps first for layer caching — requirements.txt is the single source of truth.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Project files. src/scripts/tests are bind-mounted by compose in dev, but copied
# here so the image is self-contained for a clean-clone reviewer.
COPY pytest.ini ./
COPY src ./src
COPY scripts ./scripts
COPY tests ./tests

CMD ["sleep", "infinity"]
