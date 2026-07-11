#!/bin/sh
set -eu

mkdir -p /app/data /app/generated
chown -R probe:probe /app/data /app/generated

exec gosu probe "$@"
