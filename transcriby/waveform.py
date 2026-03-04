#!/usr/bin/env python3

import tkinter as tk

import customtkinter as ctk

from transcriby.app_constants import (
    UI_ACCENT,
    UI_TIMELINE_BG,
    UI_TIMELINE_LOOP_FILL,
    UI_TIMELINE_LOOP_MARKER,
    UI_TIMELINE_PLAYHEAD,
    UI_TIMELINE_SELECT_FILL,
    UI_TIMELINE_SELECT_MARKER,
)

MARKER_LABEL_FONT = ("TkDefaultFont", 13, "bold")


class WaveformWidget(ctk.CTkFrame):
    """Timeline overlay widget (no waveform drawing)."""

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

        self._duration = None
        self._playhead = 0.0
        self._loop_start = None
        self._loop_end = None
        self._select_start = None
        self._select_end = None
        self._select_anchor = None
        self._markers = []
        self._colors = {
            "bg": UI_TIMELINE_BG,
            "loop_fill": UI_TIMELINE_LOOP_FILL,
            "loop_marker": UI_TIMELINE_LOOP_MARKER,
            "select_fill": UI_TIMELINE_SELECT_FILL,
            "select_marker": UI_TIMELINE_SELECT_MARKER,
            "playhead": UI_TIMELINE_PLAYHEAD,
            "marker_fallback": UI_ACCENT,
        }

        self.canvas = tk.Canvas(self, height=self.height, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<ButtonPress-3>", self._on_right_press)
        self.canvas.bind("<B3-Motion>", self._on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_release)

    def clear(self):
        self._duration = None
        self._playhead = 0.0
        self._loop_start = None
        self._loop_end = None
        self._select_start = None
        self._select_end = None
        self._select_anchor = None
        self._markers = []
        self._redraw()

    def set_media(self, _media_path):
        # Keep API compatibility with the old waveform widget.
        self.clear()

    def set_duration(self, duration_seconds):
        self._duration = duration_seconds
        self._redraw()

    def set_playhead(self, position_seconds):
        self._playhead = max(0.0, position_seconds if position_seconds is not None else 0.0)
        self._redraw()

    def set_loop(self, start_seconds, end_seconds):
        self._loop_start = start_seconds
        self._loop_end = end_seconds
        self._redraw()

    def set_markers(self, markers):
        self._markers = markers if isinstance(markers, list) else []
        self._redraw()

    def set_selection_preview(self, start_seconds, end_seconds):
        self._select_anchor = start_seconds
        self._select_start = start_seconds
        self._select_end = end_seconds
        self._redraw()

    def clear_selection_preview(self):
        self._select_anchor = None
        self._select_start = None
        self._select_end = None
        self._redraw()

    def apply_theme(
        self,
        bg_color=None,
        loop_fill_color=None,
        loop_marker_color=None,
        select_fill_color=None,
        select_marker_color=None,
        playhead_color=None,
        default_marker_color=None,
    ):
        """Apply visual theme colors used by the timeline overlay."""
        if(bg_color is not None):
            self._colors["bg"] = bg_color
        if(loop_fill_color is not None):
            self._colors["loop_fill"] = loop_fill_color
        if(loop_marker_color is not None):
            self._colors["loop_marker"] = loop_marker_color
        if(select_fill_color is not None):
            self._colors["select_fill"] = select_fill_color
        if(select_marker_color is not None):
            self._colors["select_marker"] = select_marker_color
        if(playhead_color is not None):
            self._colors["playhead"] = playhead_color
        if(default_marker_color is not None):
            self._colors["marker_fallback"] = default_marker_color
        self._redraw()

    def _on_resize(self, _event):
        self._redraw()

    def _on_click(self, event):
        if(self._duration is None or self._duration <= 0):
            return
        target_seconds = self._x_to_seconds(event.x)
        self.set_playhead(target_seconds)
        if(self.on_seek):
            self.on_seek(target_seconds)

    def _on_right_press(self, event):
        if(self._duration is None or self._duration <= 0):
            return
        self._select_anchor = self._x_to_seconds(event.x)
        self._select_start = self._select_anchor
        self._select_end = self._select_anchor
        self._redraw()

    def _on_right_drag(self, event):
        if(self._select_anchor is None):
            return
        self._select_end = self._x_to_seconds(event.x)
        self._redraw()

    def _on_right_release(self, event):
        if(self._select_anchor is None):
            return
        end_seconds = self._x_to_seconds(event.x)
        start_seconds = min(self._select_anchor, end_seconds)
        stop_seconds = max(self._select_anchor, end_seconds)
        self.clear_selection_preview()

        if(stop_seconds - start_seconds < 0.01):
            if(self.on_context_request):
                self.on_context_request(end_seconds, event.x_root, event.y_root)
            return
        if(self.on_loop_select):
            self.on_loop_select(start_seconds, stop_seconds)

    def _x_to_seconds(self, x):
        if(self._duration is None or self._duration <= 0):
            return(0.0)
        width = max(self.canvas.winfo_width(), 1)
        return(max(0.0, min(self._duration, (x / width) * self._duration)))

    def _seconds_to_x(self, seconds):
        if(self._duration is None or self._duration <= 0 or seconds is None):
            return(None)
        width = max(self.canvas.winfo_width(), 1)
        ratio = max(0.0, min(1.0, seconds / self._duration))
        return(ratio * width)

    def _redraw(self):
        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        self.canvas.delete("all")
        self.canvas.create_rectangle(0, 0, width, height, fill=self._colors["bg"], outline="")
        self._draw_overlays(width, height)

    def _draw_overlays(self, _width, height):
        a_x = self._seconds_to_x(self._loop_start)
        b_x = self._seconds_to_x(self._loop_end)
        if(a_x is not None and b_x is not None and b_x > a_x):
            self.canvas.create_rectangle(a_x, 0, b_x, height, fill=self._colors["loop_fill"], outline="")
            self.canvas.create_line(a_x, 0, a_x, height, fill=self._colors["loop_marker"], width=3)
            self.canvas.create_line(b_x, 0, b_x, height, fill=self._colors["loop_marker"], width=3)

        s_a_x = self._seconds_to_x(self._select_start)
        s_b_x = self._seconds_to_x(self._select_end)
        if(s_a_x is not None and s_b_x is not None and abs(s_b_x - s_a_x) > 1):
            x1, x2 = (s_a_x, s_b_x) if s_a_x <= s_b_x else (s_b_x, s_a_x)
            self.canvas.create_rectangle(x1, 0, x2, height, fill=self._colors["select_fill"], outline="")
            self.canvas.create_line(x1, 0, x1, height, fill=self._colors["select_marker"], width=2)
            self.canvas.create_line(x2, 0, x2, height, fill=self._colors["select_marker"], width=2)

        for marker in self._markers:
            if(not isinstance(marker, dict)):
                continue
            marker_seconds = marker.get("time_seconds")
            marker_x = self._seconds_to_x(marker_seconds)
            if(marker_x is None):
                continue
            marker_color = marker.get("color", self._colors["marker_fallback"])
            marker_label = str(marker.get("label", "")).strip()
            self.canvas.create_line(marker_x, 0, marker_x, height, fill=marker_color, width=2)
            if(marker_label):
                self.canvas.create_text(
                    marker_x + 3,
                    10,
                    text=marker_label,
                    fill=marker_color,
                    anchor="nw",
                    font=MARKER_LABEL_FONT,
                )

        playhead_x = self._seconds_to_x(self._playhead)
        if(playhead_x is not None):
            self.canvas.create_line(playhead_x, 0, playhead_x, height, fill=self._colors["playhead"], width=2)
