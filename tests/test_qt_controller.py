from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from transcriby.player import NANOSEC
from transcriby.qt_controller import PlaybackController


def build_controller(player) -> PlaybackController:
    controller = object.__new__(PlaybackController)
    controller.player = player
    controller.persist_recent_options = Mock()
    return controller


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


if __name__ == "__main__":
    unittest.main()
