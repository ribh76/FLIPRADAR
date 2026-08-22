FROM python:3.14.2-slim AS production

ARG PIP_VERSION=25.3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.lock ./requirements.lock
RUN pip install --upgrade "pip==${PIP_VERSION}" \
    && pip install -r requirements.lock

COPY backend/ /app/backend/
COPY scripts/ /app/scripts/

EXPOSE 8000

# Uvicorn receives this signal directly because it is the container entrypoint.
# Give its lifespan handler time to close Redis and database connections before
# the orchestrator sends SIGKILL.
STOPSIGNAL SIGTERM

CMD ["python", "-m", "uvicorn", "flipradar.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--timeout-graceful-shutdown", "30"]

# Retain the prior stage name for downstream local users while making
# `production` the explicit release image target.
FROM production AS runtime
