#!/usr/bin/env python3

import os
import threading
import tkinter as tk

import customtkinter as ctk
import numpy as np
import soundfile as sf

try:
    import av
except Exception:
    av = None

WAVE_BG_COLOR = "#101318"
WAVE_LINE_COLOR = "#8DB8E6"
LOOP_FILL_COLOR = "#2C4A63"
LOOP_MARKER_COLOR = "#63D2FF"
PLAYHEAD_COLOR = "#FF7B5C"
SELECT_FILL_COLOR = "#B8893C"
SELECT_MARKER_COLOR = "#FFD27D"


class WaveformWidget(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_seek=None,
        on_loop_select=None,
        on_context_request=None,
        on_status=None,
        height=120,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.on_seek = on_seek
        self.on_loop_select = on_loop_select
        self.on_context_request = on_context_request
        self.on_status = on_status
        self.height = height

        self._load_token = 0
        self._envelope = None
        self._duration = None
        self._message = "Open a file to show waveform"
        self._playhead = 0.0
        self._loop_start = None
        self._loop_end = None
        self._select_start = None
        self._select_end = None
        self._select_anchor = None

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

    def clear(self):
        self._load_token += 1
        self._envelope = None
        self._duration = None
        self._message = "Open a file to show waveform"
        self._playhead = 0.0
        self._loop_start = None
        self._loop_end = None
        self._select_start = None
        self._select_end = None
        self._select_anchor = None
        self.canvas.delete("all")
        self._loop_rect_id = None
        self._loop_a_id = None
        self._loop_b_id = None
        self._playhead_id = None
        self._select_rect_id = None
        self._select_a_id = None
        self._select_b_id = None

    def set_media(self, media_path):
        self.clear()
        if not media_path or not os.path.isfile(media_path):
            return

        self._message = "Loading waveform..."
        self._redraw_waveform()
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
        message = None
        try:
            data, _sr = sf.read(media_path, dtype="float32", always_2d=True)
            if data.size == 0:
                envelope = None
            else:
                mono = np.mean(np.abs(data), axis=1)
                envelope = self._build_envelope(mono)
        except Exception:
            envelope = None
            message = "Waveform decoder fallback: PyAV"

        if envelope is None:
            mono = self._decode_with_pyav(media_path)
            if mono is not None:
                envelope = self._build_envelope(mono)
                message = None

        if envelope is None:
            if av is None:
                message = "Waveform unavailable: install PyAV (pip install av)"
            else:
                message = "Waveform unavailable for this media"

        self.after(0, self._apply_envelope, token, envelope, message)

    def _decode_with_pyav(self, media_path):
        if av is None:
            return None

        container = None
        try:
            container = av.open(media_path)
        except Exception:
            return None

        audio_stream = None
        try:
            for stream in container.streams:
                if stream.type == "audio":
                    audio_stream = stream
                    break
        except Exception:
            audio_stream = None

        if audio_stream is None:
            if container is not None:
                container.close()
            return None

        resampler = None
        try:
            resampler = av.audio.resampler.AudioResampler(format="fltp", layout="mono", rate=12000)
        except Exception:
            resampler = None

        chunks = []
        total_samples = 0
        max_samples = 12_000_000
        try:
            for frame in container.decode(audio=audio_stream.index):
                if frame is None:
                    continue

                frames = [frame]
                if resampler is not None:
                    try:
                        res = resampler.resample(frame)
                        if isinstance(res, list):
                            frames = [f for f in res if f is not None]
                        elif res is not None:
                            frames = [res]
                    except Exception:
                        frames = [frame]

                for out_frame in frames:
                    arr = out_frame.to_ndarray()
                    if arr.ndim == 2:
                        if arr.shape[0] <= 8 and arr.shape[1] > arr.shape[0]:
                            mono = np.mean(np.abs(arr), axis=0)
                        else:
                            mono = np.mean(np.abs(arr), axis=1)
                    else:
                        mono = np.abs(arr.reshape(-1))

                    if mono.size == 0:
                        continue

                    mono = mono.astype(np.float32, copy=False)
                    chunks.append(mono)
                    total_samples += mono.size

                    if total_samples > max_samples:
                        chunks = [c[::2] for c in chunks]
                        total_samples = sum(c.size for c in chunks)
        except Exception:
            if container is not None:
                container.close()
            return None
        finally:
            if container is not None:
                container.close()

        if not chunks:
            return None

        return np.concatenate(chunks)

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

    def _apply_envelope(self, token, envelope, message):
        if token != self._load_token:
            return
        self._envelope = envelope
        self._message = message
        if message and self.on_status:
            self.on_status(message)
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

        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)

        self.canvas.create_rectangle(0, 0, width, height, fill=WAVE_BG_COLOR, outline="")

        if self._envelope is None or len(self._envelope) == 0:
            if self._message:
                self.canvas.create_text(
                    width / 2,
                    height / 2,
                    text=self._message,
                    fill="#BBC2CE",
                    font=("Segoe UI", 11),
                )
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

        playhead_x = self._seconds_to_x(self._playhead)
        if playhead_x is not None:
            if self._playhead_id is None:
                self._playhead_id = self.canvas.create_line(playhead_x, 0, playhead_x, height, fill=PLAYHEAD_COLOR, width=2)
            else:
                self.canvas.coords(self._playhead_id, playhead_x, 0, playhead_x, height)
