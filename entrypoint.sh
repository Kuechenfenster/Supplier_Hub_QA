#!/bin/bash
set -e

DB_URL="${DATABASE_URL:-postgresql://supplier:supplier123@db:5432/supplier_hub}"

echo "==> Supplier Hub — Coolify Entrypoint"
echo "==> DATABASE_URL: ${DB_URL//:*@/:***@}"

if [[ "$DB_URL" == postgresql://* ]] || [[ "$DB_URL" == postgres://* ]]; then
    echo "==> Waiting for PostgreSQL..."
    for i in $(seq 1 30); do
        if python -c "
import psycopg2, os, sys
try:
    conn = psycopg2.connect(os.getenv('DATABASE_URL', '$DB_URL'))
    conn.close()
    sys.exit(0)
except Exception as e:
    sys.exit(1)
" 2>/dev/null; then
            echo "==> PostgreSQL ready"
            break
        fi
        echo "    attempt $i/30 — waiting..."
        sleep 2
    done
fi

echo "==> Running database migrations..."
python backend/migrate.py || true

echo "==> Running admin seed..."
python backend/init_db.py || true

echo "==> Starting application..."
exec "$@"