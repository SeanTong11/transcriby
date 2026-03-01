#!/usr/bin/env python3

import os
import threading
import tkinter as tk

import customtkinter as ctk
import numpy as np
import soundfile as sf

WAVE_BG_COLOR = "#101318"
WAVE_LINE_COLOR = "#8DB8E6"
LOOP_FILL_COLOR = "#2C4A63"
LOOP_MARKER_COLOR = "#63D2FF"
PLAYHEAD_COLOR = "#FF7B5C"


class WaveformWidget(ctk.CTkFrame):
    def __init__(self, master, on_seek=None, height=120, **kwargs):
        super().__init__(master, **kwargs)
        self.on_seek = on_seek
        self.height = height

        self._load_token = 0
        self._envelope = None
        self._duration = None
        self._playhead = 0.0
        self._loop_start = None
        self._loop_end = None

        self.canvas = tk.Canvas(self, height=self.height, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._on_click)

        self._loop_rect_id = None
        self._loop_a_id = None
        self._loop_b_id = None
        self._playhead_id = None

    def clear(self):
        self._load_token += 1
        self._envelope = None
        self._duration = None
        self._playhead = 0.0
        self._loop_start = None
        self._loop_end = None
        self.canvas.delete("all")
        self._loop_rect_id = None
        self._loop_a_id = None
        self._loop_b_id = None
        self._playhead_id = None

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

    def _on_resize(self, _event):
        self._redraw_waveform()

    def _on_click(self, event):
        if self._duration is None or self._duration <= 0:
            return
        width = max(self.canvas.winfo_width(), 1)
        target_seconds = max(0.0, min(self._duration, (event.x / width) * self._duration))
        self.set_playhead(target_seconds)
        if self.on_seek:
            self.on_seek(target_seconds)

    def _build_envelope_worker(self, media_path, token):
        try:
            data, _sr = sf.read(media_path, dtype="float32", always_2d=True)
            if data.size == 0:
                envelope = None
            else:
                mono = np.mean(np.abs(data), axis=1)
                max_points = 5000
                if len(mono) > max_points:
                    block_size = int(np.ceil(len(mono) / max_points))
                    pad = (-len(mono)) % block_size
                    if pad:
                        mono = np.pad(mono, (0, pad), mode="constant")
                    mono = mono.reshape(-1, block_size).max(axis=1)
                max_value = float(np.max(mono)) if mono.size else 0.0
                envelope = (mono / max_value) if max_value > 0 else mono
        except Exception:
            envelope = None

        self.after(0, self._apply_envelope, token, envelope)

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

        playhead_x = self._seconds_to_x(self._playhead)
        if playhead_x is not None:
            if self._playhead_id is None:
                self._playhead_id = self.canvas.create_line(playhead_x, 0, playhead_x, height, fill=PLAYHEAD_COLOR, width=2)
            else:
                self.canvas.coords(self._playhead_id, playhead_x, 0, playhead_x, height)
