# SlowPlay Windows Installation Guide

SlowPlay for Windows uses `sounddevice` + `scipy` for lightweight audio playback (no GStreamer required!)

---

## Method 1: Run from Source (Recommended)

### Prerequisites

1. **Python 3.8 or higher**
   - Download from https://python.org
   - **Important**: Check "Add Python to PATH" during installation

2. **FFmpeg** (optional, for YouTube support)
   - Download from https://ffmpeg.org/download.html
   - Add to PATH or place in the same folder as SlowPlay

### Installation Steps

1. **Clone or download the repository**
   ```cmd
   git clone https://github.com/yourusername/slowplay.git
   cd slowplay
   ```

2. **Create a virtual environment (recommended)**
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install Python dependencies**
   ```cmd
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```cmd
   python sp-launch.py
   ```

   Or simply double-click `run_windows.bat`

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

## Optional: High Quality Export

For best audio export quality, you can install the `rubberband` CLI tool:

1. Download from https://breakfastquay.com/rubberband/
2. Extract and add `rubberband.exe` to your PATH or place it next to `SlowPlay.exe`

Without rubberband, export will use scipy (good quality but not as professional).

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
