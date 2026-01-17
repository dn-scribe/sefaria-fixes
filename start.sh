#!/bin/bash
# Quick start script for local development

echo "Starting JSON Link Viewer & Editor..."
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Set default environment variables
export ADMIN_USER=${ADMIN_USER:-danny}
export PORT=${PORT:-7860}

echo ""
echo "======================================"
echo "Server Configuration:"
echo "  Admin User: $ADMIN_USER"
echo "  Port: $PORT"
echo "======================================"
echo ""
echo "Starting server at http://localhost:$PORT"
echo "Press Ctrl+C to stop"
echo ""

# Start the server
python app.py
