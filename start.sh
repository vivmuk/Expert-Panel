#!/bin/bash
# Railway start script - uses PORT environment variable

# Don't exit on error immediately - capture diagnostics first
set +e

# Use PORT from environment (Railway sets this automatically)
PORT=${PORT:-5000}

# Ensure we're in the right directory
cd /app || {
    echo "ERROR: Cannot cd to /app"
    exit 1
}

echo "=========================================="
echo "Starting Expert Panel Application"
echo "PORT: $PORT (from environment: ${PORT:-not set, using default 5000})"
echo "Working Directory: $(pwd)"
echo "Python Version: $(python3 --version 2>&1 || python --version 2>&1)"
echo "Gunicorn Version: $(python3 -m gunicorn --version 2>&1 || echo 'not found')"
echo "Health check will be available at: http://0.0.0.0:$PORT/health"
echo "=========================================="

# Check if app.py exists
if [ ! -f "app.py" ]; then
    echo "ERROR: app.py not found in $(pwd)!"
    echo "Files in current directory:"
    ls -la
    exit 1
fi

# Test Python import (this will catch import errors early)
echo "Testing app import..."
IMPORT_ERROR=$(python3 -c "import app; print('OK')" 2>&1 || python -c "import app; print('OK')" 2>&1)
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to import app module"
    echo "Import error output:"
    echo "$IMPORT_ERROR"
    echo "Python path:"
    python3 -c "import sys; print('\n'.join(sys.path))" 2>&1 || python -c "import sys; print('\n'.join(sys.path))" 2>&1
    exit 1
fi
echo "✓ App imported successfully"

echo ""
echo "✓ All pre-flight checks passed"
echo "Starting gunicorn on 0.0.0.0:$PORT with 2 workers"
echo "Application will be ready to accept connections shortly..."
echo ""

# Start gunicorn with all configuration
# Using python3 explicitly, fallback to python
PYTHON_CMD=$(command -v python3 || command -v python)

# Now exit on error for gunicorn
set -e

# Execute gunicorn - this replaces the current process
exec $PYTHON_CMD -m gunicorn \
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

