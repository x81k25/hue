# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./
RUN uv pip install --system -r pyproject.toml

COPY . .

# move bundled config to a seed location so volume mount at /app/config
# doesn't hide it; api.py copies missing files from here on startup
RUN mkdir -p /app/seed && cp -r /app/config/. /app/seed/ && rm -rf /app/config

# config volume mount target — overridden by HUE_CONFIG_DIR in deployment
ENV HUE_CONFIG_DIR=/app/config \
    HUE_SEED_DIR=/app/seed

# default to API; UI container overrides command in k8s deployment
EXPOSE 8000 8501
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
