from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "app_source" / "app" / "ui" / "main_window.py"
s = p.read_text(encoding="utf-8")

old = 'DEV_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]\nUI_ICON_DIR = DEV_ROOT / "assets" / "ui_icons"\nPAD_ICON_DIR = DEV_ROOT / "assets" / "pad_icons"\nPROFILE_ICON_DIR = DEV_ROOT / "assets" / "profile_icons"\n'
new = '''_Path = __import__("pathlib").Path
if getattr(sys, "frozen", False):
    # cx_Freeze keeps copied resources next to the executable.
    DEV_ROOT = _Path(sys.executable).resolve().parent
else:
    DEV_ROOT = _Path(__file__).resolve().parents[2]

UI_ICON_DIR = DEV_ROOT / "assets" / "ui_icons"
PAD_ICON_DIR = DEV_ROOT / "assets" / "pad_icons"
PROFILE_ICON_DIR = DEV_ROOT / "assets" / "profile_icons"
'''

if old not in s:
    raise RuntimeError("Resource-root block not found")
s = s.replace(old, new, 1)

# v1.1.10 patch already replaces __version__ with APP_VERSION; bump it.
s = s.replace('APP_VERSION = "1.1.10 Stable"', 'APP_VERSION = "1.1.12 Stable"')
s = s.replace('APP_VERSION = "1.1.11 Stable"', 'APP_VERSION = "1.1.12 Stable"')

p.write_text(s, encoding="utf-8")

# updater version
p = root / "app_source" / "app" / "core" / "updater.py"
s = p.read_text(encoding="utf-8")
s = s.replace('APP_VERSION = "1.1.10 Stable"', 'APP_VERSION = "1.1.12 Stable"')
s = s.replace('APP_VERSION = "1.1.11 Stable"', 'APP_VERSION = "1.1.12 Stable"')
p.write_text(s, encoding="utf-8")

(root / "app_source" / "app" / "version.py").write_text('__version__ = "1.1.12 Stable"\n', encoding="utf-8")
print("v1.1.12 resource path fix applied")
