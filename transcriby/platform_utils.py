#!/usr/bin/env python3
"""
Platform abstraction module for Transcriby
Handles differences between Linux and Windows
"""

import os
import sys
import platform
import ctypes


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


def apply_window_icon(window, resources_dir: str | None = None, schedule_retry: bool = True) -> bool:
    """Apply app icon assets to a Tk/CTk window.

    Windows: prefer .ico only to keep taskbar/titlebar frame selection consistent.
    Linux/macOS: try .ico first, then fall back to multi-size iconphoto PNGs.
    """
    if resources_dir is None:
        resources_dir = get_resources_dir()

    icon_applied = False
    icon_ico = os.path.join(resources_dir, "Icona.ico")
    if os.path.isfile(icon_ico):
        icon_ico_abs = os.path.abspath(icon_ico).replace("\\", "/")
        try:
            window.iconbitmap(icon_ico_abs)
            icon_applied = True
        except Exception:
            try:
                window.wm_iconbitmap(icon_ico_abs)
                icon_applied = True
            except Exception:
                pass
        if is_windows():
            try:
                _apply_windows_hicon(window, icon_ico_abs)
                icon_applied = True
            except Exception:
                pass
        try:
            setattr(window, "_iconbitmap_method_called", True)
        except Exception:
            pass

    # Keep Windows on .ico-only path. For Linux/macOS, load PNG iconphoto fallback.
    if not is_windows():
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

    # Some Windows environments apply a default icon shortly after creation.
    # Re-apply once after that window to keep taskbar/titlebar icon stable.
    if is_windows() and icon_applied and schedule_retry:
        try:
            if not getattr(window, "_transcriby_icon_retry_scheduled", False):
                setattr(window, "_transcriby_icon_retry_scheduled", True)

                def _retry():
                    try:
                        apply_window_icon(window, resources_dir, schedule_retry=False)
                    finally:
                        setattr(window, "_transcriby_icon_retry_scheduled", False)

                # CTk may apply its default icon around 200ms after creation.
                window.after(320, _retry)
        except Exception:
            pass

    return icon_applied


def set_windows_app_user_model_id(app_id: str) -> bool:
    """Set explicit Windows AppUserModelID for stable taskbar icon grouping."""
    if not is_windows():
        return False

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        return True
    except Exception:
        return False


def _apply_windows_hicon(window, icon_path: str) -> None:
    """Force window big/small icons via Win32 API from .ico file."""
    if not is_windows():
        return

    user32 = ctypes.windll.user32
    hwnd = user32.GetParent(window.winfo_id())
    if hwnd == 0:
        hwnd = window.winfo_id()

    IMAGE_ICON = 1
    LR_LOADFROMFILE = 0x0010
    WM_SETICON = 0x0080
    ICON_SMALL = 0
    ICON_BIG = 1

    # Load explicit sizes for titlebar/taskbar contexts.
    hicon_small = user32.LoadImageW(None, icon_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
    hicon_big = user32.LoadImageW(None, icon_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)

    if hicon_small:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
        setattr(window, "_transcriby_hicon_small", hicon_small)
    if hicon_big:
        user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)
        setattr(window, "_transcriby_hicon_big", hicon_big)


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
