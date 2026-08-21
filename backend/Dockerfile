FROM python:3.14.2-slim AS runtime

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

CMD ["python", "-m", "uvicorn", "flipradar.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
