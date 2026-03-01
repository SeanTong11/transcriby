# SlowPlay Windows Installation Guide

SlowPlay for Windows uses `mpv` (libmpv) for lightweight audio playback (no GStreamer required!)

---

## Method 1: Run from Source with uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package manager written in Rust.

### Prerequisites

1. **Python 3.9 or higher**
   - Download from https://python.org
   - **Important**: Check "Add Python to PATH" during installation

2. **uv**
   - Install from https://astral.sh/uv
   - Or run: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

3. **mpv** runtime (for audio playback)
   - Download from https://mpv.io/installation/
   - Ensure `mpv.exe` is on PATH or placed next to `SlowPlay.exe`

4. **FFmpeg** (optional, for YouTube support)
   - Download from https://ffmpeg.org/download.html
   - Add to PATH or place in the same folder as SlowPlay

### Installation Steps

1. **Clone or download the repository**
   ```cmd
   git clone https://github.com/yourusername/slowplay.git
   cd slowplay
   ```

2. **Install dependencies with uv**
   ```cmd
   uv sync
   ```

3. **Run the application**
   ```cmd
   uv run python sp-launch.py
   ```

   Or activate the environment and run:
   ```cmd
   .venv\Scripts\activate
   python sp-launch.py
   ```

---

## Method 1b: Legacy pip Setup (Not Recommended)

If you prefer not to use uv:

```cmd
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python sp-launch.py
```

---

## Method 2: Build Your Own Executable

### Prerequisites
Same as Method 1, plus:
- PyInstaller (`pip install pyinstaller`)

### Build Steps

1. **Navigate to the project folder**
   ```cmd
   cd slowplay
   ```

2. **Run the build script**
   ```cmd
   python build_windows.py
   ```

3. **Find your executable**
   - The built executable will be in `dist/SlowPlay.exe`
   - A distribution folder `SlowPlay-Windows/` will also be created

---

## Export Notes

Audio export uses `soundfile + scipy` and does not require ffmpeg.

---

## Troubleshooting

### "No audio device found"
- Make sure your audio drivers are installed
- Check Windows Sound settings to ensure an output device is selected

### Audio sounds choppy or distorted
- Close other applications using audio
- Try increasing the buffer size (edit `player.py` and change `DEFAULT_BLOCK_SIZE`)

### "Module not found" error when running from source
- Make sure you installed all requirements: `pip install -r requirements.txt`
- Ensure your virtual environment is activated

### "yt-dlp not found" error
- Install yt-dlp: `pip install yt-dlp`
- Or download `yt-dlp.exe` from https://github.com/yt-dlp/yt-dlp/releases

### GUI looks wrong or crashes
- Make sure you have the latest Windows updates
- Try running in compatibility mode (right-click → Properties → Compatibility)

---

## File Locations

### Configuration
Windows: `%APPDATA%\SlowPlay\slowplaycfg.json`

### Cache/Temp Files
Windows: `%TEMP%\SlowPlay\`

### Recent Files
Stored in the config file above

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Space or 0 (numpad) | Play/Pause |
| . (numpad) | Stop |
| ← or 1 (numpad) | Rewind 5s |
| → or 3 (numpad) | Forward 5s |
| Ctrl+O | Open file |
| Ctrl+Y | YouTube download |
| Ctrl+R | Recent files |

**Note**: Some numpad shortcuts may not work on laptops without a dedicated numpad.

---

## Known Issues

1. **Drag and drop**: May require running as administrator in some cases
2. **File associations**: Not automatically set up; use "Open with" to associate audio files
3. **High DPI displays**: May need to adjust Windows scaling settings

---

## Support

For issues specific to this version, please report on GitHub.
