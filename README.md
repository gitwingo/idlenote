# ✦ IdleNote

**A scratchpad that appears when you go idle. Closes only when you click ✕.**

Stop typing or moving your mouse for a few seconds — IdleNote fades in at the corner of your screen. Read it, write in it, edit freely. Click ✕ when you're done. It saves and disappears.

No hotkey to remember. No window to hunt for. Just your thoughts, surfacing exactly when your hands stop.

---

<img width="2048" height="976" alt="idlenote-hero" src="https://github.com/user-attachments/assets/a62af784-bb99-4892-8bf0-137553ddd429" />

---

## ✨ What's new in this release

**Notes & search**
- **Multiple named notes**, with a quick switcher — click the note name in the title bar (or the `▾` beside it) to browse, search, rename, or create notes
- **Search** — `Ctrl+F` searches the current note; the switcher's filter box searches across *all* notes by name or content, and jumps straight to the highlighted hit
- **"Save dated copy"** — snapshot the current note to a timestamped file, right from the right-click menu

**Emoji picker**
- Right-click anywhere in the note → **Emoji…** for a searchable picker — type a few letters ("rocket", "heart") to filter, click to insert at your cursor
- Shows a fixed 4×7 grid and scrolls for the rest, instead of one long unwieldy list
- Icon color now matches your note's own text color in both themes, instead of staying black regardless of theme

**Appearance**
- **Light theme**, plus 5 accent colors (Orange, Teal, Violet, Crimson, Mint) — switch live from Settings, no restart
- **Adjustable font size** (8–28px) for bigger displays
- Palette moved from a blue-tinted dark to a neutral charcoal; title bar and footer text is legible now instead of barely visible
- Thicker border for a more defined window edge — no rounded corners or drop shadow, by design

**Idle behavior**
- **Snooze** — pause idle pop-ups for 15 min / 30 min / 1 hour / until you reopen the note, from the footer or tray
- **Idle thresholds now go up to 5 minutes** (previously capped at 30 seconds)

**Fixes**
- The resize grip wasn't appearing for some users — turned out a layout bug was collapsing the whole footer to zero height, not a missing icon. Fixed, and the grip is now drawn directly (dot-grid) instead of relying on a font glyph
- A note that drifted off-screen (e.g. after unplugging a monitor) now repositions itself automatically; **"Bring note back"** in the tray menu does it on demand too
- Renaming a note in the switcher could silently fail and dump you back into the note instead — rename now has its own dedicated **✎** control, separate from the click-to-switch area
- **Windows: autostart could launch a visible console window on boot, and closing it would silently kill IdleNote** since that console was the actual process hosting the app. Autostart now uses the console-less `pythonw.exe`; anyone who already has the old entry registered gets it auto-corrected on next launch, no action needed

Existing users: your old `notes.txt` is migrated automatically into the new multi-note format the first time you open this version — nothing to do manually, nothing deleted.

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
| Drag the dot-grid grip (bottom-right) | Resize the window |
| Click the note name, or **▾** | Open the note switcher |
| `Ctrl+F` inside the note | Search the current note |
| Click **zzz** (bottom-left) | Snooze idle pop-ups |
| Right-click inside note | Cut / Copy / Paste / Find / Emoji / Save dated copy / New note / Clear this note |
| Tray icon **left-click** | Open note manually anytime |
| Tray icon **right-click** | Snooze / Bring note back / Settings / Quit |

---

## Notes

Click the note name in the title bar (or the `▾` caret beside it) to open the switcher:

- **Click** a note to switch to it
- **✎** to rename, **×** to delete (your last remaining note can't be deleted)
- **+ New note** to start another one
- Type in the filter box to search — it matches both note names and note *content*, showing a snippet for content matches. Picking a content match switches to that note and jumps straight to the highlighted hit.

Each note autosaves independently, the same way the single note always did.

---

## Emoji picker

Right-click inside the note → **Emoji…**. A searchable grid pops up where you clicked:

- Type to filter by keyword (e.g. "fire", "check", "calendar")
- Click an emoji to insert it at your cursor — the picker stays open afterward so you can drop in a few in a row without reopening it each time
- Shows 4 rows × 7 columns at a time; scroll (wheel, or drag the thin bar on the right) for the rest
- Click away or press `Esc` to close

---

## Settings

Open via tray icon → right-click → **Settings**.

| Setting | Default | Range |
|---|---|---|
| Keyboard idle threshold | 5 s | 2 s – 5 min |
| Mouse idle threshold | 8 s | 2 s – 5 min |
| Opacity | 95% | 40–100% |
| Font size | 11px | 8–28px |
| Theme | Dark | Dark / Light |
| Accent | Orange | Orange / Teal / Violet / Crimson / Mint |
| Run on startup | ✓ on | toggle |

Keyboard and mouse thresholds are independent — both must be idle before the note appears. All appearance changes apply live, no restart needed.

---

## Snooze

Don't want the note popping up for a while even though you're idle (reading, in a meeting, etc.)? Click **zzz** in the footer, or use the tray menu, and pick 15 min / 30 min / 1 hour / until you next reopen the note manually. Click **zzz** again any time to cancel early.

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

- Notes are stored in `~/.idlenote/notes/` — one plain-text `.txt` file per note, plus a small `notes_index.json` tracking names and order
- "Save dated copy" snapshots go to `~/.idlenote/snapshots/`
- If you're upgrading from an older version, your old `~/.idlenote/notes.txt` is imported automatically as "Note 1" the first time you run this version
- Live word and character count shown in the footer
- Auto-saves 600ms after you stop typing, and immediately when you switch notes or quit
- Single instance — launching twice does nothing
- Autostart enabled on first launch; toggle off in Settings any time
- Windows + running from source: autostart uses `pythonw.exe` (no console window), not `python.exe` — this is handled automatically, nothing to configure

---

## Platform support

| Platform | Status |
|---|---|
| Windows 10 / 11 | ✓ Full support |
| Linux (X11) | ✓ Full support |
| Linux (Wayland) | ⚠ Needs XWayland for global idle detection — native Wayland idle detection is on the roadmap |
| macOS | Not tested |

---

## License

[GNU General Public License v3.0](LICENSE)

Free to use, modify, and distribute. If you build on this, your version must also be open source under GPL 3.0.

---

## Contributing

Issues and PRs welcome. Keep it minimal — the whole point of this tool is that it stays out of your way.
