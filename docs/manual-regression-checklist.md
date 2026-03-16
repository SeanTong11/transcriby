# Manual Regression Checklist

This checklist is used before release for UI/UX and playback regressions.

## Environment

- Python virtual environment active
- mpv runtime available on system path
- `python-mpv` importable in project environment

## Baseline Startup

- Launch app from `uv run transcriby` (or `python -m transcriby.qt_main`)
- App opens with expected default size and minimum resize limits
- Main panels render without overlapping controls

## Playback Core

- Open local audio file and verify:
  - Play/Pause works from button
  - `Numpad 0` toggles Play/Pause
  - `Numpad .` stops and rewinds
  - Left/Right and Numpad 1/3/4/6/7/9 seek as expected

## Loop Workflow

- Set loop start with `A` and loop end with `B`
- Toggle loop using `L` and switch button
- Verify active loop icon appears on Play button
- Verify `Space` restarts playback from loop start (A) when loop is enabled
- Verify `Space` is normal Play/Pause toggle when loop is disabled
- Verify `Ctrl+A`/`Ctrl+B` reset loop boundaries

## Timeline

- Timeline appears after media is loaded
- Click timeline to seek to clicked position
- Playhead updates while audio is playing
- A/B markers and highlighted loop range match current loop points

## Playback Controls

- Speed slider and entry stay synchronized
- Transpose/cents controls update pitch correctly
- Volume slider and entry stay synchronized
- Changing speed does not break loop boundary behavior

## Non-Core Flows

- Export Audio As exports file without UI freeze and without changing source timing
- Recent files dialog opens and restores playback settings

## Shortcut Documentation Consistency

- Shortcuts dialog (`F1`) list matches actual behavior:
  - Numpad 8: speed +5%
  - Numpad 2: speed -5%
  - Space: restart loop from A (loop enabled)

## Sign-off

- Record tested OS, Python version, and mpv version
- Record known issues and follow-up tasks
