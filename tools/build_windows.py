#!/usr/bin/env python3
"""
Windows build script for Transcriby
Uses PyInstaller to create a standalone executable
"""

import os
import sys
import shutil
import subprocess
import importlib.util
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _is_windows_mpv_core_dll(name: str) -> bool:
    lower = name.lower()
    if lower in {"libmpv.dll", "mpv.dll", "libmpv-2.dll", "mpv-2.dll", "mpv-1.dll"}:
        return True
    if lower.startswith("libmpv-") and lower.endswith(".dll"):
        return True
    if lower.startswith("mpv-") and lower.endswith(".dll"):
        return True
    return False


def _collect_mpv_dll_dirs():
    """Collect candidate directories that may contain libmpv DLLs."""
    dirs = []

    # Preferred: explicit environment variable from CI or local setup.
    env_dir = os.environ.get("TRANSCRIBY_MPV_DIR") or os.environ.get("SLOWPLAY_MPV_DIR")
    if env_dir:
        dirs.append(Path(env_dir))

    # Fallback: derive from mpv executable on PATH.
    mpv_exe = shutil.which("mpv")
    if mpv_exe:
        mpv_dir = Path(mpv_exe).resolve().parent
        dirs.extend(
            [
                mpv_dir,
                mpv_dir / "bin",
                mpv_dir / "lib",
                mpv_dir.parent / "bin",
                mpv_dir.parent / "lib",
            ]
        )

    # Legacy fallback for manual local builds.
    dirs.append(PROJECT_ROOT / "third_party" / "mpv")

    seen = set()
    result = []
    for d in dirs:
        try:
            key = str(d.resolve()).lower()
        except Exception:
            key = str(d).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(d)
    return result


def _find_mpv_runtime_dir():
    """Find the directory that contains libmpv core DLLs."""
    matches = []

    for base_dir in _collect_mpv_dll_dirs():
        if not base_dir.is_dir():
            continue
        try:
            for path in base_dir.rglob("*.dll"):
                if _is_windows_mpv_core_dll(path.name):
                    matches.append(path.parent)
        except OSError:
            continue

    if not matches:
        return None

    # Deduplicate while preserving order.
    unique = []
    seen = set()
    for d in matches:
        key = str(d.resolve()).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(d)

    # Prefer 64-bit/runtime-looking directories when multiple are found.
    preferred_tokens = ("x86_64", "x64", "64")
    for d in unique:
        lower = str(d).lower()
        if any(token in lower for token in preferred_tokens):
            return d

    return unique[0]


def _print_mpv_search_diagnostics():
    """Print concise diagnostics for mpv DLL discovery."""
    print("  mpv candidate directories:")
    for d in _collect_mpv_dll_dirs():
        status = "exists" if d.is_dir() else "missing"
        print(f"    - {d} [{status}]")


def check_requirements():
    """Check if all required tools are installed"""
    print("Checking requirements...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required")
        return False
    
    missing_items = []

    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print(f"  PyInstaller: OK ({PyInstaller.__version__})")
    except ImportError:
        print("  PyInstaller: NOT FOUND")
        missing_items.append("pyinstaller")
    
    # Check core dependencies
    required = [
        ('mpv', 'python-mpv', True),
        ('soundfile', 'soundfile', False),
        ('numpy', 'numpy', False),
        ('PySide6', 'PySide6', False),
    ]
    
    for module, pkg, check_spec_only in required:
        try:
            if check_spec_only:
                # python-mpv import requires libmpv runtime; check install without loading DLLs.
                if importlib.util.find_spec(module) is None:
                    raise ImportError(module)
            else:
                __import__(module)
            print(f"  {module}: OK")
        except ImportError:
            print(f"  {module}: NOT FOUND")
            missing_items.append(pkg)

    if missing_items:
        unique_missing = []
        seen = set()
        for item in missing_items:
            key = str(item).strip().lower()
            if key in seen:
                continue
            seen.add(key)
            unique_missing.append(str(item))
        print("\nMissing required Python packages:")
        for pkg in unique_missing:
            print(f"  - {pkg}")
        print("\nInstall dependencies first, then rerun build script.")
        print("Example:")
        print("  uv sync")
        print("or")
        print("  uv pip install " + " ".join(unique_missing))
        return False
    
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
        "--hidden-import", "soundfile",
        "--hidden-import", "numpy",
        "--hidden-import", "PySide6",
        "--hidden-import", "platform_utils",
    ])
    
    # Bundle libmpv DLLs from discovered runtime directory.
    added_dll_paths = set()
    core_found = False

    _print_mpv_search_diagnostics()
    runtime_dir = _find_mpv_runtime_dir()
    if runtime_dir and runtime_dir.is_dir():
        print(f"  detected mpv runtime dir: {runtime_dir}")
        try:
            names = os.listdir(runtime_dir)
        except OSError:
            names = []
        for name in names:
            lower = name.lower()
            if not lower.endswith(".dll"):
                continue
            src = runtime_dir / name
            key = str(src.resolve()).lower()
            if key in added_dll_paths:
                continue
            added_dll_paths.add(key)
            cmd.extend(["--add-binary", f"{src};."])
            if _is_windows_mpv_core_dll(lower):
                core_found = True

    if not core_found:
        print("\nError: Could not find libmpv core DLL (libmpv*.dll or mpv-*.dll).")
        print("Set TRANSCRIBY_MPV_DIR to the directory containing mpv DLLs, or install mpv on PATH.")
        return False
    print(f"  Using mpv runtime dir: {runtime_dir}")
    print("  DLLs in runtime dir:")
    for dll_name in sorted([n for n in names if n.lower().endswith(".dll")]):
        print(f"    - {dll_name}")
    print(f"  Bundling {len(added_dll_paths)} DLL(s) for mpv runtime")

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
