#!/bin/bash
# /home/life/app/fix_and_test.sh
# Version: 1.0.0
# Purpose: Fix common issues and test
# Created: 2025-06-12

cd /home/life/app

echo "=== Quick Fix and Test ==="

# 1. Remove duplicate login.html if temp_login.html exists
if [ -f "templates/temp_login.html" ] && [ -f "templates/login.html" ]; then
    echo "Removing duplicate login.html (keeping temp_login.html)"
    rm templates/login.html
fi

# 2. Fix any template references in bp_auth.py
echo "Fixing template references in bp_auth.py..."
sed -i "s/'login\.html'/'temp_login.html'/g" routes/bp_auth.py
sed -i "s/'login_help\.html'/'temp_login_help.html'/g" routes/bp_auth.py

# 3. Check what we have
echo -e "\nTemplates:"
ls -1 templates/

echo -e "\nTemplate references in bp_auth.py:"
grep "render_template" routes/bp_auth.py

# 4. Quick test
echo -e "\nRunning quick test..."
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
try:
    from life import create_app
    app = create_app('development')
    with app.test_client() as c:
        r = c.get('/login')
        print(f"GET /login: {r.status_code}")
        if r.status_code == 500:
            if b'TemplateNotFound' in r.data:
                print("  Error: Template not found")
        r = c.get('/')
        print(f"GET /: {r.status_code}")
except Exception as e:
    print(f"Error: {e}")
EOF

echo -e "\nTo run the app:"
echo "  cd /home/life/app"
echo "  python3 life.py"