#!/bin/bash
# /home/life/start_life.sh
# Version: 1.0.0
# Purpose: Quick start script for Life family archive app
# Created: 2025-06-11

set -e

echo "Life Family Archive System"
echo "========================="

# Check if running from correct directory
if [ ! -d "app" ] || [ ! -f "app/life.py" ]; then
    echo "Error: This script must be run from /home/life directory"
    echo "Current directory: $(pwd)"
    echo ""
    echo "Please run:"
    echo "  cd /home/life"
    echo "  ./start_life.sh"
    exit 1
fi

# Check Python3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python3 is not installed"
    exit 1
fi

# Activate virtual environment if exists
if [ -d "venv" ]; then
    echo "✓ Activating virtual environment"
    source venv/bin/activate
else
    echo "⚠ No virtual environment found"
    echo "  Run setup_life.sh first or install requirements manually"
fi

# Check if database exists
if [ ! -f "data/database/life.db" ]; then
    echo "⚠ Database not found - will be created on first run"
fi

# Get network info
LOCAL_IP=$(hostname -I | awk '{print $1}')
HOSTNAME=$(hostname)

# Check if running on Pi with LCD
if [ -f "/sys/class/gpio/export" ]; then
    echo "✓ Raspberry Pi detected"
    # LCD display will be handled by the app
fi

echo ""
echo "Starting Life app..."
echo "===================="
echo "Local access:   http://localhost:5555"
echo "Network access: http://$LOCAL_IP:5555"
echo "Hostname:       http://$HOSTNAME.local:5555"
echo ""
echo "Default passwords (change these!):"
echo "  View:  13TM31n"
echo "  Admin: 13TM31n"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the application
cd app && python3 life.py