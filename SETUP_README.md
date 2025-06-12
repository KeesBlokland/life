# Life App - Setup Instructions
/home/life/SETUP_README.md  
Version: 1.0.0  
Created: 2025-06-11

## Quick Setup

### 1. Initial System Setup (run once)
```bash
cd /home/life
chmod +x setup_life.sh
./setup_life.sh
```

This will:
- Install system packages (Python, Tesseract, etc.)
- Create directory structure
- Set up Python virtual environment
- Install Python packages
- Create systemd service

### 2. Application Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Run Python setup
python3 setup_life.py
```

This will:
- Create configuration files
- Set initial passwords
- Initialize database
- Create backup scripts

### 3. Copy Application Files
Copy all the app files to their proper locations:
- `app/*.py` → `/home/life/app/`
- `app/routes/bp_*.py` → `/home/life/app/routes/`
- `app/templates/temp_*.html` → `/home/life/app/templates/`
- `app/utils/util_*.py` → `/home/life/app/utils/`
- `app/static/*` → `/home/life/app/static/`

### 4. Start the Application

#### Development Mode (with debug):
```bash
./dev_life.sh
```

#### Normal Mode:
```bash
./start_life.sh
```

#### Production Mode (as service):
```bash
sudo systemctl enable life
sudo systemctl start life
sudo systemctl status life
```

## Default Access

- **URL**: http://[your-ip]:5555
- **View Password**: family-view
- **Admin Password**: family-admin

Change these in `app/config_local.py`!

## File Locations

```
/home/life/
├── app/              # Application code
├── data/             # User data (documents, images)
├── venv/             # Python virtual environment
├── backup_life.py    # Backup utility
├── start_life.sh     # Start script
└── dev_life.sh       # Development start script
```

## Daily Operations

### Create Backup
```bash
python3 backup_life.py create
```

### List Backups
```bash
python3 backup_life.py list
```

### Auto Backup (add to cron)
```bash
crontab -e
# Add: 0 3 * * * cd /home/life && /home/life/venv/bin/python backup_life.py auto
```

## Troubleshooting

### Port 5555 Already in Use
```bash
sudo lsof -i :5555
# Kill the process or use different port
```

### Permission Errors
```bash
# Fix ownership
sudo chown -R $USER:$USER /home/life
```

### LCD Not Working (on Pi)
```bash
# Check LCD service
sudo systemctl status life-lcd
```

### Database Locked
```bash
# Stop the service first
sudo systemctl stop life
# Then run maintenance
```

## Network Modes

The app automatically detects network:
- **Home Network**: Shows local IP on LCD
- **No Network**: Starts hotspot mode
  - SSID: LifeArchive
  - Pass: FamilyLife2025
  - Access: http://10.42.0.1:5555