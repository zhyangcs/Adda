#!/bin/bash
set -e

echo "Starting Adda services..."

# Start Flask backend first (Nginx needs it to be ready)
echo "Starting Flask backend on port 5000..."
cd /adda
export PYTHONPATH="/adda:/adda/pd2sql:$PYTHONPATH"
python frontend/app.py &

# Wait for Flask to be ready
echo "Waiting for Flask to start..."
until curl -s http://127.0.0.1:5000/ > /dev/null 2>&1; do
    sleep 1
done
echo "Flask is ready."

# Start Nginx in foreground (daemon off is already in nginx.conf)
echo "Starting Nginx..."
exec nginx
