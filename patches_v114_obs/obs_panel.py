from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QSizePolicy,
)


class ObsPanel(QFrame):
    connect_requested = Signal(dict)
    disconnect_requested = Signal()
    refresh_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("MonitorPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(7)

        header = QHBoxLayout()
        header.setSpacing(8)

        title = QLabel("OBS")
        title.setObjectName("SectionTitle")

        self.status = QLabel("● Desconectado")
        self.status.setStyleSheet("color:#E7B955; font-weight:700;")

        self.connect_button = QPushButton("Conectar OBS")
        self.connect_button.setMinimumWidth(108)
        self.connect_button.clicked.connect(self._connect_clicked)

        self.disconnect_button = QPushButton("Desconectar")
        self.disconnect_button.clicked.connect(self.disconnect_requested.emit)
        self.disconnect_button.setVisible(False)

        self.details_button = QToolButton()
        self.details_button.setText("Ajustes")
        self.details_button.setCheckable(True)
        self.details_button.toggled.connect(self._toggle_details)

        header.addWidget(title)
        header.addWidget(self.status)
        header.addStretch(1)
        header.addWidget(self.connect_button)
        header.addWidget(self.disconnect_button)
        header.addWidget(self.details_button)

        self.info = QLabel("Abre OBS y pulsa «Conectar OBS».")
        self.info.setObjectName("Muted")
        self.info.setWordWrap(True)
        self.info.setMaximumHeight(42)

        self.details = QFrame()
        grid = QGridLayout(self.details)
        grid.setContentsMargins(0, 4, 0, 0)
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(7)
        grid.setColumnStretch(1, 1)

        self.host_input = QLineEdit("localhost")
        self.host_input.setPlaceholderText("localhost")
        self.host_input.setToolTip("Para OBS en este mismo PC usa localhost.")

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(4455)
        self.port_input.setFixedWidth(92)
        self.port_input.setToolTip("OBS 28+ usa 4455 por defecto.")

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Contraseña de OBS (si está activada)")

        self.eye_button = QPushButton("Ver")
        self.eye_button.setCheckable(True)
        self.eye_button.setFixedWidth(54)
        self.eye_button.toggled.connect(self._show_password)

        self.auto_reconnect = QCheckBox("Reconectar automáticamente")
        self.auto_reconnect.setChecked(True)

        self.local_button = QPushButton("Usar este PC")
        self.local_button.setToolTip("Configura localhost:4455")
        self.local_button.clicked.connect(self._use_local_defaults)

        self.refresh_button = QPushButton("Recargar escenas y fuentes")
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.refresh_button.setEnabled(False)

        grid.addWidget(QLabel("Servidor"), 0, 0)
        grid.addWidget(self.host_input, 0, 1)
        grid.addWidget(QLabel("Puerto"), 0, 2)
        grid.addWidget(self.port_input, 0, 3)
        grid.addWidget(QLabel("Contraseña"), 1, 0)
        grid.addWidget(self.password_input, 1, 1, 1, 2)
        grid.addWidget(self.eye_button, 1, 3)

        bottom = QHBoxLayout()
        bottom.addWidget(self.auto_reconnect)
        bottom.addStretch(1)
        bottom.addWidget(self.local_button)
        bottom.addWidget(self.refresh_button)
        grid.addLayout(bottom, 2, 0, 1, 4)

        self.help = QLabel(
            "En OBS: Herramientas → Configuración del servidor WebSocket → "
            "activa «Habilitar servidor WebSocket». Puerto recomendado: 4455."
        )
        self.help.setObjectName("Muted")
        self.help.setWordWrap(True)
        grid.addWidget(self.help, 3, 0, 1, 4)

        layout.addLayout(header)
        layout.addWidget(self.info)
        layout.addWidget(self.details)
        self.details.setVisible(False)

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
        self.info.setText("Intentando conectar con OBS…")

    def set_connected(self, info: dict) -> None:
        self.status.setText("● Conectado")
        self.status.setStyleSheet("color:#63D98A; font-weight:700;")
        self.connect_button.setVisible(False)
        self.disconnect_button.setVisible(True)
        self.disconnect_button.setEnabled(True)
        self.refresh_button.setEnabled(True)

        version = str(info.get("obsWebSocketVersion", "") or "").strip()
        suffix = f" · WebSocket {version}" if version else ""
        self.info.setText(
            f"Conectado a {info.get('host', 'localhost')}:{info.get('port', 4455)}{suffix}"
        )

    def set_disconnected(self, message: str) -> None:
        self.status.setText("● Desconectado")
        self.status.setStyleSheet("color:#E7B955; font-weight:700;")
        self.connect_button.setVisible(True)
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Conectar OBS")
        self.disconnect_button.setVisible(False)
        self.refresh_button.setEnabled(False)
        self.info.setText(message or "OBS desconectado.")

    def set_error(self, message: str) -> None:
        text = self._friendly_error(message)
        self.status.setText("● No conectado")
        self.status.setStyleSheet("color:#F06A6A; font-weight:700;")
        self.connect_button.setVisible(True)
        self.connect_button.setEnabled(True)
        self.connect_button.setText("Reintentar")
        self.disconnect_button.setVisible(False)
        self.refresh_button.setEnabled(False)
        self.info.setText(text)
        self.details_button.setChecked(True)

    @staticmethod
    def _friendly_error(message: str) -> str:
        raw = str(message or "")
        low = raw.lower()
        if "10061" in low or "connection refused" in low or "actively refused" in low:
            return (
                "No encuentro el servidor WebSocket de OBS. Abre OBS y activa: "
                "Herramientas → Configuración del servidor WebSocket → "
                "Habilitar servidor. Usa puerto 4455."
            )
        if "requiere contraseña" in low or "authentication" in low or "contraseña" in low:
            return "OBS requiere contraseña o la contraseña no coincide. Revísala en los ajustes de WebSocket de OBS."
        if "timed out" in low or "timeout" in low:
            return "OBS no respondió a tiempo. Comprueba que esté abierto y que servidor/puerto sean correctos."
        return raw or "No se pudo conectar con OBS."

    def _toggle_details(self, visible: bool) -> None:
        self.details.setVisible(visible)
        self.details_button.setText("Ocultar" if visible else "Ajustes")

    def _show_password(self, visible: bool) -> None:
        self.password_input.setEchoMode(
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        self.eye_button.setText("Ocultar" if visible else "Ver")

    def _use_local_defaults(self) -> None:
        self.host_input.setText("localhost")
        self.port_input.setValue(4455)
        self.info.setText("Configurado para OBS en este mismo PC: localhost:4455.")
