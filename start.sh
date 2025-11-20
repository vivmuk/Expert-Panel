#!/bin/bash
# Railway start script - uses PORT environment variable

set -e  # Exit on error

# Railway sets PORT automatically - use it or default to 5000
PORT="${PORT:-5000}"

# Ensure we're in the right directory
cd /app || {
    echo "ERROR: Cannot cd to /app"
    exit 1
}

echo "=========================================="
echo "Starting Expert Panel Application"
echo "PORT: $PORT"
echo "Working Directory: $(pwd)"
echo "Health check: http://0.0.0.0:$PORT/health"
echo "=========================================="

# Verify app.py exists
if [ ! -f "app.py" ]; then
    echo "ERROR: app.py not found in $(pwd)!"
    exit 1
fi

# Test Python import
echo "Testing app import..."
python3 -c "import app" || python -c "import app" || {
    echo "ERROR: Failed to import app module"
    exit 1
}
echo "✓ App imported successfully"

# Find Python executable
PYTHON_CMD=$(command -v python3 || command -v python)

# Start gunicorn - bind to 0.0.0.0 (all interfaces) on the PORT from environment
# Use exec to replace shell process with gunicorn
exec "$PYTHON_CMD" -m gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers 2 \
    --timeout 600 \
    --keep-alive 2 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --preload \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --forwarded-allow-ips="*" \
    app:app

