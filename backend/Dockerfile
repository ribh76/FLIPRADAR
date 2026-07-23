FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY backend/ /app/backend/
COPY scripts/ /app/scripts/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "flipradar.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
