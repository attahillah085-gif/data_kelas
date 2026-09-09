#!/usr/bin/env bash
# =====================================================================
#  Skrip pemasangan The Girl House di VPS Ubuntu (Hostinger, dll).
#  Jalankan SEBAGAI ROOT di VPS yang masih bersih:
#
#     sudo bash deploy/setup_vps.sh app.domain-anda.com
#
#  Argumen 1 = domain yang sudah kamu arahkan (A record) ke IP VPS.
#  Tanpa domain, HTTPS otomatis dilewati (bisa dipasang nanti).
# =====================================================================
set -euo pipefail

DOMAIN="${1:-}"
APP_DIR="/var/www/thegirlhouse"
REPO="https://github.com/attahillah085-gif/data_kelas.git"
BRANCH="claude/thrifting-business-management-ew0pt2"

echo ">> [1/7] Memasang paket sistem…"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip nginx git curl

echo ">> [2/7] Mengambil kode aplikasi…"
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin "$BRANCH" && git -C "$APP_DIR" reset --hard "origin/$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO" "$APP_DIR"
fi

echo ">> [3/7] Menyiapkan virtual environment…"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

echo ">> [4/7] Menyiapkan file .env…"
if [ ! -f "$APP_DIR/.env" ]; then
  SECRET=$("$APP_DIR/.venv/bin/python" -c "import secrets;print(secrets.token_hex(32))")
  cat > "$APP_DIR/.env" <<EOF
SECRET_KEY=$SECRET
# Default SQLite (data tersimpan permanen di server ini). Untuk PostgreSQL,
# isi DATABASE_URL lalu restart:  systemctl restart thegirlhouse
# DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/thegirlhouse
VAPID_PUBLIC_KEY=
VAPID_PRIVATE_KEY=
VAPID_SUBJECT=mailto:admin@${DOMAIN:-thegirlhouse.id}
EOF
  echo "   .env dibuat dengan SECRET_KEY acak."
else
  echo "   .env sudah ada, dilewati."
fi

echo ">> [5/7] Mengatur izin & service…"
mkdir -p "$APP_DIR/instance"
chown -R www-data:www-data "$APP_DIR"
cp "$APP_DIR/deploy/thegirlhouse.service" /etc/systemd/system/thegirlhouse.service
systemctl daemon-reload
systemctl enable thegirlhouse
systemctl restart thegirlhouse

echo ">> [6/7] Mengatur Nginx…"
sed "s/DOMAIN_ANDA/${DOMAIN:-_}/g" "$APP_DIR/deploy/nginx-thegirlhouse.conf" \
  > /etc/nginx/sites-available/thegirlhouse
ln -sf /etc/nginx/sites-available/thegirlhouse /etc/nginx/sites-enabled/thegirlhouse
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo ">> [7/7] Mengatur HTTPS…"
if [ -n "$DOMAIN" ]; then
  apt-get install -y certbot python3-certbot-nginx
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
    -m "admin@${DOMAIN}" --redirect || \
    echo "   (Certbot gagal — pastikan domain sudah mengarah ke IP VPS, lalu ulangi: certbot --nginx -d $DOMAIN)"
else
  echo "   Domain tidak diberikan — lewati HTTPS. Pasang nanti dengan certbot."
fi

echo ""
echo "============================================================"
echo " SELESAI! Buka aplikasimu:"
if [ -n "$DOMAIN" ]; then echo "   https://$DOMAIN"; else echo "   http://IP-VPS-ANDA"; fi
echo " Halaman setup akan meminta membuat akun pemilik pertama."
echo ""
echo " Perintah berguna:"
echo "   systemctl status thegirlhouse     # cek status app"
echo "   systemctl restart thegirlhouse    # restart app"
echo "   journalctl -u thegirlhouse -f     # lihat log"
echo "============================================================"
