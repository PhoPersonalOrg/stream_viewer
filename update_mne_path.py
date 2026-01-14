#!/usr/bin/env python3
"""
Script to update the mne-python path in pyproject.toml based on the platform.
This avoids git conflicts by allowing each platform to maintain its own path.

Usage:
    python update_mne_path.py
"""
import platform
import re
from pathlib import Path

def update_mne_path():
    """Update the mne path in pyproject.toml based on the current platform."""
    pyproject_path = Path(__file__).parent / "pyproject.toml"
    
    if not pyproject_path.exists():
        print(f"Error: {pyproject_path} not found")
        return
    
    content = pyproject_path.read_text()
    
    # Determine the correct path based on platform
    system = platform.system()
    if system == "Windows":
        new_path = "../../mne-python"
    else:  # Linux, macOS, etc.
        new_path = "../mne-python"
    
    # Replace the path in the mne source definition
    pattern = r'(mne\s*=\s*\{\s*path\s*=\s*)"[^"]+"'
    replacement = f'\\1"{new_path}"'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        pyproject_path.write_text(new_content)
        print(f"Updated mne path to '{new_path}' for {system}")
    else:
        print(f"Path already set to '{new_path}' for {system}")

if __name__ == "__main__":
    update_mne_path()
