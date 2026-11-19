from pathlib import Path
import sys

root = Path(sys.argv[1])

p = root / "app_source" / "app" / "obs" / "engine.py"
s = p.read_text(encoding="utf-8")

old = '''    def _connect_worker(self) -> None:
        try:
            info = self._connect_sync()
            scenes = self.get_scenes()
            inputs = self.get_inputs()
        except Exception as exc:
            message = self._friendly_connection_error(exc)
            self.logger.exception("OBS connection failed: %s", message)
            self._close_socket()
            self.error_occurred.emit(message)
            return
        finally:
            with self._lock:
                self._connecting = False

        self.connected.emit(info)
        self.scenes_changed.emit(scenes)
        self.inputs_changed.emit(inputs)
'''

new = '''    def _connect_worker(self) -> None:
        # La conexión se considera lista en cuanto OBS completa el handshake.
        # No bloqueamos el estado "Conectado" esperando escenas/fuentes.
        try:
            info = self._connect_sync()
        except Exception as exc:
            message = self._friendly_connection_error(exc)
            self.logger.exception("OBS connection failed: %s", message)
            self._close_socket()
            self.error_occurred.emit(message)
            return
        finally:
            with self._lock:
                self._connecting = False

        self.connected.emit(info)
'''

if old not in s:
    raise RuntimeError("OBS _connect_worker block not found")
s = s.replace(old, new, 1)

# Make socket/handshake failures fail fast instead of feeling frozen.
s = s.replace("                    timeout=5,\n", "                    timeout=3.5,\n", 1)

p.write_text(s, encoding="utf-8")

# Version bump
for rel in [
    "app_source/app/ui/main_window.py",
    "app_source/app/core/updater.py",
]:
    p = root / rel
    txt = p.read_text(encoding="utf-8")
    txt = txt.replace('APP_VERSION = "1.1.16 Stable"', 'APP_VERSION = "1.1.17 Stable"')
    txt = txt.replace('APP_VERSION = "1.1.15 Stable"', 'APP_VERSION = "1.1.17 Stable"')
    p.write_text(txt, encoding="utf-8")

(root / "app_source" / "app" / "version.py").write_text(
    '__version__ = "1.1.17 Stable"\n', encoding="utf-8"
)

print("v1.1.17 fast OBS connection patch applied")
