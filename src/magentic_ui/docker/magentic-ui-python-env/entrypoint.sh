#!/bin/bash
set -e

umask 000

# Auto-install magentic-ui if workspace is mounted
if [ -d "/workspace" ] && [ -f "/workspace/pyproject.toml" ]; then
    echo "Installing magentic-ui in development mode..."
    cd /workspace
    
    # Ensure pip is up to date
    pip install --upgrade pip
    
    # Clear pip cache to avoid conflicts
    pip cache purge
    
    # Install in development mode with proper error handling
    echo "Installing magentic-ui dependencies..."
    pip install -e . --verbose || {
        echo "Warning: Failed to install magentic-ui in development mode"
        echo "Attempting alternative installation..."
        pip install --no-cache-dir -e . || echo "Alternative installation also failed"
    }
fi

exec "$@"