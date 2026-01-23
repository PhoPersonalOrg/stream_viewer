#!/usr/bin/env python3
"""
Build script for creating self-contained executables using PyInstaller.
"""

import sys
import subprocess
import shutil
from pathlib import Path

def main():
    """Build executables using PyInstaller."""
    project_root = Path(__file__).parent
    
    # Clean previous builds
    build_dir = project_root / 'build'
    dist_dir = project_root / 'dist'
    
    print("Cleaning previous builds...")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    
    # Build main application
    spec_file = project_root / 'lsl_viewer.spec'
    if not spec_file.exists():
        print(f"Error: Spec file not found: {spec_file}")
        return 1
    
    print(f"\nBuilding executable from {spec_file}...")
    result = subprocess.run(
        [sys.executable, '-m', 'PyInstaller', '--clean', str(spec_file)],
        cwd=project_root
    )
    
    if result.returncode != 0:
        print("Build failed!")
        return result.returncode
    
    print("\nBuild completed successfully!")
    print(f"Executable location: {dist_dir / 'lsl_viewer'}")
    if sys.platform == 'win32':
        print(f"Executable: {dist_dir / 'lsl_viewer.exe'}")
    else:
        print(f"Executable: {dist_dir / 'lsl_viewer'}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
