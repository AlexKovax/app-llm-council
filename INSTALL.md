# INSTALL.md — Setting up LLM Council on a fresh server

This guide documents the full setup procedure for deploying LLM Council on a Debian 11/12 server (e.g. DigitalOcean Droplet) with Nginx reverse proxy, Basic Auth, and HTTPS via Let's Encrypt.

## Prerequisites

- Debian 11 or 12 server with root access
- A domain name (e.g. `example.com`) whose **DNS already points to the server IP**
- An OpenRouter API key (`sk-or-v1-...`)
- An email address for Let's Encrypt notifications

## Step 1 — System update and base packages

```bash
apt-get update && apt-get upgrade -y
apt-get install -y curl git nginx apache2-utils python3 python3-pip build-essential ufw snapd ca-certificates gnupg rsync
```

## Step 2 — Node.js 20 LTS

The Debian default Node.js is too old. Install via NodeSource:

```bash
mkdir -p /etc/apt/keyrings
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
  | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg

echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
  > /etc/apt/sources.list.d/nodesource.list

apt-get update && apt-get install -y nodejs
node --version   # should print v20.x
```

## Step 3 — Install uv (Python package manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
ln -sf $(find $HOME/.local/bin $HOME/.cargo/bin -name uv 2>/dev/null | head -1) /usr/local/bin/uv
uv --version
```

## Step 4 — Clone the application

```bash
APP_DIR="/opt/llm-council"
git clone <your-repo-url> "$APP_DIR"
cd "$APP_DIR"
```

If you already have the code locally, you can `rsync` it up instead (see [deploy.sh](deploy.sh)).

## Step 5 — Environment file

```bash
cat > .env << EOF
OPENROUTER_API_KEY=sk-or-v1-your-key-here
EOF
```

## Step 6 — Install Python dependencies

```bash
uv sync
```

## Step 7 — Install frontend dependencies

```bash
cd frontend && npm install && cd ..
```

## Step 8 — Systemd services

Create the **backend service** at `/etc/systemd/system/llm-council-backend.service`:

```ini
[Unit]
Description=LLM Council Backend (FastAPI)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/llm-council
Environment="OPENROUTER_API_KEY=sk-or-v1-your-key-here"
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/root/.local/bin/uv run python -m backend.main
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Create the **frontend service** at `/etc/systemd/system/llm-council-frontend.service`:

```ini
[Unit]
Description=LLM Council Frontend (Vite)
After=network.target llm-council-backend.service

[Service]
Type=simple
User=root
WorkingDirectory=/opt/llm-council/frontend
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
ExecStart=/usr/bin/npm run dev -- --host 127.0.0.1 --port 5173
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

## Step 9 — Nginx reverse proxy

Generate Basic Auth credentials:

```bash
htpasswd -bc /etc/nginx/.htpasswd <username> <password>
chmod 640 /etc/nginx/.htpasswd
```

Create `/etc/nginx/sites-available/llm-council`:

```nginx
upstream llm_backend {
    server 127.0.0.1:8001;
}

upstream llm_frontend {
    server 127.0.0.1:5173;
}

server {
    listen 80;
    server_name your-domain.com;

    location /.well-known/acme-challenge/ {
        auth_basic off;
        root /var/www/html;
        allow all;
    }

    auth_basic "LLM Council - Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;

    proxy_read_timeout 300s;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;

    location / {
        proxy_pass http://llm_frontend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_cache_bypass $http_upgrade;
    }

    location /api/ {
        proxy_pass http://llm_backend/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;
    }

    location /health {
        auth_basic off;
        return 200 "ok\n";
        add_header Content-Type text/plain;
    }
}
```

Enable the site:

```bash
ln -sf /etc/nginx/sites-available/llm-council /etc/nginx/sites-enabled/llm-council
rm -f /etc/nginx/sites-enabled/default
nginx -t
```

## Step 10 — Firewall

```bash
ufw --force enable
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw deny 5173/tcp
ufw deny 8001/tcp
```

Ports 5173 (frontend) and 8001 (backend) are blocked externally — all traffic must go through Nginx.

## Step 11 — Start services

```bash
systemctl daemon-reload
systemctl enable llm-council-backend llm-council-frontend
systemctl restart llm-council-backend
sleep 4
systemctl restart llm-council-frontend
sleep 4
systemctl restart nginx
```

## Step 12 — HTTPS with Let's Encrypt

```bash
# Remove any old certbot from apt to avoid conflicts
apt-get remove -y certbot python3-certbot-nginx 2>/dev/null || true

snap install --classic certbot
ln -sf /snap/bin/certbot /usr/local/bin/certbot

certbot --nginx \
  --non-interactive \
  --agree-tos \
  --email your@email.com \
  --domains your-domain.com \
  --redirect
```

Verify automatic renewal:

```bash
snap services certbot
certbot renew --dry-run
```

## Step 13 — Verify

```bash
systemctl status llm-council-backend llm-council-frontend nginx
journalctl -u llm-council-backend -n 20
journalctl -u llm-council-frontend -n 20
```

Visit `https://your-domain.com` and log in with the credentials from Step 9.

## Useful commands

| Command | Purpose |
|---|---|
| `systemctl restart llm-council-backend llm-council-frontend` | Restart both services |
| `journalctl -u llm-council-backend -f` | Follow backend logs |
| `journalctl -u llm-council-frontend -f` | Follow frontend logs |
| `certbot renew --dry-run` | Test SSL renewal |
| `certbot certificates` | List installed certificates |
| `./deploy.sh` | Deploy code updates from local machine |
