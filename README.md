# Transcriby

**Transcriby** is a simple audio player with speed/pitch change capabilities. It is meant to help music students/teachers transcribe music and play along with it.

- **Cross-platform**: Works on Windows, Linux, and macOS
- **Lightweight**: Uses `mpv` (libmpv) for audio playback (no GStreamer required)

**Made by a musician for musicians**

![Screenshot](transcriby/resources/Screenshot.png)

## About This Fork

This project is modified from the original [SlowPlay](https://github.com/aFunkyBass/slowplay) by aFunkyBass.
Current maintained repository: [SeanTong11/transcriby](https://github.com/SeanTong11/transcriby).

**Key changes in this fork:**
- ✅ **Removed GStreamer dependency** - Now uses `mpv` (libmpv) on all platforms
- ✅ **Full Windows support** - Native Windows support without complex setup
- ✅ **Simplified installation** - No need to install GStreamer or its plugins

## Features

- [Speed and pitch change on the fly](#speed-and-pitch-change)
- [Video playback in a synced external window](#speed-and-pitch-change)
- [YouTube audio extraction from URL](#youtube-audio-extraction)
- [Loop a range of the song, with fine adjustment of boundaries](#loop-ab)
- [Waveform view with click-to-seek](#waveform-view)
- [Modified audio export in MP3 or WAV audio format](#export-modified-audio)
- [No nonsense keyboard shortcuts](#optimized-keyobard-shortcuts)
- [...and more!](#other-features)

### Speed and pitch change:

**Transcriby** can speed down/up songs or change their pitch independently "on the fly". You can import all the most common audio files format (mp3, wav, flac, aif...).
It also supports video files like mp4/m4v/mkv, which will open in a separate mpv window while the audio controls stay in Transcriby.

Speed change is made by moving the slider which will change it in 5% steps, or by entering the precise percentage value in the edit box (eg 87%).You can transpose your song up and down by semitones or fine adjust the pitch by cents, in case the song is not in tune with your instruments. For your convenience, Transcriby offers several numeric keypad shortcuts. Please take a look at the [shortcut](#optimized-keyobard-shortcuts) list further on in this document.

### YouTube audio extraction:

**Transcriby** can extract audio from YouTube videos and treat it like a regular audio file. Please follow these steps to operate on YouTube videos:

- Click on the YouTube button to open the YouTube dialog
- Paste a valid YouTube URL in the upper box and click on the YouTube icon next to it
- The dialog will search for the specified URL and show the video info and its thumbnail
- If that's the video you are looking for, click on "Open" button on the dialog to import it and get back to the main window *(downloading and extracting audio can take a little time, meanwhile the app might be unresponsive. Please wait until done)*

Audio extracted from YouTube are marked with a leading "(YT)" on the title.

>**Note** To enable this feature, you need install the latest version of [yt-dlp](https://github.com/yt-dlp/yt-dlp) and ffmpeg. Make sure `yt-dlp` it is present on your execution path. If `yt-dlp` is not found on your system, you will get an error.

### Loop A/B:

This function allows you to loop playback a section of the song. Loop controls are available directly in the main playback panel.

Use the "Set loop start" (shortcut "A" or num keypad divide) and "Set loop end" (shortcut "B" or num keypad multiply) buttons while playing to mark the loop boundaries. Toggle the "Enable loop" switch (shortcut "L") to engage/disengage loop playing. You can reset the A/B point using the reset buttons or pressing "Ctrl+A" and "Ctrl+B" on your keyboard.

To achieve maximum execution precision, you can fine adjust the loop points by moving them left and right by 10 or 100 milliseconds using the associated buttons. *NOTE: Please keep in mind that there can be very short silence gap when restarting the loop. This is normal and it can't be avoided*

### Waveform view:

Transcriby now includes a waveform panel under the seek bar:

- Click anywhere on the waveform to seek playback to that point
- A/B loop boundaries are shown directly on the waveform
- The playhead updates in real time while playing

For media containers like MP4, waveform extraction may use `ffmpeg` as a fallback decoder.

### Export modified audio:

It is possible to export modified songs by using the "Save as..." button. You can save your files either in mp3 or wav format, based on the extension of file to be saved. Currently saved audio files are in the format of 44.1K 16bit stereo. Mp3 are saved as constant bitrate 192k. Volume setting and metadata are ignored in the export operation.

### Optimized keyobard shortcuts:

If you use Transcriby for music practicing, you probably want access its functions without using the mouse or both hands, which is why most important shortcuts are assigned to the numeric keypads.

- Numbers in the left column (1, 4, 7) move the song position back by 5, 10 and 15 seconds. Numbers on the right column (3, 6, 9) move it forward accordingly. You can reach the song position you want to reharse in a bit.

- Speed controls are assigned to the central column. Numbers 2 and 8 change speed by -5% and +5% respectively, while number 5 resets the speed to normal.

- Plus and minus keys transpose the song by semitones

- Loop start and loop end can be set using the Divide and the Multiply keys respectively

- Number 0 start and pause the playback while the Dot stop and rewind.
- Spacebar restarts playback from loop start (A) when loop is enabled, otherwise it toggles play/pause.

I highly recommend taking some time to familiarize yourself with these keyboard shortucts, as they will save you a lot of time in the long run! Personally, I've been using this key combination for my music classes for a while now, and I can't think of anything better.

See the [shortcuts](#shortcuts) section for a more complete key reference.

### Other features:

- **Recent files list**: To access the recent files list use the **Ctrl+R** shortcut, or right-click on the "Open" button. Transcriby keeps track of the last 16 played files and all the playback parameters (speed, pitch, cents and volume), which are restored as you load the song again.
If the software is launched without specifying any media in the command line, it attempts to reopen the last played track.
If the last played song was extracted from a YouTube video, the app will not automatically open it to prevent unwanted downloads. You can dwonload it again by accessing the recent files dialog.

- **Drag-n-drop**: you can drop audio files straight from your file manager or from other applications.

## Installation

### Prerequisites

- **Python 3.9 or higher**
- **uv** - Fast Python package manager (install from [astral.sh/uv](https://astral.sh/uv))
- **mpv** runtime (for audio playback)
- **FFmpeg** (for YouTube support only)

**mpv runtime install:**
- **Windows**: Download from https://mpv.io/installation/ and ensure `mpv.exe` and `libmpv-2.dll` are on PATH (or next to the app)
- **macOS**: `brew install mpv`
- **Ubuntu/Debian/WSL**: `sudo apt-get install mpv`
- **Fedora**: `sudo dnf install mpv`
- **Arch**: `sudo pacman -S mpv`

**Tip (Windows):** If `python-mpv` cannot find `libmpv-2.dll`, set `TRANSCRIBY_MPV_DIR` to the folder containing the DLL (for example the same folder as `mpv.exe`).

### Quick Start with uv

[uv](https://github.com/astral-sh/uv) is a fast Python package manager written in Rust. It's the recommended way to install and run Transcriby.

#### Windows

```cmd
git clone https://github.com/SeanTong11/transcriby.git
cd transcriby

# Create venv and install dependencies
uv sync

# Run the application
uv run python transcriby-launch.py

# Or activate the environment and run normally
.venv\Scripts\activate
python transcriby-launch.py
```

#### Linux / WSL

```bash
git clone https://github.com/SeanTong11/transcriby.git
cd transcriby

# Create venv and install dependencies
uv sync

# Run the application
uv run python transcriby-launch.py

# Or activate the environment and run normally
source .venv/bin/activate
python transcriby-launch.py
```

#### macOS

```bash
brew install mpv

git clone https://github.com/SeanTong11/transcriby.git
cd transcriby

uv sync
uv run python transcriby-launch.py
```

### Development Setup

To install with all development dependencies (pyinstaller, yt-dlp):

```bash
uv sync --dev

### Windows Build

1. Download the mpv **libmpv dev** package and extract DLLs into `third_party/mpv/`
2. Run:

```cmd
powershell -ExecutionPolicy Bypass -File tools\package_windows.ps1
```
```

### Legacy pip Setup (Not Recommended)

If you prefer not to use uv:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python transcriby-launch.py
```

## Shortcuts

Transcriby offers the following shortcuts:

#### General operations:
- **Ctrl+O**: Open a file
- **Ctrl+R**: Open recent files list
- **Ctrl+Y**: Open YouTube search dialog
- **Ctrl+Q**: Quit application

#### Playback controls:
The following commands are all assigned to the numeric keypad. Refer to the drawing below for visual help.

- **0** *(numeric keypad)*: Toggle Play/Pause
- **spacebar**: Restart from loop start (A) when loop is enabled, otherwise Toggle Play/Pause
- **.** *(numeric pad dot)*: Stop and Rewind

- **HOME**: Rewind to the start of song, or to the start of loop when engaged

- **1** or **left arrow**: Rewind 5 seconds
- **4**: Rewind 10 seconds
- **7**: Rewind 15 seconds

- **3** or **right arrow**: Forward 5 seconds
- **6**: Forward 10 seconds
- **9**: Forward 15 seconds

- **8**: Increase speed by 5%
- **2**: Decrease speed by 5%
- **5**: Reset speed to 100%

- **+**: Transpose +1 semitone
- **-**: Transpose -1 semitone

#### Loop controls:
- **L**: Toggle loop playing

- **A** or **Keypad Divide**: Sets the start loop point to the current playing position
- **Ctrl+A**: Resets the start loop point to the start of the song

- **B** or **Keypad Multiply**: Sets the end loop point to the current playing position
- **Ctrl+B**: Resets the end loop point to the end of the song

![Keypad shortcuts](transcriby/resources/Keypad.png)

*(please make sure none of the input boxes have the focus. Click on an empty area of the app to take the focus back from an input box)*

## Export Notes

Audio export is performed with `soundfile + scipy` and does not require ffmpeg.

## Troubleshooting

### "No audio device found"
- Make sure your audio drivers are installed
- Check system sound settings to ensure an output device is selected

### Audio sounds choppy or distorted
- Close other applications using audio
- Try increasing the buffer size (edit `player.py` and change `DEFAULT_BLOCK_SIZE`)

### Windows exe icon does not look updated
- Rebuild from project root so `transcriby/resources/Icona.ico` is included
- Unpin and re-pin the app from taskbar
- If needed, restart Explorer (`explorer.exe`) to refresh Windows icon cache

### "Module not found" error
- Make sure you installed all requirements: `pip install -r requirements.txt`
- Ensure your virtual environment is activated

### "yt-dlp not found" error
- Install yt-dlp: `pip install yt-dlp`
- Or download from https://github.com/yt-dlp/yt-dlp/releases

### "PortAudio library not found" (Linux/WSL)
- This project no longer uses PortAudio. If you see this error, you are running an old build.

## Credits

- Original [SlowPlay](https://github.com/aFunkyBass/slowplay) by aFunkyBass
- Inspired by [Play It Slowly](https://github.com/jwagner/playitslowly) by Jonas Wagner

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).
See [COPYING](COPYING) for details.
