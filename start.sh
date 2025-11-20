#!/bin/bash
# Railway start script - uses PORT environment variable

set -e

# Use PORT from environment (Railway sets this automatically)
PORT=${PORT:-5000}

echo "Starting gunicorn on port $PORT"

# Start gunicorn with all configuration
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
    app:app

