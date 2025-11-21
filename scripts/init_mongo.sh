#!/bin/bash
# ============================================================================
# MongoDB Initialization Script
# ============================================================================
# This script initializes MongoDB by restoring from a backup if specified
# Useful for first-time setup or when deploying to a new environment
#
# Environment variables:
#   MONGO_HOST        : MongoDB host (default: localhost)
#   MONGO_PORT        : MongoDB port (default: 27017)
#   MONGO_DATABASE    : Database name (default: masque_et_la_plume)
#   INIT_BACKUP_NAME  : Name of the backup to restore (optional)
#
# Usage:
#   # Initialize with automatic latest backup detection
#   ./init_mongo.sh
#
#   # Initialize with specific backup
#   INIT_BACKUP_NAME=backup_2024-11-21_14-30-00 ./init_mongo.sh
# ============================================================================

set -e  # Exit on error

# Configuration from environment variables with defaults
MONGO_HOST="${MONGO_HOST:-localhost}"
MONGO_PORT="${MONGO_PORT:-27017}"
MONGO_DATABASE="${MONGO_DATABASE:-masque_et_la_plume}"
BACKUP_DIR="/backups"

echo "=========================================="
echo "MongoDB Initialization"
echo "=========================================="
echo "Host: ${MONGO_HOST}:${MONGO_PORT}"
echo "Database: ${MONGO_DATABASE}"
echo ""

# Wait for MongoDB to be ready
echo "Waiting for MongoDB to be ready..."
RETRIES=30
COUNT=0

while [ $COUNT -lt $RETRIES ]; do
    if mongosh --host "${MONGO_HOST}" --port "${MONGO_PORT}" --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; then
        echo "✓ MongoDB is ready"
        break
    fi

    COUNT=$((COUNT + 1))
    if [ $COUNT -eq $RETRIES ]; then
        echo "✗ MongoDB failed to start after ${RETRIES} attempts"
        exit 1
    fi

    echo "  Attempt ${COUNT}/${RETRIES}..."
    sleep 2
done

echo ""

# Check if database already exists and has data
DB_EXISTS=$(mongosh --host "${MONGO_HOST}" --port "${MONGO_PORT}" --eval "db.getMongo().getDBNames().includes('${MONGO_DATABASE}')" --quiet "${MONGO_DATABASE}" 2>/dev/null || echo "false")

if [ "${DB_EXISTS}" = "true" ]; then
    COLLECTION_COUNT=$(mongosh --host "${MONGO_HOST}" --port "${MONGO_PORT}" --eval "db.getCollectionNames().length" --quiet "${MONGO_DATABASE}" 2>/dev/null || echo "0")

    if [ "${COLLECTION_COUNT}" != "0" ]; then
        echo "ℹ️  Database '${MONGO_DATABASE}' already exists with ${COLLECTION_COUNT} collections"
        echo "   Skipping initialization to preserve existing data"
        echo ""
        echo "   To force re-initialization, manually drop the database or use restore_mongodb.sh"
        exit 0
    fi
fi

# Determine which backup to use
if [ -n "${INIT_BACKUP_NAME}" ]; then
    BACKUP_NAME="${INIT_BACKUP_NAME}"
    echo "Using specified backup: ${BACKUP_NAME}"
else
    # Find the most recent backup
    LATEST_BACKUP=$(find "${BACKUP_DIR}" -maxdepth 1 -type d -name "backup_*" 2>/dev/null | sort -r | head -n 1)

    if [ -z "${LATEST_BACKUP}" ]; then
        echo "ℹ️  No backups found in ${BACKUP_DIR}"
        echo "   Starting with empty database"
        echo ""
        echo "   To initialize from a backup, place backup files in ${BACKUP_DIR}"
        echo "   or set INIT_BACKUP_NAME environment variable"
        exit 0
    fi

    BACKUP_NAME=$(basename "${LATEST_BACKUP}")
    echo "Auto-detected latest backup: ${BACKUP_NAME}"
fi

BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Validate backup exists
if [ ! -d "${BACKUP_PATH}" ]; then
    echo "⚠️  Warning: Backup not found: ${BACKUP_PATH}"
    echo "   Starting with empty database"
    exit 0
fi

# Validate backup contains the database
DB_BACKUP_PATH="${BACKUP_PATH}/${MONGO_DATABASE}"
if [ ! -d "${DB_BACKUP_PATH}" ]; then
    echo "⚠️  Warning: Database '${MONGO_DATABASE}' not found in backup"
    echo "   Starting with empty database"
    exit 0
fi

echo ""
echo "Restoring from backup..."

# Run mongorestore
if mongorestore \
    --host="${MONGO_HOST}" \
    --port="${MONGO_PORT}" \
    --db="${MONGO_DATABASE}" \
    "${DB_BACKUP_PATH}"; then

    echo ""
    echo "✓ Database initialized successfully from backup"
else
    echo ""
    echo "⚠️  Restore failed, but continuing (database will be empty)"
fi

echo ""
echo "=========================================="
echo "Initialization Complete: $(date)"
echo "=========================================="

exit 0
