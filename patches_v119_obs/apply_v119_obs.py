from pathlib import Path
import sys

root = Path(sys.argv[1])

# Fix main.py construction.
p = root / "app_source/main.py"
s = p.read_text(encoding="utf-8")
old = 'obs_engine = ObsEngine(logger=logger, reconnect_interval_ms=int(obs_settings.get("reconnect_interval_ms", 5000)))'
new = 'obs_engine = ObsEngine()'
if old in s:
    s = s.replace(old, new, 1)
elif new not in s:
    raise RuntimeError("ObsEngine construction target not found")
p.write_text(s, encoding="utf-8")

# Add backward-compatible kwargs to the new engine too.
p = root / "app_source/app/obs/engine.py"
s = p.read_text(encoding="utf-8")
old = '    def __init__(self, parent=None) -> None:\n        super().__init__(parent)\n        self.logger = logging.getLogger("midi_premium_2.obs")\n'
new = '''    def __init__(
        self,
        parent=None,
        logger: logging.Logger | None = None,
        reconnect_interval_ms: int = 3000,
        **_ignored,
    ) -> None:
        super().__init__(parent)
        self.logger = logger or logging.getLogger("midi_premium_2.obs")
'''
if old not in s:
    raise RuntimeError("ObsEngine __init__ target not found")
s = s.replace(old, new, 1)
s = s.replace('        self._timer.setInterval(3000)\n', '        self._timer.setInterval(max(1000, int(reconnect_interval_ms)))\n', 1)
p.write_text(s, encoding="utf-8")

# Version bump.
for rel in [
    "app_source/app/ui/main_window.py",
    "app_source/app/core/updater.py",
]:
    p = root / rel
    txt = p.read_text(encoding="utf-8")
    for oldver in ("1.1.18 Stable", "1.1.17 Stable"):
        txt = txt.replace(oldver, "1.1.19 Stable")
    p.write_text(txt, encoding="utf-8")

(root / "app_source/app/version.py").write_text(
    '__version__ = "1.1.19 Stable"\n',
    encoding="utf-8",
)

print("v1.1.19 ObsEngine init compatibility fix applied")
