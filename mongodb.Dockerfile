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

# Create log rotation configuration for anacron
RUN mkdir -p /etc/anacron.daily

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

# Create anacron job file
RUN echo '#!/bin/bash' > /etc/anacron.daily/mongodb-logrotate && \
    echo '/scripts/rotate_mongodb_logs.sh --compress --keep-days 30 >> /var/log/mongodb/logrotate.log 2>&1' >> /etc/anacron.daily/mongodb-logrotate && \
    chmod +x /etc/anacron.daily/mongodb-logrotate

# Configure anacron to run the job daily
# Format: period delay job-identifier command
RUN echo '1 5 mongodb-logrotate /etc/anacron.daily/mongodb-logrotate' >> /etc/anacrontab

# Create a startup script that runs both MongoDB and anacron
RUN echo '#!/bin/bash' > /docker-entrypoint-anacron.sh && \
    echo 'set -e' >> /docker-entrypoint-anacron.sh && \
    echo '' >> /docker-entrypoint-anacron.sh && \
    echo '# Start anacron in the background' >> /docker-entrypoint-anacron.sh && \
    echo 'anacron -d &' >> /docker-entrypoint-anacron.sh && \
    echo '' >> /docker-entrypoint-anacron.sh && \
    echo '# Run the original MongoDB entrypoint' >> /docker-entrypoint-anacron.sh && \
    echo 'exec /usr/local/bin/docker-entrypoint.sh "$@"' >> /docker-entrypoint-anacron.sh && \
    chmod +x /docker-entrypoint-anacron.sh

# Use our custom entrypoint
ENTRYPOINT ["/docker-entrypoint-anacron.sh"]

# Default command (same as official mongo image)
CMD ["mongod"]
