"""
config.py - Configuration settings for Life app
Version: 1.0.0
Purpose: Central configuration management
Created: 2024-12-XX
"""

import os
from datetime import timedelta

class Config:
    """Base configuration"""
    # Paths
    BASE_DIR = '/home/life'
    APP_DIR = os.path.join(BASE_DIR, 'app')
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    DB_PATH = os.path.join(DATA_DIR, 'database', 'life.db')
    UPLOAD_FOLDER = os.path.join(APP_DIR, 'uploads')
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB max file size
    
    # Development flags
    DEBUG = True
    FOOTER_INFO = True
    TESTING = False
    
    # Network
    NETWORK_MODE = 'auto'  # auto/manual/hotspot
    MANUAL_IP = ''
    HOTSPOT_SSID = 'LifeArchive'
    HOTSPOT_PASS = 'FamilyLife2024'  # Change this
    LCD_ENABLED = True
    
    # File handling
    ALLOWED_EXTENSIONS = {
        'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'heic',
        'doc', 'docx', 'xls', 'xlsx', 'mp4', 'mov'
    }
    IMAGE_MAX_SIZE = 1024  # pixels
    IMAGE_QUALITY = 85  # JPEG quality
    
    # Security
    VIEW_PASSWORD = 'test'  # Change in production
    ADMIN_PASSWORD = 'test'  # Change in production
    
    # Features
    OCR_ENABLED = True
    AUTO_CATEGORIZE = True
    LEARN_ASSOCIATIONS = True
    
    # UI
    ITEMS_PER_PAGE = 20
    DYSLEXIA_FONT = False
    HIGH_CONTRAST = False
    
    @staticmethod
    def init_app(app):
        """Initialize application with config"""
        # Ensure directories exist
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        os.makedirs(os.path.join(Config.DATA_DIR, 'database'), exist_ok=True)
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(os.path.join(Config.DATA_DIR, 'documents'), exist_ok=True)
        os.makedirs(os.path.join(Config.DATA_DIR, 'images'), exist_ok=True)
        os.makedirs(os.path.join(Config.DATA_DIR, 'videos'), exist_ok=True)
        os.makedirs(os.path.join(Config.DATA_DIR, 'backups'), exist_ok=True)

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    FOOTER_INFO = True

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    FOOTER_INFO = False
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        # Production-specific initialization
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not app.debug:
            file_handler = RotatingFileHandler(
                os.path.join(cls.BASE_DIR, 'logs', 'life.log'),
                maxBytes=10240000,
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            app.logger.setLevel(logging.INFO)
            app.logger.info('Life application startup')

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}