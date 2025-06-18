#!/usr/bin/env python3
"""
dir_bp_main.py - Main routes - homepage, calendar, shopping lists, reminders
Version: 1.0.6
Purpose: Main routes with 4-week rolling calendar instead of rigid monthly boundaries
Created: 2025-06-11
Updated: 2025-06-13 - Modified calendar to show 4-week rolling periods for better planning
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, session
from datetime import datetime, date, timedelta
from routes.bp_auth import login_required, admin_required
from utils.util_db import get_db, query_db, execute_db
from flask import make_response

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
@main_bp.route('/calendar/<date_str>')
@login_required
def calendar(date_str=None):
    """Calendar view with 4-week rolling periods instead of rigid months"""
    
    # Determine the start date for the 4-week period
    if date_str:
        try:
            start_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = date.today()
    else:
        start_date = date.today()
    
    # Calculate 4-week period
    end_date = start_date + timedelta(days=27)  # 4 weeks (28 days total)
    
    # Get events for this 4-week period
    events = query_db('''
        SELECT id, title, date, time, category, recurring
        FROM events
        WHERE (date >= ? AND date <= ?) OR recurring IS NOT NULL
        ORDER BY date, time
    ''', (start_date, end_date))
    
    # Build calendar data for 4-week period
    calendar_data = build_calendar_data_weeks(start_date, end_date, events)
    
    # Calculate navigation dates
    prev_start = start_date - timedelta(days=28)
    next_start = start_date + timedelta(days=28)
    
    # For template compatibility, pass month/year of start date
    year = start_date.year
    month = start_date.month
    
    return render_template('temp_calendar.html',
                         year=year,
                         month=month,
                         start_date=start_date,
                         end_date=end_date,
                         prev_start=prev_start,
                         next_start=next_start,
                         calendar_data=calendar_data)

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
    
    # Get refuse bins for this day
    refuse_bins = check_refuse_collection(view_date)
    
    # Calculate prev/next dates
    prev_date = view_date - timedelta(days=1)
    next_date = view_date + timedelta(days=1)
    
    return render_template('temp_day_view.html',
                         view_date=view_date,
                         events=events,
                         refuse_bins=refuse_bins,
                         prev_date=prev_date,
                         next_date=next_date)



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
        
        if not title or not event_date:
            flash('Title and date are required', 'error')
            return redirect(url_for('main.edit_event', event_id=event_id))
        
        execute_db('''
            UPDATE events 
            SET title = ?, date = ?, time = ?, category = ?, recurring = ?, description = ?
            WHERE id = ?
        ''', (title, event_date, event_time, category, recurring, description, event_id))
        
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

@main_bp.route('/bins')
@login_required
def bin_schedule():
    """Bins button redirects directly to calendar for interaction"""
    return redirect(url_for('main.calendar'))
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

def build_calendar_data_weeks(start_date, end_date, events):
    """Build calendar data for 4-week date range instead of calendar months"""
    calendar_data = []
    
    # Convert events to dict by date
    events_by_date = {}
    for event in events:
        # Handle both string and date object types
        if isinstance(event['date'], str):
            event_date = datetime.strptime(event['date'], '%Y-%m-%d').date()
        else:
            event_date = event['date']
            
        # Only include events in our 4-week range
        if start_date <= event_date <= end_date:
            if event_date not in events_by_date:
                events_by_date[event_date] = []
            events_by_date[event_date].append(event)
    
    # Build 4 weeks of data
    current_date = start_date
    current_week = []
    
    while current_date <= end_date:
        day_events = events_by_date.get(current_date, [])
        refuse_bins = check_refuse_collection(current_date)
        
        day_data = {
            'day': current_date.day,
            'date': current_date,
            'events': day_events,
            'refuse_bins': refuse_bins,
            'is_today': current_date == date.today()
        }
        
        current_week.append(day_data)
        
        # Every 7 days, start a new week
        if len(current_week) == 7:
            calendar_data.append(current_week)
            current_week = []
        
        current_date += timedelta(days=1)
    
    # Add any remaining days
    if current_week:
        # Pad with empty days if needed
        while len(current_week) < 7:
            current_week.append({'day': None, 'date': None, 'events': [], 'refuse_bins': []})
        calendar_data.append(current_week)
    
    return calendar_data

def build_calendar_data(year, month, events):
    """Build calendar grid with events (legacy function - kept for compatibility)"""
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

 
@main_bp.route('/lists')
@main_bp.route('/lists/<list_name>')
@login_required
def lists(list_name='food'):
    """Shopping list memory support system"""
    # Get configured lists
    available_lists = current_app.config.get('SHOPPING_LISTS', [])
    
    # Non-admin users can only access food list
    if not session.get('is_admin') and list_name != 'food':
        return redirect(url_for('main.lists', list_name='food'))
    
    # Validate list name
    valid_names = [l['name'] for l in available_lists]
    if list_name not in valid_names:
        list_name = 'food'
    
    # Get master list - all items ever bought, ordered by frequency
    master_items = query_db('''
        SELECT item, MAX(quantity) as usual_quantity, COUNT(*) as times_bought,
               MAX(created_date) as last_bought
        FROM shopping_items
        WHERE list_name = ? AND master_list = 1
        GROUP BY item
        ORDER BY times_bought DESC, item
    ''', (list_name,))
    
    # Get today's list - items selected for shopping
    today_items = query_db('''
        SELECT id, item, quantity, added_date
        FROM shopping_items
        WHERE list_name = ? AND today_list = 1
        ORDER BY item
    ''', (list_name,))
    
    # Get current list info
    current_list = next((l for l in available_lists if l['name'] == list_name), {'name': 'food', 'title': 'Food Shopping'})
    
    return render_template('temp_lists.html',
                         available_lists=available_lists,
                         current_list=current_list,
                         master_items=master_items,
                         today_items=today_items)

@main_bp.route('/shopping/add_to_today', methods=['POST'])
@login_required
def add_to_today():
    """Add item from master list to today's shopping - SILENT"""
    item = request.form.get('item', '').strip()
    list_name = request.form.get('list_name', 'food')
    
    if not item:
        flash('No item specified', 'error')
        return redirect(url_for('main.lists', list_name=list_name))
    
    # Check if already on today's list
    existing = query_db('''
        SELECT id FROM shopping_items 
        WHERE list_name = ? AND item = ? AND today_list = 1
    ''', (list_name, item), one=True)
    
    if not existing:
        # Add to today's list - NO FLASH MESSAGE
        execute_db('''
            INSERT INTO shopping_items (item, list_name, today_list, master_list, added_date)
            VALUES (?, ?, 1, 0, CURRENT_TIMESTAMP)
        ''', (item, list_name))
    
    return redirect(url_for('main.lists', list_name=list_name))

@main_bp.route('/shopping/add_new', methods=['POST'])
@login_required  
def add_new_item():
    """Add completely new item to master list"""
    item = request.form.get('item', '').strip()
    list_name = request.form.get('list_name', 'food')
    add_to_today = request.form.get('add_to_today') == 'yes'
    
    if not item:
        flash('Please enter an item', 'error')
        return redirect(url_for('main.lists', list_name=list_name))
    
    # Add to master list
    execute_db('''
        INSERT INTO shopping_items (item, list_name, master_list, today_list, created_date)
        VALUES (?, ?, 1, ?, CURRENT_TIMESTAMP)
    ''', (item, list_name, 1 if add_to_today else 0))
    
    # Only flash for this major operation
    flash(f'Added {item} to master list', 'success')
    return redirect(url_for('main.lists', list_name=list_name))


@main_bp.route('/shopping/update_today/<int:item_id>', methods=['POST'])
@login_required
def update_today_item(item_id):
    """Update quantity on today's list - SILENT"""
    quantity = request.form.get('quantity', '').strip()
    list_name = request.form.get('list_name', 'food')
    
    execute_db('UPDATE shopping_items SET quantity = ? WHERE id = ? AND today_list = 1',
              (quantity, item_id))
    
    return redirect(url_for('main.lists', list_name=list_name))


@main_bp.route('/shopping/remove_from_today/<int:item_id>', methods=['POST'])
@login_required
def remove_from_today(item_id):
    """Remove item from today's list - SILENT"""
    list_name = request.form.get('list_name', 'food')
    
    # Simply delete the item from today's list
    execute_db('DELETE FROM shopping_items WHERE id = ? AND today_list = 1', (item_id,))
    
    return redirect(url_for('main.lists', list_name=list_name))

@main_bp.route('/shopping/bought_today/<int:item_id>', methods=['POST'])
@login_required
def bought_today(item_id):
    """Mark item as bought - moves to history - SILENT"""
    list_name = request.form.get('list_name', 'food')
    
    # Get item details
    item = query_db('SELECT item, quantity FROM shopping_items WHERE id = ?', (item_id,), one=True)
    
    if item:
        # Add to history (master list)
        execute_db('''
            INSERT INTO shopping_items (item, quantity, list_name, master_list, today_list, created_date)
            VALUES (?, ?, ?, 1, 0, CURRENT_TIMESTAMP)
        ''', (item['item'], item['quantity'], list_name))
        
        # Remove from today's list
        execute_db('DELETE FROM shopping_items WHERE id = ?', (item_id,))
    
    return redirect(url_for('main.lists', list_name=list_name))


@main_bp.route('/shopping/clear_today', methods=['POST'])
@login_required
def clear_today_list():
    """Clear all items from today's list"""
    list_name = request.form.get('list_name', 'food')
    
    # ONLY delete items marked as today_list = 1
    execute_db('DELETE FROM shopping_items WHERE list_name = ? AND today_list = 1', (list_name,))
    
    # Only flash for this major operation
    flash('Cleared today\'s list', 'success')
    return redirect(url_for('main.lists', list_name=list_name))

@main_bp.route('/lists/export/<list_name>')
@login_required
def export_list(list_name='food'):
    """Export today's list as text"""
    items = query_db('''
        SELECT item, quantity
        FROM shopping_items
        WHERE list_name = ? AND today_list = 1
        ORDER BY item
    ''', (list_name,))
    
    # Create text export
    lists = current_app.config.get('SHOPPING_LISTS', [])
    current_list = next((l for l in lists if l['name'] == list_name), {'title': 'Shopping'})
    
    text = f"{current_list['title']} - {datetime.now().strftime('%B %d, %Y')}\n"
    text += "=" * 40 + "\n\n"
    
    for item in items:
        if item['quantity']:
            text += f"[ ] {item['item']} ({item['quantity']})\n"
        else:
            text += f"[ ] {item['item']}\n"
    
    response = make_response(text)
    response.headers['Content-Type'] = 'text/plain; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename=shopping_{list_name}_{datetime.now().strftime("%Y%m%d")}.txt'
    
    return response

@main_bp.route('/lists/print/<list_name>')
@login_required
def print_list(list_name='food'):
    """Print-friendly view for mobile"""
    items = query_db('''
        SELECT item, quantity
        FROM shopping_items
        WHERE list_name = ? AND today_list = 1
        ORDER BY item
    ''', (list_name,))
    
    lists = current_app.config.get('SHOPPING_LISTS', [])
    current_list = next((l for l in lists if l['name'] == list_name), {'title': 'Shopping List'})
    
    return render_template('temp_print_list.html',
                         items=items,
                         list_title=current_list['title'],
                         date=datetime.now().strftime('%B %d, %Y'))   

@main_bp.route('/shopping/delete_master_item', methods=['POST'])
@admin_required
def delete_master_item():
    """Delete item from master list history"""
    item = request.form.get('item', '').strip()
    list_name = request.form.get('list_name', 'food')
    
    if item:
        # Delete ALL occurrences of this item from master list
        execute_db('''
            DELETE FROM shopping_items 
            WHERE item = ? AND list_name = ? AND master_list = 1
        ''', (item, list_name))
        
        flash(f'Removed {item} from master list', 'success')
    
    return redirect(url_for('main.lists', list_name=list_name))

@main_bp.route('/shopping/edit_master_item', methods=['GET', 'POST'])
@admin_required
def edit_master_item():
    """Edit master list item - for now, just redirect with message"""
    item = request.form.get('item', '').strip()
    list_name = request.form.get('list_name', 'food')
    
    # TODO: Implement edit form
    flash('Edit functionality coming soon', 'info')
    return redirect(url_for('main.lists', list_name=list_name))

@main_bp.route('/button-test')  # or @admin_bp.route('/button-test')
@login_required
def button_test():
    return render_template('temp_button_test.html')

@main_bp.route('/button-showcase')
@login_required
def button_showcase():
    return render_template('temp_button_showcase.html')