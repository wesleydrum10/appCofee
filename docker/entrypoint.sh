#!/bin/sh
set -eu

# Instância única: comandos administrativos/testes não executam migrations extras.
if [ "${RUN_MIGRATIONS:-true}" = "true" ] && { [ "${1:-}" = "gunicorn" ] || { [ "${1:-}" = "python" ] && [ "${2:-}" = "manage.py" ] && [ "${3:-}" = "runserver" ]; }; }; then
    python manage.py migrate --noinput
fi

# Expandir PORT sem shell intermediário entre o Gunicorn e os sinais do container.
if [ "${1:-}" = "gunicorn" ]; then
    exec "$@" --bind "0.0.0.0:${PORT:-8000}"
fi
exec "$@"
