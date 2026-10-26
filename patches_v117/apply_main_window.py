from pathlib import Path
import sys

p = Path(sys.argv[1]) / "app_source" / "app" / "ui" / "main_window.py"
s = p.read_text(encoding="utf-8")

needle = "        title_block = QVBoxLayout()\n"
repl = "        title_block = QVBoxLayout()\n        title_block.setContentsMargins(0, 0, 0, 0)\n        title_block.setSpacing(0)\n"
if repl not in s:
    if needle not in s:
        raise SystemExit("title_block target not found")
    s = s.replace(needle, repl, 1)

old = '        self.tray_icon.setIcon(QIcon(str(UI_ICON_DIR / "midi_connected.svg")))'
new = '        app_icon = DEV_ROOT / "assets" / "app_icon.ico"\n        self.tray_icon.setIcon(QIcon(str(app_icon if app_icon.exists() else UI_ICON_DIR / "midi_status.svg")))'
if new not in s:
    if old not in s:
        raise SystemExit("tray icon target not found")
    s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("main_window v1.1.7 patch applied")
