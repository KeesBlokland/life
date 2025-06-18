#!/usr/bin/env python3
"""
life.py - Main Flask application for Life family archive
Date: 2025-06-18
Version: 1.1.01
Purpose: Application initialization with file logging
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template
from config import config

def create_app(config_name=None):
    """Application factory pattern"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    # Configure logging with file output
    log_dir = app.config.get('LOG_DIR', '/home/life/logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, 'life.log')
    
    # Set up rotating file handler
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(formatter)
    
    # Configure log level
    log_level = logging.DEBUG if app.config['DEBUG'] else logging.INFO
    file_handler.setLevel(log_level)
    app.logger.setLevel(log_level)
    
    # Add handler to app logger
    app.logger.addHandler(file_handler)
    
    # Also log to console in debug mode
    if app.config['DEBUG']:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        app.logger.addHandler(console_handler)
    
    app.logger.info(f'Life app starting with config: {config_name}')
    
    # Initialize database
    from utils.util_db import init_db
    with app.app_context():
        init_db()
    
    # Register blueprints
    from routes.bp_auth import auth_bp
    from routes.bp_main import main_bp
    from routes.bp_files import files_bp
    from routes.bp_contacts import contacts_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(files_bp, url_prefix='/files')
    app.register_blueprint(contacts_bp, url_prefix='/contacts')
    
    # Register admin and api blueprints when they exist
    try:
        from routes.bp_admin import admin_bp
        app.register_blueprint(admin_bp, url_prefix='/admin')
    except ImportError:
        app.logger.warning("Admin blueprint not found - skipping")
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f'Internal error: {error}')
        return render_template('500.html'), 500
    
    # Template context processors
    @app.context_processor
    def inject_config():
        """Make config available in all templates"""
        return dict(config=app.config, DEBUG=app.config['DEBUG'])
    
    app.logger.info(f'Life app created with config: {config_name}')
    
    return app

# Create application instance
app = create_app()

if __name__ == '__main__':
    # Run application
    app.run(
        host='0.0.0.0',
        port=5555,
        debug=app.config['DEBUG']
    )