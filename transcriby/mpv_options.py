"""Shared libmpv initialization options for the embedded player."""


def build_mpv_init_options() -> dict[str, object]:
    """Return the libmpv initialization options used by the embedded player."""
    return {
        "ytdl": False,
        "vid": "auto",
        "keep_open": "always",
        "input_vo_keyboard": True,
        "input_default_bindings": False,
        # Keep the embedded player isolated from user/system mpv config and state files.
        "config": False,
        "load_scripts": False,
        "save_position_on_quit": False,
        "resume_playback": False,
    }
