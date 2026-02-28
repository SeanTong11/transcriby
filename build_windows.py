#!/usr/bin/env python3
"""
Windows build script for SlowPlay
Uses PyInstaller to create a standalone executable
"""

import os
import sys
import shutil
import subprocess


def check_requirements():
    """Check if all required tools are installed"""
    print("Checking requirements...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required")
        return False
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print(f"  PyInstaller: OK ({PyInstaller.__version__})")
    except ImportError:
        print("  PyInstaller: NOT FOUND")
        print("  Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)
    
    # Check core dependencies
    required = [
        ('sounddevice', 'sounddevice'),
        ('soundfile', 'soundfile'),
        ('scipy', 'scipy'),
        ('numpy', 'numpy'),
        ('customtkinter', 'customtkinter'),
        ('PIL', 'pillow'),
        ('CTkMessagebox', 'CTkMessagebox'),
        ('CTkToolTip', 'CTkToolTip'),
        ('tkinterdnd2', 'tkinterdnd2'),
    ]
    
    for module, pkg in required:
        try:
            __import__(module)
            print(f"  {module}: OK")
        except ImportError:
            print(f"  {module}: NOT FOUND")
            print(f"  Installing {pkg}...")
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)
    
    print("\nAll requirements satisfied!")
    return True


def build():
    """Build the executable using PyInstaller"""
    print("\nBuilding SlowPlay for Windows...")
    
    # Clean previous builds
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            print(f"  Cleaning {folder}/...")
            shutil.rmtree(folder)
    
    # Build PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=SlowPlay",
        "--windowed",
        "--onefile",
        "--clean",
        "--noconfirm",
    ]
    
    # Add data files
    cmd.extend([
        "--add-data", "slowplay/resources;resources",
        "--add-data", "slowplay/locales;locales",
    ])
    
    # Hidden imports for audio libraries
    cmd.extend([
        "--hidden-import", "sounddevice",
        "--hidden-import", "soundfile",
        "--hidden-import", "scipy",
        "--hidden-import", "numpy",
        "--hidden-import", "customtkinter",
        "--hidden-import", "CTkMessagebox",
        "--hidden-import", "CTkToolTip",
        "--hidden-import", "tkinterdnd2",
        "--hidden-import", "platform_utils",
    ])
    
    # Add icon (if exists)
    icon_path = os.path.join("slowplay", "resources", "Icona.ico")
    if os.path.exists(icon_path):
        cmd.extend(["--icon", icon_path])
    else:
        # Try to convert PNG to ICO
        png_path = os.path.join("slowplay", "resources", "Icona-256.png")
        if os.path.exists(png_path):
            try:
                from PIL import Image
                img = Image.open(png_path)
                img.save(icon_path, format='ICO', sizes=[(256,256), (128,128), (64,64), (32,32), (16,16)])
                cmd.extend(["--icon", icon_path])
                print(f"  Created icon from PNG")
            except Exception as e:
                print(f"  Warning: Could not create icon: {e}")
    
    # Main script
    cmd.append("sp-launch.py")
    
    # Run PyInstaller
    print(f"\n  Running PyInstaller...\n")
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print("\nBuild failed!")
        return False
    
    print("\nBuild successful!")
    print(f"  Executable: dist/SlowPlay.exe")
    
    # Create distribution folder
    dist_folder = "SlowPlay-Windows"
    if os.path.exists(dist_folder):
        shutil.rmtree(dist_folder)
    
    os.makedirs(dist_folder)
    
    # Copy executable
    shutil.copy("dist/SlowPlay.exe", dist_folder)
    
    # Copy README
    if os.path.exists("README.md"):
        shutil.copy("README.md", dist_folder)
    
    if os.path.exists("INSTALL_WINDOWS.md"):
        shutil.copy("INSTALL_WINDOWS.md", dist_folder)
    
    # Estimate size
    exe_size = os.path.getsize(os.path.join(dist_folder, "SlowPlay.exe"))
    print(f"\n  Distribution folder: {dist_folder}/")
    print(f"  Executable size: {exe_size / (1024*1024):.1f} MB")
    
    return True


def main():
    print("=" * 60)
    print("SlowPlay Windows Build Script")
    print("=" * 60)
    
    if not check_requirements():
        print("\nRequirements check failed. Please install missing dependencies.")
        sys.exit(1)
    
    if not build():
        print("\nBuild failed.")
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("Build completed successfully!")
    print("=" * 60)
    print(f"\nThe executable is in: SlowPlay-Windows/SlowPlay.exe")
    print("\nYou can zip this folder and distribute it to users.")
    print("No additional installation is required!")


if __name__ == "__main__":
    main()
