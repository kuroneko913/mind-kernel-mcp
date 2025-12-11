#!/bin/bash
set -e

echo "Starting Dev Environment Initialization..."

# Retry seed script until success (waits for LocalStack)
count=0
max_retries=30
until python scripts/seed_local_db.py; do
    count=$((count + 1))
    if [ $count -ge $max_retries ]; then
        echo "Failed to seed database after $max_retries attempts. Exiting."
        exit 1
    fi
    echo "Seed script failed (LocalStack might not be ready). Retrying in 2s... ($count/$max_retries)"
    sleep 2
done

echo "Deploying Lambda execution environment..."
python scripts/deploy_lambda.py

echo "Initialization Complete. Container is ready."
# Keep container alive for 'docker compose exec'
exec tail -f /dev/null
