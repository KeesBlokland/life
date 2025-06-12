"""
/home/life/app/routes/bp_files.py
Version: 1.0.0
Purpose: File handling routes - upload, download, browse, search
Created: 2025-06-11
"""

import os
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
@files_bp.route('/browse/<category>')
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
    
    files = query_db(query, args)
    total_count = query_db(count_query, count_args, one=True)['count']
    
    # Get category list
    categories = query_db('''
        SELECT DISTINCT auto_category, COUNT(*) as count
        FROM metadata m
        JOIN files f ON m.file_id = f.id
        WHERE f.deleted = 0 AND auto_category IS NOT NULL
        GROUP BY auto_category
        ORDER BY auto_category
    ''')
    
    # Add file tags
    for file in files:
        tags = query_db('''
            SELECT t.name
            FROM tags t
            JOIN file_tags ft ON t.id = ft.tag_id
            WHERE ft.file_id = ?
        ''', (file['id'],))
        file['tags'] = [tag['name'] for tag in tags]
    
    # Calculate pagination
    total_pages = (total_count + per_page - 1) // per_page
    
    return render_template('temp_files.html',
                         files=files,
                         categories=categories,
                         current_category=category,
                         page=page,
                         total_pages=total_pages)

@files_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """Upload files with metadata"""
    if request.method == 'POST':
        # Check if file was provided
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
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
                flash(f'This file already exists: {duplicate["filename"]}', 'warning')
                return redirect(url_for('files.browse'))
            
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
            title = request.form.get('title', original_filename)
            description = request.form.get('description', '')
            tags = request.form.get('tags', '').strip()
            
            execute_db('''
                INSERT INTO metadata (file_id, title, description, keywords, auto_category)
                VALUES (?, ?, ?, ?, ?)
            ''', (file_id, title, description, tags, category))
            
            # Process tags
            if tags:
                for tag_name in tags.split(','):
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
                current_app.logger.debug(f"File uploaded: {original_filename} -> {storage_path}, "
                                       f"Category: {category}, Size: {size}, Checksum: {checksum}")
            
            flash(f'File uploaded successfully: {title}', 'success')
            
            # Check for camera upload (from iPad)
            if request.form.get('camera_upload') == 'true':
                return jsonify({'success': True, 'file_id': file_id})
            
            return redirect(url_for('files.browse'))
        else:
            flash('File type not allowed', 'error')
            return redirect(request.url)
    
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
    
    results = query_db(search_query, args)
    
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
    
    # Add tags to results
    for result in results:
        tags = query_db('''
            SELECT t.name
            FROM tags t
            JOIN file_tags ft ON t.id = ft.tag_id
            WHERE ft.file_id = ?
        ''', (result['id'],))
        result['tags'] = [tag['name'] for tag in tags]
    
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
    """Soft delete file (admin only)"""
    file_info = query_db('SELECT * FROM files WHERE id = ?', (file_id,), one=True)
    
    if not file_info:
        return jsonify({'error': 'File not found'}), 404
    
    # Soft delete
    execute_db('''
        UPDATE files
        SET deleted = 1, deleted_date = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (file_id,))
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"Soft deleted file: {file_info['filename']} (ID: {file_id})")
    
    flash('File deleted', 'success')
    return redirect(url_for('files.browse'))

def find_related_files(search_term, exclude_ids):
    """Find files related to search term using semantic relationships"""
    # Look for matching relationship terms
    relationships = query_db('''
        SELECT term, related_terms
        FROM relationships
        WHERE term LIKE ? OR related_terms LIKE ?
    ''', (f'%{search_term}%', f'%{search_term}%'))
    
    related_keywords = set()
    for rel in relationships:
        if search_term.lower() in rel['term'].lower():
            import json
            related_keywords.update(json.loads(rel['related_terms']))
    
    if not related_keywords:
        return []
    
    # Search for files with related keywords
    placeholders = ','.join(['?'] * len(related_keywords))
    query = f'''
        SELECT DISTINCT f.id, f.filename, m.title, m.description
        FROM files f
        LEFT JOIN metadata m ON f.id = m.file_id
        WHERE f.deleted = 0 AND f.id NOT IN ({','.join(['?'] * len(exclude_ids))})
        AND (m.keywords IN ({placeholders}) OR m.title IN ({placeholders}))
        LIMIT 5
    '''
    
    args = exclude_ids + list(related_keywords) + list(related_keywords)
    return query_db(query, args)