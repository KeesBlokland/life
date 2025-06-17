"""
/home/life/app/routes/__init__.py
Version: 1.1.0
Purpose: Route blueprint initialization
Created: 2025-06-11
Updated: 2025-06-17 - Added contacts blueprint
"""

# Import blueprints for easy access
from .bp_auth import auth_bp, login_required, admin_required
from .bp_main import main_bp
from .bp_files import files_bp
from .bp_contacts import contacts_bp

# Export for use in other modules
__all__ = ['auth_bp', 'main_bp', 'files_bp', 'contacts_bp', 'login_required', 'admin_required']