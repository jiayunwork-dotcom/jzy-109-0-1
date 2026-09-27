# One-shot image for the Wheatstone bridge calculation service.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# Install dependencies first so the layer caches across source-only changes.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Runs as a non-root user.
RUN useradd --create-home --uid 10001 bridge && USER bridge

EXPOSE 8000

# Container start makes both core endpoints available:
#   POST /bridge/output   -- unbalanced output (+ optional galvanometer load)
#   POST /bridge/solve    -- closed-form solve of the unknown balance arm
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
