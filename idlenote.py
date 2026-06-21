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
import uuid
import platform
import signal
import subprocess

# ── Tray ──────────────────────────────────────────────────────────────────────
try:
    import pystray
    from PIL import Image, ImageDraw, ImageFont
    HAS_TRAY = True
except Exception:
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
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APP_DIR    = os.path.join(os.path.expanduser("~"), ".idlenote")
NOTES_FILE    = os.path.join(APP_DIR, "notes.txt")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")
os.makedirs(APP_DIR, exist_ok=True)

DEFAULT_SETTINGS = {
    "kb_idle_secs":    5,
    "mouse_idle_secs": 8,
    "win_x":   None,
    "win_y":   None,
    "width":   360,
    "height":  260,
    "opacity": 0.95,
    "font_size": 11,
    "theme":   "dark",     # "dark" | "light"
    "accent":  "orange",   # key into ACCENTS
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
# THEME + ACCENT PALETTES
# ──────────────────────────────────────────────────────────────────────────────
# Neutral charcoal / off-white, not blue-tinted. Every color the UI uses lives
# here so theme/accent changes never require touching widget code elsewhere.

ACCENTS = {
    "orange":  {"name": "Orange",  "base": "#ff6b2b", "hover": "#ff8c4a"},
    "teal":    {"name": "Teal",    "base": "#2bb3a3", "hover": "#48cabb"},
    "violet":  {"name": "Violet",  "base": "#8d6bff", "hover": "#a587ff"},
    "crimson": {"name": "Crimson", "base": "#ff4d6d", "hover": "#ff7088"},
    "mint":    {"name": "Mint",    "base": "#34d399", "hover": "#5be0ad"},
}

THEMES = {
    "dark": {
        "shell_bg":         "#1c1c1c",
        "border":           "#46464a",
        "bar_bg":           "#161616",
        "title_fg":         "#9a9893",
        "dim_fg":           "#5c5a56",
        "close_idle":       "#6e6c68",
        "close_hover":      "#ff5c5c",
        "text_bg":          "#181818",
        "text_fg":          "#d9d4cb",
        "select_bg":        "#34343a",
        "select_fg":        "#efe9df",
        "footer_bg":        "#161616",
        "saved_fg":         "#4ade80",
        "scrollbar_bg":     "#222222",
        "scrollbar_trough": "#181818",
        "menu_bg":          "#1c1c1c",
        "menu_fg":          "#d9d4cb",
        "menu_active_bg":   "#2a2a2a",
        "settings_bg":      "#161616",
        "settings_label":   "#8a8884",
        "slider_trough":    "#262626",
        "snooze_active":    "#ffaa44",
    },
    "light": {
        "shell_bg":         "#f6f4ef",
        "border":           "#1f1f1d",
        "bar_bg":           "#ece8df",
        "title_fg":         "#33312c",
        "dim_fg":           "#8a877e",
        "close_idle":       "#8a877e",
        "close_hover":      "#d23c3c",
        "text_bg":          "#fcfbf8",
        "text_fg":          "#2b2a26",
        "select_bg":        "#e0dac8",
        "select_fg":        "#2b2a26",
        "footer_bg":        "#ece8df",
        "saved_fg":         "#16a34a",
        "scrollbar_bg":     "#d8d3c6",
        "scrollbar_trough": "#fcfbf8",
        "menu_bg":          "#fcfbf8",
        "menu_fg":          "#2b2a26",
        "menu_active_bg":   "#ece8df",
        "settings_bg":      "#f6f4ef",
        "settings_label":   "#6b6962",
        "slider_trough":    "#e3ddcf",
        "snooze_active":    "#cc7a1f",
    },
}

def palette(settings):
    """Resolve the active theme dict merged with the active accent colors."""
    t = THEMES.get(settings.get("theme", "dark"), THEMES["dark"]).copy()
    a = ACCENTS.get(settings.get("accent", "orange"), ACCENTS["orange"])
    t["accent"]       = a["base"]
    t["accent_hover"] = a["hover"]
    return t

def fmt_secs(n):
    """5 -> '5s', 90 -> '1m30s', 300 -> '5m' — used for the idle-threshold sliders
    now that they go up to 5 minutes instead of 30 seconds."""
    n = int(n)
    if n < 60:
        return f"{n}s"
    m, s = divmod(n, 60)
    return f"{m}m{s}s" if s else f"{m}m"

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

# ──────────────────────────────────────────────────────────────────────────────
# EMOJI PICKER — curated set with searchable keywords
# ──────────────────────────────────────────────────────────────────────────────
# (emoji, "space separated keywords") — searched as a simple substring match.

EMOJI_PICKS = [
    ("🚀","rocket launch project"),        ("📧","email envelope mail message"),
    ("🛒","cart shopping groceries"),       ("🎵","music note song playlist"),
    ("🖼","photo picture image"),          ("🌀","swirl cyclone whirlpool"),
    ("🎉","party celebrate confetti win"),  ("🎯","dart target goal focus"),
    ("🙏","pray hands thanks gratitude"),   ("✅","check done complete tick"),
    ("📌","pin pushpin point"),             ("⭐","star favorite"),
    ("✨","sparkles shine new"),            ("🔥","fire hot lit streak"),
    ("❤","heart love"),                   ("👍","thumbs up like good"),
    ("💡","bulb idea light"),               ("🕐","clock time"),
    ("📝","memo note write"),               ("📅","calendar date"),
    ("💰","money bag dollar donation"),     ("🎁","gift present"),
    ("🔑","key"),                           ("🏠","house home"),
    ("🚗","car vehicle drive"),             ("📱","phone mobile smartphone"),
    ("💻","laptop computer work github"),   ("☕","coffee drink tea"),
    ("📚","books read study"),              ("🏆","trophy award win"),
    ("⚠","warning alert caution hazard"),   ("❓","question"),
    ("❗","exclamation important"),         ("😀","smile happy"),
    ("🤔","thinking hmm"),                  ("😢","sad cry"),
    ("😂","laugh lol funny"),               ("😎","cool sunglasses"),
    ("👋","wave hello hi bye"),             ("👏","clap applause"),
    ("💪","muscle strong workout"),         ("👀","eyes look watch"),
    ("🌱","leaf plant grow seedling new"),  ("☀","sun sunny"),
    ("🌙","moon night"),                    ("☁","cloud weather"),
    ("✈","airplane travel flight aero"),    ("🧳","luggage travel bag"),
    ("🗺","map location"),                  ("📍","pin location map"),
    ("📷","camera photo"),                  ("🎨","paint art design"),
    ("⚙","gear settings"),                 ("🔒","lock secure"),
    ("🔔","bell notification reminder"),    ("🗑","trash delete bin"),
    ("📁","folder file"),                   ("📊","chart graph stats"),
    ("📈","trending up chart growth"),      ("🥇","medal first place"),
    ("🚩","flag mark"),                     ("❌","cross wrong no"),
    ("➕","plus add"),                      ("➡","arrow right next"),
    ("🔁","repeat loop"),                   ("⏳","hourglass waiting"),
    ("⏰","alarm clock reminder wake"),     ("🔧","wrench tool fix"),
    ("🔗","link chain"),                    ("📎","paperclip attach"),
    ("✂","scissors cut"),                  ("📏","ruler measure"),
    ("🌍","globe earth world"),             ("🌈","rainbow"),
    ("⚡","lightning zap energy fast"),     ("💎","gem diamond"),
    ("👑","crown king queen"),              ("🎂","cake birthday"),
    ("🍕","pizza food"),                    ("🍎","apple fruit food"),
    ("🏃","run exercise"),                  ("🧘","meditate calm yoga"),
    ("😴","sleep tired rest"),              ("🧠","brain think mind"),
    ("💯","hundred perfect"),               ("🙌","raised hands celebrate"),
    ("🤝","handshake deal agreement"),      ("🐶","dog pet animal"),
    ("🐱","cat pet animal"),                ("🌳","tree nature"),
    ("🌸","flower nature"),                 ("🎓","graduation cap school"),
    ("🦊","fox animal clever"),             ("🦁","lion king brave cat"),
    ("🦄","unicorn magic fantasy"),         ("🦖","t-rex dinosaur ancient"),
    ("🌶","hot pepper spicy food"),         ("🥑","avocado healthy food"),
    ("🍿","popcorn movie cinema snack"),    ("🍺","beer drink alcohol bar"),
    ("🛸","ufo alien space mystery"),       ("🌋","volcano eruption hot nature"),
    ("🏖","beach vacation summer sea"),     ("☃","snowman winter cold snow"),
    ("🎈","balloon party celebration"),     ("🎮","game controller play gaming"),
    ("🎲","dice game luck random"),         ("🛹","skateboard skate sports"),
    ("🎸","guitar music instrument"),       ("🎙","microphone podcast audio mic"),
    ("🎬","clapperboard movie film"),       ("🏥","hospital medical doctor health"),
    ("🔋","battery power charge"),          ("🔌","electric plug connect power"),
    ("📡","satellite antenna signal"),      ("🔮","crystal ball future magic"),
    ("🧬","dna science biology gene"),      ("🔬","microscope science lab study"),
    ("🔭","telescope space astronomy"),     ("💸","money fly cash wings wealth"),
    ("⚖","balance scale law justice"),     ("⚔","swords battle fight war"),
    ("🛡","shield defend protect security"),("🏹","bow arrow target archery"),
    ("🛋","couch sofa furniture living"),   ("🧼","soap clean wash hygiene"),
    ("🚪","door entry open close"),         ("📦","package box delivery shipping"),
    ("📮","mailbox post letter mail"),     ("📜","scroll history document paper"),
    ("🖤","black heart love dark"),         ("💔","broken heart sad breakup"),
    ("💥","explosion boom burst bang"),     ("💤","zzz sleep tired snoring"),
    ("🏁","checkered flag finish race"),    ("👑","crown king queen royalty"),
    ("🎃","halloween pumpkin scary"),       ("🎄","christmas tree holiday"),
    ("🎈","balloon party celebrate"),       ("💎","gem diamond jewel"),
    ("🔮","crystal ball magic witch"),      ("🧿","evil eye protection charm"),
    ("🤠","cowboy hat country western"),     ("🤡","clown joker funny scary"),
    ("👻","ghost spooky halloween spirit"),  ("👽","alien space extraterrestrial"),
    ("🤖","robot bot tech machine"),         ("👋","wave hello hi bye"),
    ("🍿","popcorn movie cinema snack"),    ("🥞","pancakes breakfast syrup food"),
    ("🍦","ice cream soft serve dessert"),   ("🍩","donut doughnut sweet dessert"),
    ("🍪","cookie biscuit sweet snack"),     ("🍫","chocolate bar candy sweet"),
    ("🍯","honey pot sweet bee"),           ("🦁","lion wild animal cat king"),
    ("🐼","panda bear animal cute"),         ("🦊","fox animal clever wildlife"),
    ("🐙","octopus sea creature tentacle"),  ("🐬","dolphin ocean sea marine"),
    ("🐝","bee honey insect bug"),           ("🕸","spiderweb cobweb spooky"),
    ("🎡","ferris wheel amusement park"),   ("🎢","roller coaster theme park"),
    ("🎪","circus tent carnival party"),     ("🎭","performing arts theater drama"),
    ("🎫","ticket admission event pass"),    ("🎖","military medal honor award"),
    ("🥊","boxing glove fight sports"),     ("🛹","skateboard skate deck"),
    ("🧩","puzzle piece match game"),       ("🎯","dart target goal bullseye"),
    ("🔮","crystal ball fortune magic"),    ("💈","barbershop pole hair cut"),
    ("💊","pill capsule medicine drug"),    ("🩺","stethoscope doctor medical"),
    ("🪓","axe chop wood tool"),            ("💣","bomb explode weapon danger"),
    ("🚬","cigarette smoking tobacco"),      ("⚰","coffin death funeral spooky"),
    ("💎","gem diamond crystal jewel"),     ("🔮","crystal ball magic fortune"),
    ("🧱","brick wall build material"),     ("🧵","thread sewing needle craft"),
    ("🧶","yarn knitting wool craft"),       ("🧷","safety pin clip attach"),
    ("🔑","key unlock secret password"),    ("🔓","unlock open lock secure"),
    ("🧸","teddy bear toy cute plush"),     ("🧹","broom clean sweep witch"),
    ("🧺","basket laundry picnic"),         ("🧻","toilet paper roll towel"),
]

# ──────────────────────────────────────────────────────────────────────────────
# MEDIA / CALL DETECTION  (Linux + Windows)
# ──────────────────────────────────────────────────────────────────────────────

# Process names where simply RUNNING means a call/stream is active.
# Only include apps that have no idle/background state — i.e. if the
# process exists, something live is happening.
# Apps like Discord, Slack, Teams, Skype sit in the tray normally,
# so we detect their active-call state via window titles instead.
_CALL_PROCESS_NAMES = {
    # Zoom: only spawns its main process during a meeting
    "zoom", "zoom.exe",
    # Webex meeting client (separate from the launcher)
    "ciscowebexmeetings", "ciscowebexmeetings.exe",
    # OBS: if it is running, you are streaming/recording
    "obs", "obs64", "obs.exe",
}

# Browser process names (for Meet/Teams-web/etc.)
_BROWSER_NAMES = {"chrome", "chromium", "firefox", "brave", "msedge",
                  "opera", "vivaldi", "waterfox"}

# Window title keywords that reliably indicate an ACTIVE call or live stream.
# Checked against ALL window titles (not just browsers) so they catch
# Discord, Slack, Teams, Skype native apps too when a call is live.
#   Discord during call  -> "Username - Call" or "Group Call"
#   Slack during huddle  -> "Slack | Calls" or "Huddle"
#   Teams during meeting -> "Microsoft Teams - Meeting"
#   Skype during call    -> "Skype | On a call"
_CALL_TITLE_KEYWORDS = {
    # Generic call indicators
    "- call",
    "group call",
    "on a call",
    "calling…", "calling...",
    "in a meeting",
    # App-specific active states
    "google meet",
    "zoom meeting",
    "teams meeting", "teams | meeting",
    "slack | calls", "slack calls", "huddle",
    "webex meeting",
    "jitsi",
    # Live streaming
    "youtube live",
    "twitch",
}


def _run(cmd):
    """Run a shell command and return stdout, swallowing all errors.
    On Windows, CREATE_NO_WINDOW prevents the brief CMD flash."""
    try:
        kwargs = dict(capture_output=True, text=True, timeout=2)
        if platform.system() == "Windows":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(cmd, **kwargs)
        return result.stdout.strip()
    except Exception:
        return ""


def is_audio_playing() -> bool:
    """
    Returns True if any application is currently sending audio to the
    default output sink (i.e. music/video is actively playing).

    Checks PulseAudio (pactl) and PipeWire (pw-cli) on Linux,
    and the Windows Audio Session API on Windows.
    """
    system = platform.system()

    if system == "Linux":
        # ── PulseAudio ────────────────────────────────────────────────────
        out = _run(["pactl", "list", "sink-inputs"])
        if out:
            # A "Corked" state means paused; "RUNNING" means active.
            # We look for at least one non-corked sink-input.
            import re
            sinks = re.split(r"Sink Input #\d+", out)
            for sink in sinks:
                if "RUNNING" in sink:
                    return True
            # Fallback: any sink input at all with no corked flag
            if "Corked: no" in out:
                return True

        # ── PipeWire fallback ─────────────────────────────────────────────
        out = _run(["pw-cli", "list-objects", "PipeWire:Interface:Node"])
        if out and "media.class = \"Audio/Sink\"" in out:
            # crude but effective: if any node is in a running state
            if "state: \"running\"" in out:
                return True

        return False

    elif system == "Windows":
        # Pure ctypes approach — no pycaw or comtypes needed.
        # We use the Windows Core Audio API (WASAPI) to enumerate audio
        # sessions and check their peak meter value. A non-zero peak means
        # audio is actively being rendered (music, video, call audio, etc.).
        try:
            import ctypes
            import ctypes.wintypes

            # ── COM GUIDs we need ─────────────────────────────────────────
            CLSID_MMDeviceEnumerator = "{BCDE0395-E52F-467C-8E3D-C4579291692E}"
            IID_IMMDeviceEnumerator  = "{A95664D2-9614-4F35-A746-DE8DB63617E6}"
            IID_IAudioSessionManager2 = "{77AA99A0-1BD6-484F-8BC7-2C654C9A9B6F}"
            IID_IAudioSessionEnumerator = "{E2F5BB11-0570-40CA-ACDD-3AA01277DEE8}"
            IID_IAudioSessionControl2   = "{BFB7FF88-7239-4FC9-8FA2-07C950BE9C6D}"
            IID_IAudioMeterInformation  = "{C02216F6-8C67-4B5B-9D00-D008E73E0064}"

            ole32    = ctypes.windll.ole32
            ole32.CoInitialize(None)

            # Helper to make a GUID struct from a string
            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", ctypes.c_ulong),
                    ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            def guid_from_str(s):
                g = GUID()
                ole32.CLSIDFromString(s, ctypes.byref(g))
                return g

            # Get the default audio render device
            clsid    = guid_from_str(CLSID_MMDeviceEnumerator)
            iid_enum = guid_from_str(IID_IMMDeviceEnumerator)
            enumerator = ctypes.POINTER(ctypes.c_void_p)()
            hr = ole32.CoCreateInstance(
                ctypes.byref(clsid), None, 1,  # CLSCTX_INPROC_SERVER
                ctypes.byref(iid_enum),
                ctypes.byref(enumerator)
            )
            if hr != 0:
                return False

            # IMMDeviceEnumerator::GetDefaultAudioEndpoint
            # eRender=0, eConsole=0
            IMMDeviceEnumerator_vtbl_offset_GetDefault = 4
            get_default = ctypes.cast(
                ctypes.cast(enumerator, ctypes.POINTER(ctypes.c_void_p))[0],
                ctypes.POINTER(ctypes.c_void_p)
            )[IMMDeviceEnumerator_vtbl_offset_GetDefault]

            device = ctypes.c_void_p()
            GetDefaultAudioEndpoint = ctypes.WINFUNCTYPE(
                ctypes.HRESULT,
                ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
                ctypes.POINTER(ctypes.c_void_p)
            )(get_default)
            hr = GetDefaultAudioEndpoint(enumerator, 0, 0, ctypes.byref(device))
            if hr != 0 or not device:
                return False

            # IMMDevice::Activate → IAudioSessionManager2
            iid_asm2  = guid_from_str(IID_IAudioSessionManager2)
            IMMDevice_vtbl_offset_Activate = 3
            activate_fn = ctypes.cast(
                ctypes.cast(device, ctypes.POINTER(ctypes.c_void_p))[0],
                ctypes.POINTER(ctypes.c_void_p)
            )[IMMDevice_vtbl_offset_Activate]

            asm2 = ctypes.c_void_p()
            Activate = ctypes.WINFUNCTYPE(
                ctypes.HRESULT,
                ctypes.c_void_p,
                ctypes.POINTER(GUID),
                ctypes.c_uint,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            )(activate_fn)
            hr = Activate(device, ctypes.byref(iid_asm2), 0, None, ctypes.byref(asm2))
            if hr != 0 or not asm2:
                return False

            # IAudioSessionManager2::GetSessionEnumerator
            iid_se = guid_from_str(IID_IAudioSessionEnumerator)
            GetSessionEnumerator = ctypes.WINFUNCTYPE(
                ctypes.HRESULT,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
            )(ctypes.cast(
                ctypes.cast(asm2, ctypes.POINTER(ctypes.c_void_p))[0],
                ctypes.POINTER(ctypes.c_void_p)
            )[5])

            session_enum = ctypes.c_void_p()
            hr = GetSessionEnumerator(asm2, ctypes.byref(session_enum))
            if hr != 0 or not session_enum:
                return False

            # GetCount
            GetCount = ctypes.WINFUNCTYPE(
                ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)
            )(ctypes.cast(
                ctypes.cast(session_enum, ctypes.POINTER(ctypes.c_void_p))[0],
                ctypes.POINTER(ctypes.c_void_p)
            )[3])
            count = ctypes.c_int(0)
            GetCount(session_enum, ctypes.byref(count))

            # GetSession + QueryInterface for IAudioMeterInformation
            GetSession = ctypes.WINFUNCTYPE(
                ctypes.HRESULT, ctypes.c_void_p, ctypes.c_int,
                ctypes.POINTER(ctypes.c_void_p)
            )(ctypes.cast(
                ctypes.cast(session_enum, ctypes.POINTER(ctypes.c_void_p))[0],
                ctypes.POINTER(ctypes.c_void_p)
            )[4])

            iid_meter = guid_from_str(IID_IAudioMeterInformation)
            for i in range(count.value):
                session_ctl = ctypes.c_void_p()
                hr = GetSession(session_enum, i, ctypes.byref(session_ctl))
                if hr != 0 or not session_ctl:
                    continue

                # QI for IAudioMeterInformation
                meter = ctypes.c_void_p()
                QueryInterface = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p,
                    ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)
                )(ctypes.cast(
                    ctypes.cast(session_ctl, ctypes.POINTER(ctypes.c_void_p))[0],
                    ctypes.POINTER(ctypes.c_void_p)
                )[0])
                hr = QueryInterface(session_ctl, ctypes.byref(iid_meter),
                                    ctypes.byref(meter))
                if hr != 0 or not meter:
                    continue

                # GetPeakValue
                peak = ctypes.c_float(0.0)
                GetPeakValue = ctypes.WINFUNCTYPE(
                    ctypes.HRESULT, ctypes.c_void_p, ctypes.POINTER(ctypes.c_float)
                )(ctypes.cast(
                    ctypes.cast(meter, ctypes.POINTER(ctypes.c_void_p))[0],
                    ctypes.POINTER(ctypes.c_void_p)
                )[3])
                GetPeakValue(meter, ctypes.byref(peak))
                if peak.value > 0.001:   # non-trivial audio level
                    return True

        except Exception:
            pass
        return False

    return False


def _get_running_process_names() -> set:
    """Return a lowercase set of currently running process names."""
    system = platform.system()
    names = set()
    if system == "Linux":
        out = _run(["ps", "-eo", "comm"])
        if out:
            names = {line.strip().lower() for line in out.splitlines() if line.strip()}
    elif system == "Windows":
        out = _run(["tasklist", "/fo", "csv", "/nh"])
        if out:
            import csv, io
            for row in csv.reader(io.StringIO(out)):
                if row:
                    names.add(row[0].strip().lower())
    return names


def _get_browser_window_titles() -> list:
    """
    Return a list of current window titles for known browsers.
    Uses xdotool on Linux (X11), wmctrl as fallback, and win32gui on Windows.
    """
    system = platform.system()
    titles = []

    if system == "Linux":
        # xdotool is more reliable; wmctrl is a fallback
        out = _run(["xdotool", "search", "--onlyvisible", "--name", ""])
        if not out:
            out = _run(["wmctrl", "-l"])
            if out:
                titles = [" ".join(line.split()[3:]).lower()
                          for line in out.splitlines()]
                return titles
        # xdotool returns window IDs; get names
        wids = out.splitlines()
        for wid in wids[:40]:                   # cap to avoid slowness
            name = _run(["xdotool", "getwindowname", wid.strip()])
            if name:
                titles.append(name.lower())

    elif system == "Windows":
        # Pure ctypes via user32.dll — no win32gui / pywin32 needed.
        try:
            import ctypes
            import ctypes.wintypes

            user32 = ctypes.windll.user32

            # Callback type for EnumWindows
            WNDENUMPROC = ctypes.WINFUNCTYPE(
                ctypes.wintypes.BOOL,
                ctypes.wintypes.HWND,
                ctypes.wintypes.LPARAM,
            )

            buf = ctypes.create_unicode_buffer(512)

            def _cb(hwnd, _lparam):
                if user32.IsWindowVisible(hwnd):
                    user32.GetWindowTextW(hwnd, buf, 512)
                    t = buf.value
                    if t:
                        titles.append(t.lower())
                return True   # continue enumeration

            user32.EnumWindows(WNDENUMPROC(_cb), 0)
        except Exception:
            pass

    return titles


def _get_all_window_titles() -> list:
    """
    Return titles of ALL visible windows (not just browsers).
    On Linux delegates to _get_browser_window_titles which already
    enumerates all windows; on Windows uses the same ctypes path.
    """
    # On Linux the existing function already returns all windows via
    # xdotool/wmctrl regardless of app — reuse it directly.
    if platform.system() == "Linux":
        return _get_browser_window_titles()
    # On Windows _get_browser_window_titles already enumerates every
    # visible window via EnumWindows, so reuse it here too.
    return _get_browser_window_titles()


def is_call_or_stream_active() -> bool:
    """
    Returns True if a video call, meeting, or media stream is likely
    in progress. Checks running processes and ALL window titles.
    """
    procs = _get_running_process_names()

    # Direct process match (only apps where running == active call)
    for call_proc in _CALL_PROCESS_NAMES:
        if call_proc in procs:
            return True

    # Check ALL window titles — this catches Discord, Slack, Teams, Skype
    # native apps in an active call as well as browser-based calls.
    titles = _get_all_window_titles()
    for title in titles:
        for kw in _CALL_TITLE_KEYWORDS:
            if kw in title:
                return True

    return False


# Cache for should_suppress() — re-evaluated every 5 seconds so we are
# not spawning subprocesses on every 500 ms poll tick.
_suppress_cache: bool = False
_suppress_cache_time: float = 0.0
_SUPPRESS_CACHE_TTL: float = 5.0   # seconds


def should_suppress() -> bool:
    """
    Master suppression check: returns True when IdleNote should NOT appear.
    Result is cached for _SUPPRESS_CACHE_TTL seconds to avoid hammering
    subprocesses (and flashing CMD windows) on every poll tick.
    """
    global _suppress_cache, _suppress_cache_time
    now = time.time()
    if now - _suppress_cache_time < _SUPPRESS_CACHE_TTL:
        return _suppress_cache
    try:
        result = is_audio_playing() or is_call_or_stream_active()
    except Exception:
        result = False
    _suppress_cache = result
    _suppress_cache_time = now
    return result

# ──────────────────────────────────────────────────────────────────────────────
# AUTOSTART
# ──────────────────────────────────────────────────────────────────────────────

def _windows_interpreter_for_autostart():
    """On Windows, running from source means sys.executable is python.exe —
    which always opens a console. Since that console IS the process hosting
    IdleNote (not a separate wrapper), closing it kills the whole app. Use
    pythonw.exe instead, the console-less variant every CPython install on
    Windows ships right alongside python.exe."""
    py = sys.executable
    if os.path.basename(py).lower() == "python.exe":
        pyw = os.path.join(os.path.dirname(py), "pythonw.exe")
        if os.path.exists(pyw):
            return pyw
    return py

def set_autostart(enable=True):
    system = platform.system()
    if system == "Windows":
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                interpreter = _windows_interpreter_for_autostart()
                exe_path = f'"{interpreter}" "{os.path.abspath(__file__)}"'
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
        autostart_dir  = os.path.expanduser("~/.config/autostart")
        desktop_file   = os.path.join(autostart_dir, "idlenote.desktop")
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

def _selfheal_autostart():
    """One-time repair for anyone who already has the old python.exe (console)
    entry registered from a previous version — silently re-points it at
    pythonw.exe so the boot-time console window stops appearing. No-op for
    frozen .exe installs and for anyone already on pythonw.exe or Linux."""
    if platform.system() != "Windows" or getattr(sys, "frozen", False):
        return
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, "IdleNote")
        if "pythonw.exe" not in value.lower() and "python.exe" in value.lower():
            set_autostart(True)
    except Exception:
        pass

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
# NOTE STORE — multiple named notes on disk
# ──────────────────────────────────────────────────────────────────────────────
# One small JSON index (name, order, which one is active) plus one .txt file
# per note. Transparently migrates anyone still on the old single notes.txt.

class NoteStore:
    def __init__(self):
        self.dir = os.path.join(APP_DIR, "notes")
        os.makedirs(self.dir, exist_ok=True)
        self.index_path = os.path.join(APP_DIR, "notes_index.json")
        self._load_or_migrate()

    def _note_path(self, nid):
        return os.path.join(self.dir, f"{nid}.txt")

    def _save_index(self):
        try:
            json.dump(self._index, open(self.index_path, "w"), indent=2)
        except Exception:
            pass

    def _load_or_migrate(self):
        if os.path.exists(self.index_path):
            try:
                idx = json.load(open(self.index_path))
                if idx.get("order") and idx.get("notes"):
                    self._index = idx
                    return
            except Exception:
                pass
        # No usable index yet — migrate the legacy single-file note if present,
        # otherwise just start with one empty note.
        nid = uuid.uuid4().hex[:8]
        legacy_content = ""
        if os.path.exists(NOTES_FILE):
            try:
                with open(NOTES_FILE, "r", encoding="utf-8") as f:
                    legacy_content = f.read()
            except Exception:
                pass
        now = datetime.datetime.now().isoformat()
        self._index = {
            "order":  [nid],
            "active": nid,
            "notes":  {nid: {"name": "Note 1", "created": now, "modified": now}},
        }
        try:
            with open(self._note_path(nid), "w", encoding="utf-8") as f:
                f.write(legacy_content)
        except Exception:
            pass
        self._save_index()

    # ── reads ────────────────────────────────────────────────────────────────
    @property
    def active_id(self):
        return self._index["active"]

    def list(self):
        """[(id, name), ...] in display order."""
        return [(nid, self._index["notes"][nid]["name"])
                for nid in self._index["order"] if nid in self._index["notes"]]

    def get_name(self, nid):
        return self._index["notes"].get(nid, {}).get("name", "Note")

    def get_content(self, nid):
        try:
            with open(self._note_path(nid), "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def search(self, query, live_id=None, live_content=None):
        """Cross-note search by name or content. live_content lets the caller
        supply the currently-edited (possibly unsaved) text for live_id so the
        search reflects what's on screen, not just what's last saved to disk."""
        q = query.lower()
        results = []
        for nid, name in self.list():
            content = live_content if (nid == live_id and live_content is not None) \
                      else self.get_content(nid)
            name_hit = q in name.lower()
            idx = content.lower().find(q)
            if name_hit or idx != -1:
                snippet = None
                if idx != -1:
                    snippet = content[max(0, idx-15):idx+25].replace("\n", " ").strip()
                results.append((nid, name, snippet))
        return results

    # ── writes ───────────────────────────────────────────────────────────────
    def set_content(self, nid, content):
        try:
            with open(self._note_path(nid), "w", encoding="utf-8") as f:
                f.write(content)
            if nid in self._index["notes"]:
                self._index["notes"][nid]["modified"] = datetime.datetime.now().isoformat()
                self._save_index()
        except Exception:
            pass

    def set_active(self, nid):
        if nid in self._index["notes"]:
            self._index["active"] = nid
            self._save_index()

    def create(self, name=None):
        nid = uuid.uuid4().hex[:8]
        if not name:
            existing = {v["name"] for v in self._index["notes"].values()}
            n = len(self._index["order"]) + 1
            while f"Note {n}" in existing:
                n += 1
            name = f"Note {n}"
        now = datetime.datetime.now().isoformat()
        self._index["notes"][nid] = {"name": name, "created": now, "modified": now}
        self._index["order"].append(nid)
        try:
            open(self._note_path(nid), "w", encoding="utf-8").close()
        except Exception:
            pass
        self._save_index()
        return nid

    def rename(self, nid, new_name):
        new_name = new_name.strip()[:60]
        if nid in self._index["notes"] and new_name:
            self._index["notes"][nid]["name"] = new_name
            self._save_index()

    def delete(self, nid):
        """Returns True if deleted. Refuses to delete the last remaining note."""
        if len(self._index["order"]) <= 1 or nid not in self._index["notes"]:
            return False
        was_active = (nid == self._index["active"])
        self._index["order"].remove(nid)
        del self._index["notes"][nid]
        try:
            p = self._note_path(nid)
            if os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
        if was_active:
            self._index["active"] = self._index["order"][0]
        self._save_index()
        return True

# ──────────────────────────────────────────────────────────────────────────────
# SETTINGS WINDOW
# ──────────────────────────────────────────────────────────────────────────────

class SettingsWindow:
    def __init__(self, app):
        self.app = app

    def open(self):
        s   = self.app.settings
        pal = palette(s)
        F   = "Consolas"
        win = tk.Toplevel()
        win.title("IdleNote — Settings")
        win.resizable(False, False)
        win.configure(bg=pal["settings_bg"])
        win.attributes("-topmost", True)

        # Header
        tk.Label(win, text="✦ IDLENOTE SETTINGS",
                 bg=pal["settings_bg"], fg=pal["accent"],
                 font=(F, 11, "bold")).grid(
            row=0, column=0, columnspan=3,
            padx=20, pady=(18, 10), sticky="w")

        lbl = dict(bg=pal["settings_bg"], fg=pal["settings_label"], font=(F, 9), anchor="w")
        val = dict(bg=pal["settings_bg"], fg=pal["accent"], font=(F, 9), width=6, anchor="e")

        row_i = [1]

        def slider_row(text, var, lo, hi, fmt=None):
            r = row_i[0]; row_i[0] += 1
            tk.Label(win, text=text, **lbl).grid(row=r, column=0, padx=(20,8), pady=5, sticky="w")
            disp = tk.StringVar(value=(fmt(var.get()) if fmt else str(var.get())))
            var.trace_add("write", lambda *_: disp.set(fmt(var.get()) if fmt else str(var.get())))
            tk.Scale(win, from_=lo, to=hi, orient="horizontal",
                     variable=var, bg=pal["settings_bg"], fg=pal["settings_label"],
                     troughcolor=pal["slider_trough"], activebackground=pal["accent"],
                     highlightthickness=0, bd=0, length=170,
                     showvalue=False, cursor="hand2").grid(row=r, column=1, pady=5)
            tk.Label(win, textvariable=disp, **val).grid(row=r, column=2, padx=(4,20))

        kb_var    = tk.IntVar(value=s["kb_idle_secs"])
        mouse_var = tk.IntVar(value=s["mouse_idle_secs"])
        op_var    = tk.IntVar(value=int(s["opacity"] * 100))
        font_var  = tk.IntVar(value=s.get("font_size", 11))

        slider_row("Keyboard idle",    kb_var,    2, 300, fmt_secs)
        slider_row("Mouse idle",       mouse_var, 2, 300, fmt_secs)
        slider_row("Opacity",          op_var,    40, 100, lambda v: f"{v}%")
        slider_row("Font size",        font_var,  8, 28,  lambda v: f"{v}px")

        # Divider
        tk.Frame(win, bg=pal["border"], height=1).grid(
            row=row_i[0], column=0, columnspan=3, sticky="ew", padx=20, pady=(8,4))
        row_i[0] += 1

        # Theme picker
        tk.Label(win, text="Theme", **lbl).grid(row=row_i[0], column=0, padx=(20,8), pady=5, sticky="w")
        theme_var = tk.StringVar(value=s.get("theme", "dark"))
        theme_frame = tk.Frame(win, bg=pal["settings_bg"])
        theme_frame.grid(row=row_i[0], column=1, columnspan=2, sticky="w", pady=5)

        theme_btns = []
        def refresh_theme_btns():
            for b, value in theme_btns:
                sel = theme_var.get() == value
                b.config(bg=pal["accent"] if sel else pal["slider_trough"],
                         fg="#13131a" if sel else pal["settings_label"])

        for label, value in (("Dark", "dark"), ("Light", "light")):
            b = tk.Label(theme_frame, text=label, font=(F, 9), padx=10, pady=4, cursor="hand2")
            b.bind("<Button-1>", lambda e, v=value: (theme_var.set(v), refresh_theme_btns()))
            b.pack(side="left", padx=(0, 6))
            theme_btns.append((b, value))
        refresh_theme_btns()
        row_i[0] += 1

        # Accent picker
        tk.Label(win, text="Accent", **lbl).grid(row=row_i[0], column=0, padx=(20,8), pady=5, sticky="w")
        accent_var = tk.StringVar(value=s.get("accent", "orange"))
        accent_frame = tk.Frame(win, bg=pal["settings_bg"])
        accent_frame.grid(row=row_i[0], column=1, columnspan=2, sticky="w", pady=5)

        swatches = []
        def refresh_swatches():
            for sw, key in swatches:
                sw.config(text="✓" if accent_var.get() == key else "")

        for key, info in ACCENTS.items():
            sw = tk.Label(accent_frame, text="", bg=info["base"], fg="#ffffff",
                          width=2, height=1, font=(F, 9, "bold"), cursor="hand2")
            sw.bind("<Button-1>", lambda e, k=key: (accent_var.set(k), refresh_swatches()))
            sw.pack(side="left", padx=3)
            swatches.append((sw, key))
        refresh_swatches()
        row_i[0] += 1

        # Divider
        tk.Frame(win, bg=pal["border"], height=1).grid(
            row=row_i[0], column=0, columnspan=3, sticky="ew", padx=20, pady=(4,0))
        row_i[0] += 1

        # Autostart toggle
        auto_var = tk.BooleanVar(value=is_autostart_enabled())
        tk.Checkbutton(
            win, text="Run on system startup",
            variable=auto_var,
            bg=pal["settings_bg"], fg=pal["settings_label"],
            selectcolor=pal["slider_trough"],
            activebackground=pal["settings_bg"], activeforeground=pal["title_fg"],
            font=(F, 9),
            cursor="hand2"
        ).grid(row=row_i[0], column=0, columnspan=3, padx=20, pady=(10, 4), sticky="w")
        row_i[0] += 1

        # Buttons
        btn_frame = tk.Frame(win, bg=pal["settings_bg"])
        btn_frame.grid(row=row_i[0], column=0, columnspan=3, padx=20, pady=(10, 18), sticky="ew")

        def apply_close():
            s["kb_idle_secs"]    = kb_var.get()
            s["mouse_idle_secs"] = mouse_var.get()
            s["opacity"]         = op_var.get() / 100.0
            s["font_size"]       = font_var.get()
            s["theme"]           = theme_var.get()
            s["accent"]          = accent_var.get()
            save_settings(s)
            set_autostart(auto_var.get())
            self.app.apply_settings()
            win.destroy()

        tk.Button(btn_frame, text="Apply & Close",
                  command=apply_close,
                  bg=pal["accent"], fg="#fff5ee",
                  font=(F, 9, "bold"),
                  relief="flat", padx=16, pady=7,
                  activebackground=pal["accent_hover"],
                  cursor="hand2").pack(side="left")
        tk.Button(btn_frame, text="Cancel",
                  command=win.destroy,
                  bg=pal["slider_trough"], fg=pal["settings_label"],
                  font=(F, 9),
                  relief="flat", padx=16, pady=7,
                  activebackground=pal["border"],
                  cursor="hand2").pack(side="left", padx=(8, 0))

        win.update_idletasks()
        sw_, sh_ = win.winfo_screenwidth(), win.winfo_screenheight()
        ww, wh = win.winfo_reqwidth(),    win.winfo_reqheight()
        win.geometry(f"+{(sw_-ww)//2}+{(sh_-wh)//2}")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN APP
# ──────────────────────────────────────────────────────────────────────────────

class IdleNoteApp:
    FADE_STEPS = 14
    FADE_MS    = 14

    def __init__(self):
        self.settings  = load_settings()
        self._pal      = palette(self.settings)
        self.tracker   = IdleTracker()
        self.notes     = NoteStore()
        self._fade_job = None
        self._poll_job = None
        self._save_job = None
        self._visible  = False
        self._cur_alpha = 0.0
        self._dragging  = False
        self._drag_ox = self._drag_oy = 0
        self._drag_moved  = False
        self._drag_widget = None
        self._grip_hover     = False
        self._snoozed_until  = 0.0
        self._snoozed_indef  = False
        self._search_matches = []
        self._search_idx     = 0
        self._build_window()
        self._load_note()
        self.tracker.start()
        if HAS_TRAY:
            self._build_tray()

        # Enable autostart silently on first run
        if not is_autostart_enabled():
            set_autostart(True)

        # ── FIX: intercept OS/WM close so the window only hides ──────────
        # Without this, closing the window on Linux destroys the Tk root
        # and the whole process exits — even when running detached.
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_btn)

        # ── FIX: handle SIGTERM / SIGHUP gracefully (terminal detach) ────
        # When you close the terminal or the session ends, the OS sends
        # SIGHUP to the process. We catch it so the process keeps running.
        if platform.system() != "Windows":
            signal.signal(signal.SIGHUP, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)

        self._poll()

    def _handle_signal(self, signum, frame):
        """Called on SIGHUP / SIGTERM. Save and keep running (SIGHUP) or quit (SIGTERM)."""
        self._do_save()
        if signum == signal.SIGTERM:
            # Schedule a clean quit on the Tk event loop thread
            self.root.after(0, self._quit)
        # SIGHUP → just keep running (terminal was closed, process stays alive)

    # ── BUILD WINDOW ──────────────────────────────────────────────────────

    def _build_window(self):
        self.root = tk.Tk()
        self.root.title("IdleNote")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.0)
        self.root.withdraw()

        s = self.settings
        W, H = int(s["width"]), int(s["height"])

        # Position — self-heal if it would land off-screen (e.g. a monitor
        # that's since been unplugged), otherwise use the saved spot.
        x, y = s.get("win_x"), s.get("win_y")
        if x is None or y is None or not self._is_onscreen(x, y, W, H):
            x, y = self._default_anchor(W, H)
            s["win_x"], s["win_y"] = x, y
        self.root.geometry(f"{W}x{H}+{int(x)}+{int(y)}")

        F = "Consolas"

        # ── OUTER SHELL ───────────────────────────────────────────────────
        self.shell = tk.Frame(self.root, highlightthickness=2)
        self.shell.pack(fill="both", expand=True)

        # ── TITLE BAR ─────────────────────────────────────────────────────
        self.bar = tk.Frame(self.shell, height=30)
        self.bar.pack(fill="x")
        self.bar.pack_propagate(False)

        self.lbl_icon = tk.Label(self.bar, text="✦")
        self.lbl_icon.pack(side="left", padx=(10, 4))

        # Brand label — always reads "idlenote", never changes.
        self.lbl_app = tk.Label(self.bar, text="idlenote")
        self.lbl_app.pack(side="left")

        self.lbl_sep = tk.Label(self.bar, text="›")
        self.lbl_sep.pack(side="left", padx=(4, 4))

        # Active note's name — click (without dragging) opens the switcher.
        self.lbl_title = tk.Label(self.bar, text="Note 1", cursor="hand2")
        self.lbl_title.pack(side="left")

        # Caret — same click-opens-switcher behavior, just a clearer affordance.
        self.lbl_caret = tk.Label(self.bar, text="▾", cursor="hand2", padx=4)
        self.lbl_caret.pack(side="left")

        # Close button
        self.btn_close = tk.Label(self.bar, text="✕", cursor="hand2", padx=10)
        self.btn_close.pack(side="right")
        self.btn_close.bind("<Enter>",    lambda e: self.btn_close.config(fg=self._pal["close_hover"]))
        self.btn_close.bind("<Leave>",    lambda e: self.btn_close.config(fg=self._pal["close_idle"]))
        self.btn_close.bind("<Button-1>", self._on_close_btn)

        # Last-edited label
        self.lbl_time = tk.Label(self.bar, text="")
        self.lbl_time.pack(side="right", padx=(0, 2))

        # Drag bindings on the whole bar. lbl_title/lbl_caret use the same
        # press/motion/release chain as everything else (so a press-and-drag
        # anywhere still moves the window), but _drag_end() opens the switcher
        # instead if the press happened on one of those two AND the mouse
        # never actually moved — i.e. it was a click, not a drag.
        for w in (self.bar, self.lbl_icon, self.lbl_app, self.lbl_sep, self.lbl_title, self.lbl_caret):
            w.bind("<ButtonPress-1>",  self._drag_start)
            w.bind("<B1-Motion>",      self._drag_motion)
            w.bind("<ButtonRelease-1>",self._drag_end)

        # ── INLINE SEARCH BAR (hidden until Ctrl+F) ─────────────────────────
        self.search_bar = tk.Frame(self.shell)
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(self.search_bar, textvariable=self.search_var,
                                     relief="flat", font=(F, 9), bd=0)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(8,4), pady=4)
        self.search_count = tk.Label(self.search_bar, text="", font=(F, 8))
        self.search_count.pack(side="left", padx=2)
        self.btn_search_prev = tk.Label(self.search_bar, text="▴", cursor="hand2", font=(F, 8), padx=4)
        self.btn_search_next = tk.Label(self.search_bar, text="▾", cursor="hand2", font=(F, 8), padx=4)
        self.btn_search_close = tk.Label(self.search_bar, text="✕", cursor="hand2", font=(F, 8), padx=6)
        self.btn_search_prev.pack(side="left")
        self.btn_search_next.pack(side="left")
        self.btn_search_close.pack(side="left")
        self.btn_search_prev.bind("<Button-1>",  lambda e: self._search_step(-1))
        self.btn_search_next.bind("<Button-1>",  lambda e: self._search_step(1))
        self.btn_search_close.bind("<Button-1>", lambda e: self._search_close())
        self.search_var.trace_add("write", lambda *_: self._search_refresh())
        self.search_entry.bind("<Return>",       lambda e: self._search_step(1))
        self.search_entry.bind("<Shift-Return>", lambda e: self._search_step(-1))
        self.search_entry.bind("<Escape>",       lambda e: self._search_close())
        # search_bar is not packed yet — _open_search() packs it on demand

        # ── FOOTER ────────────────────────────────────────────────────────
        # Packed BEFORE the (expand=True) text area below, and pinned to the
        # bottom — otherwise Tk's packer hands the text area all the leftover
        # cavity first and the footer (and the resize grip living in it)
        # collapses to zero height. This was a pre-existing bug, not just a
        # missing glyph: the grip really wasn't there.
        self.footer = tk.Frame(self.shell, height=22)
        self.footer.pack(side="bottom", fill="x")
        self.footer.pack_propagate(False)

        self.lbl_chars = tk.Label(self.footer, text="", font=(F, 7))
        self.lbl_chars.pack(side="right", padx=10)

        # Resize grip — drawn on a Canvas (dots), not a font glyph, so it
        # always renders regardless of what monospace font is installed.
        self.grip = tk.Canvas(self.footer, width=16, height=16,
                              highlightthickness=0, cursor="sizing")
        self.grip.pack(side="right", padx=(0, 6))
        self.grip.bind("<ButtonPress-1>",   self._resize_start)
        self.grip.bind("<B1-Motion>",       self._resize_motion)
        self.grip.bind("<ButtonRelease-1>", self._resize_end)
        self.grip.bind("<Enter>", lambda e: (setattr(self, "_grip_hover", True),  self._draw_grip()))
        self.grip.bind("<Leave>", lambda e: (setattr(self, "_grip_hover", False), self._draw_grip()))

        # Saved indicator
        self.lbl_saved = tk.Label(self.footer, text="", font=(F, 7))
        self.lbl_saved.pack(side="left", padx=(10, 0))

        # Snooze toggle — plain ASCII text on purpose (see grip comment above).
        self.btn_snooze = tk.Label(self.footer, text="zzz", cursor="hand2",
                                   font=(F, 7), padx=6)
        self.btn_snooze.pack(side="left")
        self.btn_snooze.bind("<Button-1>", self._on_snooze_click)

        # ── TEXT AREA ─────────────────────────────────────────────────────
        self.txt_frame = tk.Frame(self.shell)
        self.txt_frame.pack(fill="both", expand=True)

        self.txt = tk.Text(
            self.txt_frame,
            font=(F, s.get("font_size", 11)),
            relief="flat", wrap="word",
            padx=14, pady=12,
            spacing1=2, spacing3=3,
            undo=True,
            highlightthickness=0,
            cursor="xterm", bd=0,
        )
        self.txt.pack(side="left", fill="both", expand=True)

        self.sb = tk.Scrollbar(self.txt_frame, command=self.txt.yview,
                               width=5, relief="flat", bd=0)
        self.txt.configure(yscrollcommand=self._sb_set)

        # ── TEXT BINDINGS ─────────────────────────────────────────────────
        self.txt.bind("<<Modified>>", self._on_modified)
        self.txt.bind("<Control-f>", self._open_search)
        self.root.bind("<Control-f>", self._open_search)

        # Right-click menu
        self.txt.bind("<Button-3>", self._ctx_menu)
        self.bar.bind("<Button-3>", self._ctx_menu)

        self._restyle()

    def _sb_set(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.sb.pack_forget()
        else:
            self.sb.pack(side="right", fill="y", before=self.txt)
            self.sb.set(lo, hi)

    # ── APPEARANCE ────────────────────────────────────────────────────────────

    def _restyle(self):
        """Re-apply theme + accent + font size to every widget. Called once at
        build time and again whenever Settings are applied, so all the colors
        live in THEMES/ACCENTS rather than being duplicated here and there."""
        pal = palette(self.settings)
        self._pal = pal
        fs = int(self.settings.get("font_size", 11))
        F  = "Consolas"
        title_fs = max(8, fs - 2)
        small_fs = max(7, fs - 4)

        self.root.configure(bg=pal["shell_bg"])
        self.shell.configure(bg=pal["shell_bg"], highlightbackground=pal["border"],
                              highlightcolor=pal["border"])
        self.bar.configure(bg=pal["bar_bg"])
        self.lbl_icon.configure(bg=pal["bar_bg"], fg=pal["accent"], font=(F, small_fs))
        self.lbl_app.configure(bg=pal["bar_bg"], fg=pal["title_fg"], font=(F, small_fs))
        self.lbl_sep.configure(bg=pal["bar_bg"], fg=pal["dim_fg"], font=(F, small_fs))
        self.lbl_title.configure(bg=pal["bar_bg"], fg=pal["accent"], font=(F, small_fs))
        self.lbl_caret.configure(bg=pal["bar_bg"], fg=pal["dim_fg"], font=(F, small_fs-1 if small_fs>7 else small_fs))
        self.btn_close.configure(bg=pal["bar_bg"], fg=pal["close_idle"], font=(F, title_fs))
        self.lbl_time.configure(bg=pal["bar_bg"], fg=pal["dim_fg"], font=(F, small_fs))

        self.search_bar.configure(bg=pal["bar_bg"])
        self.search_entry.configure(bg=pal["text_bg"], fg=pal["text_fg"],
                                     insertbackground=pal["accent"])
        self.search_count.configure(bg=pal["bar_bg"], fg=pal["dim_fg"])
        for b in (self.btn_search_prev, self.btn_search_next, self.btn_search_close):
            b.configure(bg=pal["bar_bg"], fg=pal["dim_fg"])

        self.txt_frame.configure(bg=pal["text_bg"])
        self.txt.configure(bg=pal["text_bg"], fg=pal["text_fg"],
                            insertbackground=pal["accent"], font=(F, fs),
                            selectbackground=pal["select_bg"], selectforeground=pal["select_fg"])
        self.txt.tag_configure("search_hit", background=pal["select_bg"])
        self.txt.tag_configure("search_current", background=pal["accent"], foreground="#13131a")

        self.sb.configure(bg=pal["scrollbar_bg"], troughcolor=pal["scrollbar_trough"],
                          activebackground=pal["accent"])

        self.footer.configure(bg=pal["footer_bg"])
        self.lbl_chars.configure(bg=pal["footer_bg"], fg=pal["dim_fg"], font=(F, small_fs))
        self.lbl_saved.configure(bg=pal["footer_bg"], fg=pal["saved_fg"], font=(F, small_fs))
        self.btn_snooze.configure(
            bg=pal["footer_bg"], font=(F, small_fs),
            fg=pal["snooze_active"] if self._is_snoozed() else pal["dim_fg"])
        self.grip.configure(bg=pal["footer_bg"])
        self._draw_grip()

    def _draw_grip(self):
        pal = self._pal
        self.grip.delete("all")
        color = pal["accent"] if self._grip_hover else pal["dim_fg"]
        for x, y in ((12,12),(12,8),(8,12),(12,4),(8,8),(4,12)):
            self.grip.create_oval(x-1, y-1, x+1, y+1, fill=color, outline=color)

    # ── DRAG ──────────────────────────────────────────────────────────────────

    def _drag_start(self, e):
        self._dragging   = True
        self._drag_moved = False
        self._drag_widget = e.widget
        self._drag_ox  = e.x_root - self.root.winfo_x()
        self._drag_oy  = e.y_root - self.root.winfo_y()
        self._drag_start_x = e.x_root
        self._drag_start_y = e.y_root

    def _drag_motion(self, e):
        if self._dragging:
            if abs(e.x_root - self._drag_start_x) > 3 or abs(e.y_root - self._drag_start_y) > 3:
                self._drag_moved = True
            self.root.geometry(f"+{e.x_root - self._drag_ox}+{e.y_root - self._drag_oy}")

    def _drag_end(self, e):
        self._dragging = False
        self.settings["win_x"] = self.root.winfo_x()
        self.settings["win_y"] = self.root.winfo_y()
        save_settings(self.settings)
        if not self._drag_moved and self._drag_widget in (self.lbl_title, self.lbl_caret):
            self._open_switcher(e)

    # ── RESIZE ────────────────────────────────────────────────────────────────

    def _resize_start(self, e):
        self._rx = e.x_root; self._ry = e.y_root
        self._rw = self.root.winfo_width()
        self._rh = self.root.winfo_height()

    def _resize_motion(self, e):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        nw = max(260, min(self._rw + (e.x_root - self._rx), sw - 40))
        nh = max(160, min(self._rh + (e.y_root - self._ry), sh - 80))
        self.root.geometry(f"{nw}x{nh}")

    def _resize_end(self, e):
        self.settings["width"]  = self.root.winfo_width()
        self.settings["height"] = self.root.winfo_height()
        save_settings(self.settings)

    # ── POSITION RECOVERY ("bring note back") ───────────────────────────────

    def _default_anchor(self, w=None, h=None):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w  = w or int(self.settings.get("width", 360))
        h  = h or int(self.settings.get("height", 260))
        return sw - w - 16, sh - h - 52

    def _is_onscreen(self, x, y, w, h, margin=60):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        return (x + w > margin and x < sw - margin and
                y + h > margin and y < sh - margin)

    def _recall(self):
        """Manual 'bring note back' — always snaps to a visible spot on the
        current primary display, regardless of where it drifted to."""
        w = int(self.settings.get("width", 360))
        h = int(self.settings.get("height", 260))
        x, y = self._default_anchor(w, h)
        self.root.geometry(f"+{x}+{y}")
        self.settings["win_x"], self.settings["win_y"] = x, y
        save_settings(self.settings)
        if self._visible:
            self.root.lift()
        else:
            self.show()

    # ── SNOOZE ────────────────────────────────────────────────────────────────

    def _is_snoozed(self):
        return self._snoozed_indef or time.time() < self._snoozed_until

    def _cancel_snooze(self):
        self._snoozed_until = 0.0
        self._snoozed_indef = False
        if hasattr(self, "btn_snooze"):
            self.btn_snooze.configure(fg=self._pal["dim_fg"])

    def _snooze_for(self, secs):
        self._snoozed_until = time.time() + secs
        self._snoozed_indef = False
        self.btn_snooze.configure(fg=self._pal["snooze_active"])

    def _snooze_indef(self):
        self._snoozed_indef = True
        self.btn_snooze.configure(fg=self._pal["snooze_active"])

    def _is_descendant(self, widget, ancestor):
        w = widget
        while w is not None:
            if w == ancestor:
                return True
            try:
                w = w.master
            except Exception:
                return False
        return False

    def _autoclose_popup(self, pop):
        """Bind a robust 'close when focus truly leaves' handler. A naive
        FocusOut bound straight on the Toplevel fires on ANY internal focus
        shuffle between its own children (e.g. moving from a filter box to a
        rename box), destroying the popup mid-interaction. Deferring one tick
        and checking whether the new focus widget is still inside this popup
        avoids that false trigger while still closing on a genuine click-away."""
        def maybe_close(e=None):
            def check():
                try:
                    cur = pop.focus_get()
                except Exception:
                    cur = None
                if cur is None or not self._is_descendant(cur, pop):
                    try:
                        pop.destroy()
                    except Exception:
                        pass
            try:
                pop.after(80, check)
            except Exception:
                pass
        pop.bind("<FocusOut>", maybe_close)

    def _on_snooze_click(self, e=None):
        if self._is_snoozed():
            self._cancel_snooze()
            return
        pal = self._pal
        pop = tk.Toplevel(self.root)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.configure(bg=pal["bar_bg"], highlightthickness=1, highlightbackground=pal["border"])
        x = self.btn_snooze.winfo_rootx()
        y = self.btn_snooze.winfo_rooty()
        pop.geometry(f"+{x}+{y-112}")

        def choose(secs):
            def _go():
                if secs is None:
                    self._snooze_indef()
                else:
                    self._snooze_for(secs)
                pop.destroy()
            return _go

        for label, secs in (("15 min", 900), ("30 min", 1800), ("1 hour", 3600), ("Until I reopen it", None)):
            b = tk.Label(pop, text=label, bg=pal["bar_bg"], fg=pal["text_fg"],
                        font=("Consolas", 8), cursor="hand2", anchor="w", padx=10, pady=5)
            b.pack(fill="x")
            b.bind("<Button-1>", lambda e, fn=choose(secs): fn())
            b.bind("<Enter>", lambda e, w=b: w.config(bg=pal["accent"], fg="#13131a"))
            b.bind("<Leave>", lambda e, w=b: w.config(bg=pal["bar_bg"], fg=pal["text_fg"]))

        self._autoclose_popup(pop)
        pop.focus_force()

    # ── EMOJI PICKER ──────────────────────────────────────────────────────────

    def _open_emoji_picker(self, e=None):
        pal = self._pal
        F = "Consolas"
        cols, visible_rows = 7, 4

        pop = tk.Toplevel(self.root)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.configure(bg=pal["bar_bg"], highlightthickness=1, highlightbackground=pal["border"])

        filter_var = tk.StringVar()
        entry = tk.Entry(pop, textvariable=filter_var, bg=pal["text_bg"], fg=pal["text_fg"],
                         insertbackground=pal["accent"], relief="flat", font=(F, 9))
        entry.pack(fill="x", padx=6, pady=(6, 4))

        # Scrollable viewport: a Canvas hosting the actual grid Frame, capped
        # to `visible_rows` tall. A custom mini scrollbar (not a native
        # tk.Scrollbar — its OS-chrome arrow buttons clash with the flat
        # theme, and dragging it takes a click-then-grab) appears only when
        # there are more rows than that to show.
        viewport = tk.Frame(pop, bg=pal["bar_bg"])
        viewport.pack(padx=4, pady=(0, 6))

        canvas = tk.Canvas(viewport, bg=pal["bar_bg"], highlightthickness=0)
        canvas.pack(side="left")

        SB_W = 6
        sb = tk.Canvas(viewport, width=SB_W, bg=pal["bar_bg"], highlightthickness=0)
        sb_state = {"lo": 0.0, "hi": 1.0, "active": False}

        def sb_draw():
            sb.delete("all")
            h = sb.winfo_height()
            if h <= 1:
                return
            lo, hi = sb_state["lo"], sb_state["hi"]
            y0, y1 = lo * h, hi * h
            if y1 - y0 < 16:                       # keep the thumb grabbable when tiny
                mid = (y0 + y1) / 2
                y0, y1 = max(0, mid - 8), min(h, mid + 8)
            color = pal["accent"] if sb_state["active"] else pal["dim_fg"]
            sb.create_rectangle(1, y0, SB_W - 1, y1, fill=color, outline="")

        def sb_yscrollcommand(lo, hi):
            sb_state["lo"], sb_state["hi"] = float(lo), float(hi)
            sb_draw()

        canvas.configure(yscrollcommand=sb_yscrollcommand)

        def sb_scroll_to(y):
            h = sb.winfo_height()
            if h <= 1:
                return
            span = sb_state["hi"] - sb_state["lo"]
            target = (y / h) - span / 2            # center the thumb under the cursor
            canvas.yview_moveto(max(0.0, min(1.0 - span, target)))

        def sb_press(ev):
            sb_state["active"] = True
            sb_draw()
            sb_scroll_to(ev.y)                     # grab-and-scroll in the same gesture

        def sb_motion(ev):
            sb_scroll_to(ev.y)

        def sb_release(ev):
            sb_state["active"] = False
            sb_draw()

        sb.bind("<Button-1>", sb_press)
        sb.bind("<B1-Motion>", sb_motion)
        sb.bind("<ButtonRelease-1>", sb_release)
        sb.bind("<Enter>", lambda ev: (sb_state.__setitem__("active", True),  sb_draw()))
        sb.bind("<Leave>", lambda ev: (sb_state.__setitem__("active", False), sb_draw()))
        sb.bind("<Configure>", lambda ev: sb_draw())

        grid_frame = tk.Frame(canvas, bg=pal["bar_bg"])
        canvas_window = canvas.create_window((0, 0), window=grid_frame, anchor="nw")

        def _on_wheel(ev):
            if getattr(ev, "num", None) == 5 or getattr(ev, "delta", 0) < 0:
                canvas.yview_scroll(1, "units")
            elif getattr(ev, "num", None) == 4 or getattr(ev, "delta", 0) > 0:
                canvas.yview_scroll(-1, "units")

        def insert_emoji(ch):
            # Inserts at wherever the text cursor last was — works even though
            # this popup (not the note) currently has keyboard focus, since
            # Text.insert() is a direct widget call, not a simulated keystroke.
            # Strip variation-selector-16: on this rendering path emoji show
            # as plain monochrome glyphs, not color emoji, and some fonts
            # render U+FE0F as a visible extra glyph instead of consuming it
            # invisibly — exactly the "clipped icon, blank space after insert"
            # symptom. The base codepoint alone renders cleanly everywhere.
            ch = ch.replace("\ufe0f", "")
            self.txt.insert("insert", ch)
            # Stays open on purpose (matches the OS emoji-panel pattern) so a
            # run of emojis can be dropped in without reopening each time.

        def rebuild(*_):
            for w_ in grid_frame.winfo_children():
                w_.destroy()
            q = filter_var.get().strip().lower()
            items = [ch for ch, kw in EMOJI_PICKS if not q or q in kw]

            if not items:
                tk.Label(grid_frame, text="no matches", bg=pal["bar_bg"], fg=pal["dim_fg"],
                        font=(F, 8)).grid(row=0, column=0, padx=4, pady=8, columnspan=cols)
            for i, ch in enumerate(items):
                r, c = divmod(i, cols)
                # fg matches the note's own text color (text_fg) per theme —
                # these are rendered as plain glyphs here, not color emoji,
                # so they need an explicit, theme-correct foreground.
                b = tk.Label(grid_frame, text=ch, bg=pal["bar_bg"], fg=pal["text_fg"],
                            font=(F, 14), cursor="hand2", width=2, height=1)
                b.grid(row=r, column=c, padx=1, pady=1)
                b.bind("<Button-1>", lambda e, ch=ch: insert_emoji(ch))
                b.bind("<Enter>", lambda e, w=b: w.config(bg=pal["menu_active_bg"]))
                b.bind("<Leave>", lambda e, w=b: w.config(bg=pal["bar_bg"]))
                for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                    b.bind(seq, _on_wheel)

            grid_frame.update_idletasks()
            content_w = grid_frame.winfo_reqwidth()
            content_h = grid_frame.winfo_reqheight()
            num_rows = max(1, -(-len(items) // cols)) if items else 1
            one_row_h = content_h / num_rows
            visible_h = int(round(one_row_h * min(visible_rows, num_rows)))

            canvas.configure(width=content_w, height=visible_h)
            canvas.itemconfig(canvas_window, width=content_w)
            canvas.configure(scrollregion=(0, 0, content_w, content_h))
            canvas.yview_moveto(0)

            if num_rows > visible_rows:
                sb.configure(height=visible_h)
                sb.pack(side="right", fill="y")
            else:
                sb.pack_forget()
            sb_draw()

            # Re-measure and re-anchor every time the filtered set changes —
            # fewer results means a shorter (and possibly narrower) popup,
            # not a fixed box with leftover space.
            pop.update_idletasks()
            place(pop.winfo_reqwidth(), pop.winfo_reqheight())

        def place(req_w, req_h):
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            if e is not None:
                ax, ay = e.x_root, e.y_root
            else:
                ax = self.root.winfo_rootx() + 20
                ay = self.root.winfo_rooty() + 20
            ax = max(4, min(ax, sw - req_w - 4))
            ay = max(4, min(ay, sh - req_h - 4))
            pop.geometry(f"{req_w}x{req_h}+{ax}+{ay}")

        canvas.bind("<MouseWheel>", _on_wheel)
        canvas.bind("<Button-4>", _on_wheel)
        canvas.bind("<Button-5>", _on_wheel)

        filter_var.trace_add("write", rebuild)
        rebuild()
        self._autoclose_popup(pop)
        pop.bind("<Escape>", lambda e: pop.destroy())
        pop.focus_force()
        entry.focus_force()

    # ── IN-NOTE SEARCH (Ctrl+F) ──────────────────────────────────────────────

    def _open_search(self, e=None):
        if not self.search_bar.winfo_ismapped():
            self.search_bar.pack(fill="x", after=self.bar)
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")
        return "break"

    def _search_close(self):
        self.txt.tag_remove("search_hit", "1.0", "end")
        self.txt.tag_remove("search_current", "1.0", "end")
        self.search_bar.pack_forget()
        self.txt.focus_set()

    def _search_refresh(self):
        query = self.search_var.get()
        self.txt.tag_remove("search_hit", "1.0", "end")
        self.txt.tag_remove("search_current", "1.0", "end")
        self._search_matches = []
        if not query:
            self.search_count.config(text="")
            return
        start = "1.0"
        while True:
            pos = self.txt.search(query, start, stopindex="end", nocase=True)
            if not pos:
                break
            end = f"{pos}+{len(query)}c"
            self.txt.tag_add("search_hit", pos, end)
            self._search_matches.append(pos)
            start = end
        self._search_idx = 0
        if self._search_matches:
            self._goto_match(0)
        else:
            self.search_count.config(text="0/0")

    def _goto_match(self, i):
        if not self._search_matches:
            return
        self.txt.tag_remove("search_current", "1.0", "end")
        pos = self._search_matches[i]
        end = f"{pos}+{len(self.search_var.get())}c"
        self.txt.tag_add("search_current", pos, end)
        self.txt.see(pos)
        self.search_count.config(text=f"{i+1}/{len(self._search_matches)}")

    def _search_step(self, direction):
        if not self._search_matches:
            return
        self._search_idx = (self._search_idx + direction) % len(self._search_matches)
        self._goto_match(self._search_idx)



    def _set_title_label(self, name):
        self.lbl_title.config(text=(name if len(name) <= 20 else name[:19] + "…"))

    def _load_note(self):
        content = self.notes.get_content(self.notes.active_id)
        if content:
            self.txt.insert("1.0", content)
            self.txt.see("end")
        self.txt.edit_modified(False)
        self._set_title_label(self.notes.get_name(self.notes.active_id))
        self._update_footer()

    def _on_modified(self, e=None):
        if self.txt.edit_modified():
            self.txt.edit_modified(False)
            self._update_footer()
            if self._save_job:
                self.root.after_cancel(self._save_job)
            self._save_job = self.root.after(600, self._do_save)

    def _do_save(self):
        self._save_job = None
        content = self.txt.get("1.0", "end-1c")
        self.notes.set_content(self.notes.active_id, content)
        now = datetime.datetime.now().strftime("%b %d, %H:%M")
        self.lbl_time.config(text=f"saved {now}")
        self.lbl_saved.config(text="✓ saved")
        self.root.after(2000, lambda: self.lbl_saved.config(text=""))

    def _flush_save(self):
        """Persist the current note immediately — used right before switching
        notes or quitting, so the debounced 600ms autosave can't lose anything."""
        if self._save_job:
            self.root.after_cancel(self._save_job)
            self._save_job = None
        self._do_save()

    def _switch_note(self, nid):
        if nid == self.notes.active_id:
            return
        self._flush_save()
        self.notes.set_active(nid)
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", self.notes.get_content(nid))
        self.txt.edit_modified(False)
        self.txt.edit_reset()
        self._set_title_label(self.notes.get_name(nid))
        self._update_footer()
        self.txt.focus_set()

    def _new_note_quick(self):
        self._flush_save()
        self._switch_note(self.notes.create())

    # ── NOTE SWITCHER ────────────────────────────────────────────────────────

    def _open_switcher(self, e=None):
        pal = self._pal
        F = "Consolas"
        pop = tk.Toplevel(self.root)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.configure(bg=pal["bar_bg"], highlightthickness=1, highlightbackground=pal["border"])
        x = self.bar.winfo_rootx()
        y = self.bar.winfo_rooty() + self.bar.winfo_height()
        w = max(220, self.root.winfo_width())

        filter_var = tk.StringVar()
        entry = tk.Entry(pop, textvariable=filter_var, bg=pal["text_bg"], fg=pal["text_fg"],
                         insertbackground=pal["accent"], relief="flat", font=(F, 9))
        entry.pack(fill="x", padx=6, pady=(6, 4))

        list_frame = tk.Frame(pop, bg=pal["bar_bg"])
        list_frame.pack(fill="both", expand=True)

        def make_row(nid, name, snippet, is_active):
            row = tk.Frame(list_frame, bg=pal["bar_bg"])
            row.pack(fill="x")

            line = tk.Frame(row, bg=pal["bar_bg"])
            line.pack(fill="x")

            can_delete = len(self.notes.list()) > 1
            btn_del = None
            if can_delete:
                btn_del = tk.Label(line, text="×", bg=pal["bar_bg"], fg=pal["dim_fg"],
                                   font=(F, 10), cursor="hand2", padx=6)
                btn_del.pack(side="right")
            btn_ren = tk.Label(line, text="✎", bg=pal["bar_bg"], fg=pal["dim_fg"],
                               font=(F, 8), cursor="hand2", padx=6)
            btn_ren.pack(side="right")

            lbl = tk.Label(line, text=("● " if is_active else "   ") + name,
                          bg=pal["bar_bg"], fg=(pal["accent"] if is_active else pal["text_fg"]),
                          font=(F, 9), anchor="w", cursor="hand2", padx=8, pady=4)
            lbl.pack(side="left", fill="x", expand=True)

            if snippet:
                tk.Label(row, text=f"     …{snippet}…", bg=pal["bar_bg"], fg=pal["dim_fg"],
                        font=(F, 7), anchor="w", padx=8).pack(fill="x")

            def pick(e=None):
                pop.destroy()
                self._switch_note(nid)
                q = filter_var.get().strip()
                if snippet and q:
                    self._open_search()
                    self.search_var.set(q)

            def start_rename(e=None):
                for w_ in line.winfo_children():
                    w_.destroy()
                rvar = tk.StringVar(value=name)
                ent = tk.Entry(line, textvariable=rvar, bg=pal["text_bg"], fg=pal["text_fg"],
                               insertbackground=pal["accent"], relief="flat", font=(F, 9))
                ent.pack(fill="x", expand=True, side="left", padx=6, pady=2)
                ent.focus_force(); ent.select_range(0, "end")
                done = []
                def commit(e=None):
                    if done: return
                    done.append(True)
                    self.notes.rename(nid, rvar.get().strip() or name)
                    if nid == self.notes.active_id:
                        self._set_title_label(self.notes.get_name(nid))
                    pop.destroy()
                    self._open_switcher()
                def cancel(e=None):
                    if done: return
                    done.append(True)
                    pop.destroy()
                    self._open_switcher()
                ent.bind("<Return>", commit)
                ent.bind("<FocusOut>", commit)
                ent.bind("<Escape>", cancel)

            def delete(e=None):
                pop.destroy()
                if not messagebox.askyesno("IdleNote", f"Delete note “{name}” permanently?",
                                           parent=self.root):
                    return
                was_active = (nid == self.notes.active_id)
                if self.notes.delete(nid) and was_active:
                    self.txt.delete("1.0", "end")
                    self.txt.insert("1.0", self.notes.get_content(self.notes.active_id))
                    self.txt.edit_modified(False)
                    self._set_title_label(self.notes.get_name(self.notes.active_id))
                    self._update_footer()

            def ctx(e):
                m = tk.Menu(self.root, tearoff=0, bg=pal["menu_bg"], fg=pal["menu_fg"],
                           activebackground=pal["menu_active_bg"], activeforeground=pal["accent"],
                           font=(F, 9), relief="flat", bd=0)
                m.add_command(label="Rename", command=start_rename)
                if can_delete:
                    m.add_command(label="Delete", command=delete)
                try:
                    m.tk_popup(e.x_root, e.y_root)
                finally:
                    m.grab_release()

            lbl.bind("<Button-1>", pick)
            lbl.bind("<Button-3>", ctx)
            lbl.bind("<Enter>", lambda e: lbl.config(bg=pal["menu_active_bg"]))
            lbl.bind("<Leave>", lambda e: lbl.config(bg=pal["bar_bg"]))
            btn_ren.bind("<Button-1>", start_rename)
            btn_ren.bind("<Enter>", lambda e: btn_ren.config(fg=pal["accent"]))
            btn_ren.bind("<Leave>", lambda e: btn_ren.config(fg=pal["dim_fg"]))
            if btn_del is not None:
                btn_del.bind("<Button-1>", delete)
                btn_del.bind("<Enter>", lambda e: btn_del.config(fg=pal["close_hover"]))
                btn_del.bind("<Leave>", lambda e: btn_del.config(fg=pal["dim_fg"]))

        def rebuild(*_):
            for w_ in list_frame.winfo_children():
                w_.destroy()
            query = filter_var.get().strip()
            live = self.txt.get("1.0", "end-1c")
            if not query:
                for nid, name in self.notes.list():
                    make_row(nid, name, None, nid == self.notes.active_id)
            else:
                for nid, name, snippet in self.notes.search(
                        query, live_id=self.notes.active_id, live_content=live):
                    make_row(nid, name, snippet, nid == self.notes.active_id)

            addrow = tk.Label(list_frame, text="+ New note", bg=pal["bar_bg"], fg=pal["dim_fg"],
                              font=(F, 9), anchor="w", cursor="hand2", padx=8, pady=5)
            addrow.pack(fill="x")
            addrow.bind("<Button-1>", lambda e: (pop.destroy(), self._new_note_quick()))
            addrow.bind("<Enter>", lambda e: addrow.config(fg=pal["accent"]))
            addrow.bind("<Leave>", lambda e: addrow.config(fg=pal["dim_fg"]))

        filter_var.trace_add("write", rebuild)
        rebuild()
        pop.update_idletasks()
        h = min(320, pop.winfo_reqheight())
        pop.geometry(f"{w}x{h}+{x}+{y}")
        self._autoclose_popup(pop)
        pop.focus_force()
        entry.focus_force()


    def _update_footer(self):
        content = self.txt.get("1.0", "end-1c")
        words = len(content.split()) if content.strip() else 0
        chars = len(content)
        self.lbl_chars.config(text=f"{words}w {chars}c")

    # ── SHOW / HIDE ───────────────────────────────────────────────────────────

    def show(self):
        if self._visible: return
        self._visible = True
        self._cancel_snooze()
        s = self.settings
        w = int(s.get("width", 360))
        h = int(s.get("height", 260))
        x, y = s.get("win_x"), s.get("win_y")
        if x is None or y is None or not self._is_onscreen(x, y, w, h):
            x, y = self._default_anchor(w, h)
            self.root.geometry(f"+{x}+{y}")
            s["win_x"], s["win_y"] = x, y
            save_settings(s)
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self._fade_to(self.settings.get("opacity", 0.95))
        self.txt.focus_set()

    def _on_close_btn(self, e=None):
        """
        Called when the user clicks ✕ OR when the window manager sends a
        delete-window event (e.g. alt+F4, or closing from a taskbar).
        We always HIDE (withdraw) instead of destroying, so the process
        stays alive.
        """
        if self._visible:
            self._visible = False
            self._do_save()
            self._fade_to(0.0, on_done=self.root.withdraw)
        else:
            # Window was already hidden; make sure it's withdrawn
            self.root.withdraw()

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
            # Only show if media/calls are not active and not snoozed
            if not self._is_snoozed() and not should_suppress():
                self.show()

        self._poll_job = self.root.after(500, self._poll)

    # ── CONTEXT MENU ─────────────────────────────────────────────────────────

    def _ctx_menu(self, e):
        pal = self._pal
        m = tk.Menu(self.root, tearoff=0,
                    bg=pal["menu_bg"], fg=pal["menu_fg"],
                    activebackground=pal["menu_active_bg"],
                    activeforeground=pal["accent"],
                    font=("Consolas", 9),
                    relief="flat", bd=0)
        m.add_command(label="Cut",   command=lambda: self.txt.event_generate("<<Cut>>"))
        m.add_command(label="Copy",  command=lambda: self.txt.event_generate("<<Copy>>"))
        m.add_command(label="Paste", command=lambda: self.txt.event_generate("<<Paste>>"))
        m.add_separator()
        m.add_command(label="Emoji…",            command=lambda: self._open_emoji_picker(e))
        m.add_command(label="Find…",            command=lambda: self._open_search())
        m.add_command(label="Save dated copy",  command=self._save_dated_copy)
        m.add_separator()
        m.add_command(label="New note",         command=self._new_note_quick)
        m.add_command(label="Clear this note…", command=self._clear_notes)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def _save_dated_copy(self):
        """Snapshot the current note to ~/.idlenote/snapshots/ — a safety net
        before 'Clear all notes' or just to keep a dated record."""
        content = self.txt.get("1.0", "end-1c")
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        snap_dir = os.path.join(APP_DIR, "snapshots")
        try:
            os.makedirs(snap_dir, exist_ok=True)
            with open(os.path.join(snap_dir, f"note_{ts}.txt"), "w", encoding="utf-8") as f:
                f.write(content)
            self.lbl_saved.config(text="✓ copy saved")
            self.root.after(2000, lambda: self.lbl_saved.config(text=""))
        except Exception:
            pass

    def _clear_notes(self):
        if messagebox.askyesno("IdleNote", "Clear all notes permanently?",
                               parent=self.root):
            self.txt.delete("1.0", "end")
            self._do_save()

    # ── APPLY SETTINGS ───────────────────────────────────────────────────────

    def apply_settings(self):
        self._restyle()
        if self._visible:
            self.root.attributes("-alpha", self.settings.get("opacity", 0.95))
        self._refresh_tray_icon()

    # ── TRAY ─────────────────────────────────────────────────────────────────

    def _build_tray(self):
        def on_left_click(icon, item=None):
            self.root.after(0, self.show)

        def on_settings(icon, item):
            self.root.after(0, lambda: SettingsWindow(self).open())

        def on_recall(icon, item):
            self.root.after(0, self._recall)

        def on_cancel_snooze(icon, item):
            self.root.after(0, self._cancel_snooze)

        def on_quit(icon, item):
            self.root.after(0, self._quit)

        def snooze_cb(secs):
            def _cb(icon, item):
                self.root.after(0, lambda: self._snooze_for(secs) if secs else self._snooze_indef())
            return _cb

        menu = pystray.Menu(
            pystray.MenuItem("Open IdleNote", on_left_click, default=True),
            pystray.MenuItem("Snooze", pystray.Menu(
                pystray.MenuItem("15 min",          snooze_cb(900)),
                pystray.MenuItem("30 min",          snooze_cb(1800)),
                pystray.MenuItem("1 hour",          snooze_cb(3600)),
                pystray.MenuItem("Until I reopen it", snooze_cb(None)),
            )),
            pystray.MenuItem("Cancel snooze", on_cancel_snooze),
            pystray.MenuItem("Bring note back", on_recall),
            pystray.MenuItem("Settings", on_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", on_quit),
        )
        self._tray_icon = pystray.Icon(
            "IdleNote", self._make_tray_icon(), "IdleNote — click to open", menu)
        threading.Thread(target=self._tray_icon.run, daemon=True).start()

    def _make_tray_icon(self, size=64):
        """Tray icon recolored to match the active accent."""
        accent_rgb = hex_to_rgb(palette(self.settings)["accent"])
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d   = ImageDraw.Draw(img)
        m   = size // 8
        d.rounded_rectangle([m, m, size-m, size-m],
                             radius=size//8,
                             fill=(20, 20, 20),
                             outline=accent_rgb, width=max(2, size//24))
        lc = (180, 175, 168)
        lx1, lx2 = m*2+2, size-m*2-2
        ly = [int(size*0.36), int(size*0.52), int(size*0.68)]
        lw = max(1, size//32)
        d.line([(lx1, ly[0]), (lx2,         ly[0])], fill=lc, width=lw)
        d.line([(lx1, ly[1]), (lx2-size//6, ly[1])], fill=lc, width=lw)
        d.line([(lx1, ly[2]), (lx2-size//4, ly[2])], fill=lc, width=lw)
        r = max(3, size//14)
        d.ellipse([size-m-r*2, m, size-m, m+r*2], fill=accent_rgb)
        return img

    def _refresh_tray_icon(self):
        if HAS_TRAY and hasattr(self, "_tray_icon"):
            try:
                self._tray_icon.icon = self._make_tray_icon()
            except Exception:
                pass

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

    _selfheal_autostart()
    app = IdleNoteApp()
    app.run()

if __name__ == "__main__":
    main()
