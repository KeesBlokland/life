#!/bin/bash
# /home/life/setup_life.sh
# Version: 1.0.0
# Purpose: System setup script for Life family archive app
# Created: 2025-06-11

set -e  # Exit on any error

echo "Life App - Family Archive System Setup"
echo "======================================"

# Check if running as regular user (not root)
if [ "$(id -u)" -eq 0 ]; then
    echo "This script should be run as a regular user, not root."
    echo "The script will use sudo when needed for system packages."
    exit 1
fi

# Determine base directory
BASE_DIR="/home/life"
echo "Setting up Life app in: $BASE_DIR"

# Update package list
echo "Updating package list..."
sudo apt update

# Check and install Python3
if command -v python3 >/dev/null 2>&1; then
    echo "✓ Python3 already installed: $(python3 --version)"
else
    echo "Installing Python3..."
    sudo apt install -y python3 python3-pip python3-venv
    echo "✓ Python3 installed successfully"
fi

# Install system dependencies
echo "Installing system dependencies..."
sudo apt install -y \
    python3-flask \
    python3-pil \
    python3-magic \
    tesseract-ocr \
    libtesseract-dev \
    sqlite3

echo "✓ System dependencies installed"

# Create application directory structure
echo "Creating application directories..."
sudo mkdir -p $BASE_DIR/{app,data,docs}
sudo mkdir -p $BASE_DIR/app/{routes,utils,models,templates,static}
sudo mkdir -p $BASE_DIR/app/static/{css,js,img}
sudo mkdir -p $BASE_DIR/data/{documents,images,videos,database,backups}
sudo mkdir -p $BASE_DIR/data/documents/{financial,medical,legal,personal}
sudo mkdir -p $BASE_DIR/data/images/{family,events,historical,documents}
sudo mkdir -p $BASE_DIR/data/videos/{family,events}
sudo mkdir -p $BASE_DIR/import/{evernote,email,queue}

echo "✓ Directory structure created"

# Fix ownership (in case directories were created by sudo)
sudo chown -R life:life $BASE_DIR

# Create Python virtual environment
echo "Creating Python virtual environment..."
cd $BASE_DIR
python3 -m venv venv
source venv/bin/activate

# Install Python packages
echo "Installing Python packages..."
pip install --upgrade pip
pip install \
    Flask==2.3.3 \
    Werkzeug==2.3.7 \
    Pillow==10.0.0 \
    pillow-heif==0.13.0 \
    python-magic==0.4.27 \
    pytesseract==0.3.10 \
    PyPDF2==3.0.1 \
    python-docx==0.8.11 \
    Whoosh==2.7.4

echo "✓ Python packages installed"

# Create systemd service file
echo "Creating systemd service..."
sudo tee /etc/systemd/system/life.service > /dev/null << EOF
[Unit]
Description=Life Family Archive System
After=network.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$BASE_DIR/app
Environment="PATH=$BASE_DIR/venv/bin"
Environment="FLASK_APP=life.py"
Environment="FLASK_ENV=production"
ExecStart=$BASE_DIR/venv/bin/python $BASE_DIR/app/life.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "✓ Systemd service created"

# Create LCD display service (if Pi with LCD)
if [ -d "/sys/class/gpio" ]; then
    echo "Creating LCD display service..."
    sudo tee /etc/systemd/system/life-lcd.service > /dev/null << EOF
[Unit]
Description=Life LCD Network Display
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=$BASE_DIR/venv/bin/python $BASE_DIR/app/utils/util_network.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
    echo "✓ LCD service created"
fi

# Set permissions
echo "Setting permissions..."
chmod -R 755 $BASE_DIR/app
chmod -R 750 $BASE_DIR/data
if [ ! -f "$BASE_DIR/app/config.py" ]; then
    echo "# Placeholder config" > "$BASE_DIR/app/config.py"
fi
chmod 600 $BASE_DIR/app/config.py  # Protect config file

# Reload systemd
sudo systemctl daemon-reload

# Get IP address
CONTAINER_IP=$(hostname -I | awk '{print $1}')

echo ""
echo "======================================"
echo "Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Copy application files to $BASE_DIR/app/"
echo "2. Activate virtual environment: source $BASE_DIR/venv/bin/activate"
echo "3. Test run: python3 $BASE_DIR/app/life.py"
echo "4. Enable service: sudo systemctl enable life"
echo "5. Start service: sudo systemctl start life"
echo ""
echo "Access the application at:"
echo "  Local: http://localhost:5555"
echo "  Network: http://$CONTAINER_IP:5555"
echo ""
echo "First visit will prompt for initial setup."
echo ""