#!/bin/bash
# Start the Supplier Hub application locally (without Docker)

set -e

echo "Starting Supplier Hub locally..."
echo "================================"

# Create database directories if they don't exist
mkdir -p backend/db

# Install dependencies if requirements.txt exists
if [ -f "backend/requirements.txt" ]; then
    echo "Installing/updating Python dependencies..."
    pip install -r backend/requirements.txt -q
fi

# Initialize the database
echo "Initializing database..."
python backend/init_db.py

# Start the application
echo "Starting application on http://localhost:9000"
echo "================================"
python backend/main.py
