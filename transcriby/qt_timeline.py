#!/usr/bin/env python3
"""Qt timeline overlay widget for seek/loop/markers interactions."""

from __future__ import annotations

import datetime as dt
from typing import Callable

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget

from transcriby.app_constants import (
    UI_ACCENT,
    UI_TIMELINE_BG,
    UI_TIMELINE_LOOP_FILL,
    UI_TIMELINE_LOOP_MARKER,
    UI_TIMELINE_PLAYHEAD,
    UI_TIMELINE_SELECT_FILL,
    UI_TIMELINE_SELECT_MARKER,
)


class QtTimelineWidget(QWidget):
    """Timeline overlay widget (no decoded waveform rendering)."""

    def __init__(
        self,
        parent=None,
        *,
        on_seek: Callable[[float], None] | None = None,
        on_loop_select: Callable[[float, float], None] | None = None,
        on_context_request: Callable[[float, QPoint], None] | None = None,
        on_marker_activate: Callable[[int, float], None] | None = None,
        height: int = 120,
    ):
        super().__init__(parent)
        self.setMinimumHeight(int(height))
        self.setMaximumHeight(int(height))
        self.setMouseTracking(True)

        self.on_seek = on_seek
        self.on_loop_select = on_loop_select
        self.on_context_request = on_context_request
        self.on_marker_activate = on_marker_activate

        self._duration: float | None = None
        self._playhead: float = 0.0
        self._loop_enabled = False
        self._loop_start: float | None = None
        self._loop_end: float | None = None
        self._select_start: float | None = None
        self._select_end: float | None = None
        self._right_anchor: float | None = None
        self._right_press_pos_x: float | None = None
        self._right_dragging = False
        self._markers: list[dict] = []

        self._colors = {
            "bg": QColor(UI_TIMELINE_BG),
            "loop_fill": QColor(UI_TIMELINE_LOOP_FILL),
            "loop_marker": QColor(UI_TIMELINE_LOOP_MARKER),
            "select_fill": QColor(UI_TIMELINE_SELECT_FILL),
            "select_marker": QColor(UI_TIMELINE_SELECT_MARKER),
            "playhead": QColor(UI_TIMELINE_PLAYHEAD),
            "marker_fallback": QColor(UI_ACCENT),
        }

    def clear(self):
        self._duration = None
        self._playhead = 0.0
        self._loop_start = None
        self._loop_end = None
        self.clear_selection_preview()
        self._markers = []
        self.update()

    def set_duration(self, duration_seconds: float | None):
        self._duration = duration_seconds if (duration_seconds is not None and duration_seconds > 0) else None
        self.update()

    def set_playhead(self, position_seconds: float | None):
        self._playhead = max(0.0, float(position_seconds or 0.0))
        self.update()

    def set_loop_enabled(self, enabled: bool):
        self._loop_enabled = bool(enabled)
        self.update()

    def set_loop(self, start_seconds: float | None, end_seconds: float | None):
        self._loop_start = start_seconds
        self._loop_end = end_seconds
        self.update()

    def set_markers(self, markers: list[dict] | None):
        self._markers = markers if isinstance(markers, list) else []
        self.update()

    def set_selection_preview(self, start_seconds: float | None, end_seconds: float | None):
        self._select_start = start_seconds
        self._select_end = end_seconds
        self.update()

    def clear_selection_preview(self):
        self._select_start = None
        self._select_end = None
        self._right_anchor = None
        self._right_press_pos_x = None
        self._right_dragging = False
        self.update()

    def _x_to_seconds(self, x: float) -> float:
        if self._duration is None or self._duration <= 0:
            return 0.0
        width = max(1, self.width())
        ratio = max(0.0, min(1.0, float(x) / float(width)))
        return float(self._duration) * ratio

    def _seconds_to_x(self, seconds: float | None) -> float | None:
        if self._duration is None or self._duration <= 0 or seconds is None:
            return None
        width = max(1, self.width())
        ratio = max(0.0, min(1.0, float(seconds) / float(self._duration)))
        return float(width) * ratio

    def _marker_hit_test(self, x: float, tolerance: float = 5.0) -> tuple[int, float] | None:
        if not self._markers:
            return None
        candidate = None
        best_dist = 10**9
        for marker in self._markers:
            if not isinstance(marker, dict):
                continue
            marker_x = self._seconds_to_x(marker.get("time_seconds"))
            if marker_x is None:
                continue
            dist = abs(float(marker_x) - float(x))
            if dist <= tolerance and dist < best_dist:
                best_dist = dist
                candidate = marker
        if candidate is None:
            return None
        try:
            marker_index = int(candidate.get("index", -1))
            marker_seconds = float(candidate.get("time_seconds", 0.0))
        except Exception:
            return None
        if marker_index < 0:
            return None
        return marker_index, marker_seconds

    def _format_seconds_text(self, seconds: float) -> str:
        safe = max(0.0, float(seconds))
        integral = int(safe)
        frac = int(round((safe - integral) * 1000))
        if frac >= 1000:
            integral += 1
            frac = 0
        return f"{dt.timedelta(seconds=integral)}.{frac:03d}"

    def mousePressEvent(self, event: QMouseEvent):
        if self._duration is None or self._duration <= 0:
            event.ignore()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            marker_target = self._marker_hit_test(event.position().x())
            if marker_target is not None:
                marker_index, marker_seconds = marker_target
                if self.on_marker_activate:
                    self.on_marker_activate(marker_index, marker_seconds)
                event.accept()
                return
            target = self._x_to_seconds(event.position().x())
            self.set_playhead(target)
            if self.on_seek:
                self.on_seek(target)
            event.accept()
            return

        if event.button() == Qt.MouseButton.RightButton:
            self._right_anchor = self._x_to_seconds(event.position().x())
            self._right_press_pos_x = float(event.position().x())
            self._right_dragging = False
            self.set_selection_preview(self._right_anchor, self._right_anchor)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._duration is not None and self._duration > 0:
            hover_seconds = self._x_to_seconds(event.position().x())
            QToolTip.showText(event.globalPosition().toPoint(), self._format_seconds_text(hover_seconds), self)

        if self._right_anchor is None or not (event.buttons() & Qt.MouseButton.RightButton):
            super().mouseMoveEvent(event)
            return

        current = self._x_to_seconds(event.position().x())
        if self._right_press_pos_x is not None and abs(float(event.position().x()) - self._right_press_pos_x) >= 3.0:
            self._right_dragging = True
        self.set_selection_preview(self._right_anchor, current)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.RightButton or self._right_anchor is None:
            super().mouseReleaseEvent(event)
            return

        end_seconds = self._x_to_seconds(event.position().x())
        anchor = float(self._right_anchor)
        was_dragging = bool(self._right_dragging)
        self.clear_selection_preview()

        if (not was_dragging) or (abs(end_seconds - anchor) < 0.01):
            if self.on_context_request:
                self.on_context_request(end_seconds, event.globalPosition().toPoint())
            event.accept()
            return

        if self.on_loop_select:
            self.on_loop_select(min(anchor, end_seconds), max(anchor, end_seconds))
        event.accept()

    def paintEvent(self, _event):
        height = max(1, self.height())
        draw_top = 6
        draw_bottom = max(draw_top + 1, height - 8)
        draw_height = max(1, draw_bottom - draw_top)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(self.rect(), self._colors["bg"])

        if self._loop_enabled:
            border_color = QColor(self._colors["loop_marker"])
            border_color.setAlpha(120)
            painter.setPen(QPen(border_color, 1))
            painter.drawRect(self.rect().adjusted(0, 0, -1, -1))
            painter.setPen(border_color)
            painter.drawText(8, draw_bottom - 2, "LOOP")

        a_x = self._seconds_to_x(self._loop_start)
        b_x = self._seconds_to_x(self._loop_end)
        if a_x is not None and b_x is not None and b_x > a_x:
            painter.fillRect(QRectF(a_x, draw_top, b_x - a_x, draw_height), self._colors["loop_fill"])
            painter.setPen(QPen(self._colors["loop_marker"], 2))
            painter.drawLine(int(a_x), draw_top, int(a_x), draw_bottom)
            painter.drawLine(int(b_x), draw_top, int(b_x), draw_bottom)

        s_a_x = self._seconds_to_x(self._select_start)
        s_b_x = self._seconds_to_x(self._select_end)
        if s_a_x is not None and s_b_x is not None and abs(s_b_x - s_a_x) > 1:
            x1, x2 = (s_a_x, s_b_x) if s_a_x <= s_b_x else (s_b_x, s_a_x)
            painter.fillRect(QRectF(x1, draw_top, x2 - x1, draw_height), self._colors["select_fill"])
            painter.setPen(QPen(self._colors["select_marker"], 2))
            painter.drawLine(int(x1), draw_top, int(x1), draw_bottom)
            painter.drawLine(int(x2), draw_top, int(x2), draw_bottom)

        painter.setFont(self.font())
        for marker in self._markers:
            if not isinstance(marker, dict):
                continue
            marker_x = self._seconds_to_x(marker.get("time_seconds"))
            if marker_x is None:
                continue
            color_raw = marker.get("color")
            color = QColor(color_raw) if isinstance(color_raw, str) else self._colors["marker_fallback"]
            if not color.isValid():
                color = self._colors["marker_fallback"]
            painter.setPen(QPen(color, 2))
            marker_top = draw_top + 4
            marker_bottom = draw_bottom - 4
            if marker_bottom <= marker_top:
                marker_top = draw_top
                marker_bottom = draw_bottom
            painter.drawLine(int(marker_x), marker_top, int(marker_x), marker_bottom)
            label = str(marker.get("label", "")).strip()
            if label:
                text_x = int(marker_x) + 4
                metrics = painter.fontMetrics()
                text_width = metrics.horizontalAdvance(label)
                text_height = metrics.height()
                bg_rect = QRectF(text_x - 2, draw_top + 1, text_width + 4, text_height)
                label_bg = QColor(0, 0, 0, 120)
                painter.fillRect(bg_rect, label_bg)
                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(text_x, draw_top + 1 + metrics.ascent(), label)

        playhead_x = self._seconds_to_x(self._playhead)
        if playhead_x is not None:
            painter.setPen(QPen(self._colors["playhead"], 2))
            painter.drawLine(int(playhead_x), draw_top, int(playhead_x), draw_bottom)
