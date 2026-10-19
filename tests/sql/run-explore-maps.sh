#!/bin/sh
set -eu
: "${VMA_EXPLORE_TEST_DATABASE_URL:?Set this to the dedicated local vma_explore_performance PostgreSQL database}"
name=$(psql "$VMA_EXPLORE_TEST_DATABASE_URL" -Atqc 'select current_database()')
if [ "$name" != "vma_explore_performance" ]; then
  echo "Refusing to run transactional Explore fixture in database: $name" >&2
  exit 2
fi
server=$(psql "$VMA_EXPLORE_TEST_DATABASE_URL" -Atqc "select coalesce(inet_server_addr()::text, 'local socket')")
case "$server" in
  127.0.0.1|127.0.0.1/32|::1|::1/128|'local socket') ;;
  *) echo "Refusing to run migration fixture on non-local PostgreSQL server: $server" >&2; exit 2 ;;
esac
psql "$VMA_EXPLORE_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f tests/sql/explore-maps.sql
if [ "${VMA_EXPLORE_BENCHMARK:-0}" = "1" ]; then
  psql "$VMA_EXPLORE_TEST_DATABASE_URL" -v ON_ERROR_STOP=1 -f tests/sql/explore-maps-benchmark.sql
fi
