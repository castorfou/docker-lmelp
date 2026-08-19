# ============================================================================
# Custom MongoDB Image with Anacron for Log Rotation
# ============================================================================
# This Dockerfile extends the official MongoDB image to add anacron support
# for automatic log rotation, suitable for laptops/desktops that may be
# powered off during scheduled cron times.
# ============================================================================

FROM mongo:latest

# Install anacron and required utilities
RUN apt-get update && \
    apt-get install -y \
        anacron \
        gzip \
    && rm -rf /var/lib/apt/lists/*

# Create log rotation and backup configuration for anacron
RUN mkdir -p /etc/anacron.daily /etc/anacron.weekly

# Create log directory with correct permissions
RUN mkdir -p /var/log/mongodb && \
    chown -R mongodb:mongodb /var/log/mongodb && \
    chmod 755 /var/log/mongodb

# Copy MongoDB configuration file
COPY config/mongod.conf /etc/mongod.conf
RUN chmod 644 /etc/mongod.conf && \
    chown mongodb:mongodb /etc/mongod.conf

# Copy the log rotation script
COPY scripts/rotate_mongodb_logs.sh /scripts/rotate_mongodb_logs.sh
RUN chmod +x /scripts/rotate_mongodb_logs.sh

# Copy the backup script
COPY scripts/backup_mongodb.sh /scripts/backup_mongodb.sh
RUN chmod +x /scripts/backup_mongodb.sh

# Create anacron job file for log rotation (daily)
RUN echo '#!/bin/bash' > /etc/anacron.daily/mongodb-logrotate && \
    echo '/scripts/rotate_mongodb_logs.sh --compress --keep-days 30 >> /var/log/mongodb/logrotate.log 2>&1' >> /etc/anacron.daily/mongodb-logrotate && \
    chmod +x /etc/anacron.daily/mongodb-logrotate

# Create anacron job file for backup (weekly)
RUN echo '#!/bin/bash' > /etc/anacron.weekly/mongodb-backup && \
    echo 'MONGO_HOST=${MONGO_HOST:-localhost}' >> /etc/anacron.weekly/mongodb-backup && \
    echo 'MONGO_PORT=${MONGO_PORT:-27017}' >> /etc/anacron.weekly/mongodb-backup && \
    echo 'MONGO_DATABASE=${MONGO_DATABASE:-masque_et_la_plume}' >> /etc/anacron.weekly/mongodb-backup && \
    echo 'BACKUP_RETENTION_WEEKS=${BACKUP_RETENTION_WEEKS:-7}' >> /etc/anacron.weekly/mongodb-backup && \
    echo 'export MONGO_HOST MONGO_PORT MONGO_DATABASE BACKUP_RETENTION_WEEKS' >> /etc/anacron.weekly/mongodb-backup && \
    echo '/scripts/backup_mongodb.sh >> /var/log/mongodb/backup.log 2>&1' >> /etc/anacron.weekly/mongodb-backup && \
    chmod +x /etc/anacron.weekly/mongodb-backup

# Configure anacron to run jobs
# Format: period delay job-identifier command
# Daily log rotation (every 1 day, wait 5 minutes after boot)
RUN echo '1 5 mongodb-logrotate /etc/anacron.daily/mongodb-logrotate' >> /etc/anacrontab
# Weekly backup (every 1 day check, script handles 7 day logic, wait 10 minutes after boot)
RUN echo '1 10 mongodb-backup /etc/anacron.weekly/mongodb-backup' >> /etc/anacrontab

# Create a startup script that runs both MongoDB and anacron
# The anacron loop must run as the mongodb user (not root): it spawns the
# backup and log-rotation jobs, which write to bind-mounted host volumes
# (/backups, /var/log/mongodb) whose ownership must stay consistent with
# mongod's own data files (issue #48).
RUN echo '#!/bin/bash' > /docker-entrypoint-anacron.sh && \
    echo 'set -e' >> /docker-entrypoint-anacron.sh && \
    echo '' >> /docker-entrypoint-anacron.sh && \
    echo '# Bind-mounted host volumes may not match the mongodb UID (999):' >> /docker-entrypoint-anacron.sh && \
    echo '# chown them (recursively for content that may already exist) while' >> /docker-entrypoint-anacron.sh && \
    echo '# still running as root, before dropping to mongodb below.' >> /docker-entrypoint-anacron.sh && \
    echo 'mkdir -p /backups /var/log/mongodb /var/spool/anacron' >> /docker-entrypoint-anacron.sh && \
    echo 'chown -R mongodb:mongodb /backups /var/log/mongodb' >> /docker-entrypoint-anacron.sh && \
    echo 'chown mongodb:mongodb /var/spool/anacron' >> /docker-entrypoint-anacron.sh && \
    echo '' >> /docker-entrypoint-anacron.sh && \
    echo '# Ownership watchdog, independent of the anacron loop below: a' >> /docker-entrypoint-anacron.sh && \
    echo '# sibling service sharing an overlapping bind-mounted parent' >> /docker-entrypoint-anacron.sh && \
    echo '# directory can re-own these paths after startup (issue #51) --' >> /docker-entrypoint-anacron.sh && \
    echo '# self-heal on a short interval instead of staying broken. Kept' >> /docker-entrypoint-anacron.sh && \
    echo '# separate from the anacron loop because `anacron -d` blocks for' >> /docker-entrypoint-anacron.sh && \
    echo '# each jobs configured anacrontab delay (minutes) before running' >> /docker-entrypoint-anacron.sh && \
    echo '# it, which would make re-chowning far too infrequent.' >> /docker-entrypoint-anacron.sh && \
    echo '(while true; do chown -R mongodb:mongodb /backups /var/log/mongodb; sleep "${CHOWN_WATCHDOG_INTERVAL:-300}"; done) &' >> /docker-entrypoint-anacron.sh && \
    echo '' >> /docker-entrypoint-anacron.sh && \
    echo '# Start anacron loop in the background (check every hour), as mongodb' >> /docker-entrypoint-anacron.sh && \
    echo '# so spawned jobs do not create root-owned files' >> /docker-entrypoint-anacron.sh && \
    echo '(while true; do gosu mongodb anacron -d; sleep "${ANACRON_LOOP_INTERVAL:-3600}"; done) &' >> /docker-entrypoint-anacron.sh && \
    echo '' >> /docker-entrypoint-anacron.sh && \
    echo '# Run the original MongoDB entrypoint' >> /docker-entrypoint-anacron.sh && \
    echo 'exec /usr/local/bin/docker-entrypoint.sh "$@"' >> /docker-entrypoint-anacron.sh && \
    chmod +x /docker-entrypoint-anacron.sh

# Use our custom entrypoint
ENTRYPOINT ["/docker-entrypoint-anacron.sh"]

# Default command (same as official mongo image)
CMD ["mongod"]
