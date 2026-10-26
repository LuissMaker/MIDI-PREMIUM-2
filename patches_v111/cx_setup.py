from pathlib import Path
import sys
from cx_Freeze import setup, Executable

root = Path(__file__).resolve().parent
src = root / "app_source"
sys.path.insert(0, str(src))

build_exe_options = {
    "packages": [
        "PySide6",
        "mido",
        "rtmidi",
        "pynput",
        "websocket",
        "app",
    ],
    "excludes": ["tkinter", "pytest", "unittest", "pydoc", "doctest"],
    "include_files": [
        (str(src / "assets"), "assets"),
        (str(src / "Scripts"), "Scripts"),
        (str(src / "app" / "actions" / "photoshop_jsx_bridge.vbs"), "app/actions/photoshop_jsx_bridge.vbs"),
        (str(src / "PORTABLE.flag"), "PORTABLE.flag"),
    ],
    "include_msvcr": True,
    "optimize": 1,
}

target = Executable(
    script=str(src / "main.py"),
    base="Win32GUI",
    target_name="MIDI Premium 2.exe",
    icon=str(src / "assets" / "app_icon.ico"),
)

setup(
    name="MIDI Premium 2",
    version="1.1.11",
    description="MIDI Premium 2",
    options={"build_exe": build_exe_options},
    executables=[target],
)
