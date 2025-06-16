#!/bin/bash

# Magentic UI Docker Setup Script
# This script contains all the helpful commands for building and running the Docker containers

set -e

echo "=== Magentic UI Docker Setup ==="

# Function to print colored output
print_step() {
    echo -e "\n\033[1;34m==> $1\033[0m"
}

print_error() {
    echo -e "\033[1;31mError: $1\033[0m"
}

print_success() {
    echo -e "\033[1;32m✓ $1\033[0m"
}

# Clean up existing containers
print_step "Cleaning up existing containers"
docker rm -f magentic-ui-python magentic-ui-browser 2>/dev/null || true

# Create Docker network if it doesn't exist
print_step "Creating Docker network"
if ! docker network ls | grep -q "my-network"; then
    docker network create my-network
    print_success "Created Docker network 'my-network'"
else
    print_success "Docker network 'my-network' already exists"
fi

# Build Python environment image
print_step "Building Python environment image"
docker build -t magentic-ui-python-env -f src/magentic_ui/docker/magentic-ui-python-env/Dockerfile src/magentic_ui/docker/magentic-ui-python-env

# Build browser environment image
print_step "Building browser environment image"
docker build -t magentic-ui-browser -f src/magentic_ui/docker/magentic-ui-browser-docker/Dockerfile src/magentic_ui/docker/magentic-ui-browser-docker

# Run Python container with workspace mounted
print_step "Starting Python container"

# Check if OPENAI_API_KEY is set in environment, otherwise read from frontend/.env
if [ -z "$OPENAI_API_KEY" ]; then
    if [ -f "frontend/.env" ]; then
        export OPENAI_API_KEY=$(grep OPENAI_API_KEY frontend/.env | cut -d '=' -f2)
        echo "Using OPENAI_API_KEY from frontend/.env"
    else
        print_error "OPENAI_API_KEY not set and frontend/.env not found. Please set OPENAI_API_KEY environment variable."
        exit 1
    fi
else
    echo "Using OPENAI_API_KEY from environment"
fi

docker run -d --name magentic-ui-python \
    --network my-network \
    -v "$(pwd):/workspace" \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -p 8081:8081 \
    -e OPENAI_API_KEY="$OPENAI_API_KEY" \
    -e INSIDE_DOCKER="1" \
    magentic-ui-python-env tail -f /dev/null

# Run browser container
print_step "Starting browser container"
docker run -d --name magentic-ui-browser --network my-network magentic-ui-browser

# Wait for containers to be ready
print_step "Waiting for containers to be ready"
sleep 5

# Install magentic-ui in development mode with optimized pip settings
print_step "Installing magentic-ui in development mode"
docker exec magentic-ui-python pip install -e /workspace --no-cache-dir -v

print_success "Docker setup complete!"

echo ""
echo "=== Useful Commands ==="
echo "Start backend server:"
echo "  docker exec magentic-ui-python python3 -m magentic_ui.backend.cli --host 0.0.0.0 --port 8081"
echo ""
echo "Start magentic-ui:"
echo "  docker exec magentic-ui-python magentic-ui --host 0.0.0.0 --port 8081"
echo ""
echo "Check health:"
echo "  docker exec magentic-ui-python python3 -c \"import requests; print(requests.get('http://localhost:8081/health').status_code)\""
echo ""
echo "View logs:"
echo "  docker logs magentic-ui-python --tail 20"
echo ""
echo "Get help:"
echo "  docker exec magentic-ui-python magentic-ui --help"
echo "  docker exec magentic-ui-python python3 -m magentic_ui.backend.cli --help"
echo ""
echo "Check running processes:"
echo "  docker exec magentic-ui-python pgrep -f magentic-ui"
echo ""
echo "Interactive shell:"
echo "  docker exec -it magentic-ui-python bash"