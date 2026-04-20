#!/bin/bash
# deploy.sh — Deploy CSR IRIT prototype to VPS
# Run as root or with sudo
set -e

APP_DIR="/opt/csr-irit"
LOG_DIR="/var/log/csr-irit"
REPO_URL="https://github.com/Lotfimln/Stage.git"  # Update with your repo

echo "=== CSR IRIT Deployment ==="

# 1. System packages
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv nginx git

# 2. Create app directory
echo "[2/7] Setting up directories..."
mkdir -p $APP_DIR $LOG_DIR
chown www-data:www-data $LOG_DIR

# 3. Clone/update repo
echo "[3/7] Deploying code..."
if [ -d "$APP_DIR/.git" ]; then
    cd $APP_DIR && git pull
else
    git clone $REPO_URL $APP_DIR
fi

# 4. Python environment
echo "[4/7] Setting up Python environment..."
python3 -m venv $APP_DIR/venv
$APP_DIR/venv/bin/pip install -q --upgrade pip
$APP_DIR/venv/bin/pip install -q -r $APP_DIR/backend/requirements.txt

# 5. Initialize database
echo "[5/7] Initializing database..."
cd $APP_DIR/backend
$APP_DIR/venv/bin/python init_db.py

# 6. Systemd service
echo "[6/7] Installing systemd service..."
cp $APP_DIR/deploy/csr.service /etc/systemd/system/csr-irit.service
systemctl daemon-reload
systemctl enable csr-irit
systemctl restart csr-irit

# 7. Nginx
echo "[7/7] Configuring Nginx..."
cp $APP_DIR/deploy/nginx.conf /etc/nginx/sites-available/csr-irit
ln -sf /etc/nginx/sites-available/csr-irit /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ""
echo "=== Deployment complete! ==="
echo "App: http://$(hostname -I | awk '{print $1}')"
echo ""
echo "Next steps:"
echo "  1. Update SECRET_KEY in /etc/systemd/system/csr-irit.service"
echo "  2. Run: sudo certbot --nginx -d lotfimelouane.com"
echo "  3. Uncomment HTTPS block in /etc/nginx/sites-available/csr-irit"
