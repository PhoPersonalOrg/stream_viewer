#!/usr/bin/env python3
"""
Script to update the mne-python path in pyproject.toml by detecting which path exists.
This avoids git conflicts by allowing each platform to maintain its own path.

Usage:
    python update_mne_path.py
"""
import re
from pathlib import Path

def find_mne_path():
    """Find the correct path to mne-python by checking which directory exists."""
    script_dir = Path(__file__).parent
    
    # Check possible paths in order of likelihood
    possible_paths = [
        "../mne-python",
        "../../mne-python",
    ]
    
    for rel_path in possible_paths:
        full_path = (script_dir / rel_path).resolve()
        if full_path.exists() and full_path.is_dir():
            return rel_path
    
    return None

def update_mne_path():
    """Update the mne path in pyproject.toml by detecting which path exists."""
    pyproject_path = Path(__file__).parent / "pyproject.toml"
    
    if not pyproject_path.exists():
        print(f"Error: {pyproject_path} not found")
        return
    
    # Find which path exists
    new_path = find_mne_path()
    
    if new_path is None:
        print("Error: Could not find mne-python directory.")
        print("Checked paths:")
        for rel_path in ["../mne-python", "../../mne-python"]:
            full_path = (Path(__file__).parent / rel_path).resolve()
            print(f"  - {rel_path} -> {full_path} (exists: {full_path.exists()})")
        return
    
    content = pyproject_path.read_text()
    
    # Replace the path in the mne source definition
    pattern = r'(mne\s*=\s*\{\s*path\s*=\s*)"[^"]+"'
    replacement = f'\\1"{new_path}"'
    
    new_content = re.sub(pattern, replacement, content)
    
    if new_content != content:
        pyproject_path.write_text(new_content)
        print(f"Updated mne path to '{new_path}' (directory exists)")
    else:
        print(f"Path already set to '{new_path}' (directory exists)")

if __name__ == "__main__":
    update_mne_path()
