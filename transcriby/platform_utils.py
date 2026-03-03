#!/usr/bin/env python3
"""
Platform abstraction module for Transcriby
Handles differences between Linux and Windows
"""

import os
import sys
import platform


def is_windows() -> bool:
    """Check if running on Windows"""
    return platform.system() == "Windows"


def is_linux() -> bool:
    """Check if running on Linux"""
    return platform.system() == "Linux"


def is_wsl() -> bool:
    """Check if running on Windows Subsystem for Linux (WSL)
    
    WSL has different behavior than native Linux in some cases,
    especially regarding X11 GUI threading. This function helps
    us apply WSL-specific workarounds when needed.
    
    Detection methods:
    1. Check /proc/version for "microsoft" or "wsl" strings
    2. Check for WSL-specific environment variables
    """
    if not is_linux():
        return False
    # Check for WSL-specific indicators in kernel version
    try:
        with open('/proc/version', 'r') as f:
            version_info = f.read().lower()
            return 'microsoft' in version_info or 'wsl' in version_info
    except:
        pass
    # Fallback: check WSL-specific environment variables
    # These are set by WSL but not in native Linux
    return 'WSL_DISTRO_NAME' in os.environ or 'WSL_INTEROP' in os.environ


def get_config_dir() -> str:
    """Get the appropriate config directory for the current platform"""
    if is_windows():
        # Windows: %APPDATA%\Transcriby
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(appdata, "Transcriby")
    else:
        # Linux: ~/.config/transcriby
        return os.path.join(os.path.expanduser("~"), ".config", "transcriby")


def get_cache_dir() -> str:
    """Get the appropriate cache/temp directory for the current platform"""
    if is_windows():
        # Windows: %LOCALAPPDATA%\Temp\Transcriby or %TEMP%\Transcriby
        temp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
        return os.path.join(temp_dir, "Transcriby")
    else:
        # Linux: /tmp or TMPDIR
        return os.path.join(tempfile.gettempdir(), "transcriby")


def get_external_cmd(cmd: str) -> str:
    """Get the appropriate command name for the current platform"""
    if is_windows():
        # On Windows, commands may have .exe extension
        if not cmd.endswith(".exe"):
            return cmd + ".exe"
    return cmd


def get_env_with_original_path():
    """Get environment with original library path (for PyInstaller compatibility)"""
    env = dict(os.environ)
    
    if is_windows():
        # On Windows, handle PATH restoration for PyInstaller
        # PyInstaller sets _MEIPASS and modifies PATH
        lp_orig = env.get('PATH_ORIG')
        if lp_orig is not None:
            env['PATH'] = lp_orig
    else:
        # On Linux, restore LD_LIBRARY_PATH
        lp_key = 'LD_LIBRARY_PATH'
        lp_orig = env.get(lp_key + '_ORIG')
        if lp_orig is not None:
            env[lp_key] = lp_orig
        else:
            env.pop(lp_key, None)
    
    return env


def _get_bundle_base_dir() -> str:
    """Return base directory for bundled resources (PyInstaller) or source."""
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))


def get_resources_dir() -> str:
    """Return resources directory for current execution context."""
    return os.path.join(_get_bundle_base_dir(), "resources")


def get_locales_dir() -> str:
    """Return locales directory for current execution context."""
    return os.path.join(_get_bundle_base_dir(), "locales")


def apply_window_icon(window, resources_dir: str | None = None) -> bool:
    """Apply app icon assets to a Tk/CTk window.

    On Windows this sets both iconphoto (runtime) and iconbitmap (.ico) to improve
    titlebar/taskbar rendering. On other platforms iconphoto is used.
    """
    if resources_dir is None:
        resources_dir = get_resources_dir()

    icon_applied = False
    icon_images = []
    icon_png_sizes = [256, 128, 96, 64, 48, 40, 32, 24, 20, 16]

    try:
        import tkinter as tk

        for size in icon_png_sizes:
            png_path = os.path.join(resources_dir, f"Icona-{size}.png")
            if os.path.isfile(png_path):
                try:
                    icon_images.append(tk.PhotoImage(master=window, file=png_path))
                except Exception:
                    pass

        if icon_images:
            try:
                window.wm_iconphoto(True, *icon_images)
                icon_applied = True
            except Exception:
                try:
                    window.iconphoto(True, *icon_images)
                    icon_applied = True
                except Exception:
                    pass
            setattr(window, "_transcriby_icon_images", icon_images)
    except Exception:
        pass

    if is_windows():
        icon_ico = os.path.join(resources_dir, "Icona.ico")
        if os.path.isfile(icon_ico):
            try:
                window.iconbitmap(icon_ico)
                icon_applied = True
            except Exception:
                pass

    return icon_applied


def check_cmd_exists(cmd: str) -> bool:
    """Check if a command exists on the system"""
    import subprocess
    
    cmd = get_external_cmd(cmd)
    env = get_env_with_original_path()
    
    try:
        if is_windows():
            # On Windows, use 'where' command
            subprocess.run(["where", cmd], env=env, capture_output=True, check=True)
        else:
            subprocess.run(["which", cmd], env=env, capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def uri_from_path(path: str) -> str:
    """Convert a file path to a URI"""
    from urllib.parse import quote
    
    if is_windows():
        # Windows path handling
        # file:///C:/path/to/file or file://server/share
        abs_path = os.path.abspath(path)
        # Convert backslashes to forward slashes
        abs_path = abs_path.replace("\\", "/")
        # Handle Windows drive letters
        if ":" in abs_path:
            # Has drive letter, e.g., C:/path
            return "file:///" + abs_path
        else:
            # UNC path, e.g., //server/share
            return "file://" + abs_path
    else:
        # Linux/macOS
        abs_path = os.path.abspath(path)
        return "file://" + quote(abs_path)


def is_valid_absolute_path(path: str) -> bool:
    """Check if a path is an absolute path (platform independent)"""
    if is_windows():
        # Windows: C:\path or \\server\share
        return os.path.isabs(path) or (len(path) >= 2 and path[1] == ":")
    else:
        # Linux: /path
        return path.startswith("/")


# Import tempfile here to avoid circular import issues
import tempfile
