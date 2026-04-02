import math
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from transcriby.player import NANOSEC, slowPlayer


def build_player(backend=None) -> slowPlayer:
    player = object.__new__(slowPlayer)
    player._player = backend or SimpleNamespace()
    player._sample_rate = None
    player._media_path = ""
    player._pitch_semitones = 0.0
    player._pitch_ratio = 1.0
    player._speed = 1.0
    player._volume = 1.0
    player.media = ""
    player.canPlay = False
    player.isPlaying = False
    player.title = ""
    player.artist = ""
    player.semitones = 0
    player.cents = 0
    player.tempo = 1.0
    player.pitch = 0.0
    player._window_key_binding_names = []
    player._mpv_exit_requested = False
    player._lifecycle_event_handler = None
    return player


class SlowPlayerAudioParamsTest(unittest.TestCase):
    @patch("transcriby.player.os.path.isfile", return_value=True)
    @patch("transcriby.player.sf.info", return_value=SimpleNamespace(samplerate=44100))
    def test_refresh_audio_params_prefers_runtime_sample_rate_over_file_info(self, _mock_info, _mock_isfile):
        backend = SimpleNamespace(audio_params={"samplerate": 48000})
        player = build_player(backend)
        player._media_path = "/tmp/example.wav"

        changed = player._refresh_audio_params()

        self.assertTrue(changed)
        self.assertEqual(player._sample_rate, 48000)

    @patch("transcriby.player.os.path.isfile", return_value=True)
    @patch("transcriby.player.sf.info", return_value=SimpleNamespace(samplerate=44100))
    def test_handle_message_reapplies_pitch_filter_when_runtime_sample_rate_arrives(self, _mock_info, _mock_isfile):
        backend = SimpleNamespace(
            pause=True,
            metadata={},
            audio_params={"samplerate": 48000},
        )
        player = build_player(backend)
        player._media_path = "/tmp/example.wav"
        player._sample_rate = 44100
        player._apply_pitch_filter = Mock()

        player.handle_message()

        self.assertEqual(player._sample_rate, 48000)
        player._apply_pitch_filter.assert_called_once_with()

    def test_apply_pitch_filter_uses_current_runtime_sample_rate(self):
        player = build_player()
        player._sample_rate = 48000
        player._set_prop = Mock()

        player.set_pitch(-1)

        applied_filter = player._set_prop.call_args.args[1]
        expected_rate = 48000 * (2 ** (-1 / 12))
        self.assertIn(f"asetrate={expected_rate}", applied_filter)
        self.assertIn("aresample=48000", applied_filter)

    def test_effective_pitch_error_is_large_when_source_rate_is_used_against_48k_runtime(self):
        source_rate = 44100
        runtime_rate = 48000
        requested_ratio = 2 ** (-1 / 12)
        effective_ratio = (source_rate * requested_ratio) / runtime_rate
        effective_semitones = 12 * math.log2(effective_ratio)

        self.assertLess(effective_semitones, -2.4)
        self.assertGreater(effective_semitones, -2.6)


class SlowPlayerTimelineTest(unittest.TestCase):
    def test_pipeline_and_song_time_do_not_scale_with_playback_speed(self):
        player = build_player()
        player._speed = 0.5
        timeline_seconds = 12.5
        timeline_ns = int(timeline_seconds * NANOSEC)

        self.assertEqual(player.pipeline_time(timeline_seconds), timeline_ns)
        self.assertEqual(player.song_time(timeline_ns), timeline_seconds)


if __name__ == "__main__":
    unittest.main()
