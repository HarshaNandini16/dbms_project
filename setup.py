# setup.py - Run this to initialize the application
import os
import subprocess
import sys

def setup_application():
    print("Setting up Book Exchange Platform...")
    
    # Install Python dependencies
    print("Installing Python packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    
    # Create necessary directories
    print("Creating directories...")
    os.makedirs("static/uploads", exist_ok=True)
    os.makedirs("static/css", exist_ok=True)
    os.makedirs("static/js", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    
    print("\nSetup complete!")
    print("\nNext steps:")
    print("1. Run the SQL script to create the database in SSMS")
    print("2. Update database connection settings in app.py if needed")
    print("3. Run the application: python app.py")
    print("4. Open browser and navigate to http://localhost:5000")

if __name__ == "__main__":
    setup_application()