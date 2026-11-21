from pathlib import Path
import sys

root = Path(sys.argv[1])
engine_src = Path(sys.argv[2]).read_text(encoding="utf-8")
(root / "app_source/app/obs/engine.py").write_text(engine_src, encoding="utf-8")

req = root / "app_source/requirements.txt"
text = req.read_text(encoding="utf-8")
if "obsws-python" not in text:
    if not text.endswith("\n"):
        text += "\n"
    text += "obsws-python==1.8.1\n"
req.write_text(text, encoding="utf-8")

for rel in [
    "app_source/app/ui/main_window.py",
    "app_source/app/core/updater.py",
]:
    p = root / rel
    s = p.read_text(encoding="utf-8")
    for old in ("1.1.17 Stable", "1.1.16 Stable", "1.1.15 Stable"):
        s = s.replace(old, "1.1.18 Stable")
    p.write_text(s, encoding="utf-8")

(root / "app_source/app/version.py").write_text(
    '__version__ = "1.1.18 Stable"\n',
    encoding="utf-8",
)

print("v1.1.18 obsws-python engine applied")
