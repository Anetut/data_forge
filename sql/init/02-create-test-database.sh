#!/bin/sh
# A second database with the same schema, used only by the integration tests.
# Runs once on an empty volume. On an existing volume run it by hand:
#   docker compose exec postgres sh /docker-entrypoint-initdb.d/02-create-test-database.sh
set -e

TEST_DB="${POSTGRES_TEST_DB:-dataforge_test}"

psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE DATABASE $TEST_DB"
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$TEST_DB" \
    -f /docker-entrypoint-initdb.d/01-create-tables.sql
