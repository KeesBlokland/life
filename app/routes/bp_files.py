"""
/home/life/app/routes/bp_files.py
Version: 1.2.1
Purpose: File handling routes - upload, download, browse, search, edit
Created: 2025-06-11
Updated: 2025-06-16 - Fixed missing shutil import for file deletion
"""

import os
import shutil
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, jsonify, current_app, session
from werkzeug.utils import secure_filename
from datetime import datetime
from routes.bp_auth import login_required, admin_required
from utils.util_db import get_db, query_db, execute_db
from utils.util_storage import (
    allowed_file, calculate_checksum, get_file_type, 
    get_file_category, move_to_storage
)
from utils.util_image import process_image_file

files_bp = Blueprint('files', __name__)

@files_bp.route('/browse')
@files_bp.route('/browse/<path:category>')
@login_required
def browse(category=None):
    """Browse files by category"""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['ITEMS_PER_PAGE']
    
    # Build query
    if category:
        query = '''
            SELECT f.id, f.filename, f.size, f.upload_date, 
                   m.title, m.description, m.auto_category
            FROM files f
            LEFT JOIN metadata m ON f.id = m.file_id
            WHERE f.deleted = 0 AND m.auto_category = ?
            ORDER BY f.upload_date DESC
            LIMIT ? OFFSET ?
        '''
        args = (category, per_page, (page - 1) * per_page)
        
        count_query = '''
            SELECT COUNT(*) as count
            FROM files f
            LEFT JOIN metadata m ON f.id = m.file_id
            WHERE f.deleted = 0 AND m.auto_category = ?
        '''
        count_args = (category,)
    else:
        query = '''
            SELECT f.id, f.filename, f.size, f.upload_date,
                   m.title, m.description, m.auto_category
            FROM files f
            LEFT JOIN metadata m ON f.id = m.file_id
            WHERE f.deleted = 0
            ORDER BY f.upload_date DESC
            LIMIT ? OFFSET ?
        '''
        args = (per_page, (page - 1) * per_page)
        
        count_query = 'SELECT COUNT(*) as count FROM files WHERE deleted = 0'
        count_args = ()
    
    files_raw = query_db(query, args)
    total_count = query_db(count_query, count_args, one=True)['count']
    
    # Convert SQLite Row objects to dicts and add tags
    files = []
    for file_row in files_raw:
        # Convert Row to dict
        file_dict = dict(file_row)
        
        # Get tags for this file
        tags = query_db('''
            SELECT t.name
            FROM tags t
            JOIN file_tags ft ON t.id = ft.tag_id
            WHERE ft.file_id = ?
        ''', (file_dict['id'],))
        file_dict['tags'] = [tag['name'] for tag in tags]
        
        files.append(file_dict)
    
    # Get category list
    categories = query_db('''
        SELECT DISTINCT auto_category, COUNT(*) as count
        FROM metadata m
        JOIN files f ON m.file_id = f.id
        WHERE f.deleted = 0 AND auto_category IS NOT NULL
        GROUP BY auto_category
        ORDER BY auto_category
    ''')
    
    # Calculate pagination
    total_pages = (total_count + per_page - 1) // per_page
    
    return render_template('temp_files.html',
                         files=files,
                         categories=categories,
                         current_category=category,
                         page=page,
                         total_pages=total_pages)

@files_bp.route('/edit/<int:file_id>', methods=['POST'])
@admin_required
def edit_file(file_id):
    """Edit file metadata - title and tags"""
    file_info = query_db('SELECT * FROM files WHERE id = ? AND deleted = 0', 
                        (file_id,), one=True)
    
    if not file_info:
        flash('File not found', 'error')
        return redirect(url_for('files.browse'))
    
    # Get form data
    new_title = request.form.get('title', '').strip()
    new_tags = request.form.get('tags', '').strip()
    
    try:
        # Update title if provided
        if new_title:
            execute_db('''
                UPDATE metadata 
                SET title = ? 
                WHERE file_id = ?
            ''', (new_title, file_id))
        
        # Update tags if provided
        if 'tags' in request.form:  # Even if empty, user wants to update tags
            # Remove existing tags
            execute_db('DELETE FROM file_tags WHERE file_id = ?', (file_id,))
            
            # Add new tags
            if new_tags:
                for tag_name in new_tags.split(','):
                    tag_name = tag_name.strip().lower()
                    if tag_name:
                        # Get or create tag
                        tag = query_db('SELECT id FROM tags WHERE name = ?', (tag_name,), one=True)
                        if not tag:
                            tag_id = execute_db('INSERT INTO tags (name) VALUES (?)', (tag_name,))
                        else:
                            tag_id = tag['id']
                        
                        # Link to file
                        execute_db('INSERT INTO file_tags (file_id, tag_id) VALUES (?, ?)',
                                 (file_id, tag_id))
        
        if current_app.config['DEBUG']:
            current_app.logger.debug(f"Updated file {file_id}: title='{new_title}', tags='{new_tags}'")
        
        flash('File updated successfully', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error updating file {file_id}: {str(e)}")
        flash('Error updating file', 'error')
    
    return redirect(url_for('files.browse'))

@files_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Upload files with metadata"""
    if request.method == 'POST':
        # Check if files were provided
        if 'files' not in request.files:
            flash('No files selected', 'error')
            return redirect(request.url)
        
        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            flash('No files selected', 'error')
            return redirect(request.url)
        
        # Get shared metadata
        shared_tags = request.form.get('tags', '').strip()
        custom_titles = request.form.getlist('titles')  # Get array of custom titles
        
        uploaded_count = 0
        for index, file in enumerate(files):
            if file and file.filename != '' and allowed_file(file.filename):
                # Secure filename
                original_filename = file.filename
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{timestamp}_{filename}"
                
                # Save to temp location first
                temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                file.save(temp_path)
                
                # Process image if needed (HEIC conversion, resize)
                if filename.lower().endswith(('.heic', '.jpg', '.jpeg', '.png', '.gif')):
                    temp_path = process_image_file(temp_path)
                    filename = os.path.basename(temp_path)
                
                # Calculate checksum
                checksum = calculate_checksum(temp_path)
                
                # Check for duplicates
                duplicate = query_db('SELECT id, filename FROM files WHERE checksum = ? AND deleted = 0', 
                                   (checksum,), one=True)
                
                if duplicate:
                    os.remove(temp_path)
                    flash(f'Duplicate file skipped: {original_filename}', 'warning')
                    continue
                
                # Get file info
                filetype = get_file_type(temp_path)
                size = os.path.getsize(temp_path)
                category = get_file_category(original_filename, filetype)
                
                # Move to storage
                storage_path = move_to_storage(temp_path, category, filename)
                
                # Store in database
                file_id = execute_db('''
                    INSERT INTO files (filename, filepath, filetype, size, checksum)
                    VALUES (?, ?, ?, ?, ?)
                ''', (original_filename, storage_path, filetype, size, checksum))
                
                # Add metadata
                title = custom_titles[index] if index < len(custom_titles) and custom_titles[index].strip() else original_filename
                
                execute_db('''
                    INSERT INTO metadata (file_id, title, description, keywords, auto_category)
                    VALUES (?, ?, ?, ?, ?)
                ''', (file_id, title, '', shared_tags, category))
                
                # Process shared tags
                if shared_tags:
                    for tag_name in shared_tags.split(','):
                        tag_name = tag_name.strip().lower()
                        if tag_name:
                            # Get or create tag
                            tag = query_db('SELECT id FROM tags WHERE name = ?', (tag_name,), one=True)
                            if not tag:
                                tag_id = execute_db('INSERT INTO tags (name) VALUES (?)', (tag_name,))
                            else:
                                tag_id = tag['id']
                            
                            # Link to file
                            execute_db('INSERT INTO file_tags (file_id, tag_id) VALUES (?, ?)',
                                     (file_id, tag_id))
                
                uploaded_count += 1
                
                if current_app.config['DEBUG']:
                    current_app.logger.debug(f"File uploaded: {original_filename} -> {storage_path}, "
                                           f"Category: {category}, Size: {size}")
        
        if uploaded_count > 0:
            flash(f'Successfully uploaded {uploaded_count} file{"s" if uploaded_count != 1 else ""}', 'success')
        else:
            flash('No files were uploaded', 'error')
        
        return redirect(url_for('files.browse'))
    
    # GET request - show upload form
    return render_template('temp_upload.html')

@files_bp.route('/download/<int:file_id>')
@login_required
def download(file_id):
    """Download file"""
    file_info = query_db('SELECT * FROM files WHERE id = ? AND deleted = 0', 
                        (file_id,), one=True)
    
    if not file_info:
        flash('File not found', 'error')
        return redirect(url_for('files.browse'))
    
    if not os.path.exists(file_info['filepath']):
        flash('File not found on disk', 'error')
        return redirect(url_for('files.browse'))
    
    # Track file access for learning associations
    if 'last_file_id' in session:
        last_id = session['last_file_id']
        if last_id != file_id:
            # Update association
            existing = query_db('''
                SELECT strength FROM learned_associations
                WHERE (file_id_1 = ? AND file_id_2 = ?) OR (file_id_1 = ? AND file_id_2 = ?)
            ''', (last_id, file_id, file_id, last_id), one=True)
            
            if existing:
                execute_db('''
                    UPDATE learned_associations
                    SET strength = strength + 0.1, last_accessed = CURRENT_TIMESTAMP
                    WHERE (file_id_1 = ? AND file_id_2 = ?) OR (file_id_1 = ? AND file_id_2 = ?)
                ''', (last_id, file_id, file_id, last_id))
            else:
                execute_db('''
                    INSERT INTO learned_associations (file_id_1, file_id_2, strength)
                    VALUES (?, ?, 1.0)
                ''', (min(last_id, file_id), max(last_id, file_id)))
    
    session['last_file_id'] = file_id
    
    return send_file(file_info['filepath'], 
                    download_name=file_info['filename'],
                    as_attachment=True)

@files_bp.route('/search')
@login_required
def search():
    """Search files"""
    query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config['ITEMS_PER_PAGE']
    
    if not query:
        return render_template('temp_search.html', query=query, results=[], total_count=0)
    
    # Search in multiple fields
    search_query = '''
        SELECT DISTINCT f.id, f.filename, f.size, f.upload_date,
               m.title, m.description, m.auto_category
        FROM files f
        LEFT JOIN metadata m ON f.id = m.file_id
        LEFT JOIN file_tags ft ON f.id = ft.file_id
        LEFT JOIN tags t ON ft.tag_id = t.id
        WHERE f.deleted = 0 AND (
            f.filename LIKE ? OR
            m.title LIKE ? OR
            m.description LIKE ? OR
            m.keywords LIKE ? OR
            m.ocr_text LIKE ? OR
            t.name LIKE ?
        )
        ORDER BY f.upload_date DESC
        LIMIT ? OFFSET ?
    '''
    
    search_term = f'%{query}%'
    args = (search_term,) * 6 + (per_page, (page - 1) * per_page)
    
    results_raw = query_db(search_query, args)
    
    # Convert to dicts and add tags
    results = []
    for result_row in results_raw:
        result_dict = dict(result_row)
        tags = query_db('''
            SELECT t.name
            FROM tags t
            JOIN file_tags ft ON t.id = ft.tag_id
            WHERE ft.file_id = ?
        ''', (result_dict['id'],))
        result_dict['tags'] = [tag['name'] for tag in tags]
        results.append(result_dict)
    
    # Get total count
    count_query = '''
        SELECT COUNT(DISTINCT f.id) as count
        FROM files f
        LEFT JOIN metadata m ON f.id = m.file_id
        LEFT JOIN file_tags ft ON f.id = ft.file_id
        LEFT JOIN tags t ON ft.tag_id = t.id
        WHERE f.deleted = 0 AND (
            f.filename LIKE ? OR
            m.title LIKE ? OR
            m.description LIKE ? OR
            m.keywords LIKE ? OR
            m.ocr_text LIKE ? OR
            t.name LIKE ?
        )
    '''
    
    total_count = query_db(count_query, (search_term,) * 6, one=True)['count']
    
    # Find related files using semantic relationships
    related_files = find_related_files(query, [r['id'] for r in results])
    
    total_pages = (total_count + per_page - 1) // per_page
    
    return render_template('temp_search.html',
                         query=query,
                         results=results,
                         related_files=related_files,
                         page=page,
                         total_pages=total_pages,
                         total_count=total_count)

@files_bp.route('/delete/<int:file_id>', methods=['POST'])
@admin_required
def delete_file(file_id):
    """Soft delete file and move to deleted_for_review folder"""
    file_info = query_db('SELECT * FROM files WHERE id = ?', (file_id,), one=True)
    
    if not file_info:
        return jsonify({'error': 'File not found'}), 404
    
    try:
        # Create deleted_for_review directory if needed
        deleted_dir = os.path.join(current_app.config['DATA_DIR'], 'deleted_for_review')
        os.makedirs(deleted_dir, exist_ok=True)
        
        # Move file to deleted folder
        old_path = file_info['filepath']
        if os.path.exists(old_path):
            filename = f"{file_id}_{os.path.basename(old_path)}"
            new_path = os.path.join(deleted_dir, filename)
            shutil.move(old_path, new_path)
            
            # Update database with new path
            execute_db('''
                UPDATE files
                SET deleted = 1, deleted_date = CURRENT_TIMESTAMP, filepath = ?
                WHERE id = ?
            ''', (new_path, file_id))
        else:
            # File already missing, just mark as deleted
            execute_db('''
                UPDATE files
                SET deleted = 1, deleted_date = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (file_id,))
    
        if current_app.config['DEBUG']:
            current_app.logger.debug(f"Moved deleted file: {old_path} -> {new_path}")
        
        flash('File moved to deleted folder', 'success')
        return redirect(url_for('files.browse'))
        
    except Exception as e:
        current_app.logger.error(f"Error deleting file {file_id}: {str(e)}")
        flash('Error deleting file', 'error')
        return redirect(url_for('files.browse'))

def find_related_files(query, exclude_ids):
    """Find related files based on semantic relationships"""
    # Placeholder function - implement semantic search logic
    return []