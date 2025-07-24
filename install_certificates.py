#!/usr/bin/env python3
"""
Script to install SSL certificates for Python on macOS.
Run this script to add the macOS system certificates to Python's certificate store.
"""
import os
import ssl
import subprocess
import sys

def install_certificates():
    """Install certificates for Python on macOS."""
    if sys.platform != 'darwin':
        print("This script is only for macOS.")
        return
    
    # Check if certificates are already installed
    try:
        ssl.create_default_context().check_hostname
        print("Certificates seem to be working already.")
    except:
        pass
    
    # Find the current Python executable
    python_path = sys.executable
    
    # Use the Install Certificates command
    print("Installing certificates...")
    cmd = [
        python_path,
        "-m", 
        "pip", 
        "install", 
        "--upgrade", 
        "certifi"
    ]
    subprocess.run(cmd)
    
    # Run the post-install script that comes with Python
    cert_script_path = os.path.join(
        os.path.dirname(os.path.dirname(python_path)),
        "Applications/Python 3.11/Install Certificates.command"
    )
    
    if os.path.exists(cert_script_path):
        print(f"Running {cert_script_path}")
        subprocess.run(["sh", cert_script_path])
    else:
        print("Could not find the Install Certificates.command script.")
        print("You may need to run it manually from your Python installation.")
        print("Alternatively, you can try:")
        print("\n  pip install --upgrade certifi\n")
        print("Or visit: https://stackoverflow.com/questions/27835619/urllib-and-ssl-certificate-verify-failed-error")
    
if __name__ == "__main__":
    install_certificates()
    print("\nIf the above steps don't work, you may need to modify main.py to use `ssl=False` in the websockets.connect call as a temporary workaround.") 