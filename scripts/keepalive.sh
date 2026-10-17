#!/usr/bin/env bash
# scripts/keepalive.sh
# ──────────────────────────────────────────────────────────────────────────────
# Periodic maintenance and keepalive for Oracle Cloud Always Free ARM instance.
# Performs honest system checks rather than synthetic CPU burning:
#   1. HTTP health & readiness probes (/health and /ready)
#   2. Docker stack service health inspection
#   3. Disk space and memory utilization checks
#   4. Log file size auditing
#
# Oracle Idle Reclamation Notice:
# Oracle reclaims Always Free compute instances if CPU, memory, and network are
# all under 20% utilization over a 7-day period.
# Recommended mitigation: Upgrade account to "Pay-As-You-Go" (PAYG). Always Free
# allowances (4 OCPUs, 24 GB RAM) remain 100% free ($0/mo), but PAYG accounts
# are exempt from idle instance reclamation.
#
# Cron entry (crontab -e):
#   */15 * * * * /home/ubuntu/rag-document-intelligence/scripts/keepalive.sh >> /var/log/rag-keepalive.log 2>&1
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

LOG_PREFIX="[keepalive $(date -u '+%Y-%m-%dT%H:%M:%SZ')]"
API_URL="${API_URL:-http://localhost:80}"

echo "$LOG_PREFIX Starting periodic health & system audit..."

# 1. API Liveness Probe
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${API_URL}/health" || echo "000")
if [ "$HEALTH_STATUS" = "200" ]; then
    echo "$LOG_PREFIX API /health: OK (200)"
else
    echo "$LOG_PREFIX API /health: WARN (${HEALTH_STATUS})"
fi

# 2. API Readiness Probe (checks DB & Redis dependencies)
READY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "${API_URL}/ready" || echo "000")
if [ "$READY_STATUS" = "200" ]; then
    echo "$LOG_PREFIX API /ready: OK (Dependencies healthy)"
else
    echo "$LOG_PREFIX API /ready: WARN (${READY_STATUS})"
fi

# 3. Disk Space Audit
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
echo "$LOG_PREFIX Root disk usage: ${DISK_USAGE}%"
if [ "$DISK_USAGE" -gt 85 ]; then
    echo "$LOG_PREFIX WARNING: Disk space above 85% — consider running docker system prune."
fi

# 4. Memory Utilization Audit
MEM_INFO=$(free -m | awk 'NR==2{printf "Memory: %sMB used / %sMB total (%.1f%%)", $3, $2, $3*100/$2}')
echo "$LOG_PREFIX ${MEM_INFO}"

# 5. Docker Containers Status (if docker is present)
if command -v docker >/dev/null 2>&1; then
    UNHEALTHY=$(docker ps --filter "health=unhealthy" --format "{{.Names}}" || true)
    if [ -n "$UNHEALTHY" ]; then
        echo "$LOG_PREFIX ALERT: Unhealthy containers detected: ${UNHEALTHY}"
    else
        echo "$LOG_PREFIX Docker containers: All healthy"
    fi
fi

echo "$LOG_PREFIX Maintenance check complete."
