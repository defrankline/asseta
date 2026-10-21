#!/usr/bin/env bash
# Least-privilege roles (passwords from environment, never committed):
#   asseta_owner - owns schema, runs migrations (NOT superuser)
#   asseta_app   - API/workers; always subject to RLS (FORCE ROW LEVEL SECURITY)
set -euo pipefail
: "${ASSETA_OWNER_DB_PASSWORD:?required}" "${ASSETA_APP_DB_PASSWORD:?required}" "${KEYCLOAK_DB_PASSWORD:?required}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v owner_pw="$ASSETA_OWNER_DB_PASSWORD" -v app_pw="$ASSETA_APP_DB_PASSWORD" -v kc_pw="$KEYCLOAK_DB_PASSWORD" <<'SQL'
CREATE ROLE asseta_owner LOGIN PASSWORD :'owner_pw';
CREATE ROLE asseta_app LOGIN PASSWORD :'app_pw';
CREATE ROLE keycloak LOGIN PASSWORD :'kc_pw';
CREATE DATABASE asseta OWNER asseta_owner;
CREATE DATABASE keycloak OWNER keycloak;
SQL

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname asseta <<'SQL'
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
ALTER SCHEMA public OWNER TO asseta_owner;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO asseta_app;
ALTER DEFAULT PRIVILEGES FOR ROLE asseta_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO asseta_app;
ALTER DEFAULT PRIVILEGES FOR ROLE asseta_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO asseta_app;
SQL
