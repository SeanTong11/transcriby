import unittest

from transcriby.mpv_options import build_mpv_init_options


class BuildMpvInitOptionsTest(unittest.TestCase):
    def test_embedded_player_disables_external_state_and_scripts(self):
        options = build_mpv_init_options()

        self.assertFalse(options["config"])
        self.assertFalse(options["load_scripts"])
        self.assertFalse(options["save_position_on_quit"])
        self.assertFalse(options["resume_playback"])

    def test_embedded_player_keeps_expected_runtime_flags(self):
        options = build_mpv_init_options()

        self.assertEqual(options["keep_open"], "always")
        self.assertEqual(options["vid"], "auto")
        self.assertTrue(options["input_vo_keyboard"])
        self.assertFalse(options["input_default_bindings"])


if __name__ == "__main__":
    unittest.main()
