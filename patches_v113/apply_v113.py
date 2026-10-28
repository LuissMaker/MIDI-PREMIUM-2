from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "app_source" / "app" / "ui" / "main_window.py"
s = p.read_text(encoding="utf-8")

# Imports needed for foreground-process guard and diagnostics.
if "import ctypes\n" not in s:
    s = s.replace("import os\n", "import os\nimport ctypes\nimport logging\n", 1)

# Add helpers immediately before handle_midi_event.
needle = "    def handle_midi_event(self, event: MidiEvent) -> None:\n"
helpers = '''    @staticmethod
    def _foreground_process_name() -> str:
        """Return the foreground executable name on Windows, or empty string."""
        if sys.platform != "win32":
            return ""
        try:
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            if not hwnd:
                return ""
            pid = ctypes.c_ulong(0)
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return ""
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value
            )
            if not handle:
                return ""
            try:
                size = ctypes.c_ulong(32768)
                buf = ctypes.create_unicode_buffer(size.value)
                if ctypes.windll.kernel32.QueryFullProcessImageNameW(
                    handle, 0, buf, ctypes.byref(size)
                ):
                    return Path(buf.value).name.lower()
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception:
            return ""
        return ""

    def _premiere_guard_active(self) -> bool:
        workspace = self.settings.data.setdefault("workspace", {})
        if not bool(workspace.get("protect_premiere_from_midi", True)):
            return False
        return self._foreground_process_name() in {
            "adobe premiere pro.exe",
            "premiere pro.exe",
        }

    def _log_premiere_guard(self, event: MidiEvent) -> None:
        logger = logging.getLogger("midi_premium_2")
        try:
            logger.warning("Premiere guard: MIDI event blocked: %s", event.summary())
        except Exception:
            logger.warning("Premiere guard: MIDI event blocked")
        self.statusBar().showMessage(
            "Protección Premiere: acción MIDI bloqueada.",
            1200,
        )

'''
if helpers not in s:
    if needle not in s:
        raise RuntimeError("handle_midi_event target not found")
    s = s.replace(needle, helpers + needle, 1)

# Block MIDI dispatch while Premiere is foreground.
guard_needle = "    def handle_midi_event(self, event: MidiEvent) -> None:\n        self.midi_monitor.append_event(event)\n"
guard_repl = """    def handle_midi_event(self, event: MidiEvent) -> None:
        self.midi_monitor.append_event(event)

        if self._premiere_guard_active():
            self._log_premiere_guard(event)
            return
"""
if guard_repl not in s:
    if guard_needle not in s:
        raise RuntimeError("MIDI event guard insertion target not found")
    s = s.replace(guard_needle, guard_repl, 1)

# Closing the main window must really terminate the application.
# This avoids the confusing "it reopened by itself" tray behavior.
close_method = '''    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            if hasattr(self, "tray_icon"):
                self.tray_icon.hide()
        except Exception:
            pass
        try:
            self.midi_engine.disconnect_device()
        except Exception:
            pass
        try:
            self.obs_engine.disconnect()
        except Exception:
            pass
        self._force_quit = True
        event.accept()
        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(0, app.quit)

'''
if close_method not in s:
    insert_at = s.find("    def _connect_obs_module(self) -> None:\n")
    if insert_at < 0:
        raise RuntimeError("_connect_obs_module target not found")
    s = s[:insert_at] + close_method + s[insert_at:]

# Version label.
s = s.replace('APP_VERSION = "1.1.12 Stable"', 'APP_VERSION = "1.1.13 Stable"')
s = s.replace('APP_VERSION = "1.1.11 Stable"', 'APP_VERSION = "1.1.13 Stable"')

p.write_text(s, encoding="utf-8")

# updater version
p = root / "app_source" / "app" / "core" / "updater.py"
u = p.read_text(encoding="utf-8")
u = u.replace('APP_VERSION = "1.1.12 Stable"', 'APP_VERSION = "1.1.13 Stable"')
u = u.replace('APP_VERSION = "1.1.11 Stable"', 'APP_VERSION = "1.1.13 Stable"')
p.write_text(u, encoding="utf-8")

(root / "app_source" / "app" / "version.py").write_text(
    '__version__ = "1.1.13 Stable"\n', encoding="utf-8"
)
print("v1.1.13 Premiere protection patch applied")
