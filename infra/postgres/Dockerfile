# Multi-arch PostGIS (official postgis/postgis image lacks arm64). Versions pinned.
FROM postgres:18.6-bookworm
RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-18-postgis-3 postgresql-18-postgis-3-scripts \
 && rm -rf /var/lib/apt/lists/*
COPY init/ /docker-entrypoint-initdb.d/
