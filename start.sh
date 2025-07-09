#!/bin/bash

# Render startup script for unified scraper service

# Set environment variables
export PYTHONUNBUFFERED=1
export DISPLAY=:99

# Check if we're in a Render environment and install Chrome if needed
if [ -n "$RENDER" ] || [ -n "$PORT" ]; then
    echo "Detected cloud deployment environment"
    
    # Install Chrome dependencies for headless operation
    echo "Installing Chrome and dependencies..."
    
    # Try to install Chrome via package manager (may not work on all cloud platforms)
    if command -v apt-get &> /dev/null; then
        echo "Using apt-get to install Chrome..."
        apt-get update -qq
        apt-get install -y -qq wget gnupg unzip curl
        
        # Add Google Chrome repository
        wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor > /etc/apt/trusted.gpg.d/google.gpg
        echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
        
        # Install Chrome
        apt-get update -qq
        apt-get install -y -qq google-chrome-stable
        
        echo "Chrome installation completed"
    else
        echo "Package manager not available, Chrome will be handled by application"
    fi
    
    # Start Xvfb (X Virtual Framebuffer) for headless Chrome
    if command -v Xvfb &> /dev/null; then
        echo "Starting Xvfb..."
        Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &
    else
        echo "Xvfb not available, using pure headless mode"
    fi
else
    echo "Local development environment detected"
fi

# Start the application
echo "Starting unified scraper service..."
uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} 