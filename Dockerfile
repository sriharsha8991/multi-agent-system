# Runner image for the data-layer scripts (seed / validate).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first for layer caching.
COPY pyproject.toml requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Install the package itself.
COPY src ./src
RUN pip install -e .

# Remaining project files (scripts, docs) are bind-mounted by compose in dev,
# but copied here so the image is self-contained for a clean-clone reviewer.
COPY scripts ./scripts

CMD ["sleep", "infinity"]
