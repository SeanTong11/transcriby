#!/usr/bin/env python3
"""
Transcriby audio player using mpv (libmpv) for playback.
Exports use soundfile + scipy (no rubberband).
"""

import math
import ctypes.util
import os
import shutil
import sys

from platform_utils import is_windows
try:
    from transcriby.debuglog import debug_log
except Exception:
    try:
        from debuglog import debug_log
    except Exception:
        def debug_log(*args, **kwargs):
            return

def _prepend_env_path_var(key: str, value: str):
    """Prepend a path entry to an env var if not already present."""
    if not value:
        return
    current = os.environ.get(key, "")
    parts = [p for p in current.split(os.pathsep) if p]
    if value in parts:
        return
    if current:
        os.environ[key] = value + os.pathsep + current
    else:
        os.environ[key] = value


def _find_posix_libmpv():
    """Best-effort lookup for libmpv on macOS/Linux."""
    env_lib = (
        os.environ.get("MPV_LIBRARY")
        or os.environ.get("TRANSCRIBY_MPV_LIBRARY")
        or os.environ.get("SLOWPLAY_MPV_LIBRARY")
    )
    if env_lib and os.path.isfile(env_lib):
        return env_lib

    candidate_dirs = []

    # Prefer bundled runtime locations first (PyInstaller and app bundle layouts).
    if hasattr(sys, "_MEIPASS"):
        meipass = os.path.abspath(getattr(sys, "_MEIPASS"))
        candidate_dirs.extend(
            [
                meipass,
                os.path.join(meipass, "lib"),
                os.path.join(meipass, "Frameworks"),
                os.path.join(meipass, "MacOS"),
            ]
        )

    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    candidate_dirs.extend(
        [
            exe_dir,
            os.path.join(exe_dir, "lib"),
            os.path.abspath(os.path.join(exe_dir, "..", "Frameworks")),
            os.path.abspath(os.path.join(exe_dir, "..", "MacOS", "lib")),
        ]
    )

    module_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_dirs.extend(
        [
            module_dir,
            os.path.join(module_dir, "lib"),
        ]
    )

    if sys.platform == "darwin":
        lib_names = ["libmpv.dylib", "libmpv.2.dylib"]
        candidate_dirs.extend(
            [
            "/opt/homebrew/opt/mpv/lib",
            "/opt/homebrew/lib",
            "/usr/local/opt/mpv/lib",
            "/usr/local/lib",
            "/opt/local/lib",
            "/usr/lib",
            ]
        )
    else:
        lib_names = ["libmpv.so.2", "libmpv.so.1", "libmpv.so"]
        candidate_dirs.extend(
            [
            "/usr/lib/x86_64-linux-gnu",
            "/usr/lib/aarch64-linux-gnu",
            "/usr/local/lib",
            "/usr/lib64",
            "/usr/lib",
            "/lib/x86_64-linux-gnu",
            "/lib/aarch64-linux-gnu",
            ]
        )

    # Respect user/library search paths when present.
    for env_key in ("DYLD_FALLBACK_LIBRARY_PATH", "LD_LIBRARY_PATH"):
        env_value = os.environ.get(env_key, "")
        if env_value:
            candidate_dirs.extend([p for p in env_value.split(os.pathsep) if p])

    mpv_exe = shutil.which("mpv")
    if mpv_exe:
        mpv_real = os.path.realpath(mpv_exe)
        mpv_bin_dir = os.path.dirname(mpv_real)
        mpv_prefix = os.path.dirname(mpv_bin_dir)
        candidate_dirs.extend(
            [
                os.path.join(mpv_prefix, "lib"),
                os.path.join(mpv_bin_dir, "..", "lib"),
            ]
        )

    seen = set()
    for d in candidate_dirs:
        if not d or d in seen:
            continue
        seen.add(d)
        for name in lib_names:
            path = os.path.abspath(os.path.join(d, name))
            if os.path.isfile(path):
                return path
    return None


def _prepare_posix_mpv_lookup():
    """Make python-mpv able to load libmpv when find_library is unreliable."""
    mpv_lib = _find_posix_libmpv()
    if not mpv_lib:
        return

    lib_dir = os.path.dirname(mpv_lib)
    os.environ.setdefault("MPV_LIBRARY", mpv_lib)
    os.environ.setdefault("TRANSCRIBY_MPV_LIBRARY", mpv_lib)
    os.environ.setdefault("SLOWPLAY_MPV_LIBRARY", mpv_lib)

    if sys.platform == "darwin":
        _prepend_env_path_var("DYLD_FALLBACK_LIBRARY_PATH", lib_dir)
    else:
        _prepend_env_path_var("LD_LIBRARY_PATH", lib_dir)

    original_find_library = ctypes.util.find_library

    def _patched_find_library(name):
        if name == "mpv":
            return mpv_lib
        return original_find_library(name)

    ctypes.util.find_library = _patched_find_library


if is_windows():
    # Ensure mpv DLLs can be found by python-mpv on Windows.
    preferred_dll_order = ["libmpv-2.dll", "mpv-2.dll", "mpv-1.dll", "libmpv.dll", "mpv.dll"]

    def _is_windows_mpv_core_dll(name: str) -> bool:
        lower = name.lower()
        if lower in {"libmpv.dll", "mpv.dll", "libmpv-2.dll", "mpv-2.dll", "mpv-1.dll"}:
            return True
        if lower.startswith("libmpv-") and lower.endswith(".dll"):
            return True
        if lower.startswith("mpv-") and lower.endswith(".dll"):
            return True
        return False

    def _dll_priority(name: str) -> int:
        lower = name.lower()
        if lower in preferred_dll_order:
            # Smaller index = higher priority
            return preferred_dll_order.index(lower)
        # Generic libmpv preferred over generic mpv-*.dll
        if lower.startswith("libmpv-"):
            return 50
        if lower.startswith("mpv-"):
            return 60
        return 100

    def _find_mpv_dll_dir():
        candidates = []

        env_dir = os.environ.get("TRANSCRIBY_MPV_DIR") or os.environ.get("SLOWPLAY_MPV_DIR")
        if env_dir:
            candidates.append(env_dir)

        mpv_exe = shutil.which("mpv")
        if mpv_exe:
            mpv_dir = os.path.dirname(mpv_exe)
            candidates.append(mpv_dir)
            # Common layouts
            candidates.append(os.path.join(mpv_dir, "bin"))
            candidates.append(os.path.join(mpv_dir, "lib"))
            candidates.append(os.path.abspath(os.path.join(mpv_dir, "..", "bin")))
            candidates.append(os.path.abspath(os.path.join(mpv_dir, "..", "lib")))

        # Fallbacks: current working dir and script dir
        candidates.append(os.getcwd())
        candidates.append(os.path.dirname(os.path.abspath(__file__)))

        seen = set()
        for base in candidates:
            if not base or base in seen or not os.path.isdir(base):
                continue
            seen.add(base)
            core_dlls = []
            try:
                for name in os.listdir(base):
                    if _is_windows_mpv_core_dll(name):
                        full = os.path.join(base, name)
                        if os.path.isfile(full):
                            core_dlls.append((name, full))
            except OSError:
                core_dlls = []
            if core_dlls:
                core_dlls.sort(key=lambda item: (_dll_priority(item[0]), item[0].lower()))
                return base, core_dlls[0][1]
        return None, None

    mpv_dir, mpv_dll = _find_mpv_dll_dir()
    if mpv_dir:
        os.environ["PATH"] = mpv_dir + os.pathsep + os.environ.get("PATH", "")
        if mpv_dll:
            os.environ.setdefault("MPV_LIBRARY", mpv_dll)
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(mpv_dir)
            except OSError:
                pass
else:
    _prepare_posix_mpv_lookup()

import mpv
import numpy as np
import soundfile as sf
from scipy import signal

import gettext
_ = gettext.gettext

# Constants
NANOSEC = 1000000000

def get_mpv_runtime_details():
    """Return diagnostic info about libmpv resolution/runtime backend."""
    details = {
        "env_mpv_library": os.environ.get("MPV_LIBRARY", ""),
        "env_transcriby_mpv_library": os.environ.get("TRANSCRIBY_MPV_LIBRARY", ""),
        "env_slowplay_mpv_library": os.environ.get("SLOWPLAY_MPV_LIBRARY", ""),
        "find_library_mpv": "",
        "backend_name": "",
        "backend_realpath": "",
    }

    try:
        found = ctypes.util.find_library("mpv")
        details["find_library_mpv"] = found or ""
    except Exception:
        details["find_library_mpv"] = ""

    try:
        backend = getattr(mpv, "backend", None)
        backend_name = getattr(backend, "_name", "") if backend is not None else ""
        details["backend_name"] = backend_name or ""
        if backend_name and os.path.isabs(backend_name) and os.path.exists(backend_name):
            details["backend_realpath"] = os.path.realpath(backend_name)
    except Exception:
        pass

    return(details)


def _uri_to_path(uri: str) -> str:
    if uri.startswith("file://"):
        path = uri[7:]
        # On Windows, remove leading '/' from paths like '/C:/...'
        if is_windows() and path.startswith("/") and len(path) > 2 and path[2] == ":":
            path = path[1:]
        return path
    return uri


def _split_atempo(factor: float) -> list[float]:
    """Split atempo factor into a chain of 0.5..2.0 values."""
    if factor <= 0:
        return [1.0]
    parts = []
    f = factor
    while f < 0.5:
        parts.append(0.5)
        f /= 0.5
    while f > 2.0:
        parts.append(2.0)
        f /= 2.0
    parts.append(f)
    return parts


class slowPlayer():
    def __init__(self):
        """Initialize the audio player"""
        # mpv player (audio/video)
        self._player = mpv.MPV(
            ytdl=False,
            vid="auto",
            input_vo_keyboard=True,
            input_default_bindings=False,
        )
        debug_log(
            "mpv",
            "initialized",
            input_vo_keyboard=True,
            input_default_bindings=False,
        )
        self._player.pause = True
        self._window_key_binding_names = []

        # Playback parameters
        self._speed = 1.0
        self._pitch_semitones = 0.0
        self._pitch_ratio = 1.0
        self._volume = 1.0
        self._sample_rate = None
        self._media_path = ""

        # Playback state
        self.media = ""
        self.canPlay = False
        self.isPlaying = False
        self.songPosition = 0.0  # Position in seconds
        self.updateInterval = 20  # milliseconds
        self.startPoint = -2  # Loop start in nanoseconds
        self.endPoint = -1  # Loop end in nanoseconds
        self.loopEnabled = False

        # Metadata
        self.title = ""
        self.artist = ""

        # For compatibility
        self.semitones = 0
        self.cents = 0
        self.tempo = 1.0
        self.pitch = 0.0

    def _get_prop(self, name, default=None):
        try:
            return getattr(self._player, name)
        except Exception:
            return default

    def _set_prop(self, name, value):
        try:
            setattr(self._player, name, value)
            return True
        except Exception:
            return False

    def _refresh_audio_params(self) -> bool:
        """Refresh audio params and return True if sample rate is available."""
        sr = None
        if self._media_path and os.path.isfile(self._media_path):
            try:
                info = sf.info(self._media_path)
                sr = info.samplerate
            except Exception:
                sr = None

        if sr is None:
            params = self._get_prop("audio_params")
            if isinstance(params, dict):
                sr = params.get("samplerate") or params.get("sample_rate")

        if sr is not None:
            self._sample_rate = int(sr)
            return True

        return False

    def _apply_pitch_filter(self):
        """Apply pitch shift using mpv audio filters (lavfi)."""
        if abs(self._pitch_semitones) < 1e-6:
            # Clear filters
            self._set_prop("af", "")
            return

        if not self._sample_rate:
            return

        ratio = self._pitch_ratio
        atempo = 1.0 / ratio
        atempo_parts = _split_atempo(atempo)

        filters = [
            f"asetrate={self._sample_rate * ratio}",
            f"aresample={self._sample_rate}",
        ]
        filters.extend([f"atempo={part}" for part in atempo_parts])

        af = "lavfi=[" + ",".join(filters) + "]"
        self._set_prop("af", af)

    def MediaLoad(self, mediafile):
        """Load audio file or URL"""
        self.Pause()

        self.media = mediafile
        self._media_path = _uri_to_path(mediafile)
        self._player.command("loadfile", mediafile)
        self._player.pause = True

        self.canPlay = True
        self.isPlaying = False

        # Update metadata (best effort)
        if self._media_path:
            self.title = os.path.splitext(os.path.basename(self._media_path))[0]
        else:
            self.title = ""
        self.artist = ""

        # Cache sample rate if available
        self._refresh_audio_params()
        self._apply_pitch_filter()

    def Play(self):
        """Start playback"""
        if not self.canPlay:
            return
        self._player.pause = False
        self.isPlaying = True

    def Pause(self):
        """Pause playback"""
        try:
            self._player.pause = True
        except Exception:
            pass
        self.isPlaying = False

    def Rewind(self):
        """Rewind to start or loop point"""
        if not self.canPlay or not self.media:
            return
        if self.loopEnabled and self.startPoint >= 0:
            self.seek_absolute(self.startPoint)
        else:
            self.seek_absolute(0)

    def seek_absolute(self, newPos):
        """Seek to absolute position (newPos in nanoseconds, pipeline time)"""
        if not self.canPlay or not self.media:
            return
        if newPos is None:
            return
        song_seconds = self.song_time(newPos)
        if song_seconds is None:
            return
        try:
            self._player.command("seek", str(song_seconds), "absolute", "exact")
        except Exception:
            return
        self.songPosition = song_seconds

    def seek_relative(self, newPos):
        """Seek relative to current position (newPos in seconds)"""
        cur = self._get_prop("time_pos")
        if cur is None:
            return
        new_time = cur + newPos
        self.seek_absolute(self.pipeline_time(new_time))

    def query_position(self):
        """Get current position in nanoseconds (pipeline time)"""
        pos = self._get_prop("time_pos")
        if pos is None:
            return None
        return int(self.pipeline_time(pos))

    def query_duration(self):
        """Get duration in nanoseconds (pipeline time)"""
        duration = self._get_prop("duration")
        if duration is None:
            return None
        return int(self.pipeline_time(duration))

    def query_percentage(self):
        """Get position as percentage (0-1000000)"""
        pos = self._get_prop("time_pos")
        duration = self._get_prop("duration")
        if pos is None or duration is None or duration == 0:
            return None
        return int(pos / duration * 1000000)

    def update_position(self):
        """Update and return position"""
        return (self.query_duration(), self.query_position())

    def handle_message(self):
        """Handle messages (compatibility)"""
        pause = self._get_prop("pause")
        if pause is not None:
            self.isPlaying = not pause

        # Update metadata if available
        if not self.artist or not self.title:
            meta = self._get_prop("metadata")
            if isinstance(meta, dict):
                self.artist = self.artist or meta.get("artist", "")
                self.title = self.title or meta.get("title", "")

        # Refresh audio params if not set yet
        if not self._sample_rate:
            if self._refresh_audio_params():
                self._apply_pitch_filter()

    def ReadyToPlay(self):
        """Prepare for playback"""
        self.canPlay = True

    def get_speed(self):
        """Get current tempo"""
        return self._speed

    def set_speed(self, speed):
        """Set playback tempo"""
        self._speed = max(0.25, min(4.0, speed))
        self.tempo = self._speed
        self._set_prop("speed", self._speed)

    def set_pitch(self, semitones):
        """Set pitch shift in semitones"""
        self._pitch_semitones = float(semitones)
        self._pitch_ratio = 2 ** (self._pitch_semitones / 12.0)
        self._apply_pitch_filter()

    def set_volume(self, volume):
        """Set volume (0.0 to 2.0)"""
        self._volume = max(0.0, min(2.0, volume))
        # mpv volume supports values > 100
        self._set_prop("volume", self._volume * 100.0)

    def pipeline_time(self, t):
        """Convert song time (seconds) to pipeline time (ns)"""
        if t is None:
            return None
        return t / self._speed * NANOSEC

    def song_time(self, t):
        """Convert pipeline time (ns) to song time (seconds)"""
        if t is None:
            return None
        return t * self._speed / NANOSEC

    def fileSave(self, src, dest, callback=None):
        """Export audio file with current tempo/pitch settings using scipy"""
        try:
            src_path = _uri_to_path(src)
            if not os.path.isfile(src_path):
                raise RuntimeError("Source file not found for export")

            data, sr = sf.read(src_path, dtype=np.float32)

            # Apply speed change
            if self._speed != 1.0:
                orig_len = len(data)
                new_len = int(orig_len / self._speed)
                if len(data.shape) == 1:
                    data = signal.resample(data, new_len)
                else:
                    data = signal.resample(data, new_len, axis=0)

            # Apply pitch change
            if self._pitch_ratio != 1.0:
                pitch_ratio = 1.0 / self._pitch_ratio
                if len(data.shape) == 1:
                    data = signal.resample(data, int(len(data) * pitch_ratio))
                else:
                    data = signal.resample(data, int(data.shape[0] * pitch_ratio), axis=0)

            sf.write(dest, data, sr)

            if callback:
                callback(100)

        except Exception as e:
            print(f"Error saving file: {e}")
            raise

    def register_window_key_binding(self, keydef: str, callback) -> bool:
        """Bind a key on mpv video window and forward it to a callback."""
        if not keydef or not callable(callback):
            return False
        register_fn = getattr(self._player, "register_key_binding", None)
        if not callable(register_fn):
            debug_log("mpv-keybind", "register_unavailable", key=keydef)
            return False

        sanitized = "".join(ch.lower() if ch.isalnum() else "_" for ch in str(keydef))
        binding_name = f"transcriby_{sanitized}_{len(self._window_key_binding_names)}"

        def _wrapped(*args, **kwargs):
            # python-mpv callback signatures vary by version:
            # some pass (state, name), some pass only name/state, some use kwargs.
            raw_state = None
            kw_state = kwargs.get("state")
            if isinstance(kw_state, str):
                raw_state = kw_state.strip().lower()
            elif args and isinstance(args[0], str):
                # In this runtime, callback receives tuples like ("d--", "space", "").
                # Only the first token is the key-event state.
                raw_state = args[0].strip().lower()

            if raw_state:
                if raw_state in {"up", "release"} or raw_state.startswith("u"):
                    debug_log("mpv-keybind", "trigger_rejected", key=keydef, state=raw_state)
                    return
                if not (
                    raw_state in {"down", "press", "repeat"}
                    or raw_state.startswith("d")
                    or raw_state.startswith("p")
                    or raw_state.startswith("r")
                ):
                    debug_log("mpv-keybind", "trigger_rejected", key=keydef, state=raw_state)
                    return

            try:
                debug_log(
                    "mpv-keybind",
                    "trigger_accepted",
                    key=keydef,
                    state=raw_state or "none",
                )
                callback()
            except Exception:
                debug_log("mpv-keybind", "callback_error", key=keydef, state=raw_state or "none")
                return

        attempts = [
            ("key_name_cb_mode_kw", True, lambda: register_fn(str(keydef), binding_name, _wrapped, mode="force")),
            ("key_name_cb_mode_pos", True, lambda: register_fn(str(keydef), binding_name, _wrapped, "force")),
            ("key_name_cb", True, lambda: register_fn(str(keydef), binding_name, _wrapped)),
            ("key_cb_mode_kw", False, lambda: register_fn(str(keydef), _wrapped, mode="force")),
            ("key_cb_mode_pos", False, lambda: register_fn(str(keydef), _wrapped, "force")),
            ("key_cb", False, lambda: register_fn(str(keydef), _wrapped)),
        ]

        for attempt_name, track_name, attempt_call in attempts:
            try:
                attempt_call()
                if track_name:
                    self._window_key_binding_names.append(binding_name)
                debug_log(
                    "mpv-keybind",
                    "register_ok",
                    key=keydef,
                    attempt=attempt_name,
                    name=binding_name if track_name else "none",
                )
                return True
            except TypeError as ex:
                debug_log(
                    "mpv-keybind",
                    "register_type_error",
                    key=keydef,
                    attempt=attempt_name,
                    error=str(ex),
                )
            except Exception as ex:
                debug_log(
                    "mpv-keybind",
                    "register_error",
                    key=keydef,
                    attempt=attempt_name,
                    error=str(ex),
                )

        on_key_press = getattr(self._player, "on_key_press", None)
        if callable(on_key_press):
            try:
                on_key_press(str(keydef))(_wrapped)
                debug_log(
                    "mpv-keybind",
                    "register_ok",
                    key=keydef,
                    attempt="on_key_press",
                    name="none",
                )
                return True
            except Exception as ex:
                debug_log(
                    "mpv-keybind",
                    "register_error",
                    key=keydef,
                    attempt="on_key_press",
                    error=str(ex),
                )

        debug_log("mpv-keybind", "register_failed", key=keydef, name=binding_name)
        return False

    def clear_window_key_bindings(self):
        unregister_fn = getattr(self._player, "unregister_key_binding", None)
        if not callable(unregister_fn):
            debug_log("mpv-keybind", "unregister_unavailable", count=len(self._window_key_binding_names))
            self._window_key_binding_names.clear()
            return
        for binding_name in self._window_key_binding_names:
            try:
                unregister_fn(binding_name)
                debug_log("mpv-keybind", "unregister_ok", name=binding_name)
            except Exception:
                debug_log("mpv-keybind", "unregister_error", name=binding_name)
                pass
        self._window_key_binding_names.clear()

    def __del__(self):
        """Cleanup"""
        self.close()

    def close(self):
        """Explicitly terminate mpv backend."""
        self.clear_window_key_bindings()
        try:
            self._player.terminate()
        except Exception:
            pass
