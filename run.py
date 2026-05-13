#!/usr/bin/env python3
"""Run the Supplier Hub application locally."""
import os
import sys

# Ensure we're in the project directory
project_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_dir)

# Add backend to Python path
sys.path.insert(0, os.path.join(project_dir, 'backend'))

# Create required directories
os.makedirs('backend/db', exist_ok=True)

# Import and run the application
from main import app

if __name__ == "__main__":
    import uvicorn
    print("Starting Supplier Hub on http://localhost:9000")
    print("Press CTRL+C to stop the server")
    uvicorn.run("run:app", host="0.0.0.0", port=9000, reload=False)
