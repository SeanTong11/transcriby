#!/usr/bin/env python3
#
# https://tkinterexamples.com/
# https://deepwiki.com/TomSchimansky/CustomTkinter/1-overview
#
#import tkinter as tk
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from CTkToolTip import *
#from tkinter import ttk
from tkinter import PhotoImage
import datetime as dt
import os
import argparse
import ctypes
from PIL import Image
import re
import sys, pathlib
from math import floor

import gettext
_ = gettext.gettext

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from transcriby.app_constants import *
from transcriby.platform_utils import (
    uri_from_path,
    is_valid_absolute_path,
    is_windows,
    is_wsl,
    get_resources_dir,
    get_locales_dir,
)
from transcriby import utils
from transcriby.player import slowPlayer
from transcriby import filedialogs
from transcriby.appsettings import *
from transcriby import recentdialog
from transcriby import aboutdialog
from transcriby import ytmanage
from transcriby.waveform import WaveformWidget

# Lazy import tkinterdnd2 to avoid X11 threading issues on WSL
# 
# Issue: On WSL, TkinterDnD._require() triggers a crash with:
#   [xcb] Unknown sequence number while appending request
#   python3: ../../src/xcb_io.c:157: append_pending_request: 
#   Assertion `!xcb_xlib_unknown_seq_number' failed.
#
# This is a known WSL-specific compatibility issue with tkinterdnd2
# and the X11 display server. Native Linux is not affected.
#
# Workaround: Dynamically select base class based on platform.
if is_wsl():
    # WSL: No DnD support to avoid X11 crash
    _AppBase = ctk.CTk
    _dnd_available = False
else:
    # Windows/Native Linux: Full DnD support
    from tkinterdnd2 import TkinterDnD
    class _AppBase(ctk.CTk, TkinterDnD.DnDWrapper):
        pass
    _dnd_available = True

class App(_AppBase):
    def __init__(self, args, *orig_args, **orig_kwargs):
        super().__init__(className=APP_TITLE, *orig_args, **orig_kwargs)
        # Initialize drag and drop on supported platforms
        if _dnd_available:
            self.TkdndVersion = TkinterDnD._require(self)

        # Load app settings
        self.settings = AppSettings()
        self.settings.loadSettings()

        # Mark app directories
        resources_dir = get_resources_dir()

        # Localizations
        gettext.bindtextdomain('slowplay', get_locales_dir())
        gettext.textdomain('slowplay')

        # Sets app title and window size
        self.geometry(INITIAL_GEOMETRY)
        self.title(APP_TITLE)

        # Sets the app icon
        self.wm_iconphoto(True, PhotoImage(file=os.path.join(resources_dir, "Icona-32.png")))
        if is_windows():
            icon_ico = os.path.join(resources_dir, "Icona.ico")
            if os.path.exists(icon_ico):
                try:
                    self.iconbitmap(icon_ico)
                except Exception:
                    pass

            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SeanTong11.Transcriby")
            except Exception:
                pass

        # Initialize the audio player
        self.player = slowPlayer()
        self.player.updateInterval = UPDATE_INTERVAL

        # set style and theme
        ctk.set_appearance_mode("Dark")

        # Loads the reset buttons icon
        resetIcon = ctk.CTkImage(
            light_image=Image.open(os.path.join(resources_dir, "Reset Icon.png")),
            dark_image=Image.open(os.path.join(resources_dir, "Reset Icon.png")),
            size=(16, 16),
        )

        # tkInter auto-variables
        self.songTime = ctk.StringVar(self)                 # Holds the song time clock
        self.songTime.set(dt.timedelta(seconds = 0))
        self.songProgress = ctk.DoubleVar(self, value=0)    # Holds the value of progress bar
        self.songProgress.set(0)

        # Global variables
        self.media = ""                     # Media complete name
        self.mediaUri = ""                  # Media URI
        self.mediaFileName = ""             # Media simple filename
        self.mediaPath = ""                 # Media absolute path

        self.bValuesChanging = False        # Flag turned when the user is changing some values
                                            # used to stop automatic updates

        self.afterCancelID = ""             # ID of the last scheduled after action

        self.bStatusBarTags = False         # Flag for the update of artist/song tags 
                                            # on the status bar

        self.songMetadata = ""              # Metadata for the songs

        self.bYouTubeFile = False           # Flag is True when the media is a YouTube video
        self.YouTubeUrl = ""                # Actual YouTube URL

        self.lastPlayingState = False       # Last status of the player

        # Build the 3 main frames: Left (shrinkable), Right (buttons)
        # and low (status ba
        self.LFrame = ctk.CTkFrame(self, width=400, height=200)
        self.RFrame = ctk.CTkFrame(self)
        self.BFrame = ctk.CTkFrame(self, height=24)

        self.LFrame.grid(row=0, column=0, sticky="nsew", padx=UI_OUTER_PAD, pady=UI_OUTER_PAD)
        self.RFrame.grid(row=0, column=1, sticky="nsew", padx=UI_OUTER_PAD, pady=UI_OUTER_PAD)
        self.BFrame.grid(row=1, column=0, columnspan=2, sticky="nsew")

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Widgets on left panel
        self.dispPosition = ctk.CTkLabel(self.LFrame, textvariable=self.songTime, font=("", TITLE_FONT_SIZE))
        self.dispPosition.grid(row=0, column=0, pady=[UI_INNER_PAD, 0], sticky="n")

        self.progress = ctk.CTkProgressBar(self.LFrame, variable=self.songProgress, height=24)
        self.progress.grid(row=1, column=0, padx=UI_INNER_PAD, pady=UI_INNER_PAD, sticky="ew")

        self.scale = ctk.CTkSlider(self.LFrame, command=self.songSeek)
        self.scale.grid(row=2, column=0, padx=UI_INNER_PAD, sticky="ew")

        self.waveform = WaveformWidget(
            self.LFrame,
            on_seek=self.waveformSeek,
            on_status=self.waveformStatus,
            height=WAVEFORM_HEIGHT,
        )
        self.waveform.grid(row=3, column=0, padx=UI_INNER_PAD, pady=(UI_INNER_PAD, 0), sticky="ew")

        self.CTLFrame = ctk.CTkFrame(self.LFrame)
        self.CTLFrame.grid(row=4, column=0, padx=UI_INNER_PAD, pady=UI_INNER_PAD, sticky="nsew")
        self.PlaybackTab = self.CTLFrame

        self.LFrame.grid_columnconfigure(0, weight=1)
        self.LFrame.grid_rowconfigure(4, weight=1)

        # Widgets on Playback Tab
        #vint = (self.register(self.validate_int),'%d','%i','%P','%s','%S','%v','%V','%W')
        vint = (self.register(self.validate_int),'%S')
        self.varSpeed = ctk.IntVar(self, value=DEFAULT_SPEED)
        self.varSpeed.trace_add("write", self.speedChanged)
        self.lblSpeed = ctk.CTkLabel(self.PlaybackTab, text=_("Speed:"), font=("", LBL_FONT_SIZE))
        self.lblSpeed.grid(row=0, column=0, pady=(UI_CONTROL_PAD_Y, 0), sticky="w")
        self.sldSpeed = ctk.CTkSlider(self.PlaybackTab, from_=MIN_SPEED_PERCENT,
                                      to=MAX_SPEED_PERCENT, number_of_steps=20, variable=self.varSpeed)
        self.sldSpeed.grid(row=0, column=1, padx=UI_INNER_PAD, sticky="ew")
        self.entSpeed = ctk.CTkEntry(self.PlaybackTab, width=56, justify="center",
                                     validate='key', validatecommand=vint)
        self.entSpeed.grid(row=0, column=2, padx=UI_INNER_PAD, pady=UI_CONTROL_PAD_Y, sticky="w")
        self.lblSpeedEntry = ctk.CTkLabel(self.PlaybackTab, text="%", font=("", LBL_FONT_SIZE))
        self.lblSpeedEntry.grid(row=0, column=3, padx=(0, UI_INNER_PAD), pady=UI_CONTROL_PAD_Y, sticky="w")
        self.btnResetSpeed = ctk.CTkButton(self.PlaybackTab, width=42, image=resetIcon,
                                           text=None, command= lambda: self.resetDefaultVar(self.varSpeed))
        self.btnResetSpeed.grid(row=0, column=4, padx=(0, UI_INNER_PAD), pady=UI_CONTROL_PAD_Y, sticky="w")
        self.btnResetSpeed_tt = CTkToolTip(self.btnResetSpeed, message=_("Reset speed"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)
        self.entSpeed.bind('<Return>', self.checkSpeed)
        self.entSpeed.bind('<KP_Enter>', self.checkSpeed)
        self.entSpeed.bind('<FocusOut>', self.checkSpeed)

        #vnegint = (self.register(self.validate_neg_int),'%d','%i','%P','%s','%S','%v','%V','%W')
        vnegint = (self.register(self.validate_neg_int),'%S', '%P')
        self.varPitchST = ctk.IntVar(self, value=DEFAULT_SEMITONES)
        self.varPitchST.trace_add("write", self.semitonesChanged)
        self.lblPitchST = ctk.CTkLabel(self.PlaybackTab, text=_("Transpose:"), font=("", LBL_FONT_SIZE))
        self.lblPitchST.grid(row=1, column=0, pady=(UI_CONTROL_PAD_Y, 0), sticky="w")
        self.sldPitchST = ctk.CTkSlider(self.PlaybackTab,from_= MIN_PITCH_SEMITONES,
                                        to = MAX_PITCH_SEMITONES, variable=self.varPitchST)
        self.sldPitchST.grid(row=1, column=1, padx=UI_INNER_PAD, sticky="ew")
        self.entPitchST = ctk.CTkEntry(self.PlaybackTab, width=56, justify="center",
                                       validate='all', validatecommand=vnegint)
        self.entPitchST.grid(row=1, column=2, padx=UI_INNER_PAD, pady=UI_CONTROL_PAD_Y, sticky="w")
        self.lblPitchSTEntry = ctk.CTkLabel(self.PlaybackTab, text="s/t", font=("", LBL_FONT_SIZE))
        self.lblPitchSTEntry.grid(row=1, column=3, padx=(0, UI_INNER_PAD), pady=UI_CONTROL_PAD_Y, sticky="w")
        self.btnResetPitchST = ctk.CTkButton(self.PlaybackTab, width=42, image=resetIcon,
                                             text=None, command= lambda: self.resetDefaultVar(self.varPitchST))
        self.btnResetPitchST.grid(row=1, column=4, padx=(0, UI_INNER_PAD), pady=UI_CONTROL_PAD_Y, sticky="w")
        self.btnResetPitchST_tt = CTkToolTip(self.btnResetPitchST, message=_("Reset transpose"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)
        self.entPitchST.bind('<Return>', self.checkSemitones)
        self.entPitchST.bind('<KP_Enter>', self.checkSemitones)
        self.entPitchST.bind('<FocusOut>', self.checkSemitones)

        self.varPitchCents = ctk.IntVar(self, value=DEFAULT_CENTS)
        self.varPitchCents.trace_add("write", self.centsChanged)
        self.lblPitchCents = ctk.CTkLabel(self.PlaybackTab, text=_("Pitch (cents):"), font=("", LBL_FONT_SIZE))
        self.lblPitchCents.grid(row=2, column=0, pady=(UI_CONTROL_PAD_Y, 0), sticky="w")
        self.sldPitchCents = ctk.CTkSlider(self.PlaybackTab,from_= MIN_PITCH_CENTS,
                                           to = MAX_PITCH_CENTS, variable=self.varPitchCents)
        self.sldPitchCents.grid(row=2, column=1, padx=UI_INNER_PAD, sticky="ew")
        self.entPitchCents = ctk.CTkEntry(self.PlaybackTab, width=56, justify="center",
                                          validate='all', validatecommand=vnegint)
        self.entPitchCents.grid(row=2, column=2, padx=UI_INNER_PAD, pady=UI_CONTROL_PAD_Y, sticky="w")
        self.lblPitchCentsEntry = ctk.CTkLabel(self.PlaybackTab, text="c.", font=("", LBL_FONT_SIZE))
        self.lblPitchCentsEntry.grid(row=2, column=3, padx=(0, UI_INNER_PAD), pady=UI_CONTROL_PAD_Y, sticky="w")
        self.btnResetPitchCents = ctk.CTkButton(self.PlaybackTab, width=42, image=resetIcon, text=None,
                                                command= lambda: self.resetDefaultVar(self.varPitchCents))
        self.btnResetPitchST_tt = CTkToolTip(self.btnResetPitchCents, message=_("Reset pitch"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)
        self.btnResetPitchCents.grid(row=2, column=4, padx=(0, UI_INNER_PAD), pady=UI_CONTROL_PAD_Y, sticky="w")
        self.entPitchCents.bind('<Return>', self.checkCents)
        self.entPitchCents.bind('<KP_Enter>', self.checkCents)
        self.entPitchCents.bind('<FocusOut>', self.checkCents)

        self.varVolume = ctk.IntVar(self, value=DEFAULT_VOLUME)
        self.varVolume.trace_add("write", self.volumeChanged)
        self.lblVolume = ctk.CTkLabel(self.PlaybackTab, text=_("Volume:"), font=("", LBL_FONT_SIZE))
        self.lblVolume.grid(row=3, column=0, pady=(UI_CONTROL_PAD_Y, 0), sticky="w")
        self.sldVolume = ctk.CTkSlider(self.PlaybackTab,from_= MIN_VOLUME,
                                           to = MAX_VOLUME, variable=self.varVolume)
        self.sldVolume.grid(row=3, column=1, padx=UI_INNER_PAD, sticky="ew")
        self.entVolume = ctk.CTkEntry(self.PlaybackTab, width=56, justify="center",
                                          validate='all', validatecommand=vint)
        self.entVolume.grid(row=3, column=2, padx=UI_INNER_PAD, pady=UI_CONTROL_PAD_Y, sticky="w")
        self.entVolume.bind('<Return>', self.checkVolume)
        self.entVolume.bind('<KP_Enter>', self.checkVolume)
        self.entVolume.bind('<FocusOut>', self.checkVolume)
        self.PlaybackTab.columnconfigure(1, weight=1)

        self.speedChanged(None, None, None)
        self.semitonesChanged(None, None, None)
        self.centsChanged(None, None, None)
        self.volumeChanged(None, None, None)

        # Inline loop controls
        self.lblLoopControls = ctk.CTkLabel(self.PlaybackTab, text=_("Loop control"), font=("", LBL_FONT_SIZE))
        self.lblLoopControls.grid(row=4, column=0, pady=(UI_INNER_PAD + 2, 0), sticky="w")

        self.loopControlsFrame = ctk.CTkFrame(self.PlaybackTab, fg_color="transparent")
        self.loopControlsFrame.grid(row=5, column=0, columnspan=5, pady=(0, UI_INNER_PAD), sticky="ew")
        self.loopControlsFrame.grid_columnconfigure(1, weight=1)

        self.loopAFrame = ctk.CTkFrame(self.loopControlsFrame, fg_color="transparent")
        self.loopAFrame.grid(row=0, column=0, pady=8, sticky="w")

        self.lblLoopStart = ctk.CTkLabel(self.loopAFrame, anchor="w", width=80, font=("", LBL_FONT_SIZE),
                                         text="---")
        self.btnResetLoopStart = ctk.CTkButton(self.loopAFrame, width=42, image=resetIcon, text=None,
                                               command=lambda: self.setLoopStart(0))
        self.btnResetLoopStart_tt = CTkToolTip(self.btnResetLoopStart, message=_("Reset loop start point\nShortcut: Ctrl+A"),
                                            delay=0.8, alpha=0.5, justify="left", follow=False)
        self.btnLoopASet = ctk.CTkButton(self.loopAFrame, width=42, text=" | ", font=("", LBL_FONT_SIZE),
                                         command=lambda: self.setLoopStart(self.player.query_position()))
        self.btnLoopASet_tt = CTkToolTip(self.btnLoopASet, message=_("Set loop start point\nShortcut: A"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)
        
        self.btnLoopABack2 = ctk.CTkButton(self.loopAFrame, width=42, text="<<", font=("", LBL_FONT_SIZE),
                                           command=lambda: self.moveLoopStart(-MOVE_LOOP_POINTS_COARSE))
        self.btnLoopABack2_tt = CTkToolTip(self.btnLoopABack2, message=_("Move loop start left by") + f" {MOVE_LOOP_POINTS_COARSE} " + _("milliseconds"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)
        self.btnLoopABack1 = ctk.CTkButton(self.loopAFrame, width=42, text="<", font=("", LBL_FONT_SIZE),
                                            command=lambda: self.moveLoopStart(-MOVE_LOOP_POINTS_FINE))
        self.btnLoopABack1_tt = CTkToolTip(self.btnLoopABack1, message=_("Move loop start left by") + f" {MOVE_LOOP_POINTS_FINE} " + _("milliseconds"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)
        self.btnLoopAFwd1 = ctk.CTkButton(self.loopAFrame, width=42, text=">", font=("", LBL_FONT_SIZE),
                                          command=lambda: self.moveLoopStart(MOVE_LOOP_POINTS_FINE))
        self.btnLoopAFwd1_tt = CTkToolTip(self.btnLoopAFwd1, message=_("Move loop start right by") + f" {MOVE_LOOP_POINTS_FINE} " + _("milliseconds"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)
        self.btnLoopAFwd2 = ctk.CTkButton(self.loopAFrame, width=42, text=">>", font=("", LBL_FONT_SIZE),
                                          command=lambda: self.moveLoopStart(MOVE_LOOP_POINTS_COARSE))
        self.btnLoopAFwd2_tt = CTkToolTip(self.btnLoopAFwd2, message=_("Move loop start right by") + f" {MOVE_LOOP_POINTS_COARSE} " + _("milliseconds"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)

        self.lblLoopStart.grid(row = 0, column = 0, columnspan=2)
        self.btnResetLoopStart.grid(row = 0, column = 2, padx=(4, 0))
        self.btnLoopASet.grid(row = 0, column = 3, padx=(4, 0))
        self.btnLoopABack2.grid(row = 1, column = 0, pady = (8, 0))
        self.btnLoopABack1.grid(row = 1, column = 1, padx=(4, 0), pady = (8, 0))
        self.btnLoopAFwd1.grid(row = 1, column = 2, padx=(4, 0), pady = (8, 0))
        self.btnLoopAFwd2.grid(row = 1, column = 3, padx=(4, 0), pady = (8, 0))

        self.loopBFrame = ctk.CTkFrame(self.loopControlsFrame, fg_color="transparent")
        self.loopBFrame.grid(row=0, column=2, pady=8, sticky="e")

        self.lblLoopEnd = ctk.CTkLabel(self.loopBFrame, anchor="e", width=80, font=("", LBL_FONT_SIZE),
                                       text="---")
        self.btnResetLoopEnd = ctk.CTkButton(self.loopBFrame, width=42, image=resetIcon, text=None,
                                             command=lambda: self.setLoopEnd(self.player.query_duration()))
        self.btnResetLoopStart_tt = CTkToolTip(self.btnResetLoopEnd, message=_("Reset loop end point\nShortcut: Ctrl+B"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)
        self.btnLoopBSet = ctk.CTkButton(self.loopBFrame, width=42, text=" | ", font=("", LBL_FONT_SIZE), 
                                         command=lambda: self.setLoopEnd(self.player.query_position()))
        self.btnLoopBSet_tt = CTkToolTip(self.btnLoopBSet, message=_("Set loop end point\nShortcut: B"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)

        self.btnLoopBBack2 = ctk.CTkButton(self.loopBFrame, width=42, text="<<", font=("", LBL_FONT_SIZE),
                                           command=lambda: self.moveLoopEnd(-MOVE_LOOP_POINTS_COARSE))
        self.btnLoopBBack2_tt = CTkToolTip(self.btnLoopBBack2, message=_("Move loop end left by") + f" {MOVE_LOOP_POINTS_COARSE} " + _("milliseconds"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)
        self.btnLoopBBack1 = ctk.CTkButton(self.loopBFrame, width=42, text="<", font=("", LBL_FONT_SIZE),
                                           command=lambda: self.moveLoopEnd(-MOVE_LOOP_POINTS_FINE))
        self.btnLoopBBack1_tt = CTkToolTip(self.btnLoopBBack1, message=_("Move loop end left by") + f" {MOVE_LOOP_POINTS_FINE} " + _("milliseconds"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)
        self.btnLoopBFwd1 =  ctk.CTkButton(self.loopBFrame, width=42, text=">", font=("", LBL_FONT_SIZE),
                                           command=lambda: self.moveLoopEnd(MOVE_LOOP_POINTS_FINE))
        self.btnLoopBFwd1_tt = CTkToolTip(self.btnLoopBFwd1, message=_("Move loop end right by") + f" {MOVE_LOOP_POINTS_FINE} " + _("milliseconds"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)
        self.btnLoopBFwd2 =  ctk.CTkButton(self.loopBFrame, width=42, text=">>", font=("", LBL_FONT_SIZE),
                                           command=lambda: self.moveLoopEnd(MOVE_LOOP_POINTS_COARSE))
        self.btnLoopBFwd2_tt = CTkToolTip(self.btnLoopBFwd2, message=_("Move loop end right by") + f" {MOVE_LOOP_POINTS_COARSE} " + _("milliseconds"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)

        self.btnLoopBSet.grid(row = 0, column = 0, padx=(4, 0))
        self.btnResetLoopEnd.grid(row = 0, column = 1, padx=(4, 0))
        self.lblLoopEnd.grid(row = 0, column = 2, columnspan=2)
        self.btnLoopBBack2.grid(row = 1, column = 0, pady = (8, 0))
        self.btnLoopBBack1.grid(row = 1, column = 1, padx=(4, 0), pady = (8, 0))
        self.btnLoopBFwd1.grid(row = 1, column = 2, padx=(4, 0), pady = (8, 0))
        self.btnLoopBFwd2.grid(row = 1, column = 3, padx=(4, 0), pady = (8, 0))

        self.loopCenterFrame = ctk.CTkFrame(self.loopControlsFrame, fg_color="transparent", bg_color="transparent")
        self.loopCenterFrame.grid(row=0, column=1, pady=8, sticky="nsew")
        
        self.swtLoopEnabled = ctk.CTkSwitch(self.loopCenterFrame, text=_("Enable loop"),
                                            onvalue=True, offvalue=False, font=("", LBL_FONT_SIZE),
                                            command=self.loopToggle)
        self.swtLoopEnabled.pack(anchor = "n")
        self.swtLoopEnabled_tt = CTkToolTip(self.swtLoopEnabled, message=_("Toggle loop playing\nShortcut: L"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)

        # Widgets on right panel
        self.loopIcon = ctk.CTkImage(
            light_image=Image.open(os.path.join(resources_dir, "Loop Icon.png")),
            dark_image=Image.open(os.path.join(resources_dir, "Loop Icon.png")),
            size=(26, 16),
        )

        self.playButton = ctk.CTkButton(self.RFrame, text=_("Play"), font=("", 18), 
                                        image=None, compound="right", command=self.togglePlay)
        self.playButton.configure(
            height=MAIN_BUTTON_HEIGHT,
            font=("", MAIN_BUTTON_FONT_SIZE),
            fg_color="#2F5D95",
            hover_color="#23436C",
        )
        self.playButton.grid(row=0, column=0, pady=(UI_INNER_PAD, 0), sticky="ew", columnspan=2)
        self.playButton_tt = CTkToolTip(self.playButton, message=_("Play/Pause"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)

        self.openButton = ctk.CTkButton(self.RFrame, text=_("Open"), font=("", SECONDARY_BUTTON_FONT_SIZE), 
                                        command=self.openFile, width=110)
        self.openButton.configure(height=SECONDARY_BUTTON_HEIGHT)
        self.openButton.grid(row=1, column=0, pady=(UI_INNER_PAD, 0), sticky="ew")
        self.openButton_tt = CTkToolTip(self.openButton, message=_("Open a file.\nRight-click to reopen a recent file"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)

        # Activate the recent file list with right-click
        self.openButton.bind("<Button-3>", self.openRecentFileDialog)

        YTIcon = ctk.CTkImage(
            light_image=Image.open(os.path.join(resources_dir, "YT_ico.png")),
            dark_image=Image.open(os.path.join(resources_dir, "YT_ico.png")),
            size=(23, 16),
        )

        self.YTBtn = ctk.CTkButton(self.RFrame, text="", width=ICON_BUTTON_WIDTH, font=("", SECONDARY_BUTTON_FONT_SIZE),
                                       image=YTIcon, command= lambda: self.openYouTubeDialog(None))
        self.YTBtn.configure(height=ICON_BUTTON_HEIGHT)
        self.YTBtn.grid(row=1, column=1, sticky="e", pady=(UI_INNER_PAD, 0), padx=(UI_INNER_PAD, 0))
        self.YTBtn_tt = CTkToolTip(self.YTBtn, message=_("Click to extract audio from a YouTube video"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)

        self.saveasButton = ctk.CTkButton(
            self.RFrame,
            text=_("Save as..."),
            font=("", SECONDARY_BUTTON_FONT_SIZE),
            command=self.saveAs,
            height=SECONDARY_BUTTON_HEIGHT,
        )
        self.saveasButton.grid(row=2, column=0, pady=UI_INNER_PAD, sticky="ew", columnspan=2)
        self.saveasButton_tt = CTkToolTip(self.saveasButton, message=_("Save the file with current speed/pitch settings as MP3 or WAV"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)

        self.aboutButton = ctk.CTkButton(
            self.RFrame,
            text=_("About"),
            font=("", AUX_BUTTON_FONT_SIZE),
            command=self.openAboutDialog,
            height=AUX_BUTTON_HEIGHT,
            fg_color="transparent",
            border_width=1,
            border_color="#4A4D55",
        )
        self.aboutButton.grid(row=3, column=0, pady=(UI_INNER_PAD, UI_INNER_PAD), sticky="sew", columnspan=2)
        self.aboutButton_tt = CTkToolTip(self.aboutButton, message=_("Show info about this software"),
                                        delay=0.8, alpha=0.5, justify="left", follow=False)
        
        self.RFrame.rowconfigure(3, weight=1)
        self.RFrame.columnconfigure(0, weight=1)

        # Widget on status bar
        self.fileLabel = ctk.CTkLabel(self.BFrame, text="", font=("", LBL_FONT_SIZE))
        self.fileLabel.grid(row=0, column=0, padx=(8), sticky="w")
        self.BFrame.columnconfigure(0, weight=1)

        self.dispSongTime(Force=True)

        self.update()
        self.minsize(max(self.winfo_width(), MIN_WINDOW_WIDTH), max(self.winfo_height(), MIN_WINDOW_HEIGHT))

        # Check if the user asked to delete the recent file list
        if(args.delete_recent is not None and args.delete_recent == True):
            self.settings.resetSettings(True)

        # Check if a filename is passed from the command line
        if(args.media != None):
            self.setFile(args.media)
        else:
            # If no file is specified tries to load the last played media
            lastPlayed = self.settings.getLastPlayedFilename()

            # Gather information about the last played file
            # if it is a YouTube video does not automatically load
            if(lastPlayed is not None):
                filePlabackOptions = self.settings.getRecentFile(lastPlayed)
                if(filePlabackOptions is not None and isinstance(filePlabackOptions, dict)):
                    # Check for local file or youtube url
                    if(PBO_DEF_YOUTUBE in filePlabackOptions and filePlabackOptions[PBO_DEF_YOUTUBE] == True):
                        pass
                        #self.setYouTubeUrl(lastPlayed, filePlabackOptions[PBO_DEF_METADATA])
                    else:
                        self.setFile(lastPlayed)

    # Open file selection and sets it for playback
    def openFile(self):
        newfile = self.selectFileToOpen()
        if(newfile != ""):
            self.bYouTubeFile = False
            self.YouTubeUrl = ""
            self.setFile(newfile)

    # Open the file selection dialog
    def selectFileToOpen(self) -> str:
        # Temporarily disables all the keypress and mouse binding
        self.unbind_all('<KeyPress>')
        self.unbind_all('<1>')
        try:
            filename = filedialogs.openFileDialog(
                title = _('Open a file'),
                initialdir = self.settings.getVal(CFG_APP_SECTION, "LastOpenDir", os.path.expanduser("~")),
                filter = OPEN_EXTENSIONS_FILTER)
        finally:
            self.bind_all('<1>', self._click_manager_)
            self.bind_all('<KeyPress>', self._hotkey_manager_)

        return(filename)

    # Reset all values
    def resetValues(self):
        self.player.startPoint = -2
        self.player.endPoint = -1
        self.waveform.clear()
        self.loopToggle(bForceDisable = True)
        self.Pause()
        self.player.Rewind()
        self.varSpeed.set(DEFAULT_SPEED)
        self.varPitchST.set(DEFAULT_SEMITONES)
        self.varPitchCents.set(DEFAULT_CENTS)
        self.songProgress.set(0)
        self.songTime.set(dt.timedelta(seconds = 0))
        self.scale.set(0)
        self.bStatusBarTags = False

    def filename2Uri(self, fname):
        # Compose a valid uri
        if is_valid_absolute_path(fname):
            Uri = uri_from_path(fname)
        else:
            Uri = fname

        return(Uri)

    # Ask the player to load the selected file
    # and prepares it to play
    def setFile(self, filename):
        #print(filename)
        if(not filename or filename == ''):
            return
        elif not os.path.isfile(filename):
            # On Windows, path may be returned with forward slashes from dialog
            # Try normalizing it
            if is_windows():
                filename = os.path.normpath(filename)
                if not os.path.isfile(filename):
                    CTkMessagebox(master = self, title = _("Error: file not found"), 
                                  message=_("Unable to open file: {}").format(filename),
                                  icon = "cancel", font = ("", LBL_FONT_SIZE))
                    return
            else:
                CTkMessagebox(master = self, title = _("Error: file not found"), 
                              message=_("Unable to open file: {}").format(filename),
                              icon = "cancel", font = ("", LBL_FONT_SIZE))
                return

        # Saves the path and name of the selected file
        self.media = os.path.realpath(filename)
        self.mediaFileName = os.path.basename(self.media)
        self.mediaPath = os.path.dirname(self.media)
        if(self.bYouTubeFile == False):
            self.settings.setVal(CFG_APP_SECTION, "LastOpenDir", self.mediaPath)

        # Compose a valid uri
        self.mediaUri = self.filename2Uri(self.media)

        # Actually load the media
        self.player.MediaLoad(self.mediaUri)
        self.player.update_position()
        self.waveform.set_media(self.media)

        # Set the metadata only if it's not a Youtube downloaded file
        if(self.bYouTubeFile == False):
            self.songMetadata = self.mediaFileName
            self.title(f"{APP_TITLE} - {self.mediaFileName}")
            recentFileKey = self.media            
        else:
            #self.songMetadata = f"(YT) - {self.songMetadata}"
            self.title(f"{APP_TITLE} - {self.songMetadata}")
            recentFileKey = self.YouTubeUrl

        # Updates window title and status bar
        self.displaySongMetadata()

        # if the file was recently open, it loads its settings
        # otherwise saves it into the list
        filePlabackOptions = self.settings.getRecentFile(recentFileKey)

        if(filePlabackOptions is not None and isinstance(filePlabackOptions, dict)):
            self.settings.moveToLastPosition(recentFileKey)
            
            self.settings.bUpdateForbidden = True
            try:
                self.resetValues()
                
                if(filePlabackOptions[PBO_DEF_SPEED] in range(MIN_SPEED_PERCENT, MAX_SPEED_PERCENT + 1)):
                    self.varSpeed.set(filePlabackOptions[PBO_DEF_SPEED])

                if(filePlabackOptions[PBO_DEF_SEMITONES] in range(MIN_PITCH_SEMITONES, MAX_PITCH_SEMITONES + 1)):
                    self.varPitchST.set(filePlabackOptions[PBO_DEF_SEMITONES])

                if(filePlabackOptions[PBO_DEF_CENTS] in range(MIN_PITCH_CENTS, MAX_PITCH_CENTS + 1)):
                    self.varPitchCents.set(filePlabackOptions[PBO_DEF_CENTS])

                if(filePlabackOptions[PBO_DEF_VOLUME] in range(MIN_VOLUME, MAX_VOLUME + 1)):
                    self.varVolume.set(filePlabackOptions[PBO_DEF_VOLUME])
            finally:
                self.settings.bUpdateForbidden = False
        else:
            self.resetValues()
            self.setRecentFilePBOptions()

    # Saves the playback options to the recent files list
    def setRecentFilePBOptions(self):
        if(self.media == "" and self.YouTubeUrl == ""):
            return

        if(self.bYouTubeFile == True):
            fname = self.YouTubeUrl
        else:
            fname = self.media

        filePlabackOptions = {
                PBO_DEF_METADATA: self.songMetadata,
                PBO_DEF_YOUTUBE: self.bYouTubeFile,
                PBO_DEF_SPEED: self.varSpeed.get(),
                PBO_DEF_SEMITONES: self.varPitchST.get(),
                PBO_DEF_CENTS: self.varPitchCents.get(),
                PBO_DEF_VOLUME: self.varVolume.get()
            }

        self.settings.addRecentFile(fname, filePlabackOptions)

    # Saves an audio file with the pitch and tempo settings
    def saveAs(self):
        if(self.player.canPlay == False):
            self.statusBarMessage(_("Please open a file..."))
            return

        # Open the file dialog
        filename = self.selectFileToSave()

        if(filename is None or str(filename) == ""):
            return

        # Check for a valid path
        if(os.path.exists(os.path.dirname(filename)) == False):
            CTkMessagebox(master = self, title = _("Filename error..."), 
                          message = _("Unable to save file: {}").format(filename),
                          icon = "cancel", font=("", LBL_FONT_SIZE))
            return

        # Check for a valid extension and in case is not present
        # add the default one
        if(filename.endswith(SAVE_EXTENSIONS_FILTER) == False):
            filename += "." + SAVE_DEFAULT_EXTENSION

        # Check once again if the file exists and ask confirmation
        # to overwrite it
        if(os.path.isfile(filename)):
            res = CTkMessagebox(master = self, title = _("Overwrite confirmation"),
                                message = _("{}\nalready exists.\n\nDo you want to overwrite it?").format(filename),
                                icon = "warning", option_1 = "Yes", option_2="No", font = ("", LBL_FONT_SIZE),
                                option_focus = "2")
            if(res.get() != "Yes"):
                return

        self.Pause()

        # Create a progress bar on the bottom panel
        self.save_prg_var = ctk.DoubleVar(self, value=0)
        self.save_prg = ctk.CTkProgressBar(self.BFrame, variable=self.save_prg_var, height=10, width=80)
        self.save_prg.grid(row=0, column=1, padx=8, pady=10, sticky="e")

        # Sets a global variable to cancel the save process
        # and adds a button that handles it
        self.save_canc_var = False
        self.save_canc = ctk.CTkButton(self.BFrame, text="X", fg_color="#aa0000", hover_color="red", 
                                       height=8, width=10, command=self.saveCancelButtonClick)
        self.save_canc.grid(row=0, column=2, padx=8, pady=8, sticky="e")

        self.save_canc_tt = CTkToolTip(self.save_canc, message=_("Cancel file save"),
                                        delay=0.5, alpha=0.5, justify="left", follow=False)

        self.update_idletasks()

        # Saves the path for future saves
        self.settings.setVal(CFG_APP_SECTION, "LastSaveDir", os.path.dirname(filename))

        # Actually asks the player to save the file and destroy
        # the progress bar afterwards
        self.statusBarMessage(_("Saving file: {}...").format(filename), static = True)
        try:
            self.player.fileSave(self.media, filename, self.saveProgress)
        finally:
            self.save_prg.destroy()
            self.save_prg_var.__del__()
            self.save_canc.destroy()
            self.save_canc_tt.destroy()
            self.displaySongMetadata()

    # Open the save file dialog
    def selectFileToSave(self) -> str:
        # Temporarily disables all the keypress and mouse binding
        self.unbind_all('<KeyPress>')
        self.unbind_all('<1>')
        try:
            filename = filedialogs.saveFileDialog(
                title=_('Save as..'),
                initialfile = self.mediaFileName if self.bYouTubeFile == False else self.songMetadata + "." + SAVE_DEFAULT_EXTENSION,
                initialdir = self.settings.getVal(CFG_APP_SECTION, "LastSaveDir", os.path.expanduser("~")),
                filter = SAVE_EXTENSIONS_FILTER,
                overwrite = False)
        finally:
            self.bind_all('<1>', self._click_manager_)
            self.bind_all('<KeyPress>', self._hotkey_manager_)

        return(filename)

    # Open a dialog to download a YouTube audio
    def openYouTubeDialog(self, event):
        # Instanciate a YouTube Manager object
        manager = ytmanage.ytManage()

        if(manager.checkYTDLP() == False):
            # Unable to find yt-dlp
            a = CTkMessagebox(master = self, title = _("Error: unable to find ") + YTDLP_CMD, 
                          message=_("Please install ") + YTDLP_CMD + _(" on your system and retry."),
                          icon = "cancel", font = ("", LBL_FONT_SIZE))
            return(False)

        # Temporarily disables all the keypress and mouse binding
        self.unbind_all('<KeyPress>')
        self.unbind_all('<1>')
        try:
            popup = ytmanage.ytDialog(self)
            rUrl, videoInfo = popup.show()
        finally:
            self.bind_all('<1>', self._click_manager_)
            self.bind_all('<KeyPress>', self._hotkey_manager_)
        
        if(rUrl == False):
            return(False)

        # Return the url of the video and its Title
        self.setYouTubeUrl(url=rUrl, vinfo=videoInfo["title"])

    # Actually load a YouTube URL
    def setYouTubeUrl(self, url: str, vinfo: str):
        manager = ytmanage.ytManage(url)

        # Download the video into a temporary file
        if(manager.downloadAudioFile(process_callback = self.dispYoutubeProgress) == False):
            CTkMessagebox(master = self, title = _("Error"), 
                            message=_("Unable to download audio file from YouTube."),
                            icon = "cancel", font = ("", LBL_FONT_SIZE))
            return(False)

        # Set the flag for Youtube and saves the URL
        self.bYouTubeFile = True
        self.YouTubeUrl = url 

        # Uses the video title as metadata to be displayed
        # on the status bar
        self.songMetadata = vinfo

        # Set the temporary file to be played
        self.setFile(manager.audioFile)

        return(True)
        
    # Open a dialog with the list of recent files
    def openRecentFileDialog(self, event):
        RecentFileList = self.settings.getRecentFiles()

        if(isinstance(RecentFileList, dict)):
            if(len(RecentFileList) <= 0):
                CTkMessagebox(master = self, title = _("Error"), 
                              message=_("No file was recently open with this software. "
                              "Please open one by clicking the open button"), 
                              icon = "cancel", font = ("", LBL_FONT_SIZE))
                return

            self.unbind_all('<KeyPress>')
            self.unbind_all('<1>')
            try:
                popup = recentdialog.recentDialog(self, RecentFileList)
                rFile = popup.show()
            finally:
                self.bind_all('<1>', self._click_manager_)
                self.bind_all('<KeyPress>', self._hotkey_manager_)
            
            if(rFile == ""):
                return(False)
            
            # check for YoutubeFile
            if(RecentFileList[rFile].get(PBO_DEF_YOUTUBE, False) == False):
                self.bYouTubeFile = False
                self.YouTubeUrl = ""
                self.setFile(rFile)
            else:
                self.setYouTubeUrl(rFile, RecentFileList[rFile].get(PBO_DEF_METADATA, ""))

    # Toggle loop playing
    def loopToggle(self, bForceDisable = False):
        if(bForceDisable == False):
            self.player.loopEnabled = not self.player.loopEnabled
        else:
            self.player.loopEnabled = False

        if(self.player.loopEnabled):
            self.playButton.configure(image = self.loopIcon, require_redraw=True)
            self.statusBarMessage(_("Loop enabled"), timeout=1000)
            self.swtLoopEnabled.select()
        else:
            self.playButton.configure(image = None, require_redraw=True)
            if(bForceDisable == False):
                self.statusBarMessage(_("Loop disabled"), timeout=1000)
            self.swtLoopEnabled.deselect()

    # Sets loop start point
    def setLoopStart(self, loopPoint = 0):
        #print(f"Loopstart: {loopPoint}")
        
        # Checks for overlapping points
        if(self.player.endPoint > 0 and 
           loopPoint >= (self.player.endPoint - self.player.pipeline_time(LOOP_MINIMUM_GAP))):
            return(False)

        # set the start point
        self.player.startPoint = loopPoint
        secs = self.player.song_time(loopPoint)
        if(secs is None):
            secs = 0
        self.lblLoopStart.configure(text = f"{dt.timedelta(seconds=floor(secs))}.{utils.get_fractional(secs, 3):03d}")
        self.syncWaveformState()

    # Sets loop end point
    def setLoopEnd(self, loopPoint = 0):
        #print(f"Loopend: {loopPoint}")
        
        # Checks for overlapping points
        if(self.player.startPoint >= 0 and 
           loopPoint <= (self.player.startPoint + self.player.pipeline_time(LOOP_MINIMUM_GAP))):
            return(False)

        # set the end point
        # Make sure the endpoint is at least LOOP_MINIMUM_GAP
        # from the end of song
        duration = self.player.query_duration()
        if(duration):
            maxEndpoint = duration - self.player.pipeline_time(LOOP_MINIMUM_GAP)
            if(loopPoint > maxEndpoint):
                loopPoint = maxEndpoint

            self.player.endPoint = loopPoint
            secs = self.player.song_time(loopPoint)
            self.lblLoopEnd.configure(text = f"{dt.timedelta(seconds=floor(secs))}.{utils.get_fractional(secs, 3):03d}")
            self.syncWaveformState()
            return(loopPoint)

    # Move the loop start by shift milliseconds
    def moveLoopStart(self, shift = 0):
        if(shift == 0):
            return(False)

        try:
            shiftPipeLineTime = self.player.pipeline_time(shift / 1000)
        except:
            return(False)
        
        if(self.player.startPoint < 0 or (self.player.startPoint + shiftPipeLineTime) < 0):
            return(False)

        self.setLoopStart(self.player.startPoint + shiftPipeLineTime)
        return(True)

    # Move the loop end by shift milliseconds
    def moveLoopEnd(self, shift = 0):
        if(shift == 0):
            return(False)

        try:
            shiftPipeLineTime = self.player.pipeline_time(shift / 1000)
        except:
            return(False)

        if(self.player.endPoint < 0 or (self.player.endPoint + shiftPipeLineTime) < 0):
            return(False)

        self.setLoopEnd(self.player.endPoint + shiftPipeLineTime)
        return(True)

    def syncWaveformState(self):
        duration = self.player.query_duration()
        if(duration is not None and duration > 0):
            self.waveform.set_duration(self.player.song_time(duration))

        loopStartSeconds = None
        loopEndSeconds = None
        if(self.player.startPoint is not None and self.player.startPoint >= 0):
            loopStartSeconds = self.player.song_time(self.player.startPoint)
        if(self.player.endPoint is not None and self.player.endPoint >= 0):
            loopEndSeconds = self.player.song_time(self.player.endPoint)
        self.waveform.set_loop(loopStartSeconds, loopEndSeconds)

        position = self.player.query_position()
        if(position is not None and position >= 0):
            self.waveform.set_playhead(self.player.song_time(position))

    def hasValidLoopRange(self):
        return (
            self.player.loopEnabled and
            self.player.startPoint is not None and
            self.player.endPoint is not None and
            self.player.startPoint >= 0 and
            self.player.endPoint > self.player.startPoint
        )

    def restartLoopFromA(self):
        if(self.player.canPlay == False):
            self.statusBarMessage(_("Please open a file..."))
            return

        if(self.hasValidLoopRange() == False):
            self.togglePlay()
            return

        self.player.seek_absolute(self.player.startPoint)
        self.Play()
        self.statusBarMessage(_("Restart loop from A"), timeout=1000)

    def waveformSeek(self, targetSeconds):
        if(self.player.canPlay == False):
            return
        self.player.seek_absolute(self.player.pipeline_time(targetSeconds))
        self.syncWaveformState()

    def waveformStatus(self, message):
        if(message):
            self.statusBarMessage(message, timeout=1800)

    # Updates the save progress bars
    def saveProgress(self, value):
        self.save_prg_var.set(value)
        self.update()
        
        # If the cancel button is pressed return False
        if(self.save_canc_var):
            return(False)
        
        return(True)
    
    # Sets the global variable to cancel save operation
    def saveCancelButtonClick(self):
        self.save_canc_var = True

    def togglePlay(self):
        if(self.player.canPlay == False):
            self.statusBarMessage(_("Please open a file..."))
            return

        if self.player.isPlaying == False:
            self.Play()
        else:
            self.Pause()

    # Start Playing   
    def Play(self):
        self.player.Play()
        self.playButton.configure(fg_color="#2E7D32", hover_color="#1E5A24", require_redraw=True)
    
    # Pause Playing
    def Pause(self):
        self.player.Pause()
        self.playButton.configure(fg_color="#2F5D95", hover_color="#23436C", require_redraw=True)

    # Stop playing and rewind
    def stopPlaying(self):
        if(self.player.canPlay == False):
            self.statusBarMessage(_("Please open a file..."))
            return

        self.Pause()
        self.player.Rewind()
        self.dispSongTime(Force=True)

    # Controls the song playback
    def songControl(self):
        duration, position = self.player.update_position()

        # If loop is not enabled and we have reached the end
        # playback is stopped
        if(self.player.loopEnabled == False):
            if(duration and position and duration > 0 and position >= duration):
                self.stopPlaying()
        else:
            # If loop is enabled and playback is not within
            # the loop range, it seeks the playback at loop start
            #print(f"Position: {position} - Loopstart = {self.player.startPoint} - Loopend = {self.player.endPoint}")
            #print(f"Distanza durata: {self.player.song_time(duration - position)} - Distanza looppoint: {self.player.song_time(self.player.endPoint - position)}")
            if(position and (position < self.player.startPoint or 
               position >= self.player.endPoint)):
                self.player.seek_absolute(self.player.startPoint)

        # Resets widget controls if it's not playing
        #if(self.lastPlayingState != self.player.isPlaying):
        #    if(self.player.isPlaying == False):
        #        self.stopPlaying()
        #
        #    self.lastPlayingState = self.player.isPlaying

    def dispSongTime(self, Force = False):
        if(self.bValuesChanging):
            return

        curpos = self.player.song_time(self.player.query_position())
        if((curpos and curpos >= 0) or Force):
            # Salva la posizione corrente in secondi
            # per poi utilizzarla in caso di cambio velocità
            if(Force):
                curpos = 0

            self.player.songPosition = curpos

            curpos = floor(curpos)
            cent = dt.timedelta(seconds = curpos)
            self.songTime.set(cent)

        curperc = self.player.query_percentage()
        if((curperc and curperc >= 0) or Force):
            if(Force):
                curperc = 0

            curperc = curperc / 1000000
            self.songProgress.set(curperc)
            self.scale.set(curperc)

        # Updates the status bar with song and artists tag
        if(self.bStatusBarTags == False):
            if(self.player.artist != "" and self.player.title != "" ):
                self.songMetadata = f"{self.player.artist} - {self.player.title}"
                self.displaySongMetadata()
                self.bStatusBarTags = True

                # Updates the info on the recent file list
                self.setRecentFilePBOptions()        

        # Sets the default loop end to duration (if not already set)
        if(self.player.endPoint != None and self.player.endPoint <= 0):
            duration = self.player.query_duration()
            if(duration != None and duration > 0):
                self.setLoopEnd(duration)

        # Sets loop start point to 0 if it is not set
        if(self.player.startPoint < 0):
            self.setLoopStart(0)

        self.syncWaveformState()

    # Display the metadata on the statusbar
    def displaySongMetadata(self):
        if(self.bYouTubeFile == False):
            self.statusBarMessage(self.songMetadata, static = True)
        else:
            self.statusBarMessage(YOUTUBE_METADATA_PREFIX + self.songMetadata, static = True)

    # Display the YouTube download progress stripping any newline at the end of strings
    def dispYoutubeProgress(self, line):
        self.statusBarMessage(re.sub(pattern=r'(.+)\n$', repl=r'\1', string=line))

        self.update()
        self.update_idletasks()

    #def validate_int(self, d, i, P, s, S, v, V, W):
    #    print("d=", d, " i=", i, " P=",P," s=", s," S=", S, " v=",v," V=", V, " W=",W)
    def validate_int(self, S):
        try:
            int(S)
        except:
            return False
        else:
            return True

    def validate_neg_int(self, S, P):
        #print("d=", d, " i=", i, " P=",P," s=", s," S=", S, " v=",v," V=", V, " W=",W)

        regex = re.compile("^(-)?[0-9]*$")
        #print(regex.match(P))
        if(regex.match(P) == None):
            return False
        else:
            return True

    def speedChanged(self, a, b, c):
        self.entSpeed.delete(0, 'end')
        self.entSpeed.insert(0, str(self.varSpeed.get()))

        # percentage conversion to 1x
        # eg: 80% = 0.8
        newtempo = self.varSpeed.get() * 0.01
        oldtempo = self.player.tempo
        
        # Nothing to do here
        if(newtempo == oldtempo):
            return

        # Save the current value on the recent files list
        self.setRecentFilePBOptions()

        self.bValuesChanging = True
        try:
            self.player.tempo = newtempo
            curpos = self.player.songPosition
            self.player.set_speed(self.player.tempo)
            # force position recalculation
            if(curpos):
                self.player.seek_absolute(self.player.pipeline_time(curpos))
            
            # recalculate loop boundaries based on new tempo
            newLoopStart = (self.player.startPoint * oldtempo) / newtempo
            newLoopEnd = (self.player.endPoint * oldtempo) / newtempo
            self.player.startPoint = newLoopStart
            self.player.endPoint = newLoopEnd

            self.syncWaveformState()
        finally:
            self.bValuesChanging = False

    def checkSpeed(self, event):
        try:
            value = int(self.entSpeed.get())
            if value < MIN_SPEED_PERCENT:
                value = MIN_SPEED_PERCENT
            elif value > MAX_SPEED_PERCENT:
                value = MAX_SPEED_PERCENT

            self.entSpeed.delete(0, 'end')
            self.entSpeed.insert(0, str(value))
            self.varSpeed.set(value)
        except:
            self.entSpeed.delete(0, 'end')
            self.entSpeed.insert(0, str(self.varSpeed.get()))

    def semitonesChanged(self, a, b, c):
        value = str(self.varPitchST.get())
        self.entPitchST.delete(0, 'end')
        self.entPitchST.insert(0, value)
        self.player.semitones = self.varPitchST.get()
        # Save the current value on the recent files list
        self.setRecentFilePBOptions()
        self.changePitch()

    def centsChanged(self, a, b, c):
        value = str(self.varPitchCents.get())
        self.entPitchCents.delete(0, 'end')
        self.entPitchCents.insert(0, value)
        self.player.cents = self.varPitchCents.get()
        # Save the current value on the recent files list
        self.setRecentFilePBOptions()
        self.changePitch()

    def volumeChanged(self, a, b, c):
        value = str(self.varVolume.get())
        self.entVolume.delete(0, 'end')
        self.entVolume.insert(0, value)
        self.player.volume = self.varVolume.get() * 0.01
        # Save the current value on the recent files list
        self.setRecentFilePBOptions()
        self.player.set_volume(self.player.volume)

    def changePitch(self):
        # converte da semitoni + centesimi
        # a unità pitch
        curpitch = self.player.semitones + (self.player.cents * 0.01)
        self.player.pitch = curpitch
        self.player.set_pitch(self.player.pitch)

    def checkSemitones(self, event):
        try:
            value = int(self.entPitchST.get())
            if value < MIN_PITCH_SEMITONES:
                value = MIN_PITCH_SEMITONES
            elif value > MAX_PITCH_SEMITONES:
                value = MAX_PITCH_SEMITONES

            self.entPitchST.delete(0, 'end')
            self.entPitchST.insert(0, str(value))
            self.varPitchST.set(value)
        except:
            self.entPitchST.delete(0, 'end')
            self.entPitchST.insert(0, str(self.varPitchST.get()))

    def checkCents(self, event):
        try:
            value = int(self.entPitchCents.get())
            if value < MIN_PITCH_CENTS:
                value = MIN_PITCH_CENTS
            elif value > MAX_PITCH_CENTS:
                value = MAX_PITCH_CENTS

            self.entPitchCents.delete(0, 'end')
            self.entPitchCents.insert(0, str(value))
            self.varPitchCents.set(value)
        except:
            self.entPitchCents.delete(0, 'end')
            self.entPitchCents.insert(0, str(self.varPitchCents.get()))

    def checkVolume(self, event):
        try:
            value = int(self.entVolume.get())
            if value < MIN_VOLUME:
                value = MIN_VOLUME
            elif value > MAX_VOLUME:
                value = MAX_VOLUME

            self.entVolume.delete(0, 'end')
            self.entVolume.insert(0, str(value))
            self.varVolume.set(value)
        except:
            self.entVolume.delete(0, 'end')
            self.entVolume.insert(0, str(self.varVolume.get()))

    def songSeek(self, val):
        dd, pp = self.player.update_position()
        if(dd is not None and dd != 0):
            newPos = val * dd
            self.player.seek_absolute(newPos)

    def resetDefaultVar(self, obj):
        if obj != None:
            try:
                if obj == self.varSpeed:
                    obj.set(DEFAULT_SPEED)
                elif obj == self.varPitchST:
                    obj.set(DEFAULT_SEMITONES)
                elif obj == self.varPitchCents:
                    obj.set(DEFAULT_CENTS)
            except:
                return
    
    # Open the about dialog
    def openAboutDialog(self):
        self.unbind_all('<KeyPress>')
        self.unbind_all('<1>')
        try:
            popup = aboutdialog.aboutDialog(self)
            popup.show()
        finally:
            self.bind_all('<1>', self._click_manager_)
            self.bind_all('<KeyPress>', self._hotkey_manager_)

    # Writes an info message on status bar and enable erasing
    # after the timeout. If static flag is set, message
    # will be permanent with erasing timeout
    def statusBarMessage(self, message, static = False, timeout = STATUS_BAR_TIMEOUT):
        if(message is None):
            return

        self.statusBarUpdate(message)

        if(static == False):
            # Sets the timeout and update the status bar
            self.afterCancelID = self.after(timeout, self.statusBarUpdate)

    # Updates the statusbar text
    # if no text is specified, it writes the song metadata
    def statusBarUpdate(self, newText = ""):
        #print(f"Messaggio {newText} - ID Cancel: {self.afterCancelID}")

        if(self.afterCancelID):
            self.after_cancel(self.afterCancelID)
            self.afterCancelID = ""

        if(newText):
            self.fileLabel.configure(text = newText)
        else:
            if(self.bYouTubeFile == False):
                self.fileLabel.configure(text = self.songMetadata)
            else:
                self.fileLabel.configure(text = YOUTUBE_METADATA_PREFIX + self.songMetadata)

    def parseHotkey(self, event):
        key = event.keysym
        state = event.state
        #print("Key: ", key, " - State: ", state)

        move = 0
        accel = 0
        # Moves left by N seconds
        if(key == 'KP_1' or key == 'Left'):
            move = -STEPS_SEC_MOVE_1
        elif(key == 'KP_4'):
            move = -STEPS_SEC_MOVE_2
        elif(key == 'KP_7'):
            move = -STEPS_SEC_MOVE_3
        
        # Moves right by N seconds
        elif(key == 'KP_3' or key == 'Right'):
            move = STEPS_SEC_MOVE_1
        elif(key == 'KP_6'):
            move = STEPS_SEC_MOVE_2
        elif(key == 'KP_9'):
            move = STEPS_SEC_MOVE_3
        # Rewind to top or to loop start
        elif(key == 'Home'):
            self.player.Rewind()
            self.dispSongTime(Force=True)
        
        # Speed song up
        elif(key == 'KP_8'):
            accel = STEPS_SPEED
        # Reset Speed
        elif(key == 'KP_5'):
            self.resetDefaultVar(self.varSpeed)
        # Speed song down
        elif(key == 'KP_2'):
            accel = -STEPS_SPEED

        # Play / Pause (space restarts active loop from A)
        elif(key == 'space'):
            self.restartLoopFromA()
        elif(key == 'KP_0'):
            self.togglePlay()
        # Stop
        elif(key == 'KP_Decimal'):
            self.stopPlaying()

        # Transpose + 1 semitone
        elif(key == 'KP_Add'):
            if(self.varPitchST.get() < MAX_PITCH_SEMITONES):
                self.varPitchST.set(self.varPitchST.get() + STEPS_SEMITONES)
        # Transpose - 1 semitone
        elif(key == 'KP_Subtract'):
            if(self.varPitchST.get() > MIN_PITCH_SEMITONES):
                self.varPitchST.set(self.varPitchST.get() - STEPS_SEMITONES)

        # Ctrl + o: open recent files dialog box
        elif(key == 'o' and state == 20):
            self.openFile()

        # Ctrl + r: open recent files dialog box
        elif(key == 'r' and state == 20):
            self.openRecentFileDialog(None)

        # Ctrl + y: open YouTube dialog box
        elif(key == 'y' and state == 20):
            self.openYouTubeDialog(None)

        # Toggle loop    
        elif(key == 'l' or key == 'L'):
            self.loopToggle()
        # Set loop start
        elif((key == 'a' or key == 'A' or key == 'KP_Divide') and state != 20):
            self.setLoopStart(self.player.query_position())
        # Set loop end
        elif((key == 'b' or key == 'B'or key == 'KP_Multiply') and state != 20):
            self.setLoopEnd(self.player.query_position())
        # Ctrl + a: Reset loop start
        elif(key == 'a' and state == 20):
            self.setLoopStart(0)
        # Ctrl + b: reset loop end
        elif(key == 'b' and state == 20):
            self.setLoopEnd(self.player.query_duration())

        # Ctrl + q: quit
        elif(key == 'q' and state == 20):
            self.destroy()
            exit()

        if(move != 0):
            self.bValuesChanging = True
            try:
                self.player.seek_relative(move)
            finally:
                self.bValuesChanging = False

        if(accel != 0):
            val = self.varSpeed.get() + accel
            if(val >= MIN_SPEED_PERCENT and val <= MAX_SPEED_PERCENT):
                self.varSpeed.set(val)

    def _hotkey_manager_(self, event):
        try:
            if(event.widget.winfo_class() != 'Entry'):
                self.parseHotkey(event)
        except:
            pass

        #print("Widget: ", widget.winfo_class(), " Object: ", widget)
        #pass

    def _click_manager_(self, event):
        widget = event.widget
        if(hasattr(widget, "focus")):
            widget.focus_set()

        #print("Widget: ", widget.winfo_class())
        #pass

    # Handles drop event
    def _drop_manager_(self, event):
        dropped_file = str(self.tk.splitlist(event.data)[0])
        if(dropped_file != ""):
            self.bYouTubeFile = False
            self.YouTubeUrl = ""
            self.setFile(dropped_file)

    # Test the dropped file
    def _drop_check_(self, event):
        # splits the files
        fList = self.tk.splitlist(event.data)

        # Rejects multiple files
        if(len(fList) > 1):
            return(REFUSE_DROP)

        # Test for a valid file extension
        _, fExt = os.path.splitext(str(fList[0]))
        if (fExt.replace(".", "") not in OPEN_EXTENSIONS_FILTER):
            return(REFUSE_DROP)

    def _tasks_(self):
        self.player.handle_message()
        self.songControl()
        self.dispSongTime()

        self.after(UPDATE_INTERVAL, self._tasks_)

def main():
    parser = argparse.ArgumentParser(description = APP_DESCRIPTION, prog = APP_NAME)
    parser.add_argument("--delete-recent", help=_("Clear the list of recently played media"), action='store_true')
    parser.add_argument("-v", "--version", action="version", version=f"{APP_NAME} - {APP_VERSION}")
    parser.add_argument("media", nargs="?", help=_("URI of the media to open"))

    args = parser.parse_args()

    app = App(args)

    app.bind_all('<KeyPress>', app._hotkey_manager_)
    app.bind_all('<1>', app._click_manager_)
    
    # Initialize drag and drop if available (disabled on WSL)
    if _dnd_available:
        from tkinterdnd2 import DND_FILES
        app.drop_target_register(DND_FILES)
        app.dnd_bind("<<Drop>>", app._drop_manager_)
        app.dnd_bind("<<DropEnter>>", app._drop_check_)

    app.after(10, app._tasks_)

    app.mainloop()

#if __name__ == "__main__":
#    main()
