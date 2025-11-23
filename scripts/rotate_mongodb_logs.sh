#!/bin/bash
# ============================================================================
# MongoDB Log Rotation Script
# ============================================================================
# This script rotates MongoDB logs by sending a logRotate command to MongoDB
# and optionally compresses old log files.
#
# Usage:
#   ./rotate_mongodb_logs.sh [OPTIONS]
#
# Options:
#   --compress    Compress rotated log files with gzip
#   --keep-days N Keep log files for N days (default: 30)
#
# For Docker:
#   docker exec lmelp-mongo /scripts/rotate_mongodb_logs.sh
#
# Can be scheduled via cron:
#   0 0 * * * docker exec lmelp-mongo /scripts/rotate_mongodb_logs.sh --compress
# ============================================================================

set -e  # Exit on error

# Configuration
MONGO_HOST="${MONGO_HOST:-localhost}"
MONGO_PORT="${MONGO_PORT:-27017}"
LOG_DIR="${MONGO_LOG_DIR:-/var/log/mongodb}"
KEEP_DAYS=30
COMPRESS=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --compress)
            COMPRESS=true
            shift
            ;;
        --keep-days)
            KEEP_DAYS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--compress] [--keep-days N]"
            exit 1
            ;;
    esac
done

# Log start
echo "=========================================="
echo "MongoDB Log Rotation Started: $(date)"
echo "=========================================="
echo "Host: ${MONGO_HOST}:${MONGO_PORT}"
echo "Log directory: ${LOG_DIR}"
echo "Keep logs for: ${KEEP_DAYS} days"
echo "Compress: ${COMPRESS}"
echo ""

# Check if MongoDB is running
if ! mongosh --host="${MONGO_HOST}" --port="${MONGO_PORT}" --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; then
    echo "Error: MongoDB is not accessible at ${MONGO_HOST}:${MONGO_PORT}"
    exit 1
fi

# Rotate logs using MongoDB's logRotate command
echo "Rotating MongoDB logs..."
if mongosh --host="${MONGO_HOST}" --port="${MONGO_PORT}" --eval "db.adminCommand({ logRotate: 1 })" --quiet; then
    echo "✓ Log rotation command successful"
else
    echo "✗ Log rotation command failed"
    exit 1
fi

# Get the current log file
CURRENT_LOG="${LOG_DIR}/mongod.log"

# Find rotated log files (MongoDB appends timestamp when rotating)
if [ -d "${LOG_DIR}" ]; then
    # Compress old log files if requested
    if [ "${COMPRESS}" = true ]; then
        echo ""
        echo "Compressing rotated log files..."
        find "${LOG_DIR}" -name "mongod.log.*" ! -name "*.gz" -type f | while IFS= read -r logfile; do
            echo "  Compressing: $(basename "${logfile}")"
            gzip "${logfile}"
        done
    fi

    # Delete old log files beyond retention period
    echo ""
    echo "Cleaning up old log files (older than ${KEEP_DAYS} days)..."

    DELETED_COUNT=0
    if [ "${COMPRESS}" = true ]; then
        # Delete compressed logs older than KEEP_DAYS
        DELETED=$(find "${LOG_DIR}" -name "mongod.log.*.gz" -type f -mtime +${KEEP_DAYS} -delete -print | wc -l)
        DELETED_COUNT=$((DELETED_COUNT + DELETED))
    fi

    # Delete uncompressed logs older than KEEP_DAYS
    DELETED=$(find "${LOG_DIR}" -name "mongod.log.*" ! -name "*.gz" -type f -mtime +${KEEP_DAYS} -delete -print | wc -l)
    DELETED_COUNT=$((DELETED_COUNT + DELETED))

    if [ "${DELETED_COUNT}" -gt 0 ]; then
        echo "  Deleted ${DELETED_COUNT} old log file(s)"
    else
        echo "  No old log files to delete"
    fi

    # Show current log file sizes
    echo ""
    echo "Current log files:"
    du -sh "${LOG_DIR}"/mongod.log* 2>/dev/null | sort -k2 || echo "  No log files found"
else
    echo "Warning: Log directory ${LOG_DIR} does not exist"
fi

echo ""
echo "=========================================="
echo "MongoDB Log Rotation Completed: $(date)"
echo "=========================================="

exit 0
