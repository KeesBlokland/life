"""
bp_contacts.py - Contacts management routes with change request system
Version: 1.0.01
Purpose: Contact management - family, institutions, banks, healthcare, utilities with CRUD and change requests
Created: 2025-06-17
Updated: 2025-06-17 - Initial implementation with fuzzy search and change request workflow
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session
from datetime import datetime
from routes.bp_auth import login_required, admin_required
from utils.util_db import query_db, execute_db

contacts_bp = Blueprint('contacts', __name__)

@contacts_bp.route('/')
@contacts_bp.route('/browse')
@login_required
def browse():
    """Browse contacts with search and filtering"""
    search_query = request.args.get('q', '').strip()
    contact_type = request.args.get('type', '')
    category = request.args.get('category', '')
    
    # Build base query
    query = '''
        SELECT c.id, c.name, c.contact_type, c.category, c.notes, c.modified_date,
               COUNT(cd.id) as detail_count
        FROM contacts c
        LEFT JOIN contact_details cd ON c.id = cd.contact_id
        WHERE 1=1
    '''
    args = []
    
    # Add search filter
    if search_query:
        # Fuzzy search across contact name, type, category, and contact details
        search_terms = search_query.split()
        search_conditions = []
        
        for term in search_terms:
            search_term = f'%{term}%'
            search_conditions.append('''
                (c.name LIKE ? OR c.contact_type LIKE ? OR c.category LIKE ? OR 
                 c.notes LIKE ? OR c.id IN (
                    SELECT DISTINCT cd2.contact_id FROM contact_details cd2 
                    WHERE cd2.field_value LIKE ? OR cd2.field_name LIKE ?
                 ))
            ''')
            args.extend([search_term] * 6)
        
        if search_conditions:
            query += ' AND (' + ' AND '.join(search_conditions) + ')'
    
    # Add type filter
    if contact_type:
        query += ' AND c.contact_type = ?'
        args.append(contact_type)
    
    # Add category filter
    if category:
        query += ' AND c.category = ?'
        args.append(category)
    
    query += '''
        GROUP BY c.id, c.name, c.contact_type, c.category, c.notes, c.modified_date
        ORDER BY c.name ASC
    '''
    
    contacts = query_db(query, args)
    
    # Get available types and categories for filters
    contact_types = query_db('SELECT DISTINCT contact_type FROM contacts ORDER BY contact_type')
    categories = query_db('SELECT DISTINCT category FROM contacts WHERE category IS NOT NULL ORDER BY category')
    
    # Convert to lists for template
    contact_types = [ct['contact_type'] for ct in contact_types]
    categories = [cat['category'] for cat in categories]
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"Found {len(contacts)} contacts with search: '{search_query}'")
    
    return render_template('temp_contacts.html',
                         contacts=contacts,
                         search_query=search_query,
                         contact_types=contact_types,
                         categories=categories,
                         selected_type=contact_type,
                         selected_category=category)

@contacts_bp.route('/view/<int:contact_id>')
@login_required
def view_contact(contact_id):
    """View single contact with all details"""
    contact = query_db('SELECT * FROM contacts WHERE id = ?', (contact_id,), one=True)
    
    if not contact:
        flash('Contact not found', 'error')
        return redirect(url_for('contacts.browse'))
    
    # Get contact details ordered by field_order
    details = query_db('''
        SELECT * FROM contact_details 
        WHERE contact_id = ? 
        ORDER BY field_order ASC, field_name ASC
    ''', (contact_id,))
    
    # Group details by type for display
    grouped_details = {
        'basic': [],
        'sensitive': []
    }
    
    for detail in details:
        if detail['is_sensitive']:
            grouped_details['sensitive'].append(detail)
        else:
            grouped_details['basic'].append(detail)
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"Viewing contact {contact_id}: {contact['name']}")
    
    return render_template('temp_contact_view.html',
                         contact=contact,
                         details=grouped_details)

@contacts_bp.route('/add', methods=['GET', 'POST'])
@admin_required
def add_contact():
    """Add new contact (admin only)"""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        contact_type = request.form.get('contact_type', '').strip()
        category = request.form.get('category', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if not name:
            flash('Contact name is required', 'error')
            return redirect(url_for('contacts.add_contact'))
        
        if not contact_type:
            flash('Contact type is required', 'error')
            return redirect(url_for('contacts.add_contact'))
        
        try:
            # Create contact
            contact_id = execute_db('''
                INSERT INTO contacts (name, contact_type, category, notes)
                VALUES (?, ?, ?, ?)
            ''', (name, contact_type, category, notes))
            
            # Process contact details from form
            detail_names = request.form.getlist('detail_name')
            detail_values = request.form.getlist('detail_value')
            detail_sensitive = request.form.getlist('detail_sensitive')
            
            for i, (field_name, field_value) in enumerate(zip(detail_names, detail_values)):
                if field_name.strip() and field_value.strip():
                    is_sensitive = str(i) in detail_sensitive
                    execute_db('''
                        INSERT INTO contact_details (contact_id, field_name, field_value, is_sensitive, field_order)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (contact_id, field_name.strip(), field_value.strip(), is_sensitive, i))
            
            flash(f'Contact "{name}" added successfully', 'success')
            return redirect(url_for('contacts.view_contact', contact_id=contact_id))
            
        except Exception as e:
            current_app.logger.error(f"Error adding contact: {str(e)}")
            flash('Error adding contact', 'error')
    
    return render_template('temp_contact_edit.html', contact=None, details=[])

@contacts_bp.route('/edit/<int:contact_id>', methods=['GET', 'POST'])
@admin_required
def edit_contact(contact_id):
    """Edit contact (admin only)"""
    contact = query_db('SELECT * FROM contacts WHERE id = ?', (contact_id,), one=True)
    
    if not contact:
        flash('Contact not found', 'error')
        return redirect(url_for('contacts.browse'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        contact_type = request.form.get('contact_type', '').strip()
        category = request.form.get('category', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if not name:
            flash('Contact name is required', 'error')
            return redirect(url_for('contacts.edit_contact', contact_id=contact_id))
        
        if not contact_type:
            flash('Contact type is required', 'error')
            return redirect(url_for('contacts.edit_contact', contact_id=contact_id))
        
        try:
            # Update contact
            execute_db('''
                UPDATE contacts 
                SET name = ?, contact_type = ?, category = ?, notes = ?, modified_date = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (name, contact_type, category, notes, contact_id))
            
            # Delete existing details
            execute_db('DELETE FROM contact_details WHERE contact_id = ?', (contact_id,))
            
            # Add new details from form
            detail_names = request.form.getlist('detail_name')
            detail_values = request.form.getlist('detail_value')
            detail_sensitive = request.form.getlist('detail_sensitive')
            
            for i, (field_name, field_value) in enumerate(zip(detail_names, detail_values)):
                if field_name.strip() and field_value.strip():
                    is_sensitive = str(i) in detail_sensitive
                    execute_db('''
                        INSERT INTO contact_details (contact_id, field_name, field_value, is_sensitive, field_order)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (contact_id, field_name.strip(), field_value.strip(), is_sensitive, i))
            
            flash(f'Contact "{name}" updated successfully', 'success')
            return redirect(url_for('contacts.view_contact', contact_id=contact_id))
            
        except Exception as e:
            current_app.logger.error(f"Error updating contact: {str(e)}")
            flash('Error updating contact', 'error')
    
    # Get existing details for editing
    details = query_db('''
        SELECT * FROM contact_details 
        WHERE contact_id = ? 
        ORDER BY field_order ASC, field_name ASC
    ''', (contact_id,))
    
    return render_template('temp_contact_edit.html', contact=contact, details=details)

@contacts_bp.route('/delete/<int:contact_id>', methods=['POST'])
@admin_required
def delete_contact(contact_id):
    """Delete contact (admin only)"""
    contact = query_db('SELECT name FROM contacts WHERE id = ?', (contact_id,), one=True)
    
    if not contact:
        flash('Contact not found', 'error')
        return redirect(url_for('contacts.browse'))
    
    try:
        # Delete contact (cascade will handle details)
        execute_db('DELETE FROM contacts WHERE id = ?', (contact_id,))
        
        flash(f'Contact "{contact["name"]}" deleted successfully', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error deleting contact: {str(e)}")
        flash('Error deleting contact', 'error')
    
    return redirect(url_for('contacts.browse'))

@contacts_bp.route('/request_change/<int:contact_id>', methods=['GET', 'POST'])
@login_required
def request_change(contact_id):
    """Submit change request for contact (users)"""
    contact = query_db('SELECT * FROM contacts WHERE id = ?', (contact_id,), one=True)
    
    if not contact:
        flash('Contact not found', 'error')
        return redirect(url_for('contacts.browse'))
    
    if request.method == 'POST':
        change_description = request.form.get('change_description', '').strip()
        
        if not change_description:
            flash('Please describe the changes needed', 'error')
            return redirect(url_for('contacts.request_change', contact_id=contact_id))
        
        try:
            execute_db('''
                INSERT INTO contact_change_requests (contact_id, contact_name, change_description, requested_by)
                VALUES (?, ?, ?, ?)
            ''', (contact_id, contact['name'], change_description, session.get('user_type', 'user')))
            
            flash('Change request submitted successfully', 'success')
            return redirect(url_for('contacts.view_contact', contact_id=contact_id))
            
        except Exception as e:
            current_app.logger.error(f"Error submitting change request: {str(e)}")
            flash('Error submitting change request', 'error')
    
    return render_template('temp_contact_change_request.html', contact=contact)

@contacts_bp.route('/request_new', methods=['GET', 'POST'])
@login_required
def request_new_contact():
    """Request new contact addition (users)"""
    if request.method == 'POST':
        contact_name = request.form.get('contact_name', '').strip()
        change_description = request.form.get('change_description', '').strip()
        
        if not contact_name:
            flash('Contact name is required', 'error')
            return redirect(url_for('contacts.request_new_contact'))
        
        if not change_description:
            flash('Please provide contact details', 'error')
            return redirect(url_for('contacts.request_new_contact'))
        
        try:
            execute_db('''
                INSERT INTO contact_change_requests (contact_id, contact_name, change_description, requested_by)
                VALUES (?, ?, ?, ?)
            ''', (None, contact_name, f"NEW CONTACT REQUEST: {change_description}", session.get('user_type', 'user')))
            
            flash('New contact request submitted successfully', 'success')
            return redirect(url_for('contacts.browse'))
            
        except Exception as e:
            current_app.logger.error(f"Error submitting new contact request: {str(e)}")
            flash('Error submitting new contact request', 'error')
    
    return render_template('temp_contact_new_request.html')

@contacts_bp.route('/admin/change_requests')
@admin_required
def admin_change_requests():
    """View all change requests (admin only)"""
    requests = query_db('''
        SELECT cr.*, c.name as existing_contact_name
        FROM contact_change_requests cr
        LEFT JOIN contacts c ON cr.contact_id = c.id
        WHERE cr.status = 'pending'
        ORDER BY cr.created_date DESC
    ''')
    
    return render_template('temp_admin_contact_requests.html', requests=requests)

@contacts_bp.route('/admin/process_request/<int:request_id>', methods=['POST'])
@admin_required
def process_change_request(request_id):
    """Process change request (admin only)"""
    action = request.form.get('action')
    admin_notes = request.form.get('admin_notes', '').strip()
    
    if action not in ['approve', 'reject']:
        flash('Invalid action', 'error')
        return redirect(url_for('contacts.admin_change_requests'))
    
    try:
        # Update request status
        execute_db('''
            UPDATE contact_change_requests 
            SET status = ?, admin_notes = ?, processed_date = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (action + 'd', admin_notes, request_id))
        
        flash(f'Change request {action}d successfully', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error processing change request: {str(e)}")
        flash('Error processing change request', 'error')
    
    return redirect(url_for('contacts.admin_change_requests'))

@contacts_bp.route('/search')
@login_required
def search():
    """AJAX search endpoint for autocomplete"""
    query = request.args.get('q', '').strip()
    
    if not query or len(query) < 2:
        return jsonify([])
    
    # Search contacts and return suggestions
    search_results = query_db('''
        SELECT DISTINCT c.id, c.name, c.contact_type, c.category
        FROM contacts c
        LEFT JOIN contact_details cd ON c.id = cd.contact_id
        WHERE c.name LIKE ? OR c.contact_type LIKE ? OR c.category LIKE ? OR 
              cd.field_value LIKE ? OR cd.field_name LIKE ?
        ORDER BY c.name ASC
        LIMIT 10
    ''', (f'%{query}%',) * 5)
    
    suggestions = []
    for result in search_results:
        suggestions.append({
            'id': result['id'],
            'name': result['name'],
            'type': result['contact_type'],
            'category': result['category']
        })
    
    return jsonify(suggestions)

@contacts_bp.route('/quick_add', methods=['POST'])
@admin_required
def quick_add():
    """Quick add contact via AJAX (admin only)"""
    name = request.form.get('name', '').strip()
    contact_type = request.form.get('type', '').strip()
    
    if not name or not contact_type:
        return jsonify({'success': False, 'message': 'Name and type required'})
    
    try:
        contact_id = execute_db('''
            INSERT INTO contacts (name, contact_type, category)
            VALUES (?, ?, ?)
        ''', (name, contact_type, 'General'))
        
        return jsonify({
            'success': True, 
            'message': f'Contact "{name}" added',
            'contact_id': contact_id
        })
        
    except Exception as e:
        current_app.logger.error(f"Error in quick add: {str(e)}")
        return jsonify({'success': False, 'message': 'Error adding contact'})

# API endpoint for contact statistics
@contacts_bp.route('/admin/bulk_process_requests', methods=['POST'])
@admin_required
def bulk_process_requests():
    """Bulk process all pending change requests (admin only)"""
    action = request.form.get('action')
    admin_notes = request.form.get('admin_notes', '').strip()
    
    if action not in ['approve_all', 'reject_all']:
        flash('Invalid bulk action', 'error')
        return redirect(url_for('contacts.admin_change_requests'))
    
    try:
        # Get all pending requests
        pending_requests = query_db('SELECT id FROM contact_change_requests WHERE status = "pending"')
        
        if not pending_requests:
            flash('No pending requests to process', 'warning')
            return redirect(url_for('contacts.admin_change_requests'))
        
        # Process all requests
        status = 'approved' if action == 'approve_all' else 'rejected'
        processed_count = 0
        
        for request_row in pending_requests:
            execute_db('''
                UPDATE contact_change_requests 
                SET status = ?, admin_notes = ?, processed_date = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (status, admin_notes, request_row['id']))
            processed_count += 1
        
        flash(f'Bulk {status} {processed_count} change requests', 'success')
        
    except Exception as e:
        current_app.logger.error(f"Error in bulk processing: {str(e)}")
        flash('Error processing bulk requests', 'error')
    
    return redirect(url_for('contacts.admin_change_requests'))

@contacts_bp.route('/api/stats')
@admin_required
def contact_stats():
    """Get contact statistics for admin dashboard"""
    stats = {
        'total_contacts': query_db('SELECT COUNT(*) as count FROM contacts', one=True)['count'],
        'pending_requests': query_db('SELECT COUNT(*) as count FROM contact_change_requests WHERE status = "pending"', one=True)['count'],
        'by_type': query_db('SELECT contact_type, COUNT(*) as count FROM contacts GROUP BY contact_type ORDER BY count DESC'),
        'recent_additions': query_db('SELECT COUNT(*) as count FROM contacts WHERE created_date >= date("now", "-7 days")', one=True)['count']
    }
    
    return jsonify(stats)