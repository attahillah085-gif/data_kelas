#!/usr/bin/env bash
# Perbarui The Girl House ke versi terbaru lalu restart.
#   sudo bash deploy/update.sh
set -euo pipefail
APP_DIR="/var/www/thegirlhouse"
BRANCH="claude/thrifting-business-management-ew0pt2"

git -C "$APP_DIR" fetch origin "$BRANCH"
git -C "$APP_DIR" reset --hard "origin/$BRANCH"
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"
chown -R www-data:www-data "$APP_DIR"
systemctl restart thegirlhouse
echo "Update selesai. Cek: systemctl status thegirlhouse"
