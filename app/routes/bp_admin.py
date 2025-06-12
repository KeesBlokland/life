"""
/home/life/app/routes/bp_admin.py
Version: 1.0.0
Purpose: Admin routes - system management, user management, settings
Created: 2025-06-11
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from datetime import datetime
from routes.bp_auth import admin_required
from utils.util_db import query_db, execute_db
from utils.util_storage import cleanup_orphaned_files, create_backup_archive, get_file_size_formatted

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
    
    # Get recent activity
    recent_files = query_db('''
        SELECT f.filename, f.upload_date, f.size, m.auto_category
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
        WHERE f.deleted = 0
        GROUP BY m.auto_category
        ORDER BY total_size DESC
    ''')
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"Admin dashboard - Total files: {stats['total_files']}, "
                                f"Total size: {get_file_size_formatted(stats['total_size'])}")
    
    return render_template('temp_admin_dashboard.html',
                         stats=stats,
                         recent_files=recent_files,
                         storage_by_category=storage_by_category)

@admin_bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """System settings management"""
    if request.method == 'POST':
        # Update settings
        for key in ['refuse_blue_day', 'refuse_yellow_day', 'refuse_brown_day', 'backup_enabled', 'backup_time']:
            value = request.form.get(key, '')
            if value:
                execute_db('''
                    INSERT OR REPLACE INTO settings (key, value, modified_date)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (key, value))
        
        flash('Settings updated successfully', 'success')
        return redirect(url_for('admin.settings'))
    
    # Get current settings
    settings_data = {}
    settings_rows = query_db('SELECT key, value FROM settings')
    for row in settings_rows:
        settings_data[row['key']] = row['value']
    
    return render_template('temp_admin_settings.html', settings=settings_data)

@admin_bp.route('/backup', methods=['POST'])
@admin_required
def create_backup():
    """Create system backup"""
    try:
        backup_path = create_backup_archive()
        if backup_path:
            flash(f'Backup created successfully: {backup_path}', 'success')
        else:
            flash('Failed to create backup', 'error')
    except Exception as e:
        current_app.logger.error(f"Backup failed: {str(e)}")
        flash(f'Backup failed: {str(e)}', 'error')
    
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/cleanup', methods=['POST'])
@admin_required
def cleanup_files():
    """Clean up orphaned files"""
    try:
        orphaned = cleanup_orphaned_files()
        if orphaned:
            flash(f'Found {len(orphaned)} orphaned files. Review them manually.', 'warning')
        else:
            flash('No orphaned files found', 'success')
    except Exception as e:
        current_app.logger.error(f"Cleanup failed: {str(e)}")
        flash(f'Cleanup failed: {str(e)}', 'error')
    
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