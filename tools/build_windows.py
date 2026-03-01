#!/usr/bin/env python3
"""
Windows build script for Transcriby
Uses PyInstaller to create a standalone executable
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
        ('mpv', 'python-mpv'),
        ('av', 'av'),
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
    print("\nBuilding Transcriby for Windows...")
    print(f"  Project root: {PROJECT_ROOT}")
    
    # Clean previous builds
    for folder in ['build', 'dist']:
        folder_path = PROJECT_ROOT / folder
        if folder_path.exists():
            print(f"  Cleaning {folder}/...")
            shutil.rmtree(folder_path)
    
    # Build PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=Transcriby",
        "--windowed",
        "--onefile",
        "--clean",
        "--noconfirm",
    ]
    
    # Add data files
    cmd.extend([
        "--add-data", f"{PROJECT_ROOT / 'transcriby' / 'resources'};resources",
        "--add-data", f"{PROJECT_ROOT / 'transcriby' / 'locales'};locales",
    ])
    
    # Hidden imports for audio libraries
    cmd.extend([
        "--hidden-import", "mpv",
        "--hidden-import", "av",
        "--hidden-import", "soundfile",
        "--hidden-import", "scipy",
        "--hidden-import", "numpy",
        "--hidden-import", "customtkinter",
        "--hidden-import", "CTkMessagebox",
        "--hidden-import", "CTkToolTip",
        "--hidden-import", "tkinterdnd2",
        "--hidden-import", "platform_utils",
        "--collect-submodules", "av",
    ])
    
    # Bundle libmpv DLLs if present (third_party/mpv)
    mpv_dir = PROJECT_ROOT / "third_party" / "mpv"
    if mpv_dir.is_dir():
        for name in os.listdir(mpv_dir):
            if name.lower().endswith(".dll"):
                src = mpv_dir / name
                cmd.extend(["--add-binary", f"{src};."])

    # Add icon (if exists)
    icon_path = PROJECT_ROOT / "transcriby" / "resources" / "Icona.ico"
    if icon_path.exists():
        cmd.extend(["--icon", str(icon_path)])
        print(f"  Using icon: {icon_path}")
    else:
        # Try to convert PNG to ICO
        png_path = PROJECT_ROOT / "transcriby" / "resources" / "Icona-256.png"
        if png_path.exists():
            try:
                from PIL import Image
                img = Image.open(str(png_path))
                img.save(icon_path, format='ICO', sizes=[(256,256), (128,128), (64,64), (32,32), (16,16)])
                cmd.extend(["--icon", str(icon_path)])
                print(f"  Created icon from PNG")
            except Exception as e:
                print(f"  Warning: Could not create icon: {e}")
    
    # Main script
    cmd.append(str(PROJECT_ROOT / "transcriby-launch.py"))
    
    # Run PyInstaller
    print(f"\n  Running PyInstaller...\n")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    
    if result.returncode != 0:
        print("\nBuild failed!")
        return False
    
    print("\nBuild successful!")
    print(f"  Executable: {PROJECT_ROOT / 'dist' / 'Transcriby.exe'}")
    
    # Create distribution folder
    dist_folder = PROJECT_ROOT / "Transcriby-Windows"
    if dist_folder.exists():
        shutil.rmtree(dist_folder)
    
    dist_folder.mkdir(parents=True, exist_ok=True)
    
    # Copy executable
    shutil.copy(PROJECT_ROOT / "dist" / "Transcriby.exe", dist_folder)
    
    # Copy README
    if (PROJECT_ROOT / "README.md").exists():
        shutil.copy(PROJECT_ROOT / "README.md", dist_folder)
    
    if (PROJECT_ROOT / "INSTALL_WINDOWS.md").exists():
        shutil.copy(PROJECT_ROOT / "INSTALL_WINDOWS.md", dist_folder)
    
    # Estimate size
    exe_size = (dist_folder / "Transcriby.exe").stat().st_size
    print(f"\n  Distribution folder: {dist_folder}/")
    print(f"  Executable size: {exe_size / (1024*1024):.1f} MB")
    
    return True


def main():
    print("=" * 60)
    print("Transcriby Windows Build Script")
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
    print(f"\nThe executable is in: Transcriby-Windows/Transcriby.exe")
    print("\nYou can zip this folder and distribute it to users.")
    print("No additional installation is required!")


if __name__ == "__main__":
    main()
