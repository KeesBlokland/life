"""
/home/life/app/routes/bp_main.py
Version: 1.0.1
Purpose: Main routes - homepage, calendar, shopping lists, reminders
Created: 2025-06-11
Updated: 2025-06-11 - Fixed date parsing for calendar events
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session
from datetime import datetime, date, timedelta
from routes.bp_auth import login_required
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
    
    # Check refuse bins for today
    refuse_bins = check_refuse_collection(today)
    
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
        SELECT id, title, date, time, category, recurring
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
        
        if not title or not event_date:
            flash('Title and date are required', 'error')
            return redirect(url_for('main.add_event'))
        
        execute_db('''
            INSERT INTO events (title, date, time, category, recurring, description)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, event_date, event_time, category, recurring, description))
        
        flash('Event added successfully', 'success')
        return redirect(url_for('main.calendar'))
    
    return render_template('temp_add_event.html')

# Helper functions
def check_refuse_collection(check_date):
    """Check which bins need to go out"""
    bins = []
    day_name = check_date.strftime('%A').lower()
    
    settings = {
        'refuse_blue_day': query_db("SELECT value FROM settings WHERE key = 'refuse_blue_day'", one=True),
        'refuse_yellow_day': query_db("SELECT value FROM settings WHERE key = 'refuse_yellow_day'", one=True),
        'refuse_brown_day': query_db("SELECT value FROM settings WHERE key = 'refuse_brown_day'", one=True)
    }
    
    if settings['refuse_blue_day'] and settings['refuse_blue_day']['value'] == day_name:
        bins.append({'type': 'Blue bin (Paper)', 'color': 'blue'})
    if settings['refuse_yellow_day'] and settings['refuse_yellow_day']['value'] == day_name:
        bins.append({'type': 'Yellow bin (Recycling)', 'color': 'yellow'})
    if settings['refuse_brown_day'] and settings['refuse_brown_day']['value'] == day_name:
        bins.append({'type': 'Brown bin (Bio)', 'color': 'brown'})
    
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
                refuse_bins = check_refuse_collection(day_date)
                
                week_data.append({
                    'day': day,
                    'date': day_date,
                    'events': day_events,
                    'refuse_bins': refuse_bins,
                    'is_today': day_date == date.today()
                })
        calendar_data.append(week_data)
    
    return calendar_data