from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from transcriby.player import NANOSEC
from transcriby.qt_controller import PlaybackController


def build_controller(player) -> PlaybackController:
    controller = object.__new__(PlaybackController)
    controller.player = player
    controller.persist_recent_options = Mock()
    controller._pending_loop_seek_target = None
    controller._pending_loop_seek_deadline = 0.0
    controller._pending_loop_seek_grace_seconds = 0.15
    controller._pending_loop_restore = None
    controller._pending_seek_restore = None
    controller.song_metadata = ""
    controller.semitones = 0
    controller.cents = 0
    controller.volume_percent = 50
    controller.favorites = []
    controller.selected_favorite_index = None
    controller.favorites_revision = 0
    controller.loop_restart_delay_enabled = False
    controller.loop_restart_delay_seconds = 0.25
    controller._refresh_loop_restart_delay_settings = Mock()
    controller.set_loop_enabled = PlaybackController.set_loop_enabled.__get__(controller, PlaybackController)
    controller.has_valid_loop_range = PlaybackController.has_valid_loop_range.__get__(controller, PlaybackController)
    controller.restart_loop_from_a = PlaybackController.restart_loop_from_a.__get__(controller, PlaybackController)
    controller.tick = PlaybackController.tick.__get__(controller, PlaybackController)
    controller._is_loop_seek_guard_active = PlaybackController._is_loop_seek_guard_active.__get__(controller, PlaybackController)
    controller._arm_loop_seek_guard = PlaybackController._arm_loop_seek_guard.__get__(controller, PlaybackController)
    controller._clear_loop_seek_guard = PlaybackController._clear_loop_seek_guard.__get__(controller, PlaybackController)
    return controller


class LoopSeekLagPlayer:
    def __init__(self, positions, *, start=10 * NANOSEC, end=20 * NANOSEC):
        self._positions = list(positions)
        self._last_position = self._positions[0]
        self.startPoint = start
        self.endPoint = end
        self.loopEnabled = True
        self.canPlay = True
        self.isPlaying = True
        self.tempo = 1.0
        self.songPosition = 0.0
        self.title = ""
        self.artist = ""
        self.handle_message = Mock()
        self.seek_absolute = Mock(side_effect=self._seek_absolute)
        self.Play = Mock()
        self.Pause = Mock()

    def _seek_absolute(self, _target):
        return True

    def update_position(self):
        if self._positions:
            self._last_position = self._positions.pop(0)
        return 60 * NANOSEC, self._last_position

    def query_position(self):
        return self._last_position

    def query_duration(self):
        return 60 * NANOSEC

    def query_percentage(self):
        return 0

    def pipeline_time(self, seconds):
        return seconds * NANOSEC

    def song_time(self, value):
        return value / NANOSEC


class PlaybackControllerSpeedTest(unittest.TestCase):
    def test_set_speed_keeps_existing_loop_boundaries_in_media_time(self):
        start_ns = 10 * NANOSEC
        end_ns = 25 * NANOSEC
        player = SimpleNamespace(
            tempo=1.0,
            songPosition=12.5,
            startPoint=start_ns,
            endPoint=end_ns,
            set_speed=Mock(),
            seek_absolute=Mock(),
        )
        controller = build_controller(player)

        result = controller.set_speed(0.5, persist=False)

        self.assertEqual(result, 0.5)
        self.assertEqual(player.tempo, 0.5)
        self.assertEqual(player.startPoint, start_ns)
        self.assertEqual(player.endPoint, end_ns)
        player.set_speed.assert_called_once_with(0.5)
        player.seek_absolute.assert_not_called()
        controller.persist_recent_options.assert_not_called()


class PlaybackControllerLoopSeekGuardTest(unittest.TestCase):
    def test_tick_does_not_repeat_loop_seek_while_position_is_stale(self):
        player = LoopSeekLagPlayer([21 * NANOSEC, 21 * NANOSEC, 12 * NANOSEC])
        controller = build_controller(player)

        controller.tick()
        controller.tick()

        player.seek_absolute.assert_called_once_with(player.startPoint)

        controller.tick()

        player.seek_absolute.assert_called_once_with(player.startPoint)

    def test_manual_restart_arms_loop_seek_guard_until_position_reenters_loop(self):
        player = LoopSeekLagPlayer([21 * NANOSEC, 21 * NANOSEC, 11 * NANOSEC])
        controller = build_controller(player)

        result = controller.restart_loop_from_a()
        self.assertEqual(result, 0)
        player.seek_absolute.assert_called_once_with(player.startPoint)
        player.Play.assert_called_once_with()

        controller.tick()

        player.seek_absolute.assert_called_once_with(player.startPoint)


if __name__ == "__main__":
    unittest.main()
