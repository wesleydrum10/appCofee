#!/bin/sh
set -eu

# Apply migrations only when starting the default development server.
if [ "${1:-}" = "python" ] && [ "${2:-}" = "manage.py" ] && [ "${3:-}" = "runserver" ]; then
    python manage.py migrate --noinput
fi

exec "$@"
