"""
util_storage.py
Date: 2025-06-18
Version: 1.0.01
Purpose: File storage operations - validation, checksums, categorization, backups fixed
"""

import os
import hashlib
import shutil
import magic
import subprocess
from datetime import datetime
from flask import current_app

def allowed_file(filename):
    """Check if file extension is allowed"""
    if '.' not in filename:
        return False
    
    ext = filename.rsplit('.', 1)[1].lower()
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', set())
    
    return ext in allowed

def calculate_checksum(filepath, algorithm='md5'):
    """Calculate file checksum for deduplication"""
    try:
        hash_obj = hashlib.new(algorithm)
        
        with open(filepath, 'rb') as f:
            # Read in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b''):
                hash_obj.update(chunk)
        
        checksum = hash_obj.hexdigest()
        
        if current_app.config['DEBUG']:
            current_app.logger.debug(f"Calculated {algorithm} checksum: {checksum} for {filepath}")
        
        return checksum
        
    except Exception as e:
        current_app.logger.error(f"Failed to calculate checksum: {str(e)}")
        return None

def get_file_type(filepath):
    """Get MIME type of file using python-magic"""
    try:
        mime = magic.Magic(mime=True)
        file_type = mime.from_file(filepath)
        
        return file_type
        
    except Exception as e:
        current_app.logger.error(f"Failed to get file type: {str(e)}")
        # Fallback to extension
        ext = filepath.rsplit('.', 1)[1].lower() if '.' in filepath else 'unknown'
        return f'application/{ext}'

def get_file_category(filename, filetype=None):
    """Determine file category based on name and type"""
    filename_lower = filename.lower()
    
    # Check by extension first
    if filename_lower.endswith(('.pdf', '.doc', '.docx', '.txt', '.odt')):
        category = 'documents'
    elif filename_lower.endswith(('.jpg', '.jpeg', '.png', '.gif', '.heic', '.bmp')):
        category = 'images'
    elif filename_lower.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
        category = 'videos'
    else:
        category = 'documents'  # Default
    
    # Refine by content/keywords
    if category == 'documents':
        # Check for specific document types
        if any(word in filename_lower for word in ['invoice', 'rechnung', 'bill', 'receipt']):
            return 'documents/financial'
        elif any(word in filename_lower for word in ['medical', 'doctor', 'prescription', 'gesundheit']):
            return 'documents/medical'
        elif any(word in filename_lower for word in ['contract', 'legal', 'vertrag', 'testament']):
            return 'documents/legal'
        else:
            return 'documents/personal'
    
    elif category == 'images':
        if any(word in filename_lower for word in ['passport', 'id', 'license', 'ausweis']):
            return 'images/documents'
        elif any(word in filename_lower for word in ['family', 'birthday', 'wedding']):
            return 'images/family'
        
        else:
            return 'images/events'
    
    elif category == 'videos':
        if any(word in filename_lower for word in ['family', 'birthday', 'christmas']):
            return 'videos/family'
        else:
            return 'videos/events'
    
    return f'{category}/personal'

def move_to_storage(temp_path, category, filename):
    """Move file from temp to permanent storage"""
    try:
        # Build storage path
        storage_base = current_app.config['DATA_DIR']
        category_path = os.path.join(storage_base, category)
        
        # Create directory if needed
        os.makedirs(category_path, exist_ok=True)
        
        # Final path
        final_path = os.path.join(category_path, filename)
        
        # Handle duplicate filenames
        if os.path.exists(final_path):
            base, ext = os.path.splitext(filename)
            counter = 1
            while os.path.exists(final_path):
                filename = f"{base}_{counter}{ext}"
                final_path = os.path.join(category_path, filename)
                counter += 1
        
        # Move file
        shutil.move(temp_path, final_path)
        
        # Set permissions
        os.chmod(final_path, 0o644)
        
        if current_app.config['DEBUG']:
            current_app.logger.debug(f"Moved file: {temp_path} -> {final_path}")
        
        return final_path
        
    except Exception as e:
        current_app.logger.error(f"Failed to move file to storage: {str(e)}")
        return temp_path

def get_file_size_formatted(size_bytes):
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def verify_file_integrity(filepath, expected_checksum):
    """Verify file integrity by comparing checksums"""
    try:
        actual_checksum = calculate_checksum(filepath)
        is_valid = actual_checksum == expected_checksum
        
        if not is_valid and current_app.config['DEBUG']:
            current_app.logger.warning(f"Checksum mismatch for {filepath}: "
                                     f"expected {expected_checksum}, got {actual_checksum}")
        
        return is_valid
        
    except Exception as e:
        current_app.logger.error(f"Failed to verify file integrity: {str(e)}")
        return False

def cleanup_orphaned_files():
    """Find and clean up files not in database - exclude system files and deleted files"""
    try:
        from utils.util_db import query_db
        
        # Get all file paths from database (including deleted files)
        db_files = query_db('SELECT filepath FROM files')
        db_paths = set(f['filepath'] for f in db_files)
        
        # Walk through storage directories - EXCLUDE system and deleted directories
        storage_base = current_app.config['DATA_DIR']
        orphaned = []
        
        # Only check document storage directories, exclude deleted_for_review
        check_dirs = ['documents', 'images', 'videos']
        
        for check_dir in check_dirs:
            check_path = os.path.join(storage_base, check_dir)
            if not os.path.exists(check_path):
                continue
                
            for root, dirs, files in os.walk(check_path):
                # Skip hidden directories and deleted_for_review
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'deleted_for_review']
                
                for filename in files:
                    filepath = os.path.join(root, filename)
                    # Skip hidden files and system files
                    if (filepath not in db_paths and 
                        not filename.startswith('.') and
                        not filename.endswith('.db') and
                        not filename.endswith('.backup') and
                        not filename.endswith('.tar.gz')):
                        orphaned.append(filepath)
        
        if current_app.config['DEBUG'] and orphaned:
            current_app.logger.info(f"Found {len(orphaned)} orphaned files")
        
        return orphaned
        
    except Exception as e:
        current_app.logger.error(f"Failed to find orphaned files: {str(e)}")
        return []

def create_backup_archive(backup_name=None):
    """Create backup archive of all data"""
    try:
        import tarfile
        
        if not backup_name:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"life_backup_{timestamp}.tar.gz"
        
        backup_dir = current_app.config['BACKUP_DIR']
        current_app.logger.info(f"Creating data backup in directory: {backup_dir}")
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_path = os.path.join(backup_dir, backup_name)
        current_app.logger.info(f"Data backup will be saved to: {backup_path}")
        
        with tarfile.open(backup_path, 'w:gz') as tar:
            # Add data directories
            for subdir in ['documents', 'images', 'videos']:
                dir_path = os.path.join(current_app.config['DATA_DIR'], subdir)
                if os.path.exists(dir_path):
                    current_app.logger.debug(f"Adding {subdir} directory to backup")
                    tar.add(dir_path, arcname=subdir)
                else:
                    current_app.logger.warning(f"Directory {dir_path} not found, skipping")
            
            # Add database
            db_path = current_app.config['DB_PATH']
            if os.path.exists(db_path):
                current_app.logger.debug("Adding database to backup")
                tar.add(db_path, arcname='database/life.db')
            else:
                current_app.logger.warning(f"Database {db_path} not found")
        
        size = os.path.getsize(backup_path)
        current_app.logger.info(f"Data backup created successfully: {backup_path} ({get_file_size_formatted(size)})")
        
        return backup_path
        
    except Exception as e:
        current_app.logger.error(f"Failed to create backup: {str(e)}")
        return None

def create_system_backup(backup_name=None):
    """Create complete system backup including code, venv, and data"""
    try:
        if not backup_name:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"life_system_backup_{timestamp}.tar.gz"
        
        backup_dir = current_app.config['BACKUP_DIR']
        current_app.logger.info(f"Creating system backup in directory: {backup_dir}")
        os.makedirs(backup_dir, exist_ok=True)
        
        backup_path = os.path.join(backup_dir, backup_name)
        temp_tar = backup_path.replace('.gz', '')  # Work with uncompressed tar first
        current_app.logger.info(f"System backup will be saved to: {backup_path}")
        
        # Create initial tar without compression
        cmd = [
            '/bin/tar',
            f'--exclude={backup_dir}',
            '--exclude=__pycache__',
            '--exclude=*.pyc',
            '--exclude=.cache',
            '--exclude=*/venv/*',
            '--exclude=*/.git/*',
            '--exclude=*.log',
            '--exclude=*.tmp',
            '-cf',  # Create uncompressed
            temp_tar,
            '/home/life'
        ]
        
        current_app.logger.info(f"Running tar command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Check return code, not stderr (tar warns about leading / but still works)
        if result.returncode != 0 and result.returncode != 1:
            current_app.logger.error(f"Tar command failed with code {result.returncode}")
            current_app.logger.error(f"STDOUT: {result.stdout}")
            current_app.logger.error(f"STDERR: {result.stderr}")
            return None
        
        if not os.path.exists(temp_tar) or os.path.getsize(temp_tar) == 0:
            current_app.logger.error(f"Tar file not created or empty: {temp_tar}")
            return None
            
        current_app.logger.info(f"Base tar created, size: {os.path.getsize(temp_tar)} bytes")
            
        # Add systemd service files
        try:
            service_cmd = ['/usr/bin/find', '/etc/systemd/system/', '-name', '*life*']
            current_app.logger.debug(f"Looking for systemd files: {' '.join(service_cmd)}")
            service_files = subprocess.run(service_cmd, capture_output=True, text=True, timeout=10)
            
            if service_files.returncode == 0:
                files_found = service_files.stdout.strip().split('\n')
                current_app.logger.info(f"Found {len(files_found)} systemd files")
                for service_file in files_found:
                    if service_file and os.path.exists(service_file):
                        current_app.logger.debug(f"Adding systemd file: {service_file}")
                        append_result = subprocess.run(['/bin/tar', '-rf', temp_tar, service_file], 
                                                     capture_output=True, text=True)
                        if append_result.returncode != 0:
                            current_app.logger.warning(f"Failed to add {service_file}: {append_result.stderr}")
            else:
                current_app.logger.warning(f"Find command failed: {service_files.stderr}")
        except Exception as e:
            current_app.logger.warning(f"Could not backup systemd files: {str(e)}")
        
        # Add nginx/apache configs if they exist
        for config_path in ['/etc/nginx/sites-available/life', '/etc/apache2/sites-available/life']:
            if os.path.exists(config_path):
                current_app.logger.debug(f"Adding web server config: {config_path}")
                append_result = subprocess.run(['/bin/tar', '-rf', temp_tar, config_path], 
                                             capture_output=True, text=True)
                if append_result.returncode != 0:
                    current_app.logger.warning(f"Failed to add {config_path}: {append_result.stderr}")
        
        # Compress the final tar
        current_app.logger.info(f"Compressing tar file to {backup_path}")
        gzip_result = subprocess.run(['/bin/gzip', '-f', temp_tar], capture_output=True, text=True)
        
        if gzip_result.returncode != 0:
            current_app.logger.error(f"Gzip failed: {gzip_result.stderr}")
            return None
        
        if not os.path.exists(backup_path):
            current_app.logger.error(f"Expected backup file {backup_path} not found after compression")
            return None
            
        size = os.path.getsize(backup_path)
        current_app.logger.info(f"System backup created successfully: {backup_path} ({get_file_size_formatted(size)})")
        
        return backup_path
        
    except Exception as e:
        current_app.logger.error(f"Failed to create system backup: {str(e)}", exc_info=True)
        return None

def cleanup_old_backups():
    """Keep only recent backups to save disk space"""
    try:
        backup_dir = current_app.config['BACKUP_DIR']
        
        # Data backups - keep last 5
        data_backups = sorted([f for f in os.listdir(backup_dir) 
                             if f.startswith('life_backup_') and f.endswith('.tar.gz')])
        if len(data_backups) > 5:
            for old_backup in data_backups[:-5]:
                os.remove(os.path.join(backup_dir, old_backup))
                current_app.logger.info(f"Deleted old data backup: {old_backup}")
        
        # System backups - keep only one per month
        system_backups = sorted([f for f in os.listdir(backup_dir) 
                               if f.startswith('life_system_backup_') and f.endswith('.tar.gz')])
        
        # Group by year-month
        from collections import defaultdict
        monthly_backups = defaultdict(list)
        for backup in system_backups:
            # Extract YYYYMM from filename
            date_part = backup.split('_')[3]  # life_system_backup_YYYYMMDD_HHMMSS.tar.gz
            year_month = date_part[:6]
            monthly_backups[year_month].append(backup)
        
        # Keep only newest per month
        for year_month, backups in monthly_backups.items():
            if len(backups) > 1:
                for old_backup in backups[:-1]:
                    os.remove(os.path.join(backup_dir, old_backup))
                    current_app.logger.info(f"Deleted old system backup: {old_backup}")
                    
    except Exception as e:
        current_app.logger.error(f"Failed to cleanup backups: {str(e)}")

def check_disk_space():
    """Check disk space and return warning if low"""
    try:
        import shutil
        
        # Get disk usage for data directory
        stat = shutil.disk_usage(current_app.config['DATA_DIR'])
        free_gb = stat.free / (1024**3)
        used_percent = (stat.used / stat.total) * 100
        
        warning_messages = []
        
        # Warn if less than 1GB free or more than 90% used
        if free_gb < 1:
            warning_messages.append(f"LOW DISK SPACE: Only {free_gb:.2f}GB free")
        
        if used_percent > 90:
            warning_messages.append(f"DISK NEARLY FULL: {used_percent:.1f}% used")
            
        # Also check backup directory
        backup_stat = shutil.disk_usage(current_app.config['BACKUP_DIR'])
        backup_size_gb = sum(os.path.getsize(os.path.join(current_app.config['BACKUP_DIR'], f)) 
                           for f in os.listdir(current_app.config['BACKUP_DIR']) 
                           if f.endswith('.tar.gz')) / (1024**3)
        
        if backup_size_gb > 5:
            warning_messages.append(f"Backup directory using {backup_size_gb:.1f}GB")
        
        return {
            'free_gb': free_gb,
            'used_percent': used_percent,
            'warnings': warning_messages,
            'healthy': len(warning_messages) == 0
        }
        
    except Exception as e:
        current_app.logger.error(f"Failed to check disk space: {str(e)}")
        return {'healthy': False, 'warnings': [f"Error checking disk: {str(e)}"]}