#!/bin/sh
set -eu
: "${VMA_MODEL_TEST_DATABASE_URL:?Set this to the dedicated local vma_l7014_model PostgreSQL database}"
name=$(psql "$VMA_MODEL_TEST_DATABASE_URL" -Atqc 'select current_database()')
if [ "$name" != "vma_l7014_model" ]; then
  echo "Refusing to run destructive migration fixture in database: $name" >&2
  exit 2
fi
server=$(psql "$VMA_MODEL_TEST_DATABASE_URL" -Atqc "select coalesce(inet_server_addr()::text, 'local socket')")
case "$server" in
  127.0.0.1|127.0.0.1/32|::1|::1/128|'local socket') ;;
  *) echo "Refusing to run migration fixture on non-local PostgreSQL server: $server" >&2; exit 2 ;;
esac
exec psql "$VMA_MODEL_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f tests/sql/l7014-model.sql
