import customtkinter as ctk
from PIL import Image
import os
import webbrowser

from transcriby.app_constants import *
from transcriby.appsettings import CFG_APP_SECTION
from transcriby.platform_utils import get_resources_dir, apply_window_icon

import gettext
_ = gettext.gettext


class aboutDialog(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        self.appSettings = kwargs.pop("appSettings", None)
        self.onPlaybackSettingsChanged = kwargs.pop("onPlaybackSettingsChanged", None)
        super().__init__(*args, **kwargs)

        WIDTH = 980
        HEIGHT = 760

        self.resources_dir = get_resources_dir()
        apply_window_icon(self, self.resources_dir)

        self.wm_title(_("Settings"))
        self.configure(fg_color=UI_BG_APP)

        if self.master is not None:
            try:
                self.transient(self.master)
            except Exception:
                pass

        self.geometry("%dx%d" % (WIDTH, HEIGHT))
        self.resizable(width=False, height=False)

        img = ctk.CTkImage(
            dark_image=Image.open(os.path.join(self.resources_dir, "Icona-64.png")),
            light_image=Image.open(os.path.join(self.resources_dir, "Icona-64.png")),
            size=(64, 64),
        )

        self.ico = ctk.CTkLabel(self, text="", image=img)
        self.ico.grid(row=0, column=0, rowspan=2, padx=10, sticky="ns")

        self.tabview = ctk.CTkTabview(self)
        self.tabview.configure(
            fg_color=UI_BG_CARD,
            segmented_button_selected_color=UI_ACCENT,
            segmented_button_selected_hover_color=UI_ACCENT_HOVER,
            segmented_button_unselected_color=UI_BG_CARD_ALT,
            segmented_button_unselected_hover_color=UI_BG_CARD,
            text_color=UI_TEXT_PRIMARY,
        )
        self.tabview.grid(row=0, column=1, padx=10, pady=10, sticky="ewsn")

        self.closeButton = ctk.CTkButton(self, text=_("Close"), font=("", 14), command=self.destroy)
        self.closeButton.configure(
            fg_color=UI_ACCENT,
            hover_color=UI_ACCENT_HOVER,
            text_color=UI_BG_APP,
        )
        self.closeButton.grid(row=1, column=1, pady=(8, 8), sticky="s")

        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        tabPlayback = self.tabview.add(_("Playback"))
        tabAbout = self.tabview.add(_("About"))
        tabShortcuts = self.tabview.add(_("Shortcuts"))
        tabPlayback.configure(fg_color=UI_BG_CARD_ALT)
        tabAbout.configure(fg_color=UI_BG_CARD_ALT)
        tabShortcuts.configure(fg_color=UI_BG_CARD_ALT)

        self._buildPlaybackTab(tabPlayback)
        self._buildAboutTab(tabAbout)
        self._buildShortcutTab(tabShortcuts)

        tabPlayback.grid_columnconfigure(0, weight=1)
        tabAbout.grid_columnconfigure(0, weight=1)
        tabShortcuts.grid_columnconfigure(0, weight=1)
        tabShortcuts.grid_rowconfigure(0, weight=1)

    def _buildPlaybackTab(self, tab):
        enabled, delaySeconds = self._readPlaybackSettings()
        self.delayEnabledVar = ctk.BooleanVar(value=enabled)
        self.delaySecondsVar = ctk.StringVar(value=f"{delaySeconds:.2f}")

        self.playbackTitle = ctk.CTkLabel(
            tab,
            text=_("Loop Restart"),
            font=("", 24, "bold"),
            text_color=UI_TEXT_PRIMARY,
            anchor="w",
        )
        self.playbackTitle.grid(row=0, column=0, padx=18, pady=(18, 6), sticky="w")

        self.delaySwitch = ctk.CTkSwitch(
            tab,
            text=_("Enable delayed restart to loop A when pressing Space"),
            variable=self.delayEnabledVar,
            command=self._onDelaySwitchChanged,
            text_color=UI_TEXT_PRIMARY,
            fg_color=UI_BG_INPUT,
            progress_color=UI_ACCENT,
            button_color=UI_ACCENT,
            button_hover_color=UI_ACCENT_HOVER,
        )
        self.delaySwitch.grid(row=1, column=0, padx=18, pady=(0, 10), sticky="w")

        self.delayRow = ctk.CTkFrame(tab, fg_color="transparent")
        self.delayRow.grid(row=2, column=0, padx=18, pady=(0, 10), sticky="w")
        self.delayRow.grid_columnconfigure(1, weight=0)

        self.delayLabel = ctk.CTkLabel(
            self.delayRow,
            text=_("Delay (seconds):"),
            font=("", LBL_FONT_SIZE),
            text_color=UI_TEXT_PRIMARY,
        )
        self.delayLabel.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="w")

        self.delayEntry = ctk.CTkEntry(
            self.delayRow,
            width=90,
            textvariable=self.delaySecondsVar,
            justify="center",
        )
        self.delayEntry.grid(row=0, column=1, padx=(0, 8), pady=0, sticky="w")
        self.delayEntry.bind("<FocusOut>", self._onDelayEntryCommit)
        self.delayEntry.bind("<Return>", self._onDelayEntryCommit)

        self.defaultDelayButton = ctk.CTkButton(
            self.delayRow,
            text=_("Reset"),
            width=72,
            height=30,
            command=self._resetDelayToDefault,
            fg_color=UI_BG_CARD_ALT,
            hover_color=UI_BG_INPUT,
            border_width=1,
            border_color=UI_BORDER_COLOR,
            text_color=UI_TEXT_PRIMARY,
        )
        self.defaultDelayButton.grid(row=0, column=2, padx=(0, 0), pady=0, sticky="w")

        self.playbackHint = ctk.CTkLabel(
            tab,
            text=_("Use this when you need a short pickup time before the loop restarts from A."),
            font=("", LBL_FONT_SIZE),
            text_color=UI_TEXT_MUTED,
            wraplength=840,
            justify="left",
            anchor="w",
        )
        self.playbackHint.grid(row=3, column=0, padx=18, pady=(0, 0), sticky="w")

    def _buildAboutTab(self, tab):
        self.aboutCoverImage = ctk.CTkImage(
            dark_image=Image.open(os.path.join(self.resources_dir, "Icona-256.png")),
            light_image=Image.open(os.path.join(self.resources_dir, "Icona-256.png")),
            size=(176, 176),
        )
        self.aboutCoverLabel = ctk.CTkLabel(tab, text="", image=self.aboutCoverImage)
        self.aboutCoverLabel.grid(row=0, column=0, pady=(10, 0), sticky="n")

        self.mainLabel = ctk.CTkLabel(
            tab,
            text=APP_TITLE,
            justify="center",
            anchor="center",
            compound="center",
            font=("", 28, "bold"),
        )
        self.mainLabel.grid(row=1, column=0, pady=(10, 0), sticky="n")

        self.versLabel = ctk.CTkLabel(
            tab,
            text=APP_VERSION,
            justify="center",
            anchor="center",
            compound="center",
            font=("", 20),
        )
        self.versLabel.grid(row=2, column=0, pady=(8, 0), sticky="n")

        self.authLabel = ctk.CTkLabel(
            tab,
            text="Maintained by Sean Tong",
            justify="center",
            anchor="center",
            compound="center",
            font=("", LBL_FONT_SIZE),
        )
        self.authLabel.grid(row=3, column=0, sticky="n")

        self.linkLabel = ctk.CTkLabel(
            tab,
            text=APP_URL,
            justify="center",
            anchor="center",
            compound="center",
            text_color=UI_ACCENT,
            font=("", LBL_FONT_SIZE),
            cursor="hand2",
        )
        self.linkLabel.grid(row=4, column=0, sticky="n")
        self.linkLabel.bind("<1>", lambda e: self.openUrl(APP_URL))

    def _buildShortcutTab(self, tab):
        SC_SECTION_TITLE = "-TITLE-"

        sc_list = [
            (SC_SECTION_TITLE, _("GENERAL SHORTCUTS:")),
            ("CTRL+O", _("Open a file")),
            ("CTRL+R", _("Open recent files list")),
            ("CTRL+Y", _("Open YouTube dialog")),
            ("CTRL+Q", _("Quit")),
            (SC_SECTION_TITLE, _("PLAYBACK SHORTCUTS:")),
            ("N. Keypad 0", _("Play/Pause")),
            ("N. Keypad .", _("Stop and rewind")),
            ("N. Keypad 1", _("Rewind 5 seconds")),
            ("N. Keypad 4", _("Rewind 10 seconds")),
            ("N. Keypad 7", _("Rewind 15 seconds")),
            ("N. Keypad 3", _("Forward 5 seconds")),
            ("N. Keypad 6", _("Forward 10 seconds")),
            ("N. Keypad 9", _("Forward 15 seconds")),
            ("Home", _("Rewind")),
            ("N. Keypad 8", _("Playback speed +0.1x")),
            ("N. Keypad 2", _("Playback speed -0.1x")),
            ("C", _("Playback speed +0.1x")),
            ("X", _("Playback speed -0.1x")),
            ("N. Keypad 5", _("Reset playback speed to 1.0x")),
            ("N. Keypad +", _("Transpose +1 semitone")),
            ("N. Keypad -", _("Transpose -1 semitone")),
            ("Enter", _("Play/Pause")),
            (",", _("Rewind 0.1 second")),
            (".", _("Forward 0.1 second")),
            ("[", _("Rewind 1 second")),
            ("]", _("Forward 1 second")),
            (SC_SECTION_TITLE, _("LOOP SHORTCUTS:")),
            ("L", _("Toggle loop playing")),
            ("Space", _("Restart loop from A (with optional delay from Settings > Playback)")),
            ("A", _("Set loop start")),
            ("B", _("Set loop end")),
            ("CTRL+A", _("Reset loop start")),
            ("CTRL+B", _("Reset loop end")),
        ]

        self.scrollFrame = ctk.CTkScrollableFrame(tab)
        self.scrollFrame.grid(row=0, column=0, padx=8, pady=8, sticky="nsew")

        self.shortcutsFrame = ctk.CTkFrame(self.scrollFrame, fg_color="transparent")
        self.shortcutsFrame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        scLabels = []
        i = 0
        for sc in sc_list:
            if sc[0] == SC_SECTION_TITLE:
                scLabels.append(ctk.CTkLabel(self.shortcutsFrame, text=sc[1], font=("", LBL_FONT_SIZE, "bold")))
                scLabels[i].grid(row=i, column=0, sticky="ew", columnspan=2, pady=(10, 0))
                i = i + 1
            else:
                scLabels.append(ctk.CTkLabel(self.shortcutsFrame, text=f"{sc[0]}: ", font=("", LBL_FONT_SIZE, "bold")))
                scLabels.append(ctk.CTkLabel(self.shortcutsFrame, text=sc[1], font=("", LBL_FONT_SIZE)))
                scLabels[i].grid(row=i, column=0, sticky="w", pady=(0, 0))
                scLabels[i + 1].grid(row=i, column=1, sticky="w", pady=(0, 0))
                i = i + 2

        self.shortcutsFrame.grid_columnconfigure(1, weight=1)

        self.scrollFrame.bind("<Button-4>", self.onScroll)
        self.scrollFrame.bind("<Button-5>", self.onScroll)
        for wid in self.scrollFrame.children.values():
            wid.bind("<Button-4>", self.onScroll)
            wid.bind("<Button-5>", self.onScroll)
        for wid in self.shortcutsFrame.children.values():
            wid.bind("<Button-4>", self.onScroll)
            wid.bind("<Button-5>", self.onScroll)

    def _readPlaybackSettings(self):
        enabled = False
        delaySeconds = 0.25
        if self.appSettings is not None:
            enabled = bool(self.appSettings.getVal(CFG_APP_SECTION, "LoopRestartDelayEnabled", False))
            rawDelay = self.appSettings.getVal(CFG_APP_SECTION, "LoopRestartDelaySeconds", 0.25)
            try:
                delaySeconds = float(rawDelay)
            except Exception:
                delaySeconds = 0.25
        delaySeconds = min(10.0, max(0.0, delaySeconds))
        return enabled, delaySeconds

    def _savePlaybackSettings(self, enabled, delaySeconds):
        if self.appSettings is None:
            return
        delaySeconds = min(10.0, max(0.0, float(delaySeconds)))
        self.appSettings.setVal(CFG_APP_SECTION, "LoopRestartDelayEnabled", bool(enabled), saveSettings=False)
        self.appSettings.setVal(CFG_APP_SECTION, "LoopRestartDelaySeconds", delaySeconds, saveSettings=False)
        self.appSettings.saveSettings()
        if callable(self.onPlaybackSettingsChanged):
            self.onPlaybackSettingsChanged(bool(enabled), delaySeconds)

    def _onDelaySwitchChanged(self):
        delaySeconds = self._getDelayFromEntry(default=0.25)
        self._savePlaybackSettings(self.delayEnabledVar.get(), delaySeconds)

    def _onDelayEntryCommit(self, event=None):
        delaySeconds = self._getDelayFromEntry(default=0.25)
        self.delaySecondsVar.set(f"{delaySeconds:.2f}")
        self._savePlaybackSettings(self.delayEnabledVar.get(), delaySeconds)

    def _resetDelayToDefault(self):
        self.delaySecondsVar.set("0.25")
        self._savePlaybackSettings(self.delayEnabledVar.get(), 0.25)

    def _getDelayFromEntry(self, default=0.25):
        try:
            value = float(self.delaySecondsVar.get())
        except Exception:
            value = default
        return min(10.0, max(0.0, value))

    def openUrl(self, url):
        webbrowser.open_new(url)

    def show(self):
        self.deiconify()
        apply_window_icon(self, self.resources_dir)
        self.after(450, lambda: apply_window_icon(self, self.resources_dir, schedule_retry=False))
        self.after(900, lambda: apply_window_icon(self, self.resources_dir, schedule_retry=False))
        self.grab_set()
        self.wm_protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind_all(sequence="<KeyPress>", func=self._keybind_)
        self.lift()
        self.attributes("-topmost", True)
        self.after_idle(self.attributes, "-topmost", False)
        self.wait_window(self)
        return True

    def _keybind_(self, event):
        key = event.keysym
        if key == "Escape" or key == "KP_Enter" or key == "Return":
            self.destroy()

    def onScroll(self, event=None):
        self.scrollFrame._parent_canvas.yview_scroll(1 if event.num == 5 else -1, "units")
