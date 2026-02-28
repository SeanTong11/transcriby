#!/usr/bin/env python3
"""
Platform abstraction module for SlowPlay
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
    """Check if running on Windows Subsystem for Linux (WSL)"""
    if not is_linux():
        return False
    # Check for WSL-specific indicators
    try:
        with open('/proc/version', 'r') as f:
            version_info = f.read().lower()
            return 'microsoft' in version_info or 'wsl' in version_info
    except:
        pass
    # Also check environment variable
    return 'WSL_DISTRO_NAME' in os.environ or 'WSL_INTEROP' in os.environ


def get_config_dir() -> str:
    """Get the appropriate config directory for the current platform"""
    if is_windows():
        # Windows: %APPDATA%\SlowPlay
        appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
        return os.path.join(appdata, "SlowPlay")
    else:
        # Linux: ~/.config/slowplay
        return os.path.join(os.path.expanduser("~"), ".config", "slowplay")


def get_cache_dir() -> str:
    """Get the appropriate cache/temp directory for the current platform"""
    if is_windows():
        # Windows: %LOCALAPPDATA%\Temp\SlowPlay or %TEMP%\SlowPlay
        temp_dir = os.environ.get("TEMP", os.path.expanduser("~"))
        return os.path.join(temp_dir, "SlowPlay")
    else:
        # Linux: /tmp or TMPDIR
        return os.path.join(tempfile.gettempdir(), "slowplay")


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
