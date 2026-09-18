#!/bin/sh
set -e

# Garante que /app/data pertence ao botuser, independente de como
# o volume foi montado pelo host (resolve PermissionError).
mkdir -p /app/data
chown -R botuser:botuser /app/data

# Executa o comando como botuser
exec gosu botuser "$@"