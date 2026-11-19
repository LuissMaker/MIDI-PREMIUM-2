from pathlib import Path
import sys

root=Path(sys.argv[1])

# Replace OBS panel with compact, user-friendly version.
panel_src=Path(sys.argv[2]).read_text(encoding="utf-8")
(root/"app_source/app/widgets/obs_panel.py").write_text(panel_src, encoding="utf-8")

# Harden connection engine: prevent duplicate connection threads and improve common errors.
p=root/"app_source/app/obs/engine.py"
s=p.read_text(encoding="utf-8")
if "self._connecting = False" not in s:
    s=s.replace("        self._manual_disconnect = False\n", "        self._manual_disconnect = False\n        self._connecting = False\n", 1)

old='''    def connect_async(self) -> None:
        self._manual_disconnect = False
        threading.Thread(
            target=self._connect_worker,
            daemon=True,
            name="ObsConnectWorker",
        ).start()
'''
new='''    def connect_async(self) -> None:
        self._manual_disconnect = False
        with self._lock:
            if self._socket is not None or self._connecting:
                return
            self._connecting = True
        threading.Thread(
            target=self._connect_worker,
            daemon=True,
            name="ObsConnectWorker",
        ).start()
'''
if old in s:
    s=s.replace(old,new,1)

old='''    def _connect_worker(self) -> None:
        try:
            info = self._connect_sync()
            scenes = self.get_scenes()
            inputs = self.get_inputs()
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            self.logger.exception("OBS connection failed: %s", message)
            self._close_socket()
            self.error_occurred.emit(message)
            return

        self.connected.emit(info)
        self.scenes_changed.emit(scenes)
        self.inputs_changed.emit(inputs)
'''
new='''    def _connect_worker(self) -> None:
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

    @staticmethod
    def _friendly_connection_error(exc: Exception) -> str:
        raw = str(exc) or exc.__class__.__name__
        low = raw.lower()
        if "10061" in low or "connection refused" in low or "actively refused" in low:
            return (
                "OBS no está aceptando conexiones. Abre OBS y activa "
                "Herramientas → Configuración del servidor WebSocket → "
                "Habilitar servidor WebSocket. Puerto recomendado: 4455."
            )
        if "timed out" in low or "timeout" in low:
            return "OBS no respondió. Comprueba que OBS esté abierto y que servidor/puerto sean correctos."
        if "requiere contraseña" in low:
            return "OBS requiere una contraseña WebSocket. Escríbela en Ajustes."
        if "rechazó la identificación" in low:
            return "OBS rechazó la contraseña WebSocket. Comprueba la contraseña e inténtalo otra vez."
        return raw
'''
if old in s:
    s=s.replace(old,new,1)
p.write_text(s,encoding="utf-8")

# Main window: clear connection feedback and always refresh sources/scenes after success.
p=root/"app_source/app/ui/main_window.py"
s=p.read_text(encoding="utf-8")
s=s.replace('APP_VERSION = "1.1.13 Stable"', 'APP_VERSION = "1.1.14 Stable"')
old='''    def connect_obs(self, data: dict) -> None:
        try:
'''
new='''    def connect_obs(self, data: dict) -> None:
        self.obs_panel.set_connecting()
        try:
'''
if old in s and new not in s:
    s=s.replace(old,new,1)
old='''    def handle_obs_connected(self, info: dict) -> None:
        self.obs_panel.set_connected(info)
        self.obs_engine.refresh_inputs_async()
'''
new='''    def handle_obs_connected(self, info: dict) -> None:
        self.obs_panel.set_connected(info)
        self.obs_engine.refresh_scenes_async()
        self.obs_engine.refresh_inputs_async()
'''
if old in s:
    s=s.replace(old,new,1)
p.write_text(s,encoding="utf-8")

# Updater/version.
p=root/"app_source/app/core/updater.py"
u=p.read_text(encoding="utf-8")
u=u.replace('APP_VERSION = "1.1.13 Stable"', 'APP_VERSION = "1.1.14 Stable"')
p.write_text(u,encoding="utf-8")
(root/"app_source/app/version.py").write_text('__version__ = "1.1.14 Stable"\n',encoding="utf-8")

print("v1.1.14 OBS UX/connection patch applied")
