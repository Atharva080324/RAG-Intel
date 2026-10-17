# Deploy to Oracle Cloud Always Free ARM VM

> **Audience**: You — the developer. This guide assumes a fresh Ubuntu 22.04 A1 instance.

---

## 1. Create the A1 Instance

1. Log in to [cloud.oracle.com](https://cloud.oracle.com).
2. **Compute → Instances → Create Instance**.
3. Shape: **VM.Standard.A1.Flex** — 4 OCPU, 24 GB RAM (all free-tier eligible).
4. Image: **Canonical Ubuntu 22.04** (Minimal).
5. Generate or upload an SSH key pair; download the private key.
6. Keep the default VCN or create one.

---

## 2. Open Ports

### VCN Security List (Oracle firewall)

1. **Networking → Virtual Cloud Networks → your VCN → Security Lists → Default**.
2. Add **Ingress Rules**:

| Protocol | Source CIDR | Port range | Notes |
|----------|-------------|-----------|-------|
| TCP | 0.0.0.0/0 | 80 | HTTP (Caddy redirect) |
| TCP | 0.0.0.0/0 | 443 | HTTPS |
| TCP | 0.0.0.0/0 | 22 | SSH (restrict to your IP in prod) |

### OS-level firewall (on the VM)

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

---

## 2.1. Configure 4 GB Swap File (OOM Prevention)

The cross-encoder, embedding models, and Celery worker operate on high-dimensional PyTorch tensors. To guarantee that neither the API nor worker processes get OOM-killed (Out-Of-Memory) during concurrent candidate reranking, configure a 4 GB swap file on the VM:

```bash
# Create and activate a 4GB swapfile
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Persist across reboots in fstab
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Verify swap is active
free -h
```

> **Memory Budget**: `docker-compose.prod.yml` enforces container memory limits:
> - `api`: 2.5 GB
> - `worker`: 2.5 GB
> - `db`: 2.0 GB
> - `redis`: 512 MB
> - `caddy`: 256 MB
> Total container allocation is ~7.75 GB of the 12 GB VM RAM, leaving ~4.25 GB uncommitted for the Linux kernel and disk buffer cache.


## 3. Install Docker

```bash
ssh -i your-key.pem ubuntu@<VM_PUBLIC_IP>

# Update & install prerequisites
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Allow your user to run Docker without sudo
sudo usermod -aG docker ubuntu
# Apply group change without re-login:
newgrp docker
docker --version   # should print Docker 24+
```

---

## 4. DuckDNS Setup (free domain)

1. Sign in at [duckdns.org](https://www.duckdns.org).
2. Create a subdomain, e.g. `rag-intel.duckdns.org`.
3. Set the IP to your Oracle VM's **public IP**.
4. Auto-update cron (optional, if your IP changes):

```bash
# Add to crontab -e
*/5 * * * * curl -s "https://www.duckdns.org/update?domains=rag-intel&token=YOUR_TOKEN&ip=" > /dev/null
```

Verify: `nslookup rag-intel.duckdns.org` should return your VM IP.

---

## 5. Clone and Configure

```bash
cd ~
git clone https://github.com/Atharva080324/rag-document-intelligence rag
cd rag

# Copy the production env template
cp .env.production.example .env.production
nano .env.production   # fill in EVERY placeholder
```

**Mandatory values to fill:**

| Variable | How to get it |
|----------|---------------|
| `POSTGRES_PASSWORD` | `openssl rand -hex 20` |
| `SECRET_KEY` | `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `API_DOMAIN` | `rag-intel.duckdns.org` (your DuckDNS subdomain) |
| `HF_TOKEN` | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) |
| `FRONTEND_URL` | Your Vercel/Netlify URL (set after Phase 4.2) |
| `CORS_ORIGINS` | Same as `FRONTEND_URL` |
| `DEMO_USER_PASSWORD` | `openssl rand -hex 16` |

---

## 6. Start the Stack

```bash
# Build the image (first time ~5 min on ARM)
docker compose -f docker-compose.prod.yml --env-file .env.production build

# Validate config (must exit 0)
docker compose -f docker-compose.prod.yml config

# Start everything
docker compose -f docker-compose.prod.yml --env-file .env.production up -d

# Watch logs
docker compose -f docker-compose.prod.yml logs -f api worker migrate
```

---

## 7. Run Migrations

The `migrate` service runs automatically on `up` (it's a dependency of `api`).  
To re-run manually:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production \
  run --rm migrate alembic upgrade head
```

---

## 8. Seed Demo Data

Add 2–3 sample PDFs to `samples/` (include one with tables):

```bash
mkdir -p samples
# Copy your PDFs:
cp /path/to/annual_report.pdf samples/
cp /path/to/data_table.pdf samples/
cp /path/to/technical_overview.txt samples/
```

Then seed:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production \
  exec api sh -c "DEMO_MODE=true API_BASE=http://localhost:8000 python scripts/seed_demo.py"
```

---

## 9. Verify

```bash
# Health check
curl https://rag-intel.duckdns.org/health
# → {"status":"ok"}

# Readiness check
curl https://rag-intel.duckdns.org/ready
# → {"status":"ready","dependencies":{"database":"ok","redis":"ok"}}

# Demo JWT
curl -X POST https://rag-intel.duckdns.org/auth/demo
# → {"access_token":"...","token_type":"bearer","expires_in":3600}
```

Open the React frontend and click **Try Demo** — documents seeded above should appear.

---

## 10. Update (Rolling Deploy)

```bash
cd ~/rag
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production build
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

---

## 11. Backup PostgreSQL

```bash
# Manual backup
docker compose -f docker-compose.prod.yml --env-file .env.production \
  exec db pg_dump -U rag ragdb | gzip > ~/backups/ragdb_$(date +%Y%m%d).sql.gz

# Cron (daily at 03:00)
mkdir -p ~/backups
# crontab -e:
0 3 * * * cd ~/rag && docker compose -f docker-compose.prod.yml --env-file .env.production exec -T db pg_dump -U rag ragdb | gzip > ~/backups/ragdb_$(date +\%Y\%m\%d).sql.gz
```

---

## 12. Idle Reclamation Risk & Keepalive

### Oracle Cloud Always Free Idle Policy
Oracle monitors Always Free compute instances and will automatically stop or reclaim instances deemed "idle":
- 95th percentile CPU utilization is less than 20% over a 7-day period.
- Network utilization is less than 20% over a 7-day period.
- Memory utilization is less than 20% over a 7-day period.

### Best Mitigation: Upgrade to Pay-As-You-Go (PAYG)
The most reliable and permanent solution is upgrading your Oracle Cloud account to **Pay-As-You-Go (PAYG)**:
1. In the Oracle Cloud Console, navigate to **Billing & Cost Management → Subscriptions → Upgrade to Paid**.
2. Add a credit card (a temporary authorization hold of ~$100 is placed and immediately reversed).
3. **No cost is incurred**: Your 4 OCPUs, 24 GB RAM, and 200 GB block volume remain within the permanent Always Free tier ($0.00/month).
4. **Benefit**: PAYG accounts are completely exempt from idle instance reclamation.

### Operational Monitoring Cron (scripts/keepalive.sh)
Rather than burning fake CPU cycles, `scripts/keepalive.sh` performs honest maintenance checks:
- Verifies API `/health` and `/ready` endpoints (checking DB + Redis).
- Audits root disk usage and warns if usage exceeds 85%.
- Audits memory utilization and checks for unhealthy Docker containers.

```bash
chmod +x scripts/keepalive.sh
# Run every 15 minutes via crontab -e:
*/15 * * * * /home/ubuntu/rag-document-intelligence/scripts/keepalive.sh >> /var/log/rag-keepalive.log 2>&1
```

### Automated Demo Uploads Purge (scripts/cleanup_demo_uploads.py)
To prevent disk accumulation on the VM from demo uploads, run the automated demo cleanup daily at 3:00 AM:

```bash
# Add to crontab -e:
0 3 * * * cd /home/ubuntu/rag-document-intelligence && docker compose -f docker-compose.prod.yml exec -T api python scripts/cleanup_demo_uploads.py >> /var/log/rag-cleanup.log 2>&1
```

---

## 13. If the VM is Reclaimed

Oracle will send an email. To recover:

1. Check **Compute → Instances** — status may be `STOPPED`.
2. Click **Start** — data in named Docker volumes survives a stop.
3. If the instance is **terminated**, restore from your pg_dump backup:

```bash
# On a new VM, after starting the stack:
gunzip -c ~/backups/ragdb_YYYYMMDD.sql.gz \
  | docker compose -f docker-compose.prod.yml exec -T db psql -U rag ragdb
```

---

## Useful Commands

```bash
# Tail all logs
docker compose -f docker-compose.prod.yml logs -f

# Restart only the API
docker compose -f docker-compose.prod.yml restart api

# Check Caddy TLS status
docker compose -f docker-compose.prod.yml exec caddy caddy version

# Celery worker status
docker compose -f docker-compose.prod.yml exec worker celery -A app.workers.celery_app inspect active
```
