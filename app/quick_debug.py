#!/usr/bin/env python3
"""
/home/life/app/quick_debug.py
Version: 1.0.0
Purpose: Quick debug to see what's happening
Created: 2025-06-12
"""

import os
import sys

print(f"Working from: {os.getcwd()}")
print(f"Python path[0]: {sys.path[0]}")

# Try the actual app
try:
    from life import create_app
    app = create_app('development')
    
    print("\n✓ App created successfully!")
    print(f"Blueprints registered: {list(app.blueprints.keys())}")
    
    print("\nRoutes:")
    with app.app_context():
        for rule in app.url_map.iter_rules():
            methods = ','.join(rule.methods - {'HEAD', 'OPTIONS'})
            print(f"  {rule.endpoint:20} {methods:6} {rule}")
    
    # Try to render login page
    print("\nTesting login route...")
    with app.test_client() as client:
        response = client.get('/login')
        print(f"  /login status: {response.status_code}")
        if response.status_code != 200:
            print(f"  Error: {response.data[:200]}")
            
        response = client.get('/')
        print(f"  / status: {response.status_code}")
        
except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()