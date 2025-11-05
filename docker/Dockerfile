# ---------- Frontend build stage ----------
FROM node:20-bookworm AS frontend-build

WORKDIR /app/frontend

# Enable corepack to use pnpm without global install
RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY frontend ./
RUN pnpm build


# ---------- Backend runtime stage ----------
FROM python:3.11-slim-bookworm AS backend

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/backend/venv/bin:$PATH"

WORKDIR /app/backend

RUN set -eux; \
    export DEBIAN_FRONTEND=noninteractive; \
    apt-get update; \
    for attempt in 1 2 3; do \
      if apt-get install -y --no-install-recommends build-essential libpq-dev curl; then \
        break; \
      fi; \
      if [ "$attempt" = "3" ]; then \
        echo "apt install failed after ${attempt} attempts" >&2; \
        exit 1; \
      fi; \
      echo "apt install failed (attempt ${attempt}), retrying in 5s..." >&2; \
      sleep 5; \
      apt-get update; \
    done; \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./requirements.txt
COPY backend/requirements-dev.txt ./requirements-dev.txt
RUN python -m venv /app/backend/venv \
    && /app/backend/venv/bin/pip install --upgrade pip setuptools wheel \
    && /app/backend/venv/bin/pip install -r requirements.txt

COPY backend /app/backend
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Default command executed by docker-compose. Can be overridden.
CMD ["/entrypoint.sh"]


# ---------- Frontend runtime stage ----------
FROM nginx:1.27-alpine AS frontend

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /app/frontend/dist /usr/share/nginx/html
