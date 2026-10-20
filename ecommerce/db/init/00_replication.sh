#!/bin/bash
# Crea el rol de replicación y permite conexiones de replicación desde la red de compose.
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "create role replicator with replication login password 'replicator'"
echo "host replication replicator all md5" >> "$PGDATA/pg_hba.conf"
