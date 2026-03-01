#!/usr/bin/env python3
"""
SlowPlay audio player using mpv (libmpv) for playback.
Exports use soundfile + scipy (no rubberband).
"""

import math
import os
import shutil
import sys

from platform_utils import is_windows

if is_windows():
    # Ensure mpv DLLs can be found by python-mpv on Windows.
    mpv_dir = os.environ.get("SLOWPLAY_MPV_DIR")
    if not mpv_dir:
        mpv_exe = shutil.which("mpv")
        if mpv_exe:
            mpv_dir = os.path.dirname(mpv_exe)
    if mpv_dir and os.path.isdir(mpv_dir):
        os.environ["PATH"] = mpv_dir + os.pathsep + os.environ.get("PATH", "")
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(mpv_dir)
            except OSError:
                pass

import mpv
import numpy as np
import soundfile as sf
from scipy import signal

import gettext
_ = gettext.gettext

# Constants
NANOSEC = 1000000000


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
        # mpv player (audio only)
        self._player = mpv.MPV(ytdl=False, vid="no", audio_display="no")
        self._player.pause = True

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
        if self.loopEnabled and self.startPoint >= 0:
            self.seek_absolute(self.startPoint)
        else:
            self.seek_absolute(0)

    def seek_absolute(self, newPos):
        """Seek to absolute position (newPos in nanoseconds, pipeline time)"""
        if newPos is None:
            return
        song_seconds = self.song_time(newPos)
        if song_seconds is None:
            return
        self._player.command("seek", str(song_seconds), "absolute", "exact")
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
        """Set volume (0.0 to 1.0)"""
        self._volume = max(0.0, min(1.0, volume))
        # mpv volume is 0..100
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

    def __del__(self):
        """Cleanup"""
        try:
            self._player.terminate()
        except Exception:
            pass
