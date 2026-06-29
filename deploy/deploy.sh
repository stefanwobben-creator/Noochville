#!/usr/bin/env bash
# NoochVille — eerste installatie op een verse Hetzner CX22 (Ubuntu 24.04)
# Draaien als root: bash deploy/deploy.sh
# Vereist: DNS van village.nooch.earth wijst al naar dit IP-adres.
set -euo pipefail

REPO="git@github.com:stefanwobben-creator/Noochville.git"
APP_DIR="/opt/noochville"
SERVICE_USER="nooch"
DOMAIN="village.nooch.earth"
EMAIL="stefanwobben@gmail.com"

echo "==> Systeem bijwerken en pakketten installeren"
apt-get update -qq
apt-get install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx git ufw

echo "==> Firewall instellen (SSH, HTTP, HTTPS)"
ufw allow OpenSSH
ufw allow "Nginx Full"
ufw --force enable

echo "==> Service-gebruiker aanmaken"
id "$SERVICE_USER" &>/dev/null || adduser --system --group --home "$APP_DIR" "$SERVICE_USER"

echo "==> Code ophalen"
if [ -d "$APP_DIR/.git" ]; then
    git -C "$APP_DIR" pull
else
    git clone "$REPO" "$APP_DIR"
fi
chown -R "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR"

echo "==> Virtualenv aanmaken en dependencies installeren"
sudo -u "$SERVICE_USER" python3 -m venv "$APP_DIR/venv"
sudo -u "$SERVICE_USER" "$APP_DIR/venv/bin/pip" install --quiet --upgrade pip
sudo -u "$SERVICE_USER" "$APP_DIR/venv/bin/pip" install --quiet -r "$APP_DIR/deploy/requirements.txt"

echo "==> Data-map aanmaken"
sudo -u "$SERVICE_USER" mkdir -p "$APP_DIR/data/output"

echo "==> Systemd-services installeren"
cp "$APP_DIR/deploy/noochville-village.service"  /etc/systemd/system/
cp "$APP_DIR/deploy/noochville-cockpit2.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable noochville-village noochville-cockpit2

echo "==> nginx-config installeren"
cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/noochville
ln -sf /etc/nginx/sites-available/noochville /etc/nginx/sites-enabled/noochville
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "==> SSL-certificaat ophalen via Certbot"
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL"

echo ""
echo "==> Secrets uploaden (nog te doen door jou, lokaal uitvoeren):"
echo "    scp .env ${SERVICE_USER}@<IP>:${APP_DIR}/.env"
echo "    scp gsc_token.json ${SERVICE_USER}@<IP>:${APP_DIR}/gsc_token.json"
echo "    ssh root@<IP> \"chown ${SERVICE_USER}:${SERVICE_USER} ${APP_DIR}/.env ${APP_DIR}/gsc_token.json\""
echo "    ssh root@<IP> \"systemctl start noochville-village noochville-cockpit2\""
echo ""
echo "Klaar. Zodra secrets zijn geupload: start de services."
