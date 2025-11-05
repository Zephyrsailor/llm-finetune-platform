#!/bin/sh
set -e

PYTHON_BIN="/app/backend/venv/bin/python"
ALEMBIC_BIN="/app/backend/venv/bin/alembic"
UVICORN_BIN="/app/backend/venv/bin/uvicorn"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "[backend] virtualenv not found; creating fresh environment..."
  python -m venv /app/backend/venv
  PYTHON_BIN="/app/backend/venv/bin/python"
  ALEMBIC_BIN="/app/backend/venv/bin/alembic"
  UVICORN_BIN="/app/backend/venv/bin/uvicorn"
  "$PYTHON_BIN" -m pip install --upgrade pip setuptools wheel
  if [ -f /app/backend/requirements.txt ]; then
    "$PYTHON_BIN" -m pip install -r /app/backend/requirements.txt
  fi
fi

echo "[backend] waiting for database..."
"$PYTHON_BIN" - <<'PYCODE'
import time
import os
import psycopg2

dsn = os.environ.get("DATABASE_URL", "")
if not dsn:
    raise SystemExit("DATABASE_URL is not set")

if dsn.startswith("postgresql+psycopg2://"):
    dsn = "postgresql://" + dsn.split("postgresql+psycopg2://", 1)[1]

start = time.time()
while True:
    try:
        conn = psycopg2.connect(dsn)
        conn.close()
        break
    except Exception as exc:  # noqa: BLE001
        if time.time() - start > 60:
            raise SystemExit(f"database connection timeout: {exc}") from exc
        time.sleep(1)
PYCODE

echo "[backend] applying migrations..."
"$ALEMBIC_BIN" upgrade head

exec "$UVICORN_BIN" app.main:app --host 0.0.0.0 --port 8000
