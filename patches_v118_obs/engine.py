from __future__ import annotations

import logging
import threading
from typing import Any

import obsws_python as obs
from PySide6.QtCore import QObject, QTimer, Signal


class ObsError(RuntimeError):
    pass


class ObsEngine(QObject):
    connected = Signal(dict)
    disconnected = Signal(str)
    scenes_changed = Signal(list)
    inputs_changed = Signal(list)
    scene_items_changed = Signal(str, list)
    error_occurred = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.logger = logging.getLogger("midi_premium_2.obs")
        self.host = "localhost"
        self.port = 4455
        self.password = ""
        self.auto_reconnect = True

        self._client: obs.ReqClient | None = None
        self._lock = threading.RLock()
        self._connecting = False
        self._manual_disconnect = False

        self._timer = QTimer(self)
        self._timer.setInterval(3000)
        self._timer.timeout.connect(self._auto_reconnect_tick)
        self._timer.start()

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._client is not None

    def configure(
        self,
        host: str,
        port: int,
        password: str,
        auto_reconnect: bool = True,
    ) -> None:
        clean_host = (host or "").strip()
        for prefix in ("ws://", "wss://", "http://", "https://"):
            if clean_host.lower().startswith(prefix):
                clean_host = clean_host[len(prefix):]
        clean_host = clean_host.split("/", 1)[0]
        if ":" in clean_host and clean_host.count(":") == 1:
            left, right = clean_host.rsplit(":", 1)
            if right.isdigit():
                clean_host = left

        self.host = clean_host or "localhost"
        self.port = max(1, min(65535, int(port)))
        self.password = password or ""
        self.auto_reconnect = bool(auto_reconnect)

    def connect_async(self) -> None:
        self._manual_disconnect = False
        with self._lock:
            if self._client is not None or self._connecting:
                return
            self._connecting = True
        threading.Thread(
            target=self._connect_worker,
            daemon=True,
            name="ObsConnectWorker",
        ).start()

    def _connect_worker(self) -> None:
        client = None
        try:
            client = obs.ReqClient(
                host=self.host,
                port=self.port,
                password=self.password,
                timeout=2.5,
            )
            version = client.send("GetVersion", raw=True) or {}
            info = {
                "host": self.host,
                "port": self.port,
                "obsVersion": version.get("obsVersion", ""),
                "obsWebSocketVersion": version.get("obsWebSocketVersion", ""),
                "rpcVersion": version.get("rpcVersion", 1),
            }
            with self._lock:
                self._client = client
            self.connected.emit(info)
        except Exception as exc:
            if client is not None:
                try:
                    client.disconnect()
                except Exception:
                    pass
            self.error_occurred.emit(self._friendly_connection_error(exc))
        finally:
            with self._lock:
                self._connecting = False

    def disconnect(self, reason: str = "OBS desconectado por el usuario.") -> None:
        self._manual_disconnect = True
        self._drop_client()
        self.disconnected.emit(reason)

    def shutdown(self) -> None:
        self._timer.stop()
        self._manual_disconnect = True
        self._drop_client()

    def _drop_client(self) -> None:
        with self._lock:
            client = self._client
            self._client = None
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                pass

    def _auto_reconnect_tick(self) -> None:
        if (
            not self.auto_reconnect
            or self._manual_disconnect
            or self.is_connected
            or self._connecting
        ):
            return
        self.connect_async()

    def _request(
        self,
        request_type: str,
        request_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            client = self._client
            if client is None:
                raise ObsError("OBS no está conectado.")
            try:
                result = client.send(
                    request_type,
                    request_data or {},
                    raw=True,
                )
                return dict(result or {})
            except Exception as exc:
                self.logger.exception("OBS request failed: %s", request_type)
                self._client = None
                try:
                    client.disconnect()
                except Exception:
                    pass
                raise ObsError(self._friendly_connection_error(exc)) from exc

    def refresh_scenes_async(self) -> None:
        threading.Thread(
            target=self._scenes_worker,
            daemon=True,
            name="ObsScenesWorker",
        ).start()

    def refresh_inputs_async(self) -> None:
        threading.Thread(
            target=self._inputs_worker,
            daemon=True,
            name="ObsInputsWorker",
        ).start()

    def refresh_scene_items_async(self, scene_name: str) -> None:
        threading.Thread(
            target=self._scene_items_worker,
            args=(scene_name,),
            daemon=True,
            name="ObsSceneItemsWorker",
        ).start()

    def _scenes_worker(self) -> None:
        try:
            self.scenes_changed.emit(self.get_scenes())
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def _inputs_worker(self) -> None:
        try:
            self.inputs_changed.emit(self.get_inputs())
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def _scene_items_worker(self, scene_name: str) -> None:
        try:
            self.scene_items_changed.emit(scene_name, self.get_scene_items(scene_name))
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def set_scene(self, scene_name: str) -> None:
        scene_name = (scene_name or "").strip()
        if not scene_name:
            raise ObsError("Selecciona una escena de OBS.")
        self._request("SetCurrentProgramScene", {"sceneName": scene_name})

    def get_scenes(self) -> list[str]:
        data = self._request("GetSceneList")
        return [
            str(item.get("sceneName", ""))
            for item in data.get("scenes", [])
            if item.get("sceneName")
        ]

    def get_inputs(self) -> list[str]:
        data = self._request("GetInputList")
        return [
            str(item.get("inputName", ""))
            for item in data.get("inputs", [])
            if item.get("inputName")
        ]

    def set_input_volume_db(self, input_name: str, volume_db: float) -> None:
        input_name = (input_name or "").strip()
        if not input_name:
            raise ObsError("Selecciona una fuente de audio de OBS.")
        self._request(
            "SetInputVolume",
            {"inputName": input_name, "inputVolumeDb": float(volume_db)},
        )

    def set_input_muted(self, input_name: str, muted: bool) -> None:
        input_name = (input_name or "").strip()
        if not input_name:
            raise ObsError("Selecciona una fuente de audio de OBS.")
        self._request(
            "SetInputMute",
            {"inputName": input_name, "inputMuted": bool(muted)},
        )

    def toggle_input_mute(self, input_name: str) -> None:
        input_name = (input_name or "").strip()
        if not input_name:
            raise ObsError("Selecciona una fuente de audio de OBS.")
        self._request("ToggleInputMute", {"inputName": input_name})

    def get_scene_items(self, scene_name: str) -> list[dict[str, Any]]:
        scene_name = (scene_name or "").strip()
        if not scene_name:
            return []
        data = self._request("GetSceneItemList", {"sceneName": scene_name})
        items: list[dict[str, Any]] = []
        for item in data.get("sceneItems", []):
            source_name = str(item.get("sourceName", "")).strip()
            item_id = item.get("sceneItemId")
            if source_name and item_id is not None:
                items.append(
                    {
                        "sourceName": source_name,
                        "sceneItemId": int(item_id),
                        "sceneItemEnabled": bool(item.get("sceneItemEnabled", True)),
                        "isGroup": bool(item.get("isGroup", False)),
                    }
                )
        return items

    def set_scene_item_enabled(
        self,
        scene_name: str,
        scene_item_id: int,
        enabled: bool,
    ) -> None:
        self._request(
            "SetSceneItemEnabled",
            {
                "sceneName": scene_name,
                "sceneItemId": int(scene_item_id),
                "sceneItemEnabled": bool(enabled),
            },
        )

    def toggle_scene_item(self, scene_name: str, scene_item_id: int) -> None:
        data = self._request(
            "GetSceneItemEnabled",
            {
                "sceneName": scene_name,
                "sceneItemId": int(scene_item_id),
            },
        )
        current = bool(data.get("sceneItemEnabled", True))
        self.set_scene_item_enabled(scene_name, scene_item_id, not current)

    @staticmethod
    def _friendly_connection_error(exc: Exception) -> str:
        raw = str(exc or "")
        low = raw.lower()
        if "timed out" in low or "timeout" in low:
            return (
                "OBS tardó demasiado en responder. Comprueba que el servidor "
                "WebSocket esté habilitado en localhost:4455."
            )
        if (
            "10061" in low
            or "connection refused" in low
            or "actively refused" in low
            or "refused" in low
        ):
            return (
                "OBS no está aceptando la conexión. En OBS activa "
                "Herramientas → Configuración del servidor WebSocket y usa 4455."
            )
        if (
            "authentication" in low
            or "identified" in low
            or "password" in low
            or "4009" in low
        ):
            return "OBS rechazó la contraseña WebSocket. Vuelve a copiarla desde OBS."
        return raw or "No se pudo conectar con OBS."
