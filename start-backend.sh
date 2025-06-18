#!/bin/bash

# Quick start script for Magentic UI backend

set -e

echo "=== Starting Magentic UI Backend ==="

# Ensure Docker network exists
echo "Checking Docker network..."
if ! docker network ls | grep -q "my-network"; then
    echo "Creating Docker network 'my-network'..."
    docker network create my-network
    echo "✓ Created Docker network 'my-network'"
else
    echo "✓ Docker network 'my-network' already exists"
fi

# Check if the magentic-ui-python container is running
if docker ps --format "table {{.Names}}" | grep -q "magentic-ui-python"; then
    echo "Starting Magentic-UI backend server with enhanced logging..."
    docker exec magentic-ui-python python3 -m magentic_ui.backend.cli \
        --host 0.0.0.0 \
        --port 8081 \
        --log-level INFO \
        --log-file /Users/dank/Desktop/magentic/magentic-ui/.magentic_ui/logs/backend.log
else
    echo "Error: magentic-ui-python container is not running."
    echo "Please run docker-setup.sh first to start the containers."
    exit 1
fi