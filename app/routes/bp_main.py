"""
/home/life/app/routes/bp_main.py
Version: 1.1.1
Purpose: Main routes with exact bin collection types
Created: 2025-06-11
Updated: 2025-06-13 - Updated to use exact bin types from config
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session
from datetime import datetime, date, timedelta
import json
from routes.bp_auth import login_required, admin_required
from utils.util_db import get_db, query_db, execute_db


main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    """Homepage with daily dashboard"""
    db = get_db()
    today = date.today()
    
    # Get today's reminders
    reminders = query_db('''
        SELECT id, title, completed, recurring
        FROM reminders
        WHERE (due_date = ? OR recurring IS NOT NULL)
        AND (completed = 0 OR recurring IS NOT NULL)
        ORDER BY completed, title
    ''', (today,))
    
    # Get upcoming appointments (next 7 days)
    appointments = query_db('''
        SELECT id, title, date, time, category
        FROM events
        WHERE date >= ? AND date <= ?
        ORDER BY date, time
        LIMIT 5
    ''', (today, today + timedelta(days=7)))
    
    # Get shopping list count
    shopping_count = query_db('''
        SELECT COUNT(*) as count
        FROM shopping_items
        WHERE completed = 0
    ''', one=True)['count']
    
    # Check bin collections for today and tomorrow
    refuse_bins = check_bin_collections(today)
    
    # Get recent files
    recent_files = query_db('''
        SELECT f.id, f.filename, m.title, f.upload_date
        FROM files f
        LEFT JOIN metadata m ON f.id = m.file_id
        WHERE f.deleted = 0
        ORDER BY f.upload_date DESC
        LIMIT 5
    ''')
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"Dashboard data - Reminders: {len(reminders)}, "
                                f"Appointments: {len(appointments)}, "
                                f"Shopping items: {shopping_count}")
    
    return render_template('temp_index.html',
                         today=today,
                         reminders=reminders,
                         appointments=appointments,
                         shopping_count=shopping_count,
                         refuse_bins=refuse_bins,
                         recent_files=recent_files)

@main_bp.route('/bins/schedule')
@login_required
def bin_schedule():
    """Manage bin collection schedule"""
    today = date.today()
    
    # Get upcoming collections
    upcoming = query_db('''
        SELECT id, date, time, bin_types, completed, notes
        FROM bin_collections
        WHERE date >= ? AND completed = 0
        ORDER BY date
    ''', (today,))
    
    # Get past collections (last 10)
    past = query_db('''
        SELECT id, date, time, bin_types, completed
        FROM bin_collections
        WHERE date < ? OR completed = 1
        ORDER BY date DESC
        LIMIT 10
    ''', (today,))
    
    # Process collections for display
    upcoming_collections = []
    for collection in upcoming:
        bin_types = json.loads(collection['bin_types'])
        days_until = (collection['date'] - today).days
        
        if days_until == 0:
            days_str = "Today"
        elif days_until == 1:
            days_str = "Tomorrow"
        else:
            days_str = f"In {days_until} days"
        
        upcoming_collections.append({
            'id': collection['id'],
            'date': collection['date'],
            'time': collection['time'],
            'bin_types': bin_types,
            'days_until': days_str,
            'notes': collection['notes']
        })
    
    past_collections = []
    for collection in past:
        bin_types = json.loads(collection['bin_types'])
        past_collections.append({
            'id': collection['id'],
            'date': collection['date'],
            'time': collection['time'],
            'bin_types': bin_types,
            'completed': collection['completed']
        })
    
    return render_template('temp_bin_schedule.html',
                         upcoming_collections=upcoming_collections,
                         past_collections=past_collections)

@main_bp.route('/bins/add', methods=['POST'])
@login_required
def add_bin_collection():
    """Add new bin collection"""
    collection_date = request.form.get('collection_date')
    collection_time = request.form.get('collection_time')
    bin_types = request.form.getlist('bin_types')
    
    if not collection_date or not bin_types:
        flash('Date and at least one bin type are required', 'error')
        return redirect(url_for('main.bin_schedule'))
    
    # Check for duplicate date
    existing = query_db('SELECT id FROM bin_collections WHERE date = ? AND completed = 0', 
                       (collection_date,), one=True)
    if existing:
        flash('Collection already scheduled for this date', 'warning')
        return redirect(url_for('main.bin_schedule'))
    
    # Store bin types as JSON
    bin_types_json = json.dumps(bin_types)
    
    execute_db('''
        INSERT INTO bin_collections (date, time, bin_types)
        VALUES (?, ?, ?)
    ''', (collection_date, collection_time, bin_types_json))
    
    # Create readable bin names for flash message
    bin_names = []
    for bin_type in bin_types:
        bin_info = current_app.config['BIN_TYPES'].get(bin_type, {})
        bin_names.append(bin_info.get('name', bin_type))
    
    flash(f'Scheduled collection for {collection_date}: {", ".join(bin_names)}', 'success')
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"Added bin collection: {collection_date}, bins: {bin_types}")
    
    return redirect(url_for('main.bin_schedule'))

@main_bp.route('/bins/delete/<int:collection_id>', methods=['POST'])
@login_required
def delete_bin_collection(collection_id):
    """Delete bin collection"""
    collection = query_db('SELECT date, bin_types FROM bin_collections WHERE id = ?', 
                         (collection_id,), one=True)
    
    if not collection:
        flash('Collection not found', 'error')
        return redirect(url_for('main.bin_schedule'))
    
    execute_db('DELETE FROM bin_collections WHERE id = ?', (collection_id,))
    
    flash(f'Deleted collection for {collection["date"]}', 'success')
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"Deleted bin collection {collection_id}")
    
    return redirect(url_for('main.bin_schedule'))

@main_bp.route('/bins/complete/<int:collection_id>', methods=['POST'])
@login_required
def complete_bin_collection(collection_id):
    """Mark bin collection as completed"""
    execute_db('''
        UPDATE bin_collections 
        SET completed = 1 
        WHERE id = ?
    ''', (collection_id,))
    
    flash('Collection marked as completed', 'success')
    return redirect(url_for('main.bin_schedule'))

@main_bp.route('/calendar')
@main_bp.route('/calendar/<int:year>/<int:month>')
@login_required
def calendar(year=None, month=None):
    """Calendar view with events and refuse collection"""
    if year is None:
        today = date.today()
        year = today.year
        month = today.month
    
    # Get events for the month
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)
    
    events = query_db('''
        SELECT id, title, date, time, category, recurring, description
        FROM events
        WHERE (date >= ? AND date <= ?) OR recurring IS NOT NULL
        ORDER BY date, time
    ''', (start_date, end_date))
    
    # Build calendar data
    calendar_data = build_calendar_data(year, month, events)
    
    return render_template('temp_calendar.html',
                         year=year,
                         month=month,
                         calendar_data=calendar_data)

@main_bp.route('/calendar/recurring')
@login_required
def recurring_events():
    """Manage recurring events - view and delete problematic ones"""
    # Get all recurring events
    recurring = query_db('''
        SELECT id, title, date, time, category, recurring, description, created_date
        FROM events
        WHERE recurring IS NOT NULL AND recurring != ''
        ORDER BY created_date DESC, title
    ''')
    
    # Get all events (to see duplicates)
    all_events = query_db('''
        SELECT id, title, date, time, category, recurring, description
        FROM events
        ORDER BY date DESC, title
        LIMIT 50
    ''')
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"Found {len(recurring)} recurring events")
    
    return render_template('temp_recurring_events.html',
                         recurring_events=recurring,
                         all_events=all_events)

@main_bp.route('/calendar/recurring/delete/<int:event_id>', methods=['POST'])
@login_required
def delete_recurring_event(event_id):
    """Delete a recurring event"""
    event = query_db('SELECT title, recurring FROM events WHERE id = ?', (event_id,), one=True)
    
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('main.recurring_events'))
    
    execute_db('DELETE FROM events WHERE id = ?', (event_id,))
    
    flash(f'Deleted recurring event: {event["title"]}', 'success')
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"Deleted recurring event {event_id}: {event['title']}")
    
    return redirect(url_for('main.recurring_events'))

@main_bp.route('/calendar/recurring/delete_all', methods=['POST'])
@admin_required
def delete_all_recurring():
    """Delete ALL recurring events (admin only)"""
    count = query_db('SELECT COUNT(*) as count FROM events WHERE recurring IS NOT NULL AND recurring != ""', one=True)['count']
    
    execute_db('DELETE FROM events WHERE recurring IS NOT NULL AND recurring != ""')
    
    flash(f'Deleted all {count} recurring events', 'success')
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"Deleted all {count} recurring events")
    
    return redirect(url_for('main.recurring_events'))

@main_bp.route('/calendar/day/<date_str>')
@login_required
def day_view(date_str):
    """Single day view with large event blocks"""
    try:
        view_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date', 'error')
        return redirect(url_for('main.calendar'))
    
    # Get events for this day
    events = query_db('''
        SELECT id, title, time, category, description
        FROM events
        WHERE date = ?
        ORDER BY time
    ''', (view_date,))
    
    # Get bin collections for this day
    refuse_bins = check_bin_collections(view_date)
    
    # Calculate prev/next dates
    prev_date = view_date - timedelta(days=1)
    next_date = view_date + timedelta(days=1)
    
    return render_template('temp_day_view.html',
                         view_date=view_date,
                         events=events,
                         refuse_bins=refuse_bins,
                         prev_date=prev_date,
                         next_date=next_date)

@main_bp.route('/lists')
@login_required
def lists():
    """Shopping list and common items"""
    shopping_items = query_db('''
        SELECT id, item, quantity, completed
        FROM shopping_items
        ORDER BY completed, item
    ''')
    
    common_items = query_db('''
        SELECT DISTINCT item
        FROM shopping_items
        WHERE common_item = 1
        ORDER BY item
    ''')
    
    return render_template('temp_lists.html',
                         shopping_items=shopping_items,
                         common_items=common_items)

@main_bp.route('/reminder/toggle/<int:reminder_id>', methods=['POST'])
@login_required
def toggle_reminder(reminder_id):
    """Toggle reminder completion status"""
    reminder = query_db('SELECT * FROM reminders WHERE id = ?', (reminder_id,), one=True)
    
    if not reminder:
        return jsonify({'error': 'Reminder not found'}), 404
    
    new_status = 0 if reminder['completed'] else 1
    completed_date = datetime.now() if new_status else None
    
    execute_db('''
        UPDATE reminders 
        SET completed = ?, completed_date = ?
        WHERE id = ?
    ''', (new_status, completed_date, reminder_id))
    
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"Toggled reminder {reminder_id} to {new_status}")
    
    return jsonify({'completed': new_status})

@main_bp.route('/shopping/add', methods=['POST'])
@login_required
def add_shopping_item():
    """Add item to shopping list"""
    item = request.form.get('item', '').strip()
    quantity = request.form.get('quantity', '').strip()
    
    if not item:
        flash('Please enter an item', 'error')
        return redirect(url_for('main.lists'))
    
    execute_db('''
        INSERT INTO shopping_items (item, quantity, completed)
        VALUES (?, ?, 0)
    ''', (item, quantity))
    
    flash(f'Added {item} to shopping list', 'success')
    return redirect(url_for('main.lists'))

@main_bp.route('/shopping/toggle/<int:item_id>', methods=['POST'])
@login_required
def toggle_shopping_item(item_id):
    """Toggle shopping item completion"""
    current = query_db('SELECT completed FROM shopping_items WHERE id = ?', 
                      (item_id,), one=True)
    
    if not current:
        return jsonify({'error': 'Item not found'}), 404
    
    new_status = 0 if current['completed'] else 1
    execute_db('UPDATE shopping_items SET completed = ? WHERE id = ?',
              (new_status, item_id))
    
    return jsonify({'completed': new_status})

@main_bp.route('/event/add', methods=['GET', 'POST'])
@login_required
def add_event():
    """Add calendar event"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        event_date = request.form.get('date')
        event_time = request.form.get('time')
        category = request.form.get('category', 'appointment')
        recurring = request.form.get('recurring')
        description = request.form.get('description', '').strip()
        
                        # Handle bin events - store bin type in description
        if category == 'bin':
            bin_type = request.form.get('bin_type', '')
            if bin_type:
                description = bin_type  # Store bin type in description for color coding
                # Title should already be set correctly by JavaScript
                if not title or title == 'Bin':
                    # Fallback title generation using config
                    bin_config = current_app.config['BIN_TYPES'].get(bin_type, {})
                    title = bin_config.get('name', 'Bin')
        
        if not title or not event_date:
            flash('Title and date are required', 'error')
            return redirect(url_for('main.add_event'))
        
        execute_db('''
            INSERT INTO events (title, date, time, category, recurring, description)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, event_date, event_time, category, recurring, description))
        
        if current_app.config['DEBUG']:
            current_app.logger.debug(f"Added event: {title} on {event_date}, category: {category}, description: {description}")
        
        flash('Event added successfully', 'success')
        return redirect(url_for('main.calendar'))
    
    return render_template('temp_add_event.html')

@main_bp.route('/event/edit/<int:event_id>', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    """Edit calendar event"""
    event = query_db('SELECT * FROM events WHERE id = ?', (event_id,), one=True)
    
    if not event:
        flash('Event not found', 'error')
        return redirect(url_for('main.calendar'))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        event_date = request.form.get('date')
        event_time = request.form.get('time')
        category = request.form.get('category', 'appointment')
        recurring = request.form.get('recurring')
        description = request.form.get('description', '').strip()
        
        # Handle bin events - store bin type in description
        if category == 'bin':
            bin_type = request.form.get('bin_type', '')
            if bin_type:
                description = bin_type  # Store bin type in description for color coding
                # Update title to match bin type using config
                bin_config = current_app.config['BIN_TYPES'].get(bin_type, {})
                title = bin_config.get('name', 'Bin')
        
        if not title or not event_date:
            flash('Title and date are required', 'error')
            return redirect(url_for('main.edit_event', event_id=event_id))
        
        execute_db('''
            UPDATE events 
            SET title = ?, date = ?, time = ?, category = ?, recurring = ?, description = ?
            WHERE id = ?
        ''', (title, event_date, event_time, category, recurring, description, event_id))
        
        if current_app.config['DEBUG']:
            current_app.logger.debug(f"Updated event {event_id}: {title}, category: {category}, description: {description}")
        
        flash('Event updated successfully', 'success')
        return redirect(url_for('main.calendar'))
    
    return render_template('temp_edit_event.html', event=event)

@main_bp.route('/event/delete/<int:event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    """Delete calendar event"""
    event = query_db('SELECT title FROM events WHERE id = ?', (event_id,), one=True)
    
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    
    execute_db('DELETE FROM events WHERE id = ?', (event_id,))
    
    flash(f'Deleted event: {event["title"]}', 'success')
    return redirect(url_for('main.calendar'))

@main_bp.route('/event/move/<int:event_id>', methods=['POST'])
@login_required
def move_event(event_id):
    """Move event to new date"""
    new_date = request.json.get('new_date')
    
    if not new_date:
        return jsonify({'error': 'New date required'}), 400
    
    event = query_db('SELECT title FROM events WHERE id = ?', (event_id,), one=True)
    
    if not event:
        return jsonify({'error': 'Event not found'}), 404
    
    execute_db('UPDATE events SET date = ? WHERE id = ?', (new_date, event_id))
    
    return jsonify({'success': True, 'message': f'Moved {event["title"]} to {new_date}'})

# Helper functions
def check_bin_collections(check_date):
    """Check bin collections for specific date"""
    # Get bin collections for today and tomorrow
    collections = query_db('''
        SELECT date, bin_types
        FROM bin_collections
        WHERE date >= ? AND date <= ? AND completed = 0
        ORDER BY date
    ''', (check_date, check_date + timedelta(days=1)))
    
    bins = []
    for collection in collections:
        collection_date = collection['date']
        bin_types = json.loads(collection['bin_types'])
        
        for bin_type in bin_types:
            bin_info = current_app.config['BIN_TYPES'].get(bin_type, {})
            if collection_date == check_date:
                bins.append({
                    'type': f"{bin_info.get('name', bin_type)} ({bin_info.get('description', '')})",
                    'color': bin_type,
                    'when': 'today'
                })
            elif collection_date == check_date + timedelta(days=1):
                bins.append({
                    'type': f"{bin_info.get('name', bin_type)} ({bin_info.get('description', '')})",
                    'color': bin_type,
                    'when': 'tomorrow'
                })
    
    return bins

def build_calendar_data(year, month, events):
    """Build calendar grid with events"""
    import calendar
    
    cal = calendar.monthcalendar(year, month)
    calendar_data = []
    
    # Convert events to dict by date
    events_by_date = {}
    for event in events:
        # Handle both string and date object types
        if isinstance(event['date'], str):
            event_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
        else:
            event_date = event['date']  # Already a date object
            
        if event_date not in events_by_date:
            events_by_date[event_date] = []
        events_by_date[event_date].append(event)
    
    # Build calendar grid
    for week in cal:
        week_data = []
        for day in week:
            if day == 0:
                week_data.append({'day': None, 'events': []})
            else:
                day_date = date(year, month, day)
                day_events = events_by_date.get(day_date, [])
                refuse_bins = check_bin_collections(day_date)
                
                week_data.append({
                    'day': day,
                    'date': day_date,
                    'events': day_events,
                    'refuse_bins': refuse_bins,
                    'is_today': day_date == date.today()
                })
        calendar_data.append(week_data)
    
    return calendar_data