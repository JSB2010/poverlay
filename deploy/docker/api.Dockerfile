# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY apps/api/requirements.txt ./apps/api/requirements.txt
RUN pip install --upgrade pip && pip install -r apps/api/requirements.txt

COPY apps/api ./apps/api

EXPOSE 8787

CMD ["uvicorn", "--app-dir", "/app/apps/api", "app.main:app", "--host", "0.0.0.0", "--port", "8787"]
