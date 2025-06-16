"""
bp_admin.py - Admin routes with orphaned file management
Version: 1.1.05
Purpose: Admin routes - system management, user management, settings, orphaned files
Created: 2025-06-11
Updated: 2025-06-16 - Added system backup functionality with fixed naming
"""

import os
import subprocess
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session
from datetime import datetime
from routes.bp_auth import admin_required
from utils.util_db import query_db, execute_db
from utils.util_storage import cleanup_orphaned_files, create_backup_archive, create_system_backup, get_file_size_formatted, calculate_checksum, get_file_type, get_file_category

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard with system overview"""
    # Get system stats
    stats = {
        'total_files': query_db('SELECT COUNT(*) as count FROM files WHERE deleted = 0', one=True)['count'],
        'total_size': query_db('SELECT SUM(size) as size FROM files WHERE deleted = 0', one=True)['size'] or 0,
        'deleted_files': query_db('SELECT COUNT(*) as count FROM files WHERE deleted = 1', one=True)['count'],
        'total_tags': query_db('SELECT COUNT(*) as count FROM tags', one=True)['count'],
        'recent_uploads': query_db('SELECT COUNT(*) as count FROM files WHERE upload_date >= date("now", "-7 days") AND deleted = 0', one=True)['count']
    }
    
    # Get disk space info
    try:
        df_result = subprocess.run(['/bin/df', '-h'], capture_output=True, text=True, timeout=10)
        if df_result.returncode == 0:
            disk_info = df_result.stdout
        else:
            disk_info = f"df command failed: {df_result.stderr}"
        current_app.logger.debug(f"df command result: {df_result.returncode}")
    except subprocess.TimeoutExpired:
        disk_info = "df command timed out"
    except Exception as e:
        current_app.logger.error(f"Failed to get disk info: {str(e)}")
        disk_info = f"Error getting disk info: {str(e)}"
    
    # Get recent activity - include file ID
    recent_files = query_db('''
        SELECT f.id, f.filename, f.upload_date, f.size, m.auto_category
        FROM files f
        LEFT JOIN metadata m ON f.id = m.file_id
        WHERE f.deleted = 0
        ORDER BY f.upload_date DESC
        LIMIT 10
    ''')
    
    # Get storage by category
    storage_by_category = query_db('''
        SELECT m.auto_category, COUNT(*) as file_count, SUM(f.size) as total_size
        FROM files f
        LEFT JOIN metadata m ON f.id = m.file_id
        WHERE f.deleted = 0 AND auto_category IS NOT NULL
        GROUP BY m.auto_category
        ORDER BY total_size DESC
    ''')
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"Admin dashboard - Total files: {stats['total_files']}, "
                                f"Total size: {get_file_size_formatted(stats['total_size'])}")
    
    return render_template('temp_admin_dashboard.html',
                         stats=stats,
                         disk_info=disk_info,
                         recent_files=recent_files,
                         storage_by_category=storage_by_category)

@admin_bp.route('/cleanup', methods=['POST'])
@admin_required
def cleanup_files():
    """Find orphaned files and redirect to display them"""
    try:
        orphaned = cleanup_orphaned_files()
        if orphaned:
            # Store in session for display
            session['orphaned_files'] = orphaned
            if current_app.config['DEBUG']:
                current_app.logger.debug(f"Found {len(orphaned)} orphaned files: {orphaned}")
            flash(f'Found {len(orphaned)} orphaned files', 'warning')
            return redirect(url_for('admin.show_orphans'))
        else:
            flash('No orphaned files found', 'success')
            return redirect(url_for('admin.dashboard'))
    except Exception as e:
        current_app.logger.error(f"Cleanup failed: {str(e)}")
        flash(f'Cleanup failed: {str(e)}', 'error')
        return redirect(url_for('admin.dashboard'))

@admin_bp.route('/orphans')
@admin_required
def show_orphans():
    """Show list of orphaned files for management"""
    orphaned_files = session.get('orphaned_files', [])
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"Displaying {len(orphaned_files)} orphaned files")
    
    return render_template('temp_admin_orphans.html', orphaned_files=orphaned_files)

@admin_bp.route('/delete_all_orphans', methods=['POST'])
@admin_required
def delete_all_orphans():
    """Delete all orphaned files"""
    try:
        orphaned_files = session.get('orphaned_files', [])
        deleted_count = 0
        
        for file_path in orphaned_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    deleted_count += 1
                    current_app.logger.info(f"Deleted orphaned file: {file_path}")
            except Exception as e:
                current_app.logger.error(f"Failed to delete {file_path}: {str(e)}")
        
        # Clear from session
        session.pop('orphaned_files', None)
        
        flash(f'Deleted {deleted_count} orphaned files', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Delete all orphans failed: {str(e)}")
        flash(f'Delete failed: {str(e)}', 'error')
    
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/delete_single_orphan', methods=['POST'])
@admin_required
def delete_single_orphan():
    """Delete a single orphaned file"""
    file_path = request.form.get('file_path')
    
    if not file_path:
        flash('No file path provided', 'error')
        return redirect(url_for('admin.show_orphans'))
    
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            current_app.logger.info(f"Deleted orphaned file: {file_path}")
            
            # Remove from session list
            orphaned_files = session.get('orphaned_files', [])
            if file_path in orphaned_files:
                orphaned_files.remove(file_path)
                session['orphaned_files'] = orphaned_files
            
            flash(f'Deleted {os.path.basename(file_path)}', 'success')
        else:
            flash('File not found', 'error')
            
    except Exception as e:
        current_app.logger.error(f"Failed to delete {file_path}: {str(e)}")
        flash(f'Delete failed: {str(e)}', 'error')
    
    return redirect(url_for('admin.show_orphans'))

@admin_bp.route('/restore_orphan', methods=['POST'])
@admin_required
def restore_orphan():
    """Restore orphaned file back to database"""
    file_path = request.form.get('file_path')
    
    if not file_path:
        flash('No file path provided', 'error')
        return redirect(url_for('admin.show_orphans'))
    
    try:
        if not os.path.exists(file_path):
            flash('File not found on disk', 'error')
            return redirect(url_for('admin.show_orphans'))
        
        # Get file info
        filename = os.path.basename(file_path)
        size = os.path.getsize(file_path)
        checksum = calculate_checksum(file_path)
        filetype = get_file_type(file_path)
        
        # Check if already exists in database
        existing = query_db('SELECT id FROM files WHERE checksum = ? AND deleted = 0', (checksum,), one=True)
        if existing:
            flash(f'File {filename} already exists in database', 'warning')
            return redirect(url_for('admin.show_orphans'))
        
        # Add back to database
        file_id = execute_db('''
            INSERT INTO files (filename, filepath, filetype, size, checksum)
            VALUES (?, ?, ?, ?, ?)
        ''', (filename, file_path, filetype, size, checksum))
        
        # Add basic metadata
        category = get_file_category(filename, filetype)
        execute_db('''
            INSERT INTO metadata (file_id, title, auto_category)
            VALUES (?, ?, ?)
        ''', (file_id, filename, category))
        
        # Remove from session list
        orphaned_files = session.get('orphaned_files', [])
        if file_path in orphaned_files:
            orphaned_files.remove(file_path)
            session['orphaned_files'] = orphaned_files
        
        current_app.logger.info(f"Restored orphaned file to database: {file_path}")
        flash(f'Restored {filename} to database', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Failed to restore {file_path}: {str(e)}")
        flash(f'Restore failed: {str(e)}', 'error')
    
    return redirect(url_for('admin.show_orphans'))

@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """System settings management"""
    if request.method == 'POST':
        # Update settings - dynamic bin types
        setting_keys = ['backup_enabled', 'backup_time', 'backup_location', 'debug_mode', 'log_level']
        
        # Add bin settings dynamically from config
        for bin_type in current_app.config.get('BIN_TYPES', {}).keys():
            setting_keys.extend([f'refuse_{bin_type}_day', f'refuse_{bin_type}_frequency'])
        
        for key in setting_keys:
            value = request.form.get(key, '')
            if value:
                execute_db('''
                    INSERT OR REPLACE INTO settings (key, value, modified_date)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (key, value))
        
        # Handle password changes
        view_password = request.form.get('view_password')
        admin_password = request.form.get('admin_password')
        
        if view_password:
            execute_db('''
                INSERT OR REPLACE INTO settings (key, value, modified_date)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', ('view_password', view_password))
            
        if admin_password:
            execute_db('''
                INSERT OR REPLACE INTO settings (key, value, modified_date)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', ('admin_password', admin_password))
        
        flash('Settings updated successfully', 'success')
        return redirect(url_for('admin.settings'))
    
    # Get current settings
    settings_data = {}
    settings_rows = query_db('SELECT key, value FROM settings')
    for row in settings_rows:
        settings_data[row['key']] = row['value']
    
    return render_template('temp_admin_settings.html', settings=settings_data)

@admin_bp.route('/data-backup', methods=['POST'])
@admin_required
def data_backup():
    """Create data backup (files + database only)"""
    try:
        backup_path = create_backup_archive()
        if backup_path:
            flash(f'Data backup created successfully: {backup_path}', 'success')
        else:
            flash('Failed to create data backup', 'error')
    except Exception as e:
        current_app.logger.error(f"Data backup failed: {str(e)}")
        flash(f'Data backup failed: {str(e)}', 'error')
    
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/system-backup', methods=['POST'])
@admin_required
def system_backup():
    """Create complete system backup"""
    try:
        backup_path = create_system_backup()
        if backup_path:
            flash(f'System backup created successfully: {backup_path}', 'success')
        else:
            flash('Failed to create system backup', 'error')
    except Exception as e:
        current_app.logger.error(f"System backup failed: {str(e)}")
        flash(f'System backup failed: {str(e)}', 'error')
    
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/files/deleted')
@admin_required
def deleted_files():
    """Show deleted files for recovery"""
    deleted = query_db('''
        SELECT f.id, f.filename, f.deleted_date, f.size, m.title
        FROM files f
        LEFT JOIN metadata m ON f.id = m.file_id
        WHERE f.deleted = 1
        ORDER BY f.deleted_date DESC
    ''')
    
    return render_template('temp_admin_deleted.html', deleted_files=deleted)

@admin_bp.route('/files/restore/<int:file_id>', methods=['POST'])
@admin_required
def restore_file(file_id):
    """Restore deleted file"""
    execute_db('''
        UPDATE files
        SET deleted = 0, deleted_date = NULL
        WHERE id = ?
    ''', (file_id,))
    
    flash('File restored successfully', 'success')
    return redirect(url_for('admin.deleted_files'))

@admin_bp.route('/api/stats')
@admin_required
def api_stats():
    """API endpoint for dashboard stats"""
    stats = {
        'total_files': query_db('SELECT COUNT(*) as count FROM files WHERE deleted = 0', one=True)['count'],
        'total_size': query_db('SELECT SUM(size) as size FROM files WHERE deleted = 0', one=True)['size'] or 0,
        'uploads_today': query_db('SELECT COUNT(*) as count FROM files WHERE DATE(upload_date) = DATE("now") AND deleted = 0', one=True)['count'],
        'uploads_week': query_db('SELECT COUNT(*) as count FROM files WHERE upload_date >= date("now", "-7 days") AND deleted = 0', one=True)['count']
    }
    
    return jsonify(stats)