"""
/home/life/app/routes/bp_auth.py
Version: 1.1.0
Purpose: Authentication routes - login, logout, session management
Created: 2025-06-11
Updated: 2025-06-12 - Single password field, direct redirect to dashboard
"""

from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app
from werkzeug.security import check_password_hash
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin access for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if not session.get('is_admin', False):
            flash('Admin access required.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and authentication"""
    if request.method == 'POST':
        password = request.form.get('password', '').strip()
        
        if current_app.config['DEBUG']:
            current_app.logger.debug(f"Login attempt with password provided: {bool(password)}")
        
        if not password:
            flash('Please enter a password.', 'error')
            return render_template('temp_login.html')
        
        # Check admin password first (gives full access)
        if password == current_app.config['ADMIN_PASSWORD']:
            session['logged_in'] = True
            session['is_admin'] = True
            session.permanent = True
            
            if current_app.config['DEBUG']:
                current_app.logger.debug("Admin login successful")
            
            # Redirect to next page or home
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('main.index'))
        
        # Check view password (gives basic access)
        elif password == current_app.config['VIEW_PASSWORD']:
            session['logged_in'] = True
            session['is_admin'] = False
            session.permanent = True
            
            if current_app.config['DEBUG']:
                current_app.logger.debug("User login successful")
            
            # Redirect to next page or home
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('main.index'))
        
        else:
            flash('Invalid password. Please try again.', 'error')
            
            if current_app.config['DEBUG']:
                current_app.logger.debug("Login failed - invalid password")
    
    return render_template('temp_login.html')

@auth_bp.route('/logout')
def logout():
    """Logout and clear session"""
    if current_app.config['DEBUG']:
        current_app.logger.debug(f"User logout - was admin: {session.get('is_admin', False)}")
    
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/help/login')
def login_help():
    """Login help with video guide"""
    return render_template('temp_login_help.html')