#!/usr/bin/env python3

import os
import subprocess
import threading
import tkinter as tk

import customtkinter as ctk
import numpy as np
import soundfile as sf

WAVE_BG_COLOR = "#121B25"
WAVE_LINE_COLOR = "#5BD6C2"
LOOP_FILL_COLOR = "#1D5A5A"
LOOP_MARKER_COLOR = "#8AF5E7"
PLAYHEAD_COLOR = "#F8A24D"
SELECT_FILL_COLOR = "#234B67"
SELECT_MARKER_COLOR = "#79C2FF"
DEFAULT_MARKER_COLOR = "#FFD166"
MARKER_LABEL_FONT = ("TkDefaultFont", 13, "bold")


class WaveformWidget(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_seek=None,
        on_loop_select=None,
        on_context_request=None,
        height=120,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.on_seek = on_seek
        self.on_loop_select = on_loop_select
        self.on_context_request = on_context_request
        self.height = height

        self._load_token = 0
        self._envelope = None
        self._duration = None
        self._playhead = 0.0
        self._loop_start = None
        self._loop_end = None
        self._select_start = None
        self._select_end = None
        self._select_anchor = None
        self._markers = []

        self.canvas = tk.Canvas(self, height=self.height, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<ButtonPress-3>", self._on_right_press)
        self.canvas.bind("<B3-Motion>", self._on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_release)

        self._loop_rect_id = None
        self._loop_a_id = None
        self._loop_b_id = None
        self._playhead_id = None
        self._select_rect_id = None
        self._select_a_id = None
        self._select_b_id = None
        self._marker_ids = []

    def clear(self):
        self._load_token += 1
        self._envelope = None
        self._duration = None
        self._playhead = 0.0
        self._loop_start = None
        self._loop_end = None
        self._select_start = None
        self._select_end = None
        self._select_anchor = None
        self._markers = []
        self.canvas.delete("all")
        self._loop_rect_id = None
        self._loop_a_id = None
        self._loop_b_id = None
        self._playhead_id = None
        self._select_rect_id = None
        self._select_a_id = None
        self._select_b_id = None
        self._marker_ids = []

    def set_media(self, media_path):
        self.clear()
        if not media_path or not os.path.isfile(media_path):
            return

        self._load_token += 1
        token = self._load_token
        worker = threading.Thread(target=self._build_envelope_worker, args=(media_path, token), daemon=True)
        worker.start()

    def set_duration(self, duration_seconds):
        self._duration = duration_seconds
        self._draw_overlays()

    def set_playhead(self, position_seconds):
        self._playhead = max(0.0, position_seconds if position_seconds is not None else 0.0)
        self._draw_overlays()

    def set_loop(self, start_seconds, end_seconds):
        self._loop_start = start_seconds
        self._loop_end = end_seconds
        self._draw_overlays()

    def set_markers(self, markers):
        if isinstance(markers, list):
            self._markers = markers
        else:
            self._markers = []
        self._draw_overlays()

    def _on_resize(self, _event):
        self._redraw_waveform()

    def _on_click(self, event):
        if self._duration is None or self._duration <= 0:
            return
        target_seconds = self._x_to_seconds(event.x)
        self.set_playhead(target_seconds)
        if self.on_seek:
            self.on_seek(target_seconds)

    def _on_right_press(self, event):
        if self._duration is None or self._duration <= 0:
            return
        self._select_anchor = self._x_to_seconds(event.x)
        self._select_start = self._select_anchor
        self._select_end = self._select_anchor
        self._draw_overlays()

    def _on_right_drag(self, event):
        if self._select_anchor is None:
            return
        self._select_end = self._x_to_seconds(event.x)
        self._draw_overlays()

    def _on_right_release(self, event):
        if self._select_anchor is None:
            return
        end_seconds = self._x_to_seconds(event.x)
        start_seconds = min(self._select_anchor, end_seconds)
        stop_seconds = max(self._select_anchor, end_seconds)
        self.clear_selection_preview()

        if stop_seconds - start_seconds < 0.01:
            if self.on_context_request:
                self.on_context_request(end_seconds, event.x_root, event.y_root)
            return
        if self.on_loop_select:
            self.on_loop_select(start_seconds, stop_seconds)

    def _x_to_seconds(self, x):
        if self._duration is None or self._duration <= 0:
            return 0.0
        width = max(self.canvas.winfo_width(), 1)
        return max(0.0, min(self._duration, (x / width) * self._duration))

    def set_selection_preview(self, start_seconds, end_seconds):
        self._select_anchor = start_seconds
        self._select_start = start_seconds
        self._select_end = end_seconds
        self._draw_overlays()

    def clear_selection_preview(self):
        self._select_anchor = None
        self._select_start = None
        self._select_end = None
        self._draw_overlays()

    def _build_envelope_worker(self, media_path, token):
        try:
            data, _sr = sf.read(media_path, dtype="float32", always_2d=True)
            if data.size == 0:
                envelope = None
            else:
                mono = np.mean(np.abs(data), axis=1)
                envelope = self._build_envelope(mono)
        except Exception:
            envelope = None

        if envelope is None:
            mono = self._decode_with_ffmpeg(media_path)
            if mono is not None:
                envelope = self._build_envelope(mono)

        self.after(0, self._apply_envelope, token, envelope)

    def _decode_with_ffmpeg(self, media_path):
        cmd = [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            media_path,
            "-vn",
            "-ac",
            "1",
            "-ar",
            "12000",
            "-f",
            "f32le",
            "-acodec",
            "pcm_f32le",
            "pipe:1",
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        except Exception:
            return None

        if result.returncode != 0 or not result.stdout:
            return None

        mono = np.frombuffer(result.stdout, dtype=np.float32)
        if mono.size == 0:
            return None
        return np.abs(mono)

    def _build_envelope(self, mono):
        if mono is None or len(mono) == 0:
            return None
        max_points = 5000
        if len(mono) > max_points:
            block_size = int(np.ceil(len(mono) / max_points))
            pad = (-len(mono)) % block_size
            if pad:
                mono = np.pad(mono, (0, pad), mode="constant")
            mono = mono.reshape(-1, block_size).max(axis=1)
        max_value = float(np.max(mono)) if mono.size else 0.0
        return (mono / max_value) if max_value > 0 else mono

    def _apply_envelope(self, token, envelope):
        if token != self._load_token:
            return
        self._envelope = envelope
        self._redraw_waveform()

    def _redraw_waveform(self):
        self.canvas.delete("all")
        self._loop_rect_id = None
        self._loop_a_id = None
        self._loop_b_id = None
        self._playhead_id = None
        self._select_rect_id = None
        self._select_a_id = None
        self._select_b_id = None
        self._marker_ids = []

        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)

        self.canvas.create_rectangle(0, 0, width, height, fill=WAVE_BG_COLOR, outline="")

        if self._envelope is None or len(self._envelope) == 0:
            self._draw_overlays()
            return

        center_y = height / 2
        amplitude = max(1, int(height * 0.45))
        n = len(self._envelope)
        for x in range(width):
            idx = int((x / max(width - 1, 1)) * (n - 1))
            amp = float(self._envelope[idx])
            y_top = center_y - amp * amplitude
            y_bot = center_y + amp * amplitude
            self.canvas.create_line(x, y_top, x, y_bot, fill=WAVE_LINE_COLOR)

        self._draw_overlays()

    def _seconds_to_x(self, seconds):
        if self._duration is None or self._duration <= 0 or seconds is None:
            return None
        width = max(self.canvas.winfo_width(), 1)
        ratio = max(0.0, min(1.0, seconds / self._duration))
        return ratio * width

    def _draw_overlays(self):
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)

        a_x = self._seconds_to_x(self._loop_start)
        b_x = self._seconds_to_x(self._loop_end)
        if a_x is not None and b_x is not None and b_x > a_x:
            if self._loop_rect_id is None:
                self._loop_rect_id = self.canvas.create_rectangle(
                    a_x, 0, b_x, height, fill=LOOP_FILL_COLOR, outline="", stipple="gray50"
                )
                self._loop_a_id = self.canvas.create_line(a_x, 0, a_x, height, fill=LOOP_MARKER_COLOR, width=2)
                self._loop_b_id = self.canvas.create_line(b_x, 0, b_x, height, fill=LOOP_MARKER_COLOR, width=2)
            else:
                self.canvas.coords(self._loop_rect_id, a_x, 0, b_x, height)
                self.canvas.coords(self._loop_a_id, a_x, 0, a_x, height)
                self.canvas.coords(self._loop_b_id, b_x, 0, b_x, height)
        elif self._loop_rect_id is not None:
            self.canvas.delete(self._loop_rect_id)
            self.canvas.delete(self._loop_a_id)
            self.canvas.delete(self._loop_b_id)
            self._loop_rect_id = None
            self._loop_a_id = None
            self._loop_b_id = None

        s_a_x = self._seconds_to_x(self._select_start)
        s_b_x = self._seconds_to_x(self._select_end)
        if s_a_x is not None and s_b_x is not None and abs(s_b_x - s_a_x) > 1:
            x1, x2 = (s_a_x, s_b_x) if s_a_x <= s_b_x else (s_b_x, s_a_x)
            if self._select_rect_id is None:
                self._select_rect_id = self.canvas.create_rectangle(
                    x1, 0, x2, height, fill=SELECT_FILL_COLOR, outline="", stipple="gray25"
                )
                self._select_a_id = self.canvas.create_line(x1, 0, x1, height, fill=SELECT_MARKER_COLOR, width=2)
                self._select_b_id = self.canvas.create_line(x2, 0, x2, height, fill=SELECT_MARKER_COLOR, width=2)
            else:
                self.canvas.coords(self._select_rect_id, x1, 0, x2, height)
                self.canvas.coords(self._select_a_id, x1, 0, x1, height)
                self.canvas.coords(self._select_b_id, x2, 0, x2, height)
        elif self._select_rect_id is not None:
            self.canvas.delete(self._select_rect_id)
            self.canvas.delete(self._select_a_id)
            self.canvas.delete(self._select_b_id)
            self._select_rect_id = None
            self._select_a_id = None
            self._select_b_id = None

        for marker_id in self._marker_ids:
            self.canvas.delete(marker_id)
        self._marker_ids = []
        for marker in self._markers:
            if not isinstance(marker, dict):
                continue
            marker_seconds = marker.get("time_seconds")
            marker_x = self._seconds_to_x(marker_seconds)
            if marker_x is None:
                continue
            marker_color = marker.get("color", DEFAULT_MARKER_COLOR)
            marker_label = str(marker.get("label", "")).strip()
            marker_line_id = self.canvas.create_line(
                marker_x,
                0,
                marker_x,
                height,
                fill=marker_color,
                width=2,
            )
            self._marker_ids.append(marker_line_id)
            if marker_label:
                marker_text_id = self.canvas.create_text(
                    marker_x + 3,
                    10,
                    text=marker_label,
                    fill=marker_color,
                    anchor="nw",
                    font=MARKER_LABEL_FONT,
                )
                self._marker_ids.append(marker_text_id)

        playhead_x = self._seconds_to_x(self._playhead)
        if playhead_x is not None:
            if self._playhead_id is None:
                self._playhead_id = self.canvas.create_line(playhead_x, 0, playhead_x, height, fill=PLAYHEAD_COLOR, width=2)
            else:
                self.canvas.coords(self._playhead_id, playhead_x, 0, playhead_x, height)
