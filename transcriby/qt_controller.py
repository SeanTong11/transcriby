#!/usr/bin/env python3
"""Playback controller for the PySide6 UI."""

from __future__ import annotations

from dataclasses import dataclass
import os
import urllib.parse

from transcriby.app_constants import (
    APP_BASE_VERSION,
    APP_VERSION,
    BUILD_CHANNEL,
    BUILD_COMMIT,
    BUILD_TAG,
    DEFAULT_CENTS,
    DEFAULT_SEEK_STEP_COARSE_MS,
    DEFAULT_SEEK_STEP_FINE_MS,
    DEFAULT_SEMITONES,
    DEFAULT_SPEED,
    DEFAULT_VOLUME,
    LOOP_MINIMUM_GAP,
    MAX_SEEK_STEP_MS,
    MAX_PITCH_CENTS,
    MAX_PITCH_SEMITONES,
    MAX_SPEED_PERCENT,
    MAX_VOLUME,
    MIN_SEEK_STEP_MS,
    MIN_PITCH_CENTS,
    MIN_PITCH_SEMITONES,
    MIN_SPEED_PERCENT,
    MIN_VOLUME,
    SAVE_DEFAULT_EXTENSION,
    SAVE_EXTENSIONS_FILTER,
    UPDATE_INTERVAL,
)
from transcriby.appsettings import (
    AppSettings,
    CFG_APP_SECTION,
    PBO_DEF_CENTS,
    PBO_DEF_CURRENT_POSITION_SECONDS,
    PBO_DEF_DURATION_SECONDS,
    PBO_DEF_FAVORITES,
    PBO_DEF_LOOP,
    PBO_DEF_METADATA,
    PBO_DEF_SEMITONES,
    PBO_DEF_SPEED,
    PBO_DEF_VOLUME,
)
from transcriby.debuglog import (
    debug_log,
    get_default_debug_log_path,
    set_debug_logging_enabled,
)
from transcriby.player import slowPlayer
from transcriby.platform_utils import is_valid_absolute_path, is_windows, uri_from_path
from transcriby import sessionfile


@dataclass
class PlaybackSnapshot:
    duration_ns: int | None
    position_ns: int | None
    position_seconds: float
    progress_ratio: float
    is_playing: bool
    can_play: bool
    song_metadata: str
    loop_start_seconds: float | None
    loop_end_seconds: float | None
    loop_enabled: bool
    speed: float
    semitones: int
    cents: int
    volume_percent: int
    favorite_count: int
    selected_favorite_index: int | None
    favorites_revision: int


class PlaybackController:
    """UI-agnostic state and playback logic for the Qt frontend."""

    def __init__(self):
        self.settings = AppSettings()
        self.settings.loadSettings()
        self.debug_logging_enabled = False
        self._refresh_debug_logging_settings()

        self.player = slowPlayer()
        self.player.updateInterval = UPDATE_INTERVAL

        self.media = ""
        self.media_uri = ""
        self.media_filename = ""
        self.media_path = ""
        self.song_metadata = ""
        self.session_tby_path = ""

        self.semitones = DEFAULT_SEMITONES
        self.cents = DEFAULT_CENTS
        self.volume_percent = DEFAULT_VOLUME

        self.favorites = []
        self.selected_favorite_index = None
        self.favorite_create_counter = 0
        self.favorites_revision = 0

        self._pending_loop_restore = None
        self._pending_seek_restore = None

        self.loop_restart_delay_enabled = False
        self.loop_restart_delay_seconds = 0.25
        self._refresh_loop_restart_delay_settings()
        self.seek_step_fine_seconds = DEFAULT_SEEK_STEP_FINE_MS / 1000.0
        self.seek_step_coarse_seconds = DEFAULT_SEEK_STEP_COARSE_MS / 1000.0
        self._refresh_seek_step_settings()

        self.reset_values()

    def close(self):
        self.persist_recent_options()
        self.player.close()

    def clear_recent_files(self):
        self.settings.resetSettings(True)

    def get_recent_files(self) -> dict:
        recent = self.settings.getRecentFiles()
        if isinstance(recent, dict):
            return dict(recent)
        return {}

    def remove_recent_file(self, file_key: str):
        if not file_key:
            return
        if self.settings.delRecentFile(file_key):
            self.settings.saveSettings()

    def filename_to_uri(self, filename: str) -> str:
        if is_valid_absolute_path(filename):
            return uri_from_path(filename)
        return filename

    def consume_mpv_exit_request(self) -> bool:
        return bool(self.player.consume_exit_request())

    def has_session_tby_path(self) -> bool:
        return bool(str(self.session_tby_path or "").strip())

    def get_session_tby_path(self) -> str:
        return str(self.session_tby_path or "")

    def _add_recent_tby_entry(self, tby_path: str):
        normalized_tby = os.path.realpath(str(tby_path or "").strip())
        if not normalized_tby:
            return
        self.settings.addRecentFile(
            normalized_tby,
            {
                "EntryType": "tby",
                "Metadata": os.path.basename(normalized_tby),
            },
        )

    def _touch_favorites(self):
        self.favorites_revision += 1

    def _favorite_sort_key(self, favorite: dict) -> tuple[float, int]:
        return (
            float(favorite.get("time_seconds", 0.0)),
            int(favorite.get("created_seq", 0)),
        )

    def _assign_favorite_defaults(self, favorite, fallback_index=0):
        if not isinstance(favorite, dict):
            return None

        try:
            seconds = float(favorite.get("time_seconds"))
        except Exception:
            return None

        if seconds < 0:
            return None

        created_seq = favorite.get("created_seq")
        try:
            created_seq = int(created_seq)
        except Exception:
            created_seq = self.favorite_create_counter
            self.favorite_create_counter += 1

        if created_seq >= self.favorite_create_counter:
            self.favorite_create_counter = created_seq + 1

        return {
            "time_seconds": seconds,
            "created_seq": created_seq if created_seq is not None else fallback_index,
        }

    def _load_favorites(self, raw_favorites):
        loaded = []
        self.favorite_create_counter = 0

        if isinstance(raw_favorites, list):
            for idx, favorite in enumerate(raw_favorites):
                if isinstance(favorite, dict):
                    normalized = self._assign_favorite_defaults(favorite, idx)
                else:
                    normalized = self._assign_favorite_defaults({"time_seconds": favorite}, idx)
                if normalized is not None:
                    loaded.append(normalized)

        loaded.sort(key=self._favorite_sort_key)
        self.favorites = loaded
        self.selected_favorite_index = None
        self._touch_favorites()

    def get_favorites_display(self) -> list[dict]:
        result = []
        for idx, favorite in enumerate(self.favorites):
            seconds = float(favorite.get("time_seconds", 0.0))
            result.append(
                {
                    "index": idx,
                    "time_seconds": seconds,
                    "label": f"{idx + 1}. {seconds:.3f}s",
                }
            )
        return result

    def _current_position_seconds(self) -> float | None:
        cur_pos = self.player.query_position()
        if cur_pos is None or cur_pos < 0:
            return None
        return self.player.song_time(cur_pos)

    def seek_to_seconds(self, seconds: float) -> bool:
        if not self.player.canPlay:
            return False
        self.player.seek_absolute(self.player.pipeline_time(seconds))
        self.persist_recent_options()
        return True

    def select_favorite(self, index: int) -> bool:
        if index < 0 or index >= len(self.favorites):
            return False
        self.selected_favorite_index = index
        self._touch_favorites()
        return True

    def seek_to_favorite(self, index: int) -> bool:
        if not self.select_favorite(index):
            return False
        seconds = self.favorites[index].get("time_seconds")
        return self.seek_to_seconds(seconds)

    def add_favorite(self, seconds: float) -> tuple[bool, str]:
        if seconds is None:
            return False, "Invalid favorite time"

        created_seq = self.favorite_create_counter
        self.favorite_create_counter += 1

        new_favorite = {
            "time_seconds": max(0.0, float(seconds)),
            "created_seq": created_seq,
        }

        self.favorites.append(new_favorite)
        self.favorites.sort(key=self._favorite_sort_key)
        self.selected_favorite_index = self.favorites.index(new_favorite)
        self._touch_favorites()
        self.persist_recent_options()
        return True, f"Favorite #{self.selected_favorite_index + 1} added"

    def add_favorite_at_current(self) -> tuple[bool, str]:
        if not self.player.canPlay:
            return False, "Please open a file..."

        seconds = self._current_position_seconds()
        if seconds is None:
            return False, "Unable to read current position"

        return self.add_favorite(seconds)

    def delete_favorite(self) -> tuple[bool, str]:
        if len(self.favorites) <= 0:
            return False, "No favorites"

        if (
            self.selected_favorite_index is not None
            and self.selected_favorite_index >= 0
            and self.selected_favorite_index < len(self.favorites)
        ):
            index = self.selected_favorite_index
        else:
            index = max(
                range(len(self.favorites)),
                key=lambda i: int(self.favorites[i].get("created_seq", -1)),
            )

        del self.favorites[index]
        if len(self.favorites) <= 0:
            self.selected_favorite_index = None
        else:
            self.selected_favorite_index = min(index, len(self.favorites) - 1)

        self._touch_favorites()
        self.persist_recent_options()
        return True, "Favorite deleted"

    def _jump_favorite_by_direction(self, direction=1) -> tuple[bool, str]:
        if not self.player.canPlay or len(self.favorites) <= 0:
            return False, "No favorites"

        cur_seconds = self._current_position_seconds()
        if cur_seconds is None:
            cur_seconds = 0.0

        indexed_favorites = sorted(
            [(f.get("time_seconds"), idx) for idx, f in enumerate(self.favorites)],
            key=lambda item: item[0],
        )

        target_index = None
        eps = 1e-4
        if direction >= 0:
            for fav_seconds, idx in indexed_favorites:
                if fav_seconds > (cur_seconds + eps):
                    target_index = idx
                    break
            if target_index is None:
                target_index = indexed_favorites[0][1]
        else:
            for fav_seconds, idx in reversed(indexed_favorites):
                if fav_seconds < (cur_seconds - eps):
                    target_index = idx
                    break
            if target_index is None:
                target_index = indexed_favorites[-1][1]

        self.selected_favorite_index = target_index
        self._touch_favorites()
        self.seek_to_seconds(self.favorites[target_index].get("time_seconds"))
        return True, f"Jump to favorite #{target_index + 1}"

    def jump_to_next_favorite(self) -> tuple[bool, str]:
        return self._jump_favorite_by_direction(direction=1)

    def jump_to_previous_favorite(self) -> tuple[bool, str]:
        return self._jump_favorite_by_direction(direction=-1)

    def _normalize_loop_restart_delay(self, value) -> float:
        try:
            delay_seconds = float(value)
        except Exception:
            delay_seconds = 0.25
        return min(10.0, max(0.0, delay_seconds))

    def _refresh_loop_restart_delay_settings(self):
        self.loop_restart_delay_enabled = bool(
            self.settings.getVal(CFG_APP_SECTION, "LoopRestartDelayEnabled", False)
        )
        self.loop_restart_delay_seconds = self._normalize_loop_restart_delay(
            self.settings.getVal(CFG_APP_SECTION, "LoopRestartDelaySeconds", 0.25)
        )

    def get_loop_restart_delay_settings(self) -> tuple[bool, float]:
        self._refresh_loop_restart_delay_settings()
        return bool(self.loop_restart_delay_enabled), float(self.loop_restart_delay_seconds)

    def set_loop_restart_delay_settings(self, enabled: bool, delay_seconds: float) -> tuple[bool, float]:
        normalized_delay = self._normalize_loop_restart_delay(delay_seconds)
        self.settings.setVal(CFG_APP_SECTION, "LoopRestartDelayEnabled", bool(enabled))
        self.settings.setVal(CFG_APP_SECTION, "LoopRestartDelaySeconds", normalized_delay)
        self._refresh_loop_restart_delay_settings()
        return bool(self.loop_restart_delay_enabled), float(self.loop_restart_delay_seconds)

    def _normalize_seek_step_ms(self, value, default_ms: int) -> int:
        try:
            ms_value = int(round(float(value)))
        except Exception:
            ms_value = int(default_ms)
        ms_value = min(MAX_SEEK_STEP_MS, max(MIN_SEEK_STEP_MS, ms_value))
        return int(ms_value)

    def _refresh_seek_step_settings(self):
        fine_ms = self._normalize_seek_step_ms(
            self.settings.getVal(CFG_APP_SECTION, "SeekStepFineMs", DEFAULT_SEEK_STEP_FINE_MS),
            DEFAULT_SEEK_STEP_FINE_MS,
        )
        coarse_ms = self._normalize_seek_step_ms(
            self.settings.getVal(CFG_APP_SECTION, "SeekStepCoarseMs", DEFAULT_SEEK_STEP_COARSE_MS),
            DEFAULT_SEEK_STEP_COARSE_MS,
        )
        if coarse_ms < fine_ms:
            coarse_ms = fine_ms
        self.seek_step_fine_seconds = float(fine_ms) / 1000.0
        self.seek_step_coarse_seconds = float(coarse_ms) / 1000.0

    def get_seek_step_settings_ms(self) -> tuple[int, int]:
        self._refresh_seek_step_settings()
        return (
            int(round(self.seek_step_fine_seconds * 1000.0)),
            int(round(self.seek_step_coarse_seconds * 1000.0)),
        )

    def get_seek_step_settings_seconds(self) -> tuple[float, float]:
        self._refresh_seek_step_settings()
        return float(self.seek_step_fine_seconds), float(self.seek_step_coarse_seconds)

    def set_seek_step_settings_ms(self, fine_ms, coarse_ms) -> tuple[int, int]:
        normalized_fine_ms = self._normalize_seek_step_ms(fine_ms, DEFAULT_SEEK_STEP_FINE_MS)
        normalized_coarse_ms = self._normalize_seek_step_ms(coarse_ms, DEFAULT_SEEK_STEP_COARSE_MS)
        if normalized_coarse_ms < normalized_fine_ms:
            normalized_coarse_ms = normalized_fine_ms
        self.settings.setVal(CFG_APP_SECTION, "SeekStepFineMs", normalized_fine_ms)
        self.settings.setVal(CFG_APP_SECTION, "SeekStepCoarseMs", normalized_coarse_ms)
        self._refresh_seek_step_settings()
        return self.get_seek_step_settings_ms()

    def _refresh_debug_logging_settings(self):
        enabled = bool(self.settings.getVal(CFG_APP_SECTION, "DebugLoggingEnabled", False))
        self.debug_logging_enabled = enabled
        set_debug_logging_enabled(enabled)
        debug_log(
            "settings",
            "debug_logging_refresh",
            path=get_default_debug_log_path(),
            enabled=enabled,
        )

    def get_debug_logging_settings(self) -> tuple[bool, str]:
        self._refresh_debug_logging_settings()
        return bool(self.debug_logging_enabled), get_default_debug_log_path()

    def set_debug_logging_settings(self, enabled: bool) -> tuple[bool, str]:
        self.settings.setVal(CFG_APP_SECTION, "DebugLoggingEnabled", bool(enabled))
        self._refresh_debug_logging_settings()
        debug_log(
            "settings",
            "debug_logging_updated",
            path=get_default_debug_log_path(),
            enabled=bool(self.debug_logging_enabled),
        )
        return bool(self.debug_logging_enabled), get_default_debug_log_path()

    def reset_values(self):
        self.player.startPoint = -2
        self.player.endPoint = -1
        self.player.loopEnabled = False

        self.pause()
        self.player.Rewind()

        self.player.songPosition = 0.0

        self.favorites = []
        self.selected_favorite_index = None
        self.favorite_create_counter = 0
        self._touch_favorites()

        self._pending_loop_restore = None
        self._pending_seek_restore = None

        self.set_speed(DEFAULT_SPEED, persist=False)
        self.set_pitch_components(DEFAULT_SEMITONES, DEFAULT_CENTS, persist=False)
        self.set_volume_percent(DEFAULT_VOLUME, persist=False)

    def load_file(self, filename: str, apply_recent_options: bool = False) -> tuple[bool, str]:
        if not filename:
            return False, "Empty file path"

        candidate = filename
        if not os.path.isfile(candidate):
            candidate = os.path.normpath(candidate)
            if not os.path.isfile(candidate):
                return False, f"Unable to open file: {filename}"

        self.media = os.path.realpath(candidate)
        self.media_filename = os.path.basename(self.media)
        self.media_path = os.path.dirname(self.media)
        self.media_uri = self.filename_to_uri(self.media)
        self.song_metadata = self.media_filename
        self.session_tby_path = ""

        self.settings.setVal(CFG_APP_SECTION, "LastOpenDir", self.media_path)

        self.player.MediaLoad(self.media_uri)
        self.player.update_position()

        if apply_recent_options:
            playback_options = self.settings.getRecentFile(self.media)
            if isinstance(playback_options, dict):
                self.settings.moveToLastPosition(self.media)
                self._apply_playback_options(playback_options)
                return True, ""

        self.settings.bUpdateForbidden = True
        try:
            self.reset_values()
        finally:
            self.settings.bUpdateForbidden = False

        self.settings.moveToLastPosition(self.media)
        self.persist_recent_options()
        return True, ""

    def load_last_played_media(self) -> bool:
        recent = self.settings.getRecentFiles()
        if not isinstance(recent, dict):
            return False
        for key in reversed(list(recent.keys())):
            if str(key).lower().endswith(".tby"):
                continue
            if os.path.isfile(key):
                ok, _msg = self.load_file(key, apply_recent_options=False)
                return ok
        return False

    def load_last_session_or_media(self) -> tuple[bool, str]:
        last_tby = self.settings.getLastSessionTby()
        if isinstance(last_tby, str) and last_tby.strip():
            normalized_tby = os.path.realpath(last_tby)
            if os.path.isfile(normalized_tby):
                ok, message = self.open_tby_session(normalized_tby)
                if ok:
                    return True, message
            else:
                self.settings.setLastSessionTby("")

        if self.load_last_played_media():
            return True, "Loaded last played media"
        return False, ""

    def _build_loop_data(self) -> dict:
        loop_data = {"enabled": bool(self.player.loopEnabled)}
        if self.player.startPoint is not None and self.player.startPoint >= 0:
            loop_data["start_seconds"] = self.player.song_time(self.player.startPoint)
        if self.player.endPoint is not None and self.player.endPoint >= 0:
            loop_data["end_seconds"] = self.player.song_time(self.player.endPoint)
        return loop_data

    def _query_duration_seconds(self) -> float | None:
        duration = self.player.query_duration()
        if duration is None or duration <= 0:
            return None
        return self.player.song_time(duration)

    def _normalize_loop_restore(self, loop_data) -> dict:
        start_seconds = None
        end_seconds = None
        enable_loop = False

        if isinstance(loop_data, dict):
            try:
                start_seconds = float(loop_data.get("start_seconds"))
            except Exception:
                start_seconds = None
            try:
                end_seconds = float(loop_data.get("end_seconds"))
            except Exception:
                end_seconds = None
            enable_loop = bool(loop_data.get("enabled", False))

        if start_seconds is not None and start_seconds < 0:
            start_seconds = 0.0
        if end_seconds is not None and end_seconds < 0:
            end_seconds = 0.0
        if start_seconds is not None and end_seconds is not None and end_seconds < start_seconds:
            start_seconds, end_seconds = end_seconds, start_seconds

        return {
            "start_seconds": start_seconds,
            "end_seconds": end_seconds,
            "enabled": enable_loop,
        }

    def _try_apply_loop_restore(self, loop_data) -> bool:
        normalized = self._normalize_loop_restore(loop_data)
        duration_seconds = self._query_duration_seconds()
        if duration_seconds is None:
            return False

        start_seconds = normalized["start_seconds"]
        end_seconds = normalized["end_seconds"]
        enable_loop = normalized["enabled"]

        if start_seconds is not None:
            start_seconds = max(0.0, min(start_seconds, duration_seconds))
        if end_seconds is not None:
            end_seconds = max(0.0, min(end_seconds, duration_seconds))

        if start_seconds is None:
            start_seconds = 0.0
        if end_seconds is None:
            end_seconds = duration_seconds

        if (end_seconds - start_seconds) < LOOP_MINIMUM_GAP:
            end_seconds = min(duration_seconds, start_seconds + LOOP_MINIMUM_GAP)
            if (end_seconds - start_seconds) < LOOP_MINIMUM_GAP:
                start_seconds = max(0.0, end_seconds - LOOP_MINIMUM_GAP)

        self.player.startPoint = -2
        self.player.endPoint = -1
        self.set_loop_start(self.player.pipeline_time(start_seconds), persist=False)
        self.set_loop_end(self.player.pipeline_time(end_seconds), persist=False)
        self.set_loop_enabled(enable_loop, persist=False)
        return True

    def _try_restore_current_position(self, position_seconds: float | None) -> bool:
        if position_seconds is None:
            return True
        duration_seconds = self._query_duration_seconds()
        if duration_seconds is None:
            return False
        target_seconds = max(0.0, min(float(position_seconds), duration_seconds))
        return self.seek_seconds(target_seconds, persist=False)

    def _apply_playback_options(self, playback_options):
        if not isinstance(playback_options, dict):
            return

        self.settings.bUpdateForbidden = True
        try:
            self.reset_values()

            saved_speed = playback_options.get(PBO_DEF_SPEED, DEFAULT_SPEED)
            try:
                saved_speed = float(saved_speed)
                # Backward compatibility: old config used percentages like 100.
                if saved_speed > 10:
                    saved_speed = saved_speed * 0.01
            except Exception:
                saved_speed = DEFAULT_SPEED
            self.set_speed(saved_speed, persist=False)

            saved_semitones = playback_options.get(PBO_DEF_SEMITONES, DEFAULT_SEMITONES)
            saved_cents = playback_options.get(PBO_DEF_CENTS, DEFAULT_CENTS)
            self.set_pitch_components(saved_semitones, saved_cents, persist=False)

            saved_volume = playback_options.get(PBO_DEF_VOLUME, DEFAULT_VOLUME)
            self.set_volume_percent(saved_volume, persist=False)
        finally:
            self.settings.bUpdateForbidden = False

        self._load_favorites(playback_options.get(PBO_DEF_FAVORITES, []))

        if self._try_apply_loop_restore(playback_options.get(PBO_DEF_LOOP, {})):
            self._pending_loop_restore = None
        else:
            self._pending_loop_restore = self._normalize_loop_restore(playback_options.get(PBO_DEF_LOOP, {}))

        try:
            current_position_seconds = float(playback_options.get(PBO_DEF_CURRENT_POSITION_SECONDS))
        except Exception:
            current_position_seconds = None

        if self._try_restore_current_position(current_position_seconds):
            self._pending_seek_restore = None
        else:
            self._pending_seek_restore = current_position_seconds

        self.persist_recent_options()

    def _apply_pending_session_restore(self):
        if self._pending_loop_restore is not None:
            if self._try_apply_loop_restore(self._pending_loop_restore):
                self._pending_loop_restore = None
        if self._pending_seek_restore is not None:
            if self._try_restore_current_position(self._pending_seek_restore):
                self._pending_seek_restore = None

    def _build_playback_options(self) -> dict:
        duration_seconds = None
        current_position_seconds = None
        duration = self.player.query_duration()
        position = self.player.query_position()
        if duration is not None and duration > 0:
            duration_seconds = self.player.song_time(duration)
        if position is not None and position >= 0:
            current_position_seconds = self.player.song_time(position)

        return {
            PBO_DEF_METADATA: self.song_metadata,
            PBO_DEF_SPEED: self.player.tempo,
            PBO_DEF_SEMITONES: self.semitones,
            PBO_DEF_CENTS: self.cents,
            PBO_DEF_VOLUME: self.volume_percent,
            PBO_DEF_DURATION_SECONDS: duration_seconds,
            PBO_DEF_CURRENT_POSITION_SECONDS: current_position_seconds,
            PBO_DEF_LOOP: self._build_loop_data(),
            PBO_DEF_FAVORITES: [
                {
                    "time_seconds": f.get("time_seconds"),
                    "created_seq": f.get("created_seq"),
                }
                for f in self.favorites
            ],
        }

    def persist_recent_options(self):
        if not self.media:
            return
        self.settings.addRecentFile(self.media, self._build_playback_options())

    def has_valid_loop_range(self) -> bool:
        return (
            self.player.loopEnabled
            and self.player.startPoint is not None
            and self.player.endPoint is not None
            and self.player.startPoint >= 0
            and self.player.endPoint > self.player.startPoint
        )

    def set_loop_enabled(self, enabled: bool, persist: bool = True):
        self.player.loopEnabled = bool(enabled)
        if persist:
            self.persist_recent_options()

    def set_loop_start(self, loop_point_ns: int | float, persist: bool = True) -> bool:
        if loop_point_ns is None:
            return False
        if self.player.endPoint > 0:
            min_gap_ns = self.player.pipeline_time(LOOP_MINIMUM_GAP)
            if loop_point_ns >= (self.player.endPoint - min_gap_ns):
                return False
        self.player.startPoint = int(loop_point_ns)
        if persist:
            self.persist_recent_options()
        return True

    def set_loop_end(self, loop_point_ns: int | float, persist: bool = True) -> bool:
        if loop_point_ns is None:
            return False
        if self.player.startPoint >= 0:
            min_gap_ns = self.player.pipeline_time(LOOP_MINIMUM_GAP)
            if loop_point_ns <= (self.player.startPoint + min_gap_ns):
                return False

        duration = self.player.query_duration()
        if duration:
            max_endpoint = duration - self.player.pipeline_time(LOOP_MINIMUM_GAP)
            if loop_point_ns > max_endpoint:
                loop_point_ns = max_endpoint

        self.player.endPoint = int(loop_point_ns)
        if persist:
            self.persist_recent_options()
        return True

    def set_loop_start_relaxed(self, loop_point_ns: int | float, persist: bool = True) -> tuple[bool, bool]:
        """Set loop start and reset B when needed to keep a valid order.

        Returns:
            (success, boundary_reset)
        """
        if loop_point_ns is None:
            return False, False

        if self.set_loop_start(loop_point_ns, persist=False):
            if persist:
                self.persist_recent_options()
            return True, False

        # If A crosses B, clear B and retry.
        self.player.endPoint = -1
        if self.set_loop_start(loop_point_ns, persist=False):
            if persist:
                self.persist_recent_options()
            return True, True
        return False, False

    def set_loop_end_relaxed(self, loop_point_ns: int | float, persist: bool = True) -> tuple[bool, bool]:
        """Set loop end and reset A when needed to keep a valid order.

        Returns:
            (success, boundary_reset)
        """
        if loop_point_ns is None:
            return False, False

        if self.set_loop_end(loop_point_ns, persist=False):
            if persist:
                self.persist_recent_options()
            return True, False

        # If B crosses A, clear A and retry.
        self.player.startPoint = -2
        if self.set_loop_end(loop_point_ns, persist=False):
            if persist:
                self.persist_recent_options()
            return True, True
        return False, False

    def move_loop_start_ms(self, shift_ms: int | float) -> tuple[bool, str]:
        if not self.player.canPlay:
            return False, "Please open a file..."

        try:
            shift_seconds = float(shift_ms) / 1000.0
        except Exception:
            return False, "Invalid loop start shift"

        current_point = self.player.startPoint if (self.player.startPoint is not None and self.player.startPoint >= 0) else 0
        new_point = int(current_point + self.player.pipeline_time(shift_seconds))
        if new_point < 0:
            new_point = 0

        if not self.set_loop_start(new_point):
            return False, "Loop start must be before B"
        return True, "Loop start adjusted"

    def move_loop_end_ms(self, shift_ms: int | float) -> tuple[bool, str]:
        if not self.player.canPlay:
            return False, "Please open a file..."

        try:
            shift_seconds = float(shift_ms) / 1000.0
        except Exception:
            return False, "Invalid loop end shift"

        duration = self.player.query_duration()
        if duration is None or duration <= 0:
            return False, "Unable to read media duration"

        current_point = self.player.endPoint if (self.player.endPoint is not None and self.player.endPoint > 0) else int(duration)
        new_point = int(current_point + self.player.pipeline_time(shift_seconds))
        if new_point < 0:
            new_point = 0

        if not self.set_loop_end(new_point):
            return False, "Loop end must be after A"
        return True, "Loop end adjusted"

    def apply_loop_range_seconds(self, start_seconds: float, end_seconds: float) -> bool:
        if not self.player.canPlay:
            return False
        if start_seconds is None or end_seconds is None:
            return False

        lo = min(start_seconds, end_seconds)
        hi = max(start_seconds, end_seconds)

        duration = self.player.query_duration()
        if duration is None or duration <= 0:
            return False
        duration_seconds = self.player.song_time(duration)
        if duration_seconds is None or duration_seconds <= 0:
            return False

        lo = max(0.0, min(lo, duration_seconds))
        hi = max(0.0, min(hi, duration_seconds))
        if (hi - lo) < LOOP_MINIMUM_GAP:
            hi = min(duration_seconds, lo + LOOP_MINIMUM_GAP)
            if (hi - lo) < LOOP_MINIMUM_GAP:
                lo = max(0.0, hi - LOOP_MINIMUM_GAP)
        if (hi - lo) <= 0:
            return False

        self.player.startPoint = -2
        self.player.endPoint = -1
        ok_start = self.set_loop_start(self.player.pipeline_time(lo), persist=False)
        ok_end = self.set_loop_end(self.player.pipeline_time(hi), persist=False)
        if ok_start and ok_end:
            self.persist_recent_options()
            return True
        return False

    def rewind(self):
        self.player.Rewind()

    def play(self):
        if not self.player.loopEnabled:
            duration = self.player.query_duration()
            position = self.player.query_position()
            if (
                duration is not None
                and position is not None
                and duration > 0
                and position >= duration
            ):
                self.player.seek_absolute(0)
        self.player.Play()

    def pause(self):
        self.player.Pause()

    def toggle_play(self):
        if not self.player.canPlay:
            return False
        if self.player.isPlaying:
            self.pause()
        else:
            self.play()
        return True

    def stop_playing(self):
        if not self.player.canPlay:
            return
        self.pause()
        self.player.Rewind()

    def stop_at_end(self):
        if not self.player.canPlay:
            return
        self.pause()
        duration = self.player.query_duration()
        if duration is not None and duration > 0:
            self.player.seek_absolute(duration)

    def restart_loop_from_a(self) -> int:
        """Restart loop from A.

        Returns:
            -1: no media loaded
            -2: no valid loop range, so play/pause was toggled
            0: restarted immediately
            >0: delayed restart in milliseconds
        """
        if not self.player.canPlay:
            return -1

        if not self.has_valid_loop_range():
            self.toggle_play()
            return -2

        self._refresh_loop_restart_delay_settings()
        if self.loop_restart_delay_enabled and self.loop_restart_delay_seconds > 0:
            delay_ms = int(round(self.loop_restart_delay_seconds * 1000))
            self.player.seek_absolute(self.player.startPoint)
            self.pause()
            return delay_ms

        self.player.seek_absolute(self.player.startPoint)
        self.play()
        return 0

    def seek_fraction(self, fraction: float) -> bool:
        duration, _position = self.player.update_position()
        if duration is None or duration <= 0:
            return False
        fraction = min(1.0, max(0.0, float(fraction)))
        self.player.seek_absolute(fraction * duration)
        self.persist_recent_options()
        return True

    def seek_relative(self, seconds: float) -> bool:
        if not self.player.canPlay:
            return False
        self.player.seek_relative(float(seconds))
        self.persist_recent_options()
        return True

    def seek_seconds(self, seconds: float, persist: bool = True) -> bool:
        if not self.player.canPlay:
            return False
        self.player.seek_absolute(self.player.pipeline_time(seconds))
        if persist:
            self.persist_recent_options()
        return True

    def set_speed(self, value: float, persist: bool = True) -> float:
        speed_value = round(float(value), 1)
        if speed_value < MIN_SPEED_PERCENT:
            speed_value = MIN_SPEED_PERCENT
        elif speed_value > MAX_SPEED_PERCENT:
            speed_value = MAX_SPEED_PERCENT

        new_tempo = speed_value
        old_tempo = self.player.tempo
        if abs(new_tempo - old_tempo) < 1e-9:
            return new_tempo

        self.player.tempo = new_tempo
        self.player.set_speed(new_tempo)

        if persist:
            self.persist_recent_options()
        return new_tempo

    def set_pitch_components(self, semitones, cents, persist: bool = True):
        try:
            st_value = int(semitones)
        except Exception:
            st_value = DEFAULT_SEMITONES
        try:
            cents_value = int(cents)
        except Exception:
            cents_value = DEFAULT_CENTS

        st_value = min(MAX_PITCH_SEMITONES, max(MIN_PITCH_SEMITONES, st_value))
        cents_value = min(MAX_PITCH_CENTS, max(MIN_PITCH_CENTS, cents_value))

        self.semitones = st_value
        self.cents = cents_value
        self.player.semitones = st_value
        self.player.cents = cents_value
        self.player.pitch = st_value + (cents_value * 0.01)
        self.player.set_pitch(self.player.pitch)

        if persist:
            self.persist_recent_options()

    def set_volume_percent(self, value, persist: bool = True) -> int:
        try:
            volume_value = int(value)
        except Exception:
            volume_value = DEFAULT_VOLUME

        volume_value = min(MAX_VOLUME, max(MIN_VOLUME, volume_value))
        self.volume_percent = volume_value
        self.player.volume = volume_value * 0.01
        self.player.set_volume(self.player.volume)

        if persist:
            self.persist_recent_options()
        return volume_value

    def _build_tby_data(self) -> dict:
        session_media = {
            "path": self.media,
            "metadata": self.song_metadata,
        }
        session_build_info = {
            "app_version": APP_VERSION,
            "app_base_version": APP_BASE_VERSION,
            "build_channel": BUILD_CHANNEL,
            "build_tag": BUILD_TAG,
            "build_commit": BUILD_COMMIT,
        }
        return {
            "media": session_media,
            "playback_options": self._build_playback_options(),
            "build_info": session_build_info,
        }

    def _normalize_tby_export_filename(self, filename: str) -> str:
        out = str(filename).strip()
        if out == "":
            return ""

        if out.lower().endswith(".tby"):
            return out

        stem, ext = os.path.splitext(out)
        if ext:
            out = stem
        return out + ".tby"

    def _resolve_session_media_path(self, raw_media_path: str, tby_file: str) -> str:
        media_path = str(raw_media_path or "").strip()
        if media_path == "":
            return ""

        if media_path.startswith("file://"):
            parsed = urllib.parse.urlparse(media_path)
            if parsed.scheme == "file":
                parsed_path = urllib.parse.unquote(parsed.path or "")
                if is_windows() and len(parsed_path) > 2 and parsed_path[0] == "/" and parsed_path[2] == ":":
                    parsed_path = parsed_path[1:]
                media_path = parsed_path

        if not os.path.isabs(media_path):
            media_path = os.path.join(os.path.dirname(tby_file), media_path)

        return os.path.realpath(media_path)

    def open_tby_session(self, tby_file: str) -> tuple[bool, str]:
        normalized_tby = os.path.realpath(tby_file)
        try:
            session_data = sessionfile.load_tby(normalized_tby)
        except Exception as ex:
            return False, f"Unable to open .tby file: {ex}"

        media_data = session_data.get("media", {})
        playback_options = session_data.get("playback_options", {})
        media_path_raw = ""
        if isinstance(media_data, dict):
            media_path_raw = media_data.get("path", "")

        if not media_path_raw:
            return False, "Invalid .tby file: missing media path"

        media_path = self._resolve_session_media_path(media_path_raw, normalized_tby)
        if not os.path.isfile(media_path):
            return False, f"Unable to open file: {media_path}"

        ok, message = self.load_file(media_path, apply_recent_options=False)
        if not ok:
            return False, message

        self._apply_playback_options(playback_options)
        self.settings.setVal(CFG_APP_SECTION, "LastOpenDir", os.path.dirname(media_path))
        self.session_tby_path = normalized_tby
        self.settings.setLastSessionTby(normalized_tby)
        self._add_recent_tby_entry(normalized_tby)

        status = "Loaded .tby session"
        build_info = session_data.get("build_info", {})
        if isinstance(build_info, dict):
            source_version = str(build_info.get("app_version", "")).strip()
            if source_version != "":
                status = f"{status} ({source_version})"
        return True, status

    def save_tby_session(self) -> tuple[bool, str, str]:
        if not self.player.canPlay:
            return False, "Please open a file...", ""
        current_path = str(self.session_tby_path or "").strip()
        if not current_path:
            return False, "No session file path. Use Save Session As...", ""
        return self.save_tby_session_as(current_path)

    def save_tby_session_as(self, filename: str) -> tuple[bool, str, str]:
        if not self.player.canPlay:
            return False, "Please open a file...", ""

        out_file = self._normalize_tby_export_filename(filename)
        if out_file == "":
            return False, "Invalid output filename", ""

        try:
            sessionfile.save_tby(out_file, self._build_tby_data())
        except Exception as ex:
            return False, f"Unable to save .tby file: {ex}", ""

        saved_realpath = os.path.realpath(out_file)
        self.session_tby_path = saved_realpath
        self.settings.setVal(CFG_APP_SECTION, "LastSaveDir", os.path.dirname(out_file))
        self.settings.setLastSessionTby(saved_realpath)
        self._add_recent_tby_entry(saved_realpath)
        return True, f"Saved .tby: {out_file}", out_file

    def export_tby_session(self, filename: str) -> tuple[bool, str, str]:
        # Backward-compatible wrapper for older call sites.
        return self.save_tby_session_as(filename)

    def normalize_audio_export_filename(self, filename: str) -> str:
        out = str(filename).strip()
        if out == "":
            return ""

        ext = os.path.splitext(out)[1].lower().lstrip(".")
        if ext not in SAVE_EXTENSIONS_FILTER:
            out = out + "." + SAVE_DEFAULT_EXTENSION
        return out

    def export_audio_file(self, filename: str) -> tuple[bool, str, str]:
        if not self.player.canPlay:
            return False, "Please open a file...", ""

        out_file = self.normalize_audio_export_filename(filename)
        if out_file == "":
            return False, "Invalid output filename", ""

        out_dir = os.path.dirname(out_file)
        if out_dir and not os.path.isdir(out_dir):
            return False, f"Unable to save file: {out_file}", ""

        self.pause()

        try:
            self.player.fileSave(self.media, out_file)
        except Exception as ex:
            return False, f"Failed to export file: {ex}", ""

        self.settings.setVal(CFG_APP_SECTION, "LastSaveDir", os.path.dirname(out_file))
        return True, f"Saved file: {out_file}", out_file

    def tick(self) -> PlaybackSnapshot:
        self.player.handle_message()
        duration, position = self.player.update_position()

        if not self.player.loopEnabled:
            if (
                self.player.isPlaying
                and duration is not None
                and position is not None
                and duration > 0
                and position >= duration
            ):
                self.stop_at_end()
                duration, position = self.player.update_position()
        else:
            if not self.has_valid_loop_range():
                self.set_loop_enabled(False, persist=False)
            elif position is not None and (
                position < self.player.startPoint or position >= self.player.endPoint
            ):
                self.player.seek_absolute(self.player.startPoint)
                duration, position = self.player.update_position()

        if self.player.endPoint is not None and self.player.endPoint <= 0:
            if duration is not None and duration > 0:
                self.set_loop_end(duration, persist=False)
        if self.player.startPoint is not None and self.player.startPoint < 0:
            self.set_loop_start(0, persist=False)

        if self.player.artist and self.player.title:
            new_metadata = f"{self.player.artist} - {self.player.title}"
            if new_metadata != self.song_metadata:
                self.song_metadata = new_metadata
                self.persist_recent_options()

        self._apply_pending_session_restore()

        position_ns = self.player.query_position()
        duration_ns = self.player.query_duration()
        position_seconds = 0.0
        if position_ns is not None and position_ns >= 0:
            converted = self.player.song_time(position_ns)
            if converted is not None:
                position_seconds = max(0.0, converted)
        self.player.songPosition = position_seconds

        progress_ratio = 0.0
        percentage = self.player.query_percentage()
        if percentage is not None and percentage >= 0:
            progress_ratio = max(0.0, min(1.0, percentage / 1000000))

        loop_start_seconds = None
        loop_end_seconds = None
        if self.player.startPoint is not None and self.player.startPoint >= 0:
            loop_start_seconds = self.player.song_time(self.player.startPoint)
        if self.player.endPoint is not None and self.player.endPoint >= 0:
            loop_end_seconds = self.player.song_time(self.player.endPoint)

        return PlaybackSnapshot(
            duration_ns=duration_ns,
            position_ns=position_ns,
            position_seconds=position_seconds,
            progress_ratio=progress_ratio,
            is_playing=bool(self.player.isPlaying),
            can_play=bool(self.player.canPlay),
            song_metadata=self.song_metadata,
            loop_start_seconds=loop_start_seconds,
            loop_end_seconds=loop_end_seconds,
            loop_enabled=bool(self.player.loopEnabled),
            speed=float(self.player.tempo),
            semitones=int(self.semitones),
            cents=int(self.cents),
            volume_percent=int(self.volume_percent),
            favorite_count=len(self.favorites),
            selected_favorite_index=self.selected_favorite_index,
            favorites_revision=self.favorites_revision,
        )
