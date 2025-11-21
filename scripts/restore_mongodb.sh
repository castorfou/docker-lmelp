#!/bin/bash
# ============================================================================
# MongoDB Restore Script
# ============================================================================
# This script restores a MongoDB database from a backup created by backup_mongodb.sh
#
# Environment variables:
#   MONGO_HOST     : MongoDB host (default: localhost)
#   MONGO_PORT     : MongoDB port (default: 27017)
#   MONGO_DATABASE : Database name to restore (default: masque_et_la_plume)
#
# Usage:
#   ./restore_mongodb.sh [backup_name]
#
# Example:
#   ./restore_mongodb.sh backup_2024-11-21_14-30-00
#
# If no backup name is provided, the script will list available backups
# ============================================================================

set -e  # Exit on error

# Configuration from environment variables with defaults
MONGO_HOST="${MONGO_HOST:-localhost}"
MONGO_PORT="${MONGO_PORT:-27017}"
MONGO_DATABASE="${MONGO_DATABASE:-masque_et_la_plume}"
BACKUP_DIR="/backups"

# Function to list available backups
list_backups() {
    echo "Available backups:"
    echo ""

    BACKUPS=$(find "${BACKUP_DIR}" -maxdepth 1 -type d -name "backup_*" 2>/dev/null | sort -r)

    if [ -z "${BACKUPS}" ]; then
        echo "  No backups found in ${BACKUP_DIR}"
        return 1
    fi

    echo "${BACKUPS}" | while IFS= read -r backup; do
        BACKUP_NAME=$(basename "${backup}")
        BACKUP_SIZE=$(du -sh "${backup}" | cut -f1)
        BACKUP_DATE=$(stat -c %y "${backup}" | cut -d' ' -f1,2 | cut -d'.' -f1)
        echo "  ${BACKUP_NAME}"
        echo "    Size: ${BACKUP_SIZE}"
        echo "    Date: ${BACKUP_DATE}"
        echo ""
    done

    return 0
}

# Check if backup name was provided
if [ -z "$1" ]; then
    echo "=========================================="
    echo "MongoDB Restore Script"
    echo "=========================================="
    echo ""
    list_backups
    echo "Usage: $0 <backup_name>"
    echo ""
    echo "Example:"
    echo "  $0 backup_2024-11-21_14-30-00"
    echo ""
    exit 1
fi

BACKUP_NAME="$1"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Validate backup exists
if [ ! -d "${BACKUP_PATH}" ]; then
    echo "Error: Backup not found: ${BACKUP_PATH}"
    echo ""
    list_backups
    exit 1
fi

# Validate backup contains the database
DB_BACKUP_PATH="${BACKUP_PATH}/${MONGO_DATABASE}"
if [ ! -d "${DB_BACKUP_PATH}" ]; then
    echo "Error: Database '${MONGO_DATABASE}' not found in backup: ${BACKUP_PATH}"
    echo ""
    echo "Available databases in this backup:"
    find "${BACKUP_PATH}" -maxdepth 1 -type d ! -path "${BACKUP_PATH}" -exec basename {} \;
    exit 1
fi

# Log start
echo "=========================================="
echo "MongoDB Restore Started: $(date)"
echo "=========================================="
echo "Host: ${MONGO_HOST}:${MONGO_PORT}"
echo "Database: ${MONGO_DATABASE}"
echo "Backup: ${BACKUP_NAME}"
echo ""

# Warning prompt
echo "⚠️  WARNING: This will DROP the existing database '${MONGO_DATABASE}' and restore from backup!"
echo ""
read -p "Are you sure you want to continue? (yes/no): " -r REPLY
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Restore cancelled."
    exit 0
fi

# Run mongorestore with --drop to replace existing database
echo "Restoring database..."
if mongorestore \
    --host="${MONGO_HOST}" \
    --port="${MONGO_PORT}" \
    --db="${MONGO_DATABASE}" \
    --drop \
    "${DB_BACKUP_PATH}"; then

    echo ""
    echo "✓ Restore successful!"
else
    echo ""
    echo "✗ Restore failed!"
    exit 1
fi

echo ""
echo "=========================================="
echo "MongoDB Restore Completed: $(date)"
echo "=========================================="

exit 0
