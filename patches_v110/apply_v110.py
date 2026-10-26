from pathlib import Path
import sys

root = Path(sys.argv[1])

# updater.py: remove runtime dependency on app.version
p = root / "app_source" / "app" / "core" / "updater.py"
s = p.read_text(encoding="utf-8")
s = s.replace("from app.version import __version__\n", 'APP_VERSION = "1.1.10 Stable"\n')
s = s.replace("return str(__version__).split()[0]", "return APP_VERSION.split()[0]")
p.write_text(s, encoding="utf-8")

# main_window.py: same idea; keep version local to the module
p = root / "app_source" / "app" / "ui" / "main_window.py"
s = p.read_text(encoding="utf-8")
s = s.replace("from app.version import __version__\n", 'APP_VERSION = "1.1.10 Stable"\n')
s = s.replace("__version__", "APP_VERSION")
p.write_text(s, encoding="utf-8")

# main.py: add an import/startup smoke marker. This line is reached only after
# every top-level import (including MainWindow and updater) succeeded.
p = root / "app_source" / "main.py"
s = p.read_text(encoding="utf-8")
if "import os\n" not in s:
    s = s.replace("import logging\n", "import logging\nimport os\n", 1)
if "MIDI_PREMIUM_SMOKE_MARKER" not in s:
    needle = "def main() -> int:\n"
    repl = '''def main() -> int:
    smoke_marker = os.environ.get("MIDI_PREMIUM_SMOKE_MARKER", "").strip()
    if smoke_marker:
        try:
            Path(smoke_marker).write_text("OK", encoding="utf-8")
            return 0
        except Exception:
            return 91
'''
    if needle not in s:
        raise RuntimeError("Could not locate main()")
    s = s.replace(needle, repl, 1)
p.write_text(s, encoding="utf-8")

# Keep compatibility file present, even though startup no longer depends on it.
(root / "app_source" / "app" / "version.py").write_text('__version__ = "1.1.10 Stable"\n', encoding="utf-8")

# Safety check: startup files must not import app.version anymore.
for rel in [
    "app_source/app/core/updater.py",
    "app_source/app/ui/main_window.py",
]:
    text = (root / rel).read_text(encoding="utf-8")
    if "from app.version" in text:
        raise RuntimeError(f"Residual app.version dependency in {rel}")

print("v1.1.10 startup patch applied")
