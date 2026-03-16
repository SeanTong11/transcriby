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
APP_USER_MODEL_ID = "SeanTong11.Transcriby"

INITIAL_GEOMETRY = "1280x860"
MIN_WINDOW_WIDTH = 1120
MIN_WINDOW_HEIGHT = 760

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

# UI theme tokens (vintage radio amber)
UI_BG_APP = "#17120D"
UI_BG_CARD = "#231C15"
UI_BG_CARD_ALT = "#2D241B"
UI_BG_INPUT = "#19130E"
UI_BORDER_COLOR = "#5A4B35"
UI_TEXT_PRIMARY = "#F2E5C6"
UI_TEXT_MUTED = "#C9B58E"

UI_ACCENT = "#D7BE84"
UI_ACCENT_HOVER = "#C5A86A"
UI_SUCCESS = "#CDB07A"
UI_SUCCESS_HOVER = "#B6965F"
UI_DANGER = "#9F5C4C"
UI_DANGER_HOVER = "#854939"
UI_FAVORITE_COLORS = (
    "#59D1D9",
    "#FF9F5A",
    "#F97316",
    "#EAB308",
    "#F59E0B",
    "#6EE7B7",
)

# Timeline/loop overlay tokens
UI_TIMELINE_BG = "#14100C"
UI_TIMELINE_LOOP_FILL = "#5E482A"
UI_TIMELINE_LOOP_MARKER = "#F2D89A"
UI_TIMELINE_SELECT_FILL = "#3A2D1D"
UI_TIMELINE_SELECT_MARKER = "#E6C37C"
UI_TIMELINE_PLAYHEAD = "#FFF1CC"

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

DEFAULT_SEEK_STEP_FINE_MS = 100
DEFAULT_SEEK_STEP_COARSE_MS = 1000
MIN_SEEK_STEP_MS = 10
MAX_SEEK_STEP_MS = 60000

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

# Defines the minimum gap for loop, which is the gap between loop start and loop end
# Also it defines the minimum distance from the loop end and the song end.
#
# Since the song control routine runs every UPDATE_INTERVAL, we define this gap
# to be at least twice as much, to make sure it will fall in one of the
# routine execution time.
LOOP_MINIMUM_GAP = ((UPDATE_INTERVAL * 4) / 1000)     # Loop minimum gap in seconds

MOVE_LOOP_POINTS_COARSE = 100       # Milliseconds to move back and forward loop boundaries (coarse)
MOVE_LOOP_POINTS_FINE   = 10        # Milliseconds to move back and forward loop boundaries (fine)
