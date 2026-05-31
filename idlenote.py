#!/usr/bin/env python3
"""
IdleNote — Idle-triggered scratchpad.
Appears when keyboard+mouse both idle. Closes only on ✕.
Tray left-click opens it. Notes auto-saved locally.
"""

import tkinter as tk
from tkinter import messagebox
import threading
import time
import os
import sys
import json
import datetime
import platform

# ── Tray ──────────────────────────────────────────────────────────────────────
try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False

# ── Global input listener ─────────────────────────────────────────────────────
try:
    from pynput import mouse as pynmouse, keyboard as pynkeyboard
    HAS_PYNPUT = True
except ImportError:
    HAS_PYNPUT = False

# ──────────────────────────────────────────────────────────────────────────────
# PATHS
# ──────────────────────────────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    # Running as PyInstaller exe
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APP_DIR       = os.path.join(os.path.expanduser("~"), ".idlenote")
NOTES_FILE    = os.path.join(APP_DIR, "notes.txt")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
os.makedirs(APP_DIR, exist_ok=True)

DEFAULT_SETTINGS = {
    "kb_idle_secs":    5,
    "mouse_idle_secs": 8,
    "win_x":  None,
    "win_y":  None,
    "width":  360,
    "height": 260,
    "opacity": 0.95,
}

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            s = DEFAULT_SETTINGS.copy()
            s.update(json.load(open(SETTINGS_FILE)))
            return s
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()

def save_settings(s):
    try:
        json.dump(s, open(SETTINGS_FILE, "w"), indent=2)
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────────────────────
# AUTOSTART
# ──────────────────────────────────────────────────────────────────────────────
def set_autostart(enable=True):
    system = platform.system()
    if system == "Windows":
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            exe_path = sys.executable if getattr(sys, 'frozen', False) else \
                       f'"{sys.executable}" "{os.path.abspath(__file__)}"'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                winreg.KEY_SET_VALUE) as key:
                if enable:
                    winreg.SetValueEx(key, "IdleNote", 0, winreg.REG_SZ, exe_path)
                else:
                    try: winreg.DeleteValue(key, "IdleNote")
                    except FileNotFoundError: pass
        except Exception as e:
            print(f"Autostart error: {e}")

    elif system == "Linux":
        autostart_dir = os.path.expanduser("~/.config/autostart")
        desktop_file  = os.path.join(autostart_dir, "idlenote.desktop")
        os.makedirs(autostart_dir, exist_ok=True)
        if enable:
            exe = sys.executable if getattr(sys, 'frozen', False) else \
                  f"{sys.executable} {os.path.abspath(__file__)}"
            content = f"""[Desktop Entry]
Type=Application
Name=IdleNote
Exec={exe}
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
"""
            with open(desktop_file, "w") as f:
                f.write(content)
        else:
            if os.path.exists(desktop_file):
                os.remove(desktop_file)


def is_autostart_enabled():
    system = platform.system()
    if system == "Windows":
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                winreg.QueryValueEx(key, "IdleNote")
                return True
        except Exception:
            return False
    elif system == "Linux":
        return os.path.exists(os.path.expanduser("~/.config/autostart/idlenote.desktop"))
    return False


# ──────────────────────────────────────────────────────────────────────────────
# IDLE TRACKER
# ──────────────────────────────────────────────────────────────────────────────
class IdleTracker:
    def __init__(self):
        self.last_kb    = time.time()
        self.last_mouse = time.time()
        self._lock = threading.Lock()
        self._kb_listener    = None
        self._mouse_listener = None

    def touch_kb(self):
        with self._lock: self.last_kb = time.time()

    def touch_mouse(self):
        with self._lock: self.last_mouse = time.time()

    def idle_kb_secs(self):
        with self._lock: return time.time() - self.last_kb

    def idle_mouse_secs(self):
        with self._lock: return time.time() - self.last_mouse

    def start(self):
        if not HAS_PYNPUT: return
        def on_key(*_):    self.touch_kb()
        def on_move(*_):   self.touch_mouse()
        def on_click(*_):  self.touch_mouse()
        def on_scroll(*_): self.touch_mouse()
        try:
            self._kb_listener = pynkeyboard.Listener(
                on_press=on_key, on_release=on_key, daemon=True)
            self._mouse_listener = pynmouse.Listener(
                on_move=on_move, on_click=on_click, on_scroll=on_scroll, daemon=True)
            self._kb_listener.start()
            self._mouse_listener.start()
        except Exception as e:
            print(f"pynput error: {e}")

    def stop(self):
        if self._kb_listener:
            try: self._kb_listener.stop()
            except: pass
        if self._mouse_listener:
            try: self._mouse_listener.stop()
            except: pass


# ──────────────────────────────────────────────────────────────────────────────
# SETTINGS WINDOW
# ──────────────────────────────────────────────────────────────────────────────
class SettingsWindow:
    def __init__(self, app):
        self.app = app

    def open(self):
        s   = self.app.settings
        win = tk.Toplevel()
        win.title("IdleNote — Settings")
        win.resizable(False, False)
        win.configure(bg="#13131a")
        win.attributes("-topmost", True)

        # Header
        tk.Label(win, text="✦  IDLENOTE SETTINGS",
                 bg="#13131a", fg="#ff6b2b",
                 font=("Consolas", 11, "bold")).grid(
                 row=0, column=0, columnspan=3,
                 padx=20, pady=(18, 10), sticky="w")

        lbl = dict(bg="#13131a", fg="#888899", font=("Consolas", 9), anchor="w")
        val = dict(bg="#13131a", fg="#ffaa44", font=("Consolas", 9), width=4, anchor="e")

        def slider_row(row, text, key, lo, hi):
            tk.Label(win, text=text, **lbl).grid(row=row, column=0, padx=(20,8), pady=5, sticky="w")
            var = tk.IntVar(value=s[key])
            sc  = tk.Scale(win, from_=lo, to=hi, orient="horizontal",
                           variable=var, bg="#13131a", fg="#d4cfc8",
                           troughcolor="#1e1e28", activebackground="#ff6b2b",
                           highlightthickness=0, bd=0, length=170,
                           showvalue=False, cursor="hand2")
            sc.grid(row=row, column=1, pady=5)
            disp = tk.Label(win, textvariable=var, **val)
            disp.grid(row=row, column=2, padx=(4,20))
            return var

        kb_var    = slider_row(1, "Keyboard idle (s)",  "kb_idle_secs",    2, 30)
        mouse_var = slider_row(2, "Mouse idle (s)",      "mouse_idle_secs", 2, 30)

        # Opacity row
        tk.Label(win, text="Opacity (%)", **lbl).grid(
            row=3, column=0, padx=(20,8), pady=5, sticky="w")
        op_var = tk.IntVar(value=int(s["opacity"] * 100))
        tk.Scale(win, from_=40, to=100, orient="horizontal",
                 variable=op_var, bg="#13131a", fg="#d4cfc8",
                 troughcolor="#1e1e28", activebackground="#ff6b2b",
                 highlightthickness=0, bd=0, length=170,
                 showvalue=False, cursor="hand2").grid(row=3, column=1, pady=5)
        tk.Label(win, textvariable=op_var, **val).grid(row=3, column=2, padx=(4,20))

        # Divider
        tk.Frame(win, bg="#2a2a38", height=1).grid(
            row=4, column=0, columnspan=3, sticky="ew", padx=20, pady=(8,0))

        # Autostart toggle
        auto_var = tk.BooleanVar(value=is_autostart_enabled())
        tk.Checkbutton(
            win, text="Run on system startup",
            variable=auto_var,
            bg="#13131a", fg="#888899",
            selectcolor="#1e1e28",
            activebackground="#13131a", activeforeground="#d4cfc8",
            font=("Consolas", 9),
            cursor="hand2"
        ).grid(row=5, column=0, columnspan=3, padx=20, pady=(10, 4), sticky="w")

        # Buttons
        btn_frame = tk.Frame(win, bg="#13131a")
        btn_frame.grid(row=6, column=0, columnspan=3, padx=20, pady=(10, 18), sticky="ew")

        def apply_close():
            s["kb_idle_secs"]    = kb_var.get()
            s["mouse_idle_secs"] = mouse_var.get()
            s["opacity"]         = op_var.get() / 100.0
            save_settings(s)
            set_autostart(auto_var.get())
            self.app.apply_settings()
            win.destroy()

        tk.Button(btn_frame, text="Apply & Close",
                  command=apply_close,
                  bg="#ff6b2b", fg="#fff5ee",
                  font=("Consolas", 9, "bold"),
                  relief="flat", padx=16, pady=7,
                  activebackground="#ff8c4a",
                  cursor="hand2").pack(side="left")

        tk.Button(btn_frame, text="Cancel",
                  command=win.destroy,
                  bg="#252530", fg="#888899",
                  font=("Consolas", 9),
                  relief="flat", padx=16, pady=7,
                  activebackground="#2e2e3e",
                  cursor="hand2").pack(side="left", padx=(8, 0))

        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = win.winfo_reqwidth(),   win.winfo_reqheight()
        win.geometry(f"+{(sw-ww)//2}+{(sh-wh)//2}")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ──────────────────────────────────────────────────────────────────────────────
class IdleNoteApp:

    FADE_STEPS = 14
    FADE_MS    = 14

    def __init__(self):
        self.settings  = load_settings()
        self.tracker   = IdleTracker()
        self._fade_job = None
        self._poll_job = None
        self._save_job = None
        self._visible  = False
        self._cur_alpha = 0.0
        self._dragging  = False
        self._drag_ox = self._drag_oy = 0

        self._build_window()
        self._load_note()
        self.tracker.start()

        if HAS_TRAY:
            self._build_tray()

        # Enable autostart silently on first run
        if not is_autostart_enabled():
            set_autostart(True)

        self._poll()

    # ── BUILD WINDOW ──────────────────────────────────────────────────────────
    def _build_window(self):
        self.root = tk.Tk()
        self.root.title("IdleNote")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.0)
        self.root.configure(bg="#0d0d12")
        self.root.withdraw()

        s    = self.settings
        W, H = int(s["width"]), int(s["height"])

        # Position
        x, y = s.get("win_x"), s.get("win_y")
        if x is None or y is None:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            x  = sw - W - 16
            y  = sh - H - 52   # above taskbar
        self.root.geometry(f"{W}x{H}+{int(x)}+{int(y)}")

        # ── OUTER SHELL ───────────────────────────────────────────────────────
        self.shell = tk.Frame(self.root, bg="#1a1a24",
                              highlightthickness=1,
                              highlightbackground="#2c2c40",
                              highlightcolor="#ff6b2b")
        self.shell.pack(fill="both", expand=True)

        # ── TITLE BAR ─────────────────────────────────────────────────────────
        self.bar = tk.Frame(self.shell, bg="#111118", height=30)
        self.bar.pack(fill="x")
        self.bar.pack_propagate(False)

        self.lbl_icon = tk.Label(self.bar, text="✦",
                                 bg="#111118", fg="#ff6b2b",
                                 font=("Consolas", 9))
        self.lbl_icon.pack(side="left", padx=(10, 4))

        self.lbl_title = tk.Label(self.bar, text="idlenote",
                                  bg="#111118", fg="#3a3a50",
                                  font=("Consolas", 9))
        self.lbl_title.pack(side="left")

        # Close button
        self.btn_close = tk.Label(self.bar, text="✕",
                                  bg="#111118", fg="#3a3a50",
                                  font=("Consolas", 10),
                                  cursor="hand2", padx=10)
        self.btn_close.pack(side="right")
        self.btn_close.bind("<Enter>",  lambda e: self.btn_close.config(fg="#ff5555"))
        self.btn_close.bind("<Leave>",  lambda e: self.btn_close.config(fg="#3a3a50"))
        self.btn_close.bind("<Button-1>", self._on_close_btn)

        # Last-edited label
        self.lbl_time = tk.Label(self.bar, text="",
                                 bg="#111118", fg="#2a2a3c",
                                 font=("Consolas", 7))
        self.lbl_time.pack(side="right", padx=(0, 2))

        # Drag bindings on bar
        for w in (self.bar, self.lbl_icon, self.lbl_title):
            w.bind("<ButtonPress-1>",   self._drag_start)
            w.bind("<B1-Motion>",       self._drag_motion)
            w.bind("<ButtonRelease-1>", self._drag_end)

        # ── TEXT AREA ─────────────────────────────────────────────────────────
        txt_frame = tk.Frame(self.shell, bg="#0f0f17")
        txt_frame.pack(fill="both", expand=True)

        self.txt = tk.Text(
            txt_frame,
            bg="#0f0f17", fg="#cec8c0",
            insertbackground="#ff6b2b",
            font=("Consolas", 11),
            relief="flat", wrap="word",
            padx=14, pady=12,
            spacing1=2, spacing3=3,
            undo=True,
            highlightthickness=0,
            selectbackground="#252540",
            selectforeground="#e8e0d5",
            cursor="xterm", bd=0,
        )
        self.txt.pack(side="left", fill="both", expand=True)

        self.sb = tk.Scrollbar(txt_frame, command=self.txt.yview,
                               bg="#1a1a24", troughcolor="#0f0f17",
                               width=5, relief="flat", bd=0,
                               activebackground="#ff6b2b")
        self.txt.configure(yscrollcommand=self._sb_set)

        # ── FOOTER ────────────────────────────────────────────────────────────
        self.footer = tk.Frame(self.shell, bg="#111118", height=22)
        self.footer.pack(fill="x")
        self.footer.pack_propagate(False)

        self.lbl_chars = tk.Label(self.footer, text="",
                                  bg="#111118", fg="#2a2a3c",
                                  font=("Consolas", 7))
        self.lbl_chars.pack(side="right", padx=10)

        # Resize grip
        self.grip = tk.Label(self.footer, text="⠿",
                             bg="#111118", fg="#2a2a3c",
                             font=("Consolas", 8), cursor="sizing")
        self.grip.pack(side="right", padx=(0, 4))
        self.grip.bind("<ButtonPress-1>",  self._resize_start)
        self.grip.bind("<B1-Motion>",      self._resize_motion)
        self.grip.bind("<ButtonRelease-1>", self._resize_end)

        # Saved indicator
        self.lbl_saved = tk.Label(self.footer, text="",
                                  bg="#111118", fg="#4ade80",
                                  font=("Consolas", 7))
        self.lbl_saved.pack(side="left", padx=10)

        # ── TEXT BINDINGS ─────────────────────────────────────────────────────
        self.txt.bind("<<Modified>>", self._on_modified)

        # Right-click menu
        self.txt.bind("<Button-3>",   self._ctx_menu)
        self.bar.bind("<Button-3>",   self._ctx_menu)

    def _sb_set(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.sb.pack_forget()
        else:
            self.sb.pack(side="right", fill="y", before=self.txt)
            self.sb.set(lo, hi)

    # ── DRAG ──────────────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._dragging = True
        self._drag_ox  = e.x_root - self.root.winfo_x()
        self._drag_oy  = e.y_root - self.root.winfo_y()

    def _drag_motion(self, e):
        if self._dragging:
            self.root.geometry(f"+{e.x_root - self._drag_ox}+{e.y_root - self._drag_oy}")

    def _drag_end(self, e):
        self._dragging = False
        self.settings["win_x"] = self.root.winfo_x()
        self.settings["win_y"] = self.root.winfo_y()
        save_settings(self.settings)

    # ── RESIZE ────────────────────────────────────────────────────────────────
    def _resize_start(self, e):
        self._rx = e.x_root; self._ry = e.y_root
        self._rw = self.root.winfo_width()
        self._rh = self.root.winfo_height()

    def _resize_motion(self, e):
        nw = max(260, self._rw + (e.x_root - self._rx))
        nh = max(160, self._rh + (e.y_root - self._ry))
        self.root.geometry(f"{nw}x{nh}")

    def _resize_end(self, e):
        self.settings["width"]  = self.root.winfo_width()
        self.settings["height"] = self.root.winfo_height()
        save_settings(self.settings)

    # ── NOTE I/O ──────────────────────────────────────────────────────────────
    def _load_note(self):
        if os.path.exists(NOTES_FILE):
            try:
                with open(NOTES_FILE, "r", encoding="utf-8") as f:
                    content = f.read()
                self.txt.insert("1.0", content)
                self.txt.see("end")
            except Exception:
                pass
        self.txt.edit_modified(False)
        self._update_footer()

    def _on_modified(self, e=None):
        if self.txt.edit_modified():
            self.txt.edit_modified(False)
            self._update_footer()
            if self._save_job:
                self.root.after_cancel(self._save_job)
            self._save_job = self.root.after(600, self._do_save)

    def _do_save(self):
        content = self.txt.get("1.0", "end-1c")
        try:
            with open(NOTES_FILE, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception:
            pass
        now = datetime.datetime.now().strftime("%b %d, %H:%M")
        self.lbl_time.config(text=f"saved {now}")
        self.lbl_saved.config(text="✓ saved")
        self.root.after(2000, lambda: self.lbl_saved.config(text=""))

    def _update_footer(self):
        content = self.txt.get("1.0", "end-1c")
        words    = len(content.split()) if content.strip() else 0
        chars    = len(content)
        self.lbl_chars.config(text=f"{words}w  {chars}c")

    # ── SHOW / HIDE ───────────────────────────────────────────────────────────
    def show(self):
        if self._visible: return
        self._visible = True
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self._fade_to(self.settings.get("opacity", 0.95))
        self.txt.focus_set()

    def _on_close_btn(self, e=None):
        if self._visible:
            self._visible = False
            self._do_save()
            self._fade_to(0.0, on_done=self.root.withdraw)

    def _fade_to(self, target, on_done=None):
        if self._fade_job:
            self.root.after_cancel(self._fade_job)
            self._fade_job = None
        steps   = self.FADE_STEPS
        current = self._cur_alpha
        delta   = (target - current) / steps

        def step(n, cur):
            cur = round(max(0.0, min(1.0, cur + delta)), 3)
            self._cur_alpha = cur
            self.root.attributes("-alpha", cur)
            if n > 1:
                self._fade_job = self.root.after(self.FADE_MS, step, n - 1, cur)
            else:
                self.root.attributes("-alpha", target)
                self._cur_alpha = target
                if on_done: on_done()

        step(steps, current)

    # ── IDLE POLL ─────────────────────────────────────────────────────────────
    def _poll(self):
        kb_idle    = self.tracker.idle_kb_secs()
        mouse_idle = self.tracker.idle_mouse_secs()
        kb_th      = self.settings["kb_idle_secs"]
        mouse_th   = self.settings["mouse_idle_secs"]

        if kb_idle >= kb_th and mouse_idle >= mouse_th and not self._visible:
            self.show()

        self._poll_job = self.root.after(500, self._poll)

    # ── CONTEXT MENU ─────────────────────────────────────────────────────────
    def _ctx_menu(self, e):
        m = tk.Menu(self.root, tearoff=0,
                    bg="#1a1a24", fg="#d4cfc8",
                    activebackground="#252540",
                    activeforeground="#ff6b2b",
                    font=("Consolas", 9),
                    relief="flat", bd=0)
        m.add_command(label="Cut",   command=lambda: self.txt.event_generate("<<Cut>>"))
        m.add_command(label="Copy",  command=lambda: self.txt.event_generate("<<Copy>>"))
        m.add_command(label="Paste", command=lambda: self.txt.event_generate("<<Paste>>"))
        m.add_separator()
        m.add_command(label="Clear all notes…", command=self._clear_notes)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def _clear_notes(self):
        if messagebox.askyesno("IdleNote", "Clear all notes permanently?",
                               parent=self.root):
            self.txt.delete("1.0", "end")
            self._do_save()

    # ── APPLY SETTINGS ───────────────────────────────────────────────────────
    def apply_settings(self):
        if self._visible:
            self.root.attributes("-alpha", self.settings.get("opacity", 0.95))

    # ── TRAY ─────────────────────────────────────────────────────────────────
    def _build_tray(self):
        def make_icon(size=64):
            img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            d   = ImageDraw.Draw(img)
            m   = size // 8
            # Background card
            d.rounded_rectangle([m, m, size-m, size-m],
                                 radius=size//8,
                                 fill=(20, 20, 30),
                                 outline=(255, 107, 43), width=max(2, size//24))
            # Three text lines
            lc = (180, 170, 160)
            lx1, lx2 = m*2+2, size-m*2-2
            ly  = [int(size*0.36), int(size*0.52), int(size*0.68)]
            lw  = max(1, size//32)
            d.line([(lx1, ly[0]), (lx2, ly[0])], fill=lc, width=lw)
            d.line([(lx1, ly[1]), (lx2-size//6, ly[1])], fill=lc, width=lw)
            d.line([(lx1, ly[2]), (lx2-size//4, ly[2])], fill=lc, width=lw)
            # Accent dot
            r = max(3, size//14)
            d.ellipse([size-m-r*2, m, size-m, m+r*2],
                      fill=(255, 107, 43))
            return img

        def on_left_click(icon, item=None):
            # pystray passes item=None for a direct left-click on some platforms
            self.root.after(0, self.show)

        def on_settings(icon, item):
            self.root.after(0, lambda: SettingsWindow(self).open())

        def on_quit(icon, item):
            self.root.after(0, self._quit)

        menu = pystray.Menu(
            pystray.MenuItem("Open IdleNote",  on_left_click, default=True),
            pystray.MenuItem("Settings",       on_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit",           on_quit),
        )

        self._tray_icon = pystray.Icon(
            "IdleNote", make_icon(), "IdleNote — click to open", menu)

        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    # ── QUIT ─────────────────────────────────────────────────────────────────
    def _quit(self):
        self._do_save()
        self.tracker.stop()
        if HAS_TRAY and hasattr(self, "_tray_icon"):
            try: self._tray_icon.stop()
            except: pass
        self.root.destroy()

    # ── RUN ──────────────────────────────────────────────────────────────────
    def run(self):
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self._quit()


# ──────────────────────────────────────────────────────────────────────────────
# SINGLE-INSTANCE GUARD + ENTRY
# ──────────────────────────────────────────────────────────────────────────────
def main():
    lock_file = os.path.join(APP_DIR, "idlenote.lock")
    system    = platform.system()

    if system != "Windows":
        try:
            import fcntl
            lf = open(lock_file, "w")
            fcntl.flock(lf, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, BlockingIOError):
            print("IdleNote is already running.")
            sys.exit(0)
    else:
        try:
            import ctypes
            mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "IdleNoteSingleInstance")
            if ctypes.windll.kernel32.GetLastError() == 183:
                sys.exit(0)
        except Exception:
            pass

    app = IdleNoteApp()
    app.run()


if __name__ == "__main__":
    main()
