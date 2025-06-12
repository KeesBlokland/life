#!/bin/bash
# /home/life/dev_life.sh
# Version: 1.0.0
# Purpose: Development mode startup with debug enabled
# Created: 2025-06-11

# Quick development start with debugging enabled
export FLASK_ENV=development
export FLASK_DEBUG=1

echo "Life App - DEVELOPMENT MODE"
echo "=========================="
echo "Debug: ON"
echo "Footer Info: ON"
echo ""

# Activate venv if exists
[ -d "venv" ] && source venv/bin/activate

# Get IP
IP=$(hostname -I | awk '{print $1}')
echo "Access at: http://$IP:5555"
echo ""

cd app && python3 life.py