# ✦ IdleNote

**A scratchpad that appears when you go idle. Closes only when you click ✕.**

Stop typing or moving your mouse for a few seconds — IdleNote fades in at the corner of your screen. Read it, write in it, edit freely. Click ✕ when you're done. It saves and disappears.

No hotkey to remember. No window to hunt for. Just your thoughts, surfacing exactly when your hands stop.

---

## Download

**→ [Latest Release](../../releases/latest)** — grab `IdleNote.exe` for Windows. No Python, no install. Just run.

Linux users: see [Running from source](#running-from-source) below.

---

## How it works

| What you do | What happens |
|---|---|
| Go idle (keyboard + mouse both still) | Note fades in |
| Move mouse or type — outside the note | Note stays open — interact freely |
| Click **✕** top-right | Note closes and saves |
| Drag the title bar | Reposition; place is remembered |
| Drag **⠿** grip (bottom-right) | Resize the window |
| Right-click inside note | Cut / Copy / Paste / Clear all |
| Tray icon **left-click** | Open note manually anytime |
| Tray icon **right-click** | Settings / Quit |

---

## Settings

Open via tray icon → right-click → **Settings**

| Setting | Default | Range |
|---|---|---|
| Keyboard idle threshold | 5 s | 2–30 s |
| Mouse idle threshold | 8 s | 2–30 s |
| Opacity | 95% | 40–100% |
| Run on startup | ✓ on | toggle |

Keyboard and mouse thresholds are independent — both must be idle before the note appears.

---

## Running from source

**Requirements**

```bash
pip install pynput pystray pillow
```

On Linux, also make sure `python3-tk` is installed:

```bash
sudo apt install python3-tk   # Debian/Ubuntu
sudo dnf install python3-tkinter  # Fedora
```

**Run**

```bash
python idlenote.py
```

---

## Building the EXE yourself

**Windows**

```bat
build_exe.bat
```

Produces `dist\IdleNote.exe`. No Python required to run the output.

**Linux**

```bash
bash build_exe_linux.sh
```

Produces `dist/idlenote`.

---

## Notes & data

- All notes saved to `~/.idlenote/notes.txt` — plain text, open in any editor
- Live word and character count shown in the footer
- Auto-saves 600ms after you stop typing
- Single instance — launching twice does nothing
- Autostart enabled on first launch; toggle off in Settings any time

---

## Platform support

| Platform | Status |
|---|---|
| Windows 10 / 11 | ✓ Full support |
| Linux (X11) | ✓ Full support |
| Linux (Wayland) | ⚠ Needs XWayland for global idle detection |
| macOS | Not tested |

---

## License

[GNU General Public License v3.0](LICENSE)

Free to use, modify, and distribute. If you build on this, your version must also be open source under GPL 3.0.

---

## Contributing

Issues and PRs welcome. Keep it minimal — the whole point of this tool is that it stays out of your way.
