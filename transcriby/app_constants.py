from transcriby.build_version import (
    APP_VERSION,
    APP_BASE_VERSION,
    BUILD_CHANNEL,
    BUILD_TAG,
    BUILD_COMMIT,
)

# Definitions

APP_TITLE = "Transcriby"
APP_NAME = "transcriby"
APP_DESCRIPTION = "Transcriby is a simple audio player with speed/pitch \
change capabilities, using mpv (libmpv)."

APP_URL = "https://github.com/SeanTong11/transcriby"

INITIAL_GEOMETRY = "1000x620"
MIN_WINDOW_WIDTH = 920
MIN_WINDOW_HEIGHT = 560

THEME_NAME = "clam"         # tkInter Theme
LBL_FONT_SIZE = 14          # Label standard size
TITLE_FONT_SIZE = 30
WAVEFORM_HEIGHT = 132

UI_OUTER_PAD = 12
UI_INNER_PAD = 10
UI_CONTROL_PAD_Y = 6

MAIN_BUTTON_FONT_SIZE = 20
SECONDARY_BUTTON_FONT_SIZE = 16
AUX_BUTTON_FONT_SIZE = 14

MAIN_BUTTON_HEIGHT = 52
SECONDARY_BUTTON_HEIGHT = 38
AUX_BUTTON_HEIGHT = 32
ICON_BUTTON_WIDTH = 40
ICON_BUTTON_HEIGHT = 38

# UI theme tokens (dark mode)
UI_BG_APP = "#11161D"
UI_BG_CARD = "#1A222C"
UI_BG_CARD_ALT = "#22303C"
UI_BG_INPUT = "#121A23"
UI_BORDER_COLOR = "#334659"
UI_TEXT_PRIMARY = "#EAF2FA"
UI_TEXT_MUTED = "#A5B7C8"

UI_ACCENT = "#2FB8A3"
UI_ACCENT_HOVER = "#229985"
UI_SUCCESS = "#26C7AE"
UI_SUCCESS_HOVER = "#1EA48F"
UI_DANGER = "#B23A48"
UI_DANGER_HOVER = "#8A2E38"

UI_CARD_RADIUS = 14
UI_INPUT_RADIUS = 8

DEFAULT_SPEED = 1.0         # Default speed (x)
SPEED_SLIDER_MIN = 0.0      # UI-only slider minimum, keeps 1.0 centered on the track
MIN_SPEED_PERCENT = 0.1     # Minimum speed (x)
MAX_SPEED_PERCENT = 2.0     # Maximum speed (x)
STEPS_SPEED = 0.1           # Speed incr/decr steps (x)

DEFAULT_SEMITONES = 0       # Default semitone transpose (0 = no transpose)
MIN_PITCH_SEMITONES = -12   # Maximum semitones transpose down
MAX_PITCH_SEMITONES = 12    # Maximum semitones transpose up
STEPS_SEMITONES = 1         # Transpose incr/decr steps (semitones)

DEFAULT_CENTS = 0           # Default detune in cents (0 = no detune)
MIN_PITCH_CENTS = -50       # Maximum detune down (cents)
MAX_PITCH_CENTS = 50        # Maximum detune up (cents)

DEFAULT_VOLUME = 100
MIN_VOLUME = 0
MAX_VOLUME = 200

STEPS_SEC_MOVE_1 = 5        # Seconds to move using the num keypad +/- min
STEPS_SEC_MOVE_2 = 10       # Seconds to move using the num keypad +/- med
STEPS_SEC_MOVE_3 = 15       # Seconds to move using the num keypad +/- max

# Song position update interval in milliseconds
UPDATE_INTERVAL = 20

# Status bar message disappear time
STATUS_BAR_TIMEOUT = 3000

# Allowed audio files extensions (open)
OPEN_EXTENSIONS_FILTER = (
    'mp3',
    'wav',
    'flac',
    'aif',
    'ogg',
    'aac',
    'alac',
    'wma',
    'm4a',
    'mp4',
    'm4v',
    'mkv'
)

# Allowed audio files extensions (save)
SAVE_EXTENSIONS_FILTER = (
    'mp3',
    'wav',
)

# Default save file extension
SAVE_DEFAULT_EXTENSION = "mp3"

# YouTube constants
YTDLP_CMD = "yt-dlp"                   # Command to execute for video managing
YT_AUDIO_FORMAT_PRESET = "aac"         # default audio extraction format 
YT_AUDIO_FORMAT_EXTENSION = "m4a"      # default extracted audio extension
YT_THUMB_FORMAT_EXTENSION = "png"      # default thumbnail extraction format
YT_AUDIO_FILE_PREFIX = "trYT_"


# Defines the minimum gap for loop, which is the gap between loop start and loop end
# Also it defines the minimum distance from the loop end and the song end.
#
# Since the song control routine runs every UPDATE_INTERVAL, we define this gap
# to be at least twice as much, to make sure it will fall in one of the
# routine execution time.
LOOP_MINIMUM_GAP = ((UPDATE_INTERVAL * 4) / 1000)     # Loop minimum gap in seconds

MOVE_LOOP_POINTS_COARSE = 100       # Milliseconds to move back and forward loop boundaries (coarse)
MOVE_LOOP_POINTS_FINE   = 10        # Milliseconds to move back and forward loop boundaries (fine)
