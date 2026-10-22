#!/usr/bin/env bash
# Idempotent: role + database for the MLflow backend store (works on fresh AND existing volumes, unlike init/).
# Run by the `mlflow-db-init` compose one-shot as the Postgres superuser; passwords only from the environment.
set -euo pipefail
: "${PGPASSWORD:?required}" "${MLFLOW_DB_PASSWORD:?required}"
psql -v ON_ERROR_STOP=1 -h postgres -U postgres -d postgres -v pw="$MLFLOW_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE mlflow LOGIN PASSWORD %L', :'pw') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mlflow')
\gexec
SELECT format('ALTER ROLE mlflow PASSWORD %L', :'pw')
\gexec
SELECT 'CREATE DATABASE mlflow OWNER mlflow' WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'mlflow')
\gexec
SQL
