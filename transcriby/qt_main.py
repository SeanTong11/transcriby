#!/usr/bin/env python3
"""PySide6 frontend entrypoint for Transcriby."""

from __future__ import annotations

import argparse
import os
import pathlib
import sys

# Keep compatibility with legacy absolute imports used by existing modules.
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from transcriby.app_constants import (
    APP_DESCRIPTION,
    APP_NAME,
    APP_USER_MODEL_ID,
    APP_VERSION,
)
from transcriby.platform_utils import set_windows_app_user_model_id, set_windows_dpi_awareness
from transcriby.qt_controller import PlaybackController
from transcriby import player as player_module
from transcriby.player import slowPlayer


def smoke_check() -> int:
    test_player = slowPlayer()
    try:
        test_player.Pause()
        print("smoke-check: slowPlayer init OK", flush=True)
        details = player_module.get_mpv_runtime_details()
        print(f"smoke-check: mpv backend name = {details.get('backend_name', '')}", flush=True)
        print(f"smoke-check: mpv backend realpath = {details.get('backend_realpath', '')}", flush=True)
        print(f"smoke-check: find_library('mpv') = {details.get('find_library_mpv', '')}", flush=True)
        print(f"smoke-check: env MPV_LIBRARY = {details.get('env_mpv_library', '')}", flush=True)

        require_bundled = str(os.environ.get("TRANSCRIBY_REQUIRE_BUNDLED_MPV", "")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if require_bundled:
            backend_path = details.get("backend_realpath") or details.get("backend_name") or ""
            backend_real = pathlib.Path(str(backend_path)).resolve() if backend_path else None
            executable = pathlib.Path(sys.executable).resolve()
            frameworks_dir = executable.parents[1] / "Frameworks"
            if backend_real is None:
                print("smoke-check: bundled libmpv FAIL (backend path missing)", file=sys.stderr, flush=True)
                return 1
            try:
                in_frameworks = backend_real.is_relative_to(frameworks_dir)
            except Exception:
                in_frameworks = str(backend_real).startswith(str(frameworks_dir))
            if not in_frameworks or backend_real.name not in {"libmpv.dylib", "libmpv.2.dylib"}:
                print(
                    f"smoke-check: bundled libmpv FAIL (got {backend_real}, expected under {frameworks_dir})",
                    file=sys.stderr,
                    flush=True,
                )
                return 1
            print(f"smoke-check: bundled libmpv OK ({backend_real})", flush=True)
    finally:
        test_player.close()
    return 0


def main():
    parser = argparse.ArgumentParser(description=APP_DESCRIPTION, prog=APP_NAME + "-qt")
    parser.add_argument("--delete-recent", help="Clear the list of recently played media", action="store_true")
    parser.add_argument("--smoke-check", help="Run non-GUI startup smoke check and exit", action="store_true")
    parser.add_argument("-v", "--version", action="version", version=f"{APP_NAME} - {APP_VERSION}")
    parser.add_argument("media", nargs="?", help="Path of the media to open")

    args = parser.parse_args()

    if args.smoke_check:
        return smoke_check()

    try:
        from PySide6.QtWidgets import QApplication
    except Exception as ex:
        print(f"Unable to start Qt UI: {ex}", file=sys.stderr, flush=True)
        return 1

    from transcriby.qt_window import TranscribyQtWindow

    set_windows_dpi_awareness()
    set_windows_app_user_model_id(APP_USER_MODEL_ID)

    app = QApplication(sys.argv)
    controller = PlaybackController()
    if args.delete_recent:
        controller.clear_recent_files()

    window = TranscribyQtWindow(controller, args)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
