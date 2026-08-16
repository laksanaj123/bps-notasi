#!/usr/bin/env bash
# Backup notasi.db + uploads/ + exports/ ke backups/, hapus backup > 14 hari.
# Dijalankan dari root repo (sejajar dengan docker-compose.yml), lewat cron:
#   0 2 * * * cd /path/ke/notasi-app && ./scripts/backup.sh >> backups/backup.log 2>&1
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_DIR="$REPO_DIR/data"
BACKUP_DIR="$REPO_DIR/backups"
RETENTION_DAYS=14
STAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"

tar -czf "$BACKUP_DIR/notasi-backup-$STAMP.tar.gz" \
    -C "$DATA_DIR" db uploads exports

find "$BACKUP_DIR" -name "notasi-backup-*.tar.gz" -mtime "+$RETENTION_DAYS" -delete

echo "[$STAMP] backup selesai: $BACKUP_DIR/notasi-backup-$STAMP.tar.gz"
