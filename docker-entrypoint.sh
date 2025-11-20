#!/bin/sh
set -e

# Use Railway's PORT if set, otherwise use 8080
PORT=${PORT:-8080}

echo "=========================================="
echo "Starting Expert Panel Application"
echo "PORT: $PORT"
echo "Working Directory: $(pwd)"
echo "=========================================="

# Execute gunicorn with explicit port
exec gunicorn \
    --bind 0.0.0.0:$PORT \
    --workers 2 \
    --timeout 600 \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --preload \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --capture-output \
    --enable-stdio-inheritance \
    --forwarded-allow-ips="*" \
    app:app
