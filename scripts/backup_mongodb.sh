#!/bin/bash
# ============================================================================
# MongoDB Backup Script
# ============================================================================
# This script creates a timestamped backup of the MongoDB database
# and manages backup retention according to the configured policy
#
# Environment variables:
#   MONGO_HOST              : MongoDB host (default: localhost)
#   MONGO_PORT              : MongoDB port (default: 27017)
#   MONGO_DATABASE          : Database name to backup (default: masque_et_la_plume)
#   BACKUP_RETENTION_WEEKS  : Number of weeks to retain backups (default: 7)
#
# Usage:
#   ./backup_mongodb.sh
# ============================================================================

set -e  # Exit on error

# Configuration from environment variables with defaults
MONGO_HOST="${MONGO_HOST:-localhost}"
MONGO_PORT="${MONGO_PORT:-27017}"
MONGO_DATABASE="${MONGO_DATABASE:-masque_et_la_plume}"
BACKUP_RETENTION_WEEKS="${BACKUP_RETENTION_WEEKS:-7}"
BACKUP_DIR="/backups"

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

# Create timestamp for backup folder
DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_NAME="backup_${DATE}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Log start
echo "=========================================="
echo "MongoDB Backup Started: $(date)"
echo "=========================================="
echo "Host: ${MONGO_HOST}:${MONGO_PORT}"
echo "Database: ${MONGO_DATABASE}"
echo "Backup path: ${BACKUP_PATH}"
echo ""

# Run mongodump
echo "Creating backup..."
if mongodump \
    --host="${MONGO_HOST}" \
    --port="${MONGO_PORT}" \
    --db="${MONGO_DATABASE}" \
    --out="${BACKUP_PATH}"; then

    echo ""
    echo "✓ Backup successful: ${BACKUP_NAME}"

    # Calculate size of backup
    BACKUP_SIZE=$(du -sh "${BACKUP_PATH}" | cut -f1)
    echo "  Size: ${BACKUP_SIZE}"
else
    echo ""
    echo "✗ Backup failed!"
    exit 1
fi

# Cleanup old backups
echo ""
echo "Cleaning up old backups (retention: ${BACKUP_RETENTION_WEEKS} weeks)..."

# Find and delete backups older than retention period
RETENTION_DAYS=$((BACKUP_RETENTION_WEEKS * 7))
OLD_BACKUPS=$(find "${BACKUP_DIR}" -maxdepth 1 -type d -name "backup_*" -mtime +${RETENTION_DAYS} 2>/dev/null)

if [ -n "${OLD_BACKUPS}" ]; then
    echo "Removing old backups:"
    echo "${OLD_BACKUPS}" | while IFS= read -r backup; do
        echo "  - $(basename "${backup}")"
        rm -rf "${backup}"
    done
else
    echo "  No old backups to remove"
fi

# List current backups
echo ""
echo "Current backups:"
find "${BACKUP_DIR}" -maxdepth 1 -type d -name "backup_*" -printf "%T@ %p\n" 2>/dev/null | \
    sort -rn | \
    awk '{print "  - " substr($2, index($2, "backup_"))}' || echo "  No backups found"

echo ""
echo "=========================================="
echo "MongoDB Backup Completed: $(date)"
echo "=========================================="

exit 0
