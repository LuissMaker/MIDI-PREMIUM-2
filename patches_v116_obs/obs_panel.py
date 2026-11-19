from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QVBoxLayout, QSizePolicy
)


class ObsPanel(QFrame):
    connect_requested = Signal(dict)
    disconnect_requested = Signal()
    refresh_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(168)
        self.setMaximumHeight(205)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(7)

        header = QHBoxLayout()
        title = QLabel("Conexión OBS")
        title.setObjectName("SectionTitle")
        self.status = QLabel("● Desconectado")
        self.status.setStyleSheet("color:#E7B955; font-weight:700;")
        self.connect_button = QPushButton("Conectar")
        self.connect_button.setMinimumWidth(92)
        self.connect_button.clicked.connect(self._connect_clicked)
        self.disconnect_button = QPushButton("Desconectar")
        self.disconnect_button.setMinimumWidth(92)
        self.disconnect_button.setVisible(False)
        self.disconnect_button.clicked.connect(self.disconnect_requested.emit)

        header.addWidget(title)
        header.addSpacing(8)
        header.addWidget(self.status)
        header.addStretch(1)
        header.addWidget(self.connect_button)
        header.addWidget(self.disconnect_button)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)

        self.host_input = QLineEdit("localhost")
        self.host_input.setPlaceholderText("localhost")
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(4455)
        self.port_input.setFixedWidth(94)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Contraseña WebSocket (si usas una)")
        self.eye_button = QPushButton("Ver")
        self.eye_button.setCheckable(True)
        self.eye_button.setFixedWidth(58)
        self.eye_button.toggled.connect(self._show_password)

        grid.addWidget(QLabel("Servidor"), 0, 0)
        grid.addWidget(self.host_input, 0, 1)
        grid.addWidget(QLabel("Puerto"), 0, 2)
        grid.addWidget(self.port_input, 0, 3)
        grid.addWidget(QLabel("Contraseña"), 1, 0)
        grid.addWidget(self.password_input, 1, 1, 1, 2)
        grid.addWidget(self.eye_button, 1, 3)

        actions = QHBoxLayout()
        self.auto_reconnect = QCheckBox("Reconectar automáticamente")
        self.auto_reconnect.setChecked(True)
        self.local_button = QPushButton("Usar localhost:4455")
        self.local_button.clicked.connect(self._use_local_defaults)
        self.refresh_button = QPushButton("Recargar OBS")
        self.refresh_button.setEnabled(False)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)

        actions.addWidget(self.auto_reconnect)
        actions.addStretch(1)
        actions.addWidget(self.local_button)
        actions.addWidget(self.refresh_button)

        self.info = QLabel("Abre OBS y pulsa «Conectar».")
        self.info.setObjectName("Muted")
        self.info.setWordWrap(True)
        self.info.setMinimumHeight(30)
        self.info.setMaximumHeight(38)

        root.addLayout(header)
        root.addLayout(grid)
        root.addLayout(actions)
        root.addWidget(self.info)

    @staticmethod
    def _clean_host(value: str) -> str:
        host = (value or "").strip()
        for prefix in ("ws://", "wss://", "http://", "https://"):
            if host.lower().startswith(prefix):
                host = host[len(prefix):]
        host = host.split("/", 1)[0]
        if ":" in host and host.count(":") == 1:
            left, right = host.rsplit(":", 1)
            if right.isdigit():
                host = left
        return host.strip() or "localhost"

    def get_settings(self) -> dict:
        return {
            "host": self._clean_host(self.host_input.text()),
            "port": self.port_input.value(),
            "password": self.password_input.text(),
            "auto_reconnect": self.auto_reconnect.isChecked(),
        }

    def set_settings(self, settings: dict) -> None:
        self.host_input.setText(self._clean_host(str(settings.get("host", "localhost"))))
        try:
            self.port_input.setValue(int(settings.get("port", 4455)))
        except Exception:
            self.port_input.setValue(4455)
        self.password_input.setText(str(settings.get("password", "")))
        self.auto_reconnect.setChecked(bool(settings.get("auto_reconnect", True)))

    def _connect_clicked(self) -> None:
        self.set_connecting()
        self.connect_requested.emit(self.get_settings())

    def set_connecting(self) -> None:
        self.status.setText("● Conectando…")
        self.status.setStyleSheet("color:#62A8FF; font-weight:700;")
        self.connect_button.setEnabled(False)
        self.connect_button.setText("Conectando…")
        self.info.setText("Intentando conectar con OBS WebSocket…")

    def set_connected(self, info: dict) -> None:
        self.status.setText("● Conectado")
        self.status.setStyleSheet("color:#63D98A; font-weight:700;")
        self.connect_button.setVisible(False)
        self.disconnect_button.setVisible(True)
        self.refresh_button.setEnabled(True)
        version = str(info.get("obsWebSocketVersion", "") or "").strip()
        suffix = f" · WS {version}" if version else ""
        self.info.setText(
            f"Conectado a {info.get('host', 'localhost')}:{info.get('port', 4455)}{suffix}"
        )

    def set_disconnected(self, message: str) -> None:
        self.status.setText("● Desconectado")
        self.status.setStyleSheet("color:#E7B955; font-weight:700;")
        self.connect_button.setVisible(True)
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Conectar")
        self.disconnect_button.setVisible(False)
        self.refresh_button.setEnabled(False)
        self.info.setText(message or "OBS desconectado.")

    def set_error(self, message: str) -> None:
        self.status.setText("● No conectado")
        self.status.setStyleSheet("color:#F06A6A; font-weight:700;")
        self.connect_button.setVisible(True)
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Reintentar")
        self.disconnect_button.setVisible(False)
        self.refresh_button.setEnabled(False)
        self.info.setText(self._friendly_error(message))

    @staticmethod
    def _friendly_error(message: str) -> str:
        raw = str(message or "")
        low = raw.lower()
        if "10061" in low or "connection refused" in low or "actively refused" in low:
            return "OBS no acepta conexiones. En OBS activa Herramientas → Configuración del servidor WebSocket y usa el puerto 4455."
        if "requiere contraseña" in low or "authentication" in low or "contraseña" in low:
            return "La contraseña WebSocket falta o no coincide con la configurada en OBS."
        if "timed out" in low or "timeout" in low:
            return "OBS no respondió. Comprueba que esté abierto y que uses localhost:4455."
        return raw or "No se pudo conectar con OBS."

    def _show_password(self, visible: bool) -> None:
        self.password_input.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        self.eye_button.setText("Ocultar" if visible else "Ver")

    def _use_local_defaults(self) -> None:
        self.host_input.setText("localhost")
        self.port_input.setValue(4455)
        self.info.setText("Listo para OBS en este mismo PC: localhost:4455.")
