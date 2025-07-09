#!/bin/bash

# Render startup script for unified scraper service

# Set environment variables
export PYTHONUNBUFFERED=1
export DISPLAY=:99

# Install Chrome dependencies (if not using Docker)
if ! command -v google-chrome &> /dev/null; then
    echo "Installing Chrome dependencies..."
    apt-get update
    apt-get install -y wget gnupg xvfb
    
    # Add Google Chrome repository
    wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list
    
    # Install Chrome
    apt-get update
    apt-get install -y google-chrome-stable
    
    # Install ChromeDriver
    CHROME_DRIVER_VERSION=$(curl -sS chromedriver.storage.googleapis.com/LATEST_RELEASE)
    wget -O /tmp/chromedriver.zip http://chromedriver.storage.googleapis.com/$CHROME_DRIVER_VERSION/chromedriver_linux64.zip
    unzip /tmp/chromedriver.zip chromedriver -d /usr/local/bin/
    chmod +x /usr/local/bin/chromedriver
    rm /tmp/chromedriver.zip
fi

# Start Xvfb (X Virtual Framebuffer) for headless Chrome
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &

# Start the application
echo "Starting unified scraper service..."
exec gunicorn app:app -w 2 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --timeout 120 