import customtkinter as ctk
from PIL import Image
import os
import webbrowser

from transcriby.app_constants import *
from transcriby.platform_utils import get_resources_dir, apply_window_icon

import gettext
_ = gettext.gettext

class aboutDialog(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        WIDTH = 980
        HEIGHT = 760

        # Mark app directories
        resources_dir = get_resources_dir()
        apply_window_icon(self, resources_dir)
                
        self.wm_title(_("About"))
        
        self.geometry("%dx%d" % (WIDTH, HEIGHT))
        self.resizable(width=False, height=False)

        img = ctk.CTkImage(dark_image=Image.open(os.path.join(resources_dir, "Icona-64.png")), 
                                light_image=Image.open(os.path.join(resources_dir, "Icona-64.png")),
                                size=(64, 64))

        self.ico = ctk.CTkLabel(self, text="", image=img)
        self.ico.grid(row=0, column=0, rowspan=2, padx=10, sticky="ns")

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=1, padx=10, pady=10, sticky="ewsn")
        
        self.closeButton = ctk.CTkButton(self, text=_("Close"), font=("", 14), command=self.destroy)
        self.closeButton.grid(row=1, column=1, pady=(8, 8), sticky="s")

        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

        tab1 = self.tabview.add(_("About"))
        tab2 = self.tabview.add(_("Shortcuts"))

        # Widget on tab 1: "About"
        self.mainLabel = ctk.CTkLabel(tab1, text=APP_TITLE, justify="center", anchor="center", 
                                      compound="center", font=("", 28, "bold"))
        self.mainLabel.grid(row=0, column=0, pady=(10, 0), sticky="n")

        self.versLabel = ctk.CTkLabel(tab1, text=APP_VERSION, justify="center", anchor="center", 
                                      compound="center", font=("", 20))
        self.versLabel.grid(row=1, column=0, pady=(8, 0), sticky="n")

        self.authLabel = ctk.CTkLabel(tab1, text="Maintained by Sean Tong", justify="center", anchor="center",
                                      compound="center", font=("", LBL_FONT_SIZE))
        self.authLabel.grid(row=2, column=0, sticky="n")

        self.linkLabel = ctk.CTkLabel(tab1, text=APP_URL, justify="center", anchor="center", 
                                      compound="center", text_color="#1f538d", font=("", LBL_FONT_SIZE), cursor="hand2")
        self.linkLabel.grid(row=3, column=0, sticky="n")
        self.linkLabel.bind("<1>", lambda e: self.openUrl(APP_URL))

        # Widget on tab 2: "Shorcuts"
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
            ("Space", _("Restart loop from A (loop enabled)")),
            ("A", _("Set loop start")),
            ("B", _("Set loop end")),
            ("CTRL+A", _("Reset loop start")),
            ("CTRL+B", _("Reset loop end")),
        ]

        self.scrollFrame = ctk.CTkScrollableFrame(tab2)
        self.scrollFrame.grid(row = 0, column = 0, padx = 8, pady = 8, sticky="nsew")

        self.shortcutsFrame = ctk.CTkFrame(self.scrollFrame, fg_color="transparent")
        self.shortcutsFrame.grid(row = 0, column = 0, padx = 10, pady = 10, sticky="nsew")
        
        scLabels = []
        i = 0
        for sc in sc_list:
            if (sc[0] == SC_SECTION_TITLE):
                scLabels.append(ctk.CTkLabel(self.shortcutsFrame, text=sc[1], font=("", LBL_FONT_SIZE, "bold")))
                scLabels[i].grid(row = i, column = 0, sticky = "ew", columnspan = 2, pady=(10, 0))
                i = i + 1
            else:
                scLabels.append(ctk.CTkLabel(self.shortcutsFrame, text=f"{sc[0]}: ", font=("", LBL_FONT_SIZE, "bold")))
                scLabels.append(ctk.CTkLabel(self.shortcutsFrame, text=sc[1], font=("", LBL_FONT_SIZE)))
    
                scLabels[i].grid(row = i, column = 0, sticky = "w", pady=(0, 0))
                scLabels[i + 1].grid(row = i, column = 1, sticky = "w", pady=(0, 0))
                i = i + 2

        self.shortcutsFrame.grid_columnconfigure(1, weight=1)

        # Keep wheel scrolling enabled for dense shortcut lists.
        self.scrollFrame.bind("<Button-4>", self.onScroll)
        self.scrollFrame.bind("<Button-5>", self.onScroll)
        for wid in self.scrollFrame.children.values():
            wid.bind("<Button-4>", self.onScroll)
            wid.bind("<Button-5>", self.onScroll)
        for wid in self.shortcutsFrame.children.values():
            wid.bind("<Button-4>", self.onScroll)
            wid.bind("<Button-5>", self.onScroll)

        
        tab1.grid_columnconfigure(0, weight=1)
        tab2.grid_columnconfigure(0, weight=1)
        tab2.grid_rowconfigure(0, weight=1)
    
    def openUrl(self, url):
        webbrowser.open_new(url)


    def show(self):
        self.deiconify()
        self.grab_set()
        self.wm_protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind_all(sequence="<KeyPress>", func=self._keybind_)
        #self.after(10)
        self.lift()
        self.attributes('-topmost',True)
        self.after_idle(self.attributes, '-topmost', False)
        self.wait_window(self)
        return(True)
    
    def _keybind_(self, event):
        key = event.keysym
        state = event.state
        #print("Key: ", key, " - State: ", state)

        if(key == "Escape" or key == "KP_Enter" or key == "Return"):
            self.destroy()

    def onScroll(self, event = None):
        self.scrollFrame._parent_canvas.yview_scroll(1 if event.num == 5 else -1, "units")
