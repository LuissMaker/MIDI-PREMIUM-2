from __future__ import annotations

import os
import sys
import time
from copy import deepcopy

from PySide6.QtCore import QEvent, QTimer, Qt, QSize
from PySide6.QtGui import QAction, QCloseEvent, QIcon, QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QDialog,
    QDialogButtonBox,
    QApplication,
    QLabel,
    QMenu,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSystemTrayIcon,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.actions.engine import ActionEngine
from app.actions.photoshop_psd import list_psd_elements, PhotoshopPsdError
from app.continuous.engine import ContinuousActionEngine
from app.continuous.router import MpkMiniKnobRouter
from app.core.profile_store import ProfileStore
from app.core.secure_store import protect_text, unprotect_text
from app.core.settings import SettingsManager
from app.core.updater import UpdateService, current_version, launch_installer, update_available
from app.midi.engine import MidiEngine
from app.midi.event import MidiEvent
from app.midi.pad_router import MpkMiniPadRouter
from app.obs.engine import ObsEngine
from app.version import __version__
from app.ui.osd import ActionOsd
from app.widgets.action_editor import ActionEditor
from app.widgets.knob_panel import KnobPanel
from app.widgets.config_dialogs import AppSettingsDialog, KnobEditDialog, PadEditDialog, PsdElementPickerDialog, ProfileEditDialog
from app.widgets.midi_monitor import MidiMonitor
from app.widgets.obs_panel import ObsPanel
from app.widgets.pad_widget import PadWidget

DEV_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
UI_ICON_DIR = DEV_ROOT / "assets" / "ui_icons"
PAD_ICON_DIR = DEV_ROOT / "assets" / "pad_icons"
PROFILE_ICON_DIR = DEV_ROOT / "assets" / "profile_icons"


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: SettingsManager,
        profiles: ProfileStore,
        midi_engine: MidiEngine,
        action_engine: ActionEngine,
        obs_engine: ObsEngine,
        continuous_engine: ContinuousActionEngine,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.profiles = profiles
        self.midi_engine = midi_engine
        self.action_engine = action_engine
        self.obs_engine = obs_engine
        self.continuous_engine = continuous_engine
        self.pad_router = MpkMiniPadRouter()
        self.knob_router = MpkMiniKnobRouter()
        self.action_cooldown_seconds = 0.25
        self.last_action_trigger: dict[int, float] = {}
        self._force_quit = False
        self._geometry_save_timer = QTimer(self)
        self._geometry_save_timer.setSingleShot(True)
        self._geometry_save_timer.timeout.connect(self._save_live_geometry)
        self.update_service = UpdateService(self)
        self.update_service.check_finished.connect(self._on_update_check_finished)
        self.update_service.download_progress.connect(self._on_update_download_progress)
        self.update_service.download_finished.connect(self._on_update_download_finished)
        self._pending_update_manifest: dict = {}

        workspace = settings.data["workspace"]
        self.active_bank = str(workspace.get("active_bank", "A"))
        self.selected_pad = int(workspace.get("selected_pad", 1))
        self.stream_mode = bool(workspace.get("stream_mode", False))
        self.compact_mode = bool(workspace.get("compact_mode", True))
        self.compact_editor_open = False
        self.profile_data: dict = {}
        self.pad_widgets: dict[int, PadWidget] = {}
        self._midi_learn_target: str | None = None
        self._midi_learn_dialog = None
        self._joystick_detect_axis: str | None = None
        self._joystick_axis_armed = {"horizontal": True, "vertical": True}
        self._joystick_last_trigger = {"horizontal": 0.0, "vertical": 0.0}
        self._binding_last_trigger: dict[str, float] = {}
        self._initializing = True

        window = settings.data["window"]
        self.resize(
            int(window.get("width", 1180)),
            int(window.get("height", 760)),
        )
        self.setMinimumSize(860, 560)
        self.setWindowTitle(f"MIDI Premium 2 — {__version__}")

        x, y = window.get("x"), window.get("y")
        if isinstance(x, int) and isinstance(y, int):
            self.move(x, y)

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self._build_top_bar())
        root_layout.addWidget(self._build_workspace(), 1)
        self.osd = ActionOsd()
        self._setup_tray()
        self._sync_windows_startup(bool(self.settings.data.setdefault("workspace", {}).get("start_with_windows", False)))

        self._load_profiles()
        self.change_bank(self.active_bank)
        self.select_pad(self.selected_pad)
        self.set_stream_mode(self.stream_mode)
        self.set_compact_mode(self.compact_mode, initial=True)
        self._connect_midi_module()
        self._connect_obs_module()
        self._initializing = False

        self.statusBar().showMessage(
            "MIDI, acciones y OBS preparados."
        )
        if bool(self.settings.data.setdefault("updates", {}).get("check_on_start", True)):
            QTimer.singleShot(1800, lambda: self.update_service.check_async(interactive=False))

    def _build_top_bar(self) -> QFrame:
        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_bar.setFixedHeight(54)
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(14, 0, 14, 0)

        title_block = QVBoxLayout()
        title_block.setContentsMargins(0, 0, 0, 0)
        title_block.setSpacing(0)
        title = QLabel("MIDI Premium 2")
        title.setObjectName("AppTitle")
        self.app_subtitle = QLabel(__version__)
        self.app_subtitle.setObjectName("Muted")
        title_block.addWidget(title)
        title_block.addWidget(self.app_subtitle)
        self.app_subtitle.setVisible(False)

        self.stream_button = QPushButton("Modo Stream")
        self.stream_button.setCheckable(True)
        self.stream_button.clicked.connect(self.set_stream_mode)

        # Botón de modo compacto: solo icono, sin checkbox ni texto.
        # Conservamos el nombre del atributo por compatibilidad con la lógica existente.
        self.compact_checkbox = QPushButton()
        self.compact_checkbox.setCheckable(True)
        self.compact_checkbox.setFixedSize(36, 34)
        compact_icon = UI_ICON_DIR / "compact_mode.svg"
        self.compact_checkbox.setIcon(
            QIcon(self._tinted_svg_pixmap(compact_icon, "#C9D5E4", 18))
        )
        self.compact_checkbox.setIconSize(QSize(18, 18))
        self.compact_checkbox.setToolTip(
            "Alternar modo compacto / modo normal"
        )
        self.compact_checkbox.toggled.connect(self.set_compact_mode)

        self.profile_combo = QComboBox()
        self.profile_combo.setIconSize(QSize(20, 20))
        self.profile_combo.setMinimumWidth(150)
        self.profile_combo.setMaximumWidth(220)
        self.profile_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.profile_combo.currentTextChanged.connect(self.change_profile)
        self.profile_combo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.profile_combo.customContextMenuRequested.connect(self._show_profile_context_menu)
        self.profile_combo.setToolTip("Selecciona un perfil. Clic derecho para editar nombre e icono.")

        self.add_profile_button = QPushButton()
        self.add_profile_button.setIcon(QIcon(str(UI_ICON_DIR / "add_preset.svg")))
        self.add_profile_button.setToolTip("Añadir preset / perfil")
        self.add_profile_button.setFixedWidth(36)
        self.add_profile_button.clicked.connect(self.create_profile)
        self.routes_button = QPushButton()
        self.routes_button.setFixedSize(36, 34)
        self.routes_button.setIcon(QIcon(self._tinted_svg_pixmap(UI_ICON_DIR / "configuration.svg", "#C9D5E4", 18)))
        self.routes_button.setIconSize(QSize(18, 18))
        self.routes_button.setToolTip("Configuración")
        self.routes_button.clicked.connect(self.open_app_settings)

        layout.addLayout(title_block)
        layout.addStretch()
        layout.addWidget(self.stream_button)
        layout.addWidget(self.compact_checkbox)
        self.profile_label = QLabel("Perfil")
        layout.addWidget(self.profile_label)
        layout.addWidget(self.profile_combo)
        layout.addWidget(self.add_profile_button)
        layout.addWidget(self.routes_button)
        return top_bar

    def _build_workspace(self) -> QWidget:
        self.workspace = QWidget()
        layout = QHBoxLayout(self.workspace)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.controller_panel = self._build_controller_panel()
        self.editor_panel = self._build_editor_panel()
        layout.addWidget(self.controller_panel, 5)
        layout.addWidget(self.editor_panel, 5)
        return self.workspace

    def _build_controller_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Sidebar")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 7, 8, 7)
        layout.setSpacing(7)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Una sola barra compacta: sección + bancos + estado MIDI.
        control_row = QHBoxLayout()
        control_row.setSpacing(6)
        title = QLabel("Controlador")
        title.setObjectName("SectionTitle")
        control_row.addWidget(title)
        control_row.addSpacing(4)

        self.bank_a_button = QPushButton("BANK A")
        self.bank_a_button.setCheckable(True)
        self.bank_b_button = QPushButton("BANK B")
        self.bank_b_button.setCheckable(True)
        self.bank_group = QButtonGroup(self)
        self.bank_group.setExclusive(True)
        self.bank_group.addButton(self.bank_a_button)
        self.bank_group.addButton(self.bank_b_button)
        self.bank_a_button.clicked.connect(lambda _=False: self.change_bank("A"))
        self.bank_b_button.clicked.connect(lambda _=False: self.change_bank("B"))
        self.bank_a_button.setFixedHeight(30)
        self.bank_b_button.setFixedHeight(30)
        control_row.addWidget(self.bank_a_button)
        control_row.addWidget(self.bank_b_button)
        control_row.addStretch(1)

        self.device_status_icon = QLabel()
        self.device_status_icon.setFixedSize(16, 16)
        self.device_status = QLabel("MIDI desconectado")
        self.reload_midi_button = QPushButton()
        self.reload_midi_button.setFixedSize(28, 28)
        self.reload_midi_button.setIcon(QIcon(str(UI_ICON_DIR / "reload_midi.svg")))
        self.reload_midi_button.setToolTip("Recargar dispositivos MIDI")
        self.reload_midi_button.clicked.connect(self.reload_midi)
        self._set_midi_status(False, "MIDI desconectado")
        control_row.addWidget(self.device_status_icon)
        control_row.addWidget(self.device_status)
        control_row.addWidget(self.reload_midi_button)

        pad_container = QWidget(panel)
        pad_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        grid = QGridLayout(pad_container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(7)
        for col in range(4):
            grid.setColumnStretch(col, 1)

        for local_pad in range(1, 9):
            widget = PadWidget(local_pad)
            widget.clicked.connect(self.handle_pad_clicked)
            widget.context_requested.connect(self.show_pad_context_menu)
            self.pad_widgets[local_pad] = widget
            grid.addWidget(widget, 0 if local_pad <= 4 else 1, (local_pad - 1) % 4)

        self.knob_panel = KnobPanel()
        self.knob_panel.save_requested.connect(self.save_knob_configuration)
        self.knob_panel.edit_requested.connect(self.open_knob_editor)
        self.knob_panel.context_requested.connect(self.show_knob_context_menu)
        self.midi_monitor = MidiMonitor()

        layout.addLayout(control_row)
        layout.addWidget(pad_container)
        layout.addWidget(self.knob_panel)
        layout.addWidget(self.midi_monitor)
        return panel

    def _build_editor_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("EditorPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        editor_heading = QHBoxLayout()
        self.editor_title = QLabel("PAD 01")
        self.editor_title.setObjectName("SectionTitle")
        self.compact_close_button = QPushButton("×")
        self.compact_close_button.setFixedSize(32, 32)
        self.compact_close_button.setToolTip("Cerrar editor y volver al modo compacto")
        self.compact_close_button.clicked.connect(self.close_compact_editor)
        self.compact_close_button.setVisible(False)
        editor_heading.addWidget(self.editor_title)
        editor_heading.addStretch()
        editor_heading.addWidget(self.compact_close_button)

        self.editor_subtitle = QLabel()
        self.editor_subtitle.setObjectName("Muted")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ejemplo: Pantalla completa")
        self.obs_panel = ObsPanel()
        self.action_editor = ActionEditor(global_paths=self.settings.data.setdefault("paths", {}))
        self.action_editor.refresh_obs_scenes_requested.connect(
            self.obs_engine.refresh_scenes_async
        )
        self.action_editor.refresh_obs_inputs_requested.connect(
            self.obs_engine.refresh_inputs_async
        )
        self.action_editor.refresh_scene_items_requested.connect(
            self.obs_engine.refresh_scene_items_async
        )

        buttons = QHBoxLayout()
        delete_button = QPushButton("Eliminar")
        delete_button.clicked.connect(self.delete_current_pad)
        test_button = QPushButton("Probar acción")
        test_button.clicked.connect(self.simulate_action)
        save_button = QPushButton("Guardar cambios")
        save_button.clicked.connect(self.save_current_pad)
        buttons.addWidget(delete_button)
        buttons.addStretch()
        buttons.addWidget(test_button)
        buttons.addWidget(save_button)

        layout.addLayout(editor_heading)
        layout.addWidget(self.editor_subtitle)
        layout.addWidget(QLabel("Nombre del pad"))
        layout.addWidget(self.name_input)
        layout.addWidget(QLabel("Tipo de acción"))
        layout.addWidget(self.action_editor, 1)
        layout.addWidget(self.obs_panel)
        layout.addLayout(buttons)
        self.action_editor.action_type_changed.connect(self._sync_main_obs_visibility)
        self._sync_main_obs_visibility(str(self.action_editor.action_combo.currentData()))
        return panel

    def _sync_main_obs_visibility(self, action_type: str) -> None:
        self.obs_panel.setVisible(str(action_type).startswith("obs_"))

    def _connect_midi_module(self) -> None:
        midi_settings = self.settings.data.setdefault("midi", {})
        preferred = str(midi_settings.get("preferred_device", ""))
        auto_reconnect = bool(midi_settings.get("auto_reconnect", True))
        self.midi_engine.configure_reconnect(preferred, auto_reconnect)

        self.midi_monitor.refresh_requested.connect(
            self.midi_engine.refresh_devices
        )
        self.midi_monitor.connect_requested.connect(
            self.connect_midi_device
        )
        self.midi_monitor.disconnect_requested.connect(
            self.midi_engine.disconnect_device
        )

        self.midi_engine.devices_changed.connect(self.handle_midi_devices)
        self.midi_engine.connected.connect(self.handle_midi_connected)
        self.midi_engine.disconnected.connect(self.handle_midi_disconnected)
        self.midi_engine.event_received.connect(self.handle_midi_event)
        self.midi_engine.error_occurred.connect(self.handle_midi_error)

        devices = self.midi_engine.refresh_devices()
        selected = self.midi_engine.choose_default_device(devices, preferred)
        self.midi_monitor.set_devices(devices, selected)

        if bool(midi_settings.get("auto_connect", True)):
            QTimer.singleShot(250, self.midi_engine.auto_connect)

    def connect_midi_device(self, device_name: str) -> None:
        if self.midi_engine.connect_device(device_name):
            self.settings.data.setdefault("midi", {})[
                "preferred_device"
            ] = device_name
            self.settings.save()

    def handle_midi_devices(self, devices: list[str]) -> None:
        preferred = str(
            self.settings.data.setdefault("midi", {}).get(
                "preferred_device",
                "",
            )
        )
        selected = self.midi_engine.choose_default_device(devices, preferred)
        self.midi_monitor.set_devices(devices, selected)

    def _tinted_svg_pixmap(self, path, color: str, size: int = 16) -> QPixmap:
        pix = QIcon(str(path)).pixmap(size, size)
        if pix.isNull():
            return pix
        result = QPixmap(pix.size())
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        painter.drawPixmap(0, 0, pix)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(result.rect(), QColor(color))
        painter.end()
        return result

    def _set_midi_status(self, connected: bool, text: str) -> None:
        color = "#63D98A" if connected else "#F06A6A"
        icon = self._tinted_svg_pixmap(UI_ICON_DIR / "midi_status.svg", color, 16)
        self.device_status_icon.setPixmap(icon)
        self.device_status_icon.setStyleSheet("background:transparent;")
        self.device_status.setText(text)
        self.device_status.setStyleSheet(f"color:{color}; font-weight:700;")

    def reload_midi(self) -> None:
        devices = self.midi_engine.refresh_devices()
        preferred = str(self.settings.data.setdefault("midi", {}).get("preferred_device", ""))
        selected = self.midi_engine.choose_default_device(devices, preferred)
        self.midi_monitor.set_devices(devices, selected)
        if selected:
            self.connect_midi_device(selected)
        else:
            self._set_midi_status(False, "MIDI desconectado")
            self.statusBar().showMessage("No se encontró un dispositivo MIDI compatible.", 3000)

    def handle_midi_connected(self, device_name: str) -> None:
        self._set_midi_status(True, "MIDI conectado")
        self.midi_monitor.set_connected(device_name)
        self.settings.data.setdefault("midi", {})[
            "preferred_device"
        ] = device_name
        self.settings.save()

    def handle_midi_disconnected(self, reason: str) -> None:
        self._set_midi_status(False, "MIDI desconectado")
        self.midi_monitor.set_disconnected(reason)

    def handle_midi_error(self, message: str) -> None:
        self._set_midi_status(False, "Error MIDI")
        self.midi_monitor.set_error(message)

    def handle_midi_event(self, event: MidiEvent) -> None:
        self.midi_monitor.append_event(event)

        dialog = self._midi_learn_dialog
        if dialog is not None and hasattr(dialog, "append_midi_test_event"):
            dialog.append_midi_test_event(event)
            if getattr(dialog, "is_midi_test_listening", lambda: False)():
                return

        # Detección de eje de palanca: acepta pitchwheel o CC y no ejecuta acciones.
        if self._joystick_detect_axis:
            signature = self._joystick_event_signature(event)
            if signature:
                axis = self._joystick_detect_axis
                self._joystick_detect_axis = None
                dialog = self._midi_learn_dialog
                if dialog is not None and hasattr(dialog, "set_joystick_axis"):
                    dialog.set_joystick_axis(axis, signature, event.summary())
                self.show_toast(f"Eje {axis} detectado: {event.summary()}")
                return

        # MIDI Learn captura el siguiente control físico sin ejecutar su acción normal.
        if self._midi_learn_target:
            signature = self._event_binding_signature(event)
            if signature:
                target = self._midi_learn_target
                self._midi_learn_target = None
                dialog = self._midi_learn_dialog
                if dialog is not None:
                    dialog.set_learned_binding(target, signature, event.summary())
                self.show_toast(f"Control MIDI aprendido: {event.summary()}")
                return

        if self._dispatch_global_midi_binding(event):
            return

        if self._dispatch_joystick(event):
            return

        knob_route=self.knob_router.route(event)
        if knob_route is not None:
            cfg=self.knob_panel.knob_config(knob_route.knob)
            self.knob_panel.update_value(knob_route.knob,knob_route.value)
            self._show_knob_osd(knob_route.knob, knob_route.value, cfg)
            self.continuous_engine.update_knob(knob_route.knob,knob_route.value,cfg)
            return

        route = self.pad_router.route(event)
        if route is None:
            return

        if event.is_release:
            self.pad_widgets[route.local_pad].set_activity(False)
            return

        if not event.is_press:
            return

        # El BANK seleccionado en MIDI Premium manda. Los mensajes de nota del
        # controlador pueden pertenecer a un banco físico distinto, pero nunca
        # deben hacer que BANK B ejecute una asignación de BANK A (o viceversa).
        display_number = route.local_pad if self.active_bank == "A" else route.local_pad + 8

        self.select_pad(route.local_pad)
        self.pad_widgets[route.local_pad].set_activity(True)
        self.execute_pad_action(display_number)



    @staticmethod
    def _event_binding_signature(event: MidiEvent) -> str:
        # Solo capturamos eventos utilizables como botones. Para CC/nota se guarda
        # canal + número; el valor/velocidad no forma parte del identificador.
        if event.type in {"note_on", "note_off"} and event.note is not None:
            if event.type == "note_off" or (event.velocity or 0) <= 0:
                return ""
            return f"note:{event.channel if event.channel is not None else -1}:{int(event.note)}"
        if event.type == "control_change" and event.control is not None:
            if (event.value or 0) <= 0:
                return ""
            return f"cc:{event.channel if event.channel is not None else -1}:{int(event.control)}"
        if event.type == "program_change" and event.program is not None:
            return f"program:{event.channel if event.channel is not None else -1}:{int(event.program)}"
        return ""

    @staticmethod
    def _joystick_event_signature(event: MidiEvent) -> str:
        if event.type == "pitchwheel" and event.pitch is not None:
            return f"pitch:{event.channel if event.channel is not None else -1}"
        if event.type == "control_change" and event.control is not None:
            return f"cc:{event.channel if event.channel is not None else -1}:{int(event.control)}"
        return ""

    @staticmethod
    def _normalized_joystick_value(event: MidiEvent) -> float | None:
        if event.type == "pitchwheel" and event.pitch is not None:
            value = float(event.pitch) / 8192.0
            return max(-1.0, min(1.0, value))
        if event.type == "control_change" and event.value is not None:
            # Ejes CC de joystick suelen usar 64 como centro, 0/127 como extremos.
            value = (float(event.value) - 64.0) / 63.0
            return max(-1.0, min(1.0, value))
        return None

    def _execute_joystick_action(self, action: str) -> None:
        action = str(action or "none")
        if action == "profile_prev": self.previous_profile()
        elif action == "profile_next": self.next_profile()
        elif action == "bank_a": self.change_bank("A")
        elif action == "bank_b": self.change_bank("B")
        elif action == "bank_toggle": self.change_bank("B" if self.active_bank == "A" else "A")
        elif action == "show_hide":
            if self.isVisible() and not self.isMinimized(): self.hide()
            else: self.show_from_tray()

    def _dispatch_joystick(self, event: MidiEvent) -> bool:
        cfg = dict(self.settings.data.setdefault("midi", {}).get("joystick", {}) or {})
        signature = self._joystick_event_signature(event)
        if not signature:
            return False
        axis = ""
        if signature and signature == str(cfg.get("horizontal_signature", "")).strip():
            axis = "horizontal"
        elif signature and signature == str(cfg.get("vertical_signature", "")).strip():
            axis = "vertical"
        if not axis:
            return False
        value = self._normalized_joystick_value(event)
        if value is None:
            return True
        threshold = max(0.35, min(0.95, float(cfg.get("threshold", 0.65))))
        deadzone = max(0.05, min(0.35, float(cfg.get("center_deadzone", 0.18))))
        cooldown = max(0.10, float(cfg.get("cooldown_ms", 300)) / 1000.0)

        # Volver al centro rearma el eje. Mientras no vuelva, ningún mensaje extra
        # puede cambiar varios perfiles/bancos durante una sola inclinación.
        if abs(value) <= deadzone:
            self._joystick_axis_armed[axis] = True
            return True
        if not self._joystick_axis_armed.get(axis, True):
            return True
        now = time.monotonic()
        if now - self._joystick_last_trigger.get(axis, 0.0) < cooldown:
            return True
        if value >= threshold:
            action = cfg.get("right_action" if axis == "horizontal" else "up_action", "none")
        elif value <= -threshold:
            action = cfg.get("left_action" if axis == "horizontal" else "down_action", "none")
        else:
            return True
        self._joystick_axis_armed[axis] = False
        self._joystick_last_trigger[axis] = now
        self._execute_joystick_action(str(action))
        return True

    def _dispatch_global_midi_binding(self, event: MidiEvent) -> bool:
        signature = self._event_binding_signature(event)
        if not signature:
            return False
        bindings = dict(self.settings.data.setdefault("midi", {}).get("bindings", {}) or {})
        key = next((k for k, v in bindings.items() if str(v).strip() == signature), "")
        if not key:
            return False
        now = time.monotonic()
        if now - self._binding_last_trigger.get(key, 0.0) < 0.30:
            return True
        self._binding_last_trigger[key] = now
        if key == "profile_prev": self.previous_profile()
        elif key == "profile_next": self.next_profile()
        elif key == "bank_a": self.change_bank("A")
        elif key == "bank_b": self.change_bank("B")
        elif key == "bank_toggle": self.change_bank("B" if self.active_bank == "A" else "A")
        elif key == "show_hide":
            if self.isVisible() and not self.isMinimized(): self.hide()
            else: self.show_from_tray()
        else: return False
        return True

    def _connect_obs_module(self) -> None:
        obs_settings = self.settings.data.setdefault("obs", {})
        try:
            password = unprotect_text(
                str(obs_settings.get("password_protected", ""))
            )
        except Exception:
            password = ""

        visible_settings = {
            "host": obs_settings.get("host", "localhost"),
            "port": obs_settings.get("port", 4455),
            "password": password,
            "auto_reconnect": obs_settings.get(
                "auto_reconnect",
                True,
            ),
        }
        self.obs_panel.set_settings(visible_settings)

        self.obs_panel.connect_requested.connect(
            self.connect_obs
        )
        self.obs_panel.disconnect_requested.connect(
            self.obs_engine.disconnect
        )
        self.obs_panel.refresh_requested.connect(
            self.obs_engine.refresh_scenes_async
        )

        self.obs_engine.connected.connect(
            self.handle_obs_connected
        )
        self.obs_engine.disconnected.connect(
            self.handle_obs_disconnected
        )
        self.obs_engine.scenes_changed.connect(self.handle_obs_scenes)
        self.obs_engine.inputs_changed.connect(self.handle_obs_inputs)
        self.obs_engine.scene_items_changed.connect(
            self.handle_obs_scene_items
        )
        self.obs_engine.error_occurred.connect(
            self.handle_obs_error
        )

        self.continuous_engine.value_applied.connect(self.handle_continuous_value_applied)
        self.continuous_engine.error_occurred.connect(self.handle_continuous_error)

        self.obs_engine.configure(
            str(obs_settings.get("host", "localhost")),
            int(obs_settings.get("port", 4455)),
            password,
            bool(obs_settings.get("auto_reconnect", True)),
        )

        if bool(obs_settings.get("auto_connect", False)):
            QTimer.singleShot(500, self.obs_engine.connect_async)

    def connect_obs(self, data: dict) -> None:
        try:
            protected = protect_text(str(data.get("password", "")))
        except Exception as exc:
            self.handle_obs_error(
                f"No se pudo proteger la contraseña: {exc}"
            )
            return

        obs_settings = self.settings.data.setdefault("obs", {})
        obs_settings.update(
            {
                "host": str(data.get("host", "localhost")),
                "port": int(data.get("port", 4455)),
                "password_protected": protected,
                "auto_connect": True,
                "auto_reconnect": bool(
                    data.get("auto_reconnect", True)
                ),
            }
        )
        self.settings.save()

        self.obs_engine.configure(
            obs_settings["host"],
            obs_settings["port"],
            str(data.get("password", "")),
            obs_settings["auto_reconnect"],
        )
        self.obs_engine.connect_async()

    def handle_obs_connected(self, info: dict) -> None:
        self.obs_panel.set_connected(info)
        self.obs_engine.refresh_inputs_async()
        self.statusBar().showMessage(
            "OBS conectado y autenticado.",
            3500,
        )

    def handle_obs_disconnected(self, message: str) -> None:
        self.obs_panel.set_disconnected(message)
        self.statusBar().showMessage("OBS desconectado", 3500)
        self.statusBar().setToolTip(f"OBS: {message}" if message else "OBS desconectado")

    def handle_obs_error(self, message: str) -> None:
        self.obs_panel.set_error(message)
        self.statusBar().showMessage("OBS desconectado", 4500)
        self.statusBar().setToolTip(f"OBS: {message}")

    def handle_obs_scenes(self, scenes: list[str]) -> None:
        self.action_editor.set_obs_scenes(scenes)
        self.statusBar().showMessage(
            f"OBS: {len(scenes)} escenas detectadas.",
            3000,
        )

    def handle_obs_inputs(self, inputs: list[str]) -> None:
        self.knob_panel.set_sources(inputs)
        self.action_editor.set_obs_inputs(inputs)

    def handle_obs_scene_items(
        self,
        scene_name: str,
        items: list[dict],
    ) -> None:
        self.action_editor.set_scene_items(scene_name, items)
        self.statusBar().showMessage(
            f"OBS: {len(items)} fuentes en «{scene_name}».",
            3000,
        )

    def save_knob_configuration(self) -> None:
        self.profile_data["knobs"]=self.knob_panel.get_config()
        self.profiles.save(self.profile_combo.currentText(),self.profile_data)
        self.statusBar().showMessage("Configuración de perillas guardada.",3000)

    def handle_continuous_value_applied(self, knob:int, midi_value:int, db:float) -> None:
        self.knob_panel.update_value(knob,midi_value,db)

    def handle_continuous_error(self, knob:int, message:str) -> None:
        self.knob_panel.set_error(knob,message)
        self.statusBar().showMessage(f"K{knob}: {message}",5000)

    def _load_profiles(self) -> None:
        names = self.profiles.list_profiles()
        requested = str(
            self.settings.data["workspace"].get("active_profile", "General")
        )
        if requested not in names:
            requested = names[0]

        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for profile_name in names:
            try:
                pdata = self.profiles.load(profile_name)
                icon_name = str(pdata.get("icon", "") or "").strip()
            except Exception:
                icon_name = ""
            icon_path = PROFILE_ICON_DIR / icon_name if icon_name else None
            if icon_path is not None and icon_path.exists():
                self.profile_combo.addItem(QIcon(str(icon_path)), profile_name)
            else:
                self.profile_combo.addItem(profile_name)
        self.profile_combo.setCurrentText(requested)
        self.profile_combo.blockSignals(False)
        self.change_profile(requested)

    def create_profile(self) -> None:
        name, accepted = QInputDialog.getText(
            self,
            "Nuevo perfil",
            "Nombre del perfil:",
        )
        name = name.strip()
        if not accepted or not name:
            return
        self.profiles.create(name)
        self._load_profiles()
        self.profile_combo.setCurrentText(name)

    def _show_profile_context_menu(self, pos) -> None:
        menu = QMenu(self.profile_combo)
        edit_action = menu.addAction("Editar perfil…")
        duplicate_action = menu.addAction("Duplicar perfil…")
        delete_action = menu.addAction("Eliminar perfil…")
        icon_name = str(self.profile_data.get("icon", "") or "").strip() if self.profile_data else ""
        icon_path = PROFILE_ICON_DIR / icon_name if icon_name else None
        if icon_path is not None and icon_path.exists():
            profile_icon = QIcon(str(icon_path))
            edit_action.setIcon(profile_icon)
            duplicate_action.setIcon(profile_icon)
        chosen = menu.exec(self.profile_combo.mapToGlobal(pos))
        if chosen == edit_action:
            self.edit_current_profile()
        elif chosen == duplicate_action:
            self.duplicate_current_profile()
        elif chosen == delete_action:
            self.delete_current_profile()

    def edit_current_profile(self) -> None:
        old_name = self.profile_combo.currentText().strip()
        if not old_name:
            return
        icon_name = str(self.profile_data.get("icon", "") or "").strip() if self.profile_data else ""
        dialog = ProfileEditDialog(old_name, icon_name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_name = dialog.profile_name()
        if not new_name:
            QMessageBox.warning(self, "Editar perfil", "El nombre del perfil no puede estar vacío.")
            return
        try:
            self.profile_data["knobs"] = self.knob_panel.get_config()
            self.profile_data["icon"] = dialog.icon_name
            self.profile_data["name"] = new_name
            self.profiles.save(old_name, self.profile_data)
            if new_name != old_name:
                self.profiles.rename(old_name, new_name)
        except Exception as exc:
            QMessageBox.warning(self, "Editar perfil", str(exc))
            return
        self.settings.data.setdefault("workspace", {})["active_profile"] = new_name
        self.settings.save()
        self._load_profiles()
        self.profile_combo.setCurrentText(new_name)
        self._show_profile_osd(new_name)

    def duplicate_current_profile(self) -> None:
        source_name = self.profile_combo.currentText().strip()
        if not source_name:
            return
        suggested = f"{source_name} copia"
        # Buscar un nombre sugerido que no choque con perfiles existentes.
        existing = {name.lower() for name in self.profiles.list_profiles()}
        if suggested.lower() in existing:
            n = 2
            while f"{source_name} copia {n}".lower() in existing:
                n += 1
            suggested = f"{source_name} copia {n}"
        new_name, accepted = QInputDialog.getText(
            self, "Duplicar perfil", "Nombre de la copia:", text=suggested
        )
        new_name = str(new_name or "").strip()
        if not accepted or not new_name:
            return
        if new_name.lower() in existing:
            QMessageBox.warning(self, "Duplicar perfil", f"Ya existe un perfil llamado «{new_name}».")
            return
        try:
            self.profile_data["knobs"] = self.knob_panel.get_config()
            self.profiles.save(source_name, self.profile_data)
            copied = deepcopy(self.profile_data)
            copied["name"] = new_name
            self.profiles.save(new_name, copied)
        except Exception as exc:
            QMessageBox.warning(self, "Duplicar perfil", str(exc))
            return
        self.settings.data.setdefault("workspace", {})["active_profile"] = new_name
        self.settings.save()
        self._load_profiles()
        self.profile_combo.setCurrentText(new_name)
        self._show_profile_osd(new_name)

    def delete_current_profile(self) -> None:
        name = self.profile_combo.currentText().strip()
        if not name:
            return
        names = self.profiles.list_profiles()
        if len(names) <= 1:
            QMessageBox.information(
                self, "Eliminar perfil", "Debe existir al menos un perfil."
            )
            return
        answer = QMessageBox.question(
            self,
            "Eliminar perfil",
            f"¿Eliminar el perfil «{name}»?\n\nEsta acción eliminará sus BANK, PADs, perillas e icono asignado.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.profiles.delete(name)
        except Exception as exc:
            QMessageBox.warning(self, "Eliminar perfil", str(exc))
            return
        remaining = self.profiles.list_profiles()
        next_name = remaining[0]
        self.settings.data.setdefault("workspace", {})["active_profile"] = next_name
        self.settings.save()
        self._load_profiles()
        self.profile_combo.setCurrentText(next_name)

    def previous_profile(self) -> None:
        count = self.profile_combo.count()
        if count <= 1:
            return
        self.profile_combo.setCurrentIndex((self.profile_combo.currentIndex() - 1) % count)

    def next_profile(self) -> None:
        count = self.profile_combo.count()
        if count <= 1:
            return
        self.profile_combo.setCurrentIndex((self.profile_combo.currentIndex() + 1) % count)

    def show_toast(self, text: str) -> None:
        if not hasattr(self, "toast_label"):
            self.toast_label = QLabel(self)
            self.toast_label.setStyleSheet("background:#202833; color:#F3F7FF; border:1px solid #3A4657; border-radius:10px; padding:10px 18px; font-weight:700;")
            self.toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.toast_label.setText(text)
        self.toast_label.adjustSize()
        x = max(8, (self.width() - self.toast_label.width()) // 2)
        y = max(8, self.height() - self.toast_label.height() - 58)
        self.toast_label.move(x, y)
        self.toast_label.show()
        self.toast_label.raise_()
        QTimer.singleShot(1600, self.toast_label.hide)

    def _show_pad_osd(self, display_number: int) -> None:
        workspace = self.settings.data.setdefault("workspace", {})
        if not bool(workspace.get("show_action_osd", True)):
            return
        data = self.pad_data(display_number)
        name = str(data.get("name", "") or "").strip()
        if not name or name == "Sin asignar":
            name = f"PAD {display_number:02d}"
        bank = "A" if int(display_number) <= 8 else "B"
        icon_name = str(data.get("icon", "") or "").strip()
        icon_path = PAD_ICON_DIR / icon_name if icon_name else None
        self.osd.show_pad(
            name=name,
            bank=bank,
            icon_path=icon_path,
            duration_ms=int(workspace.get("osd_duration_ms", 1400)),
            show_icon=bool(workspace.get("osd_show_icon", True)),
            show_bank=bool(workspace.get("osd_show_bank", True)),
        )

    def _show_knob_osd(self, knob: int, midi_value: int, cfg: dict) -> None:
        workspace = self.settings.data.setdefault("workspace", {})
        if not bool(workspace.get("show_knob_osd", True)):
            return
        typ = str((cfg or {}).get("type", "none"))
        if typ == "none":
            return
        percent = round(max(0, min(127, int(midi_value))) * 100 / 127)
        custom_name = str((cfg or {}).get("name", "") or "").strip()
        source = str((cfg or {}).get("source", "") or "").strip()
        if custom_name:
            label = f"K{knob} · {custom_name}"
        elif source:
            label = f"K{knob} · {source}"
        else:
            label = f"K{knob}"
        if typ == "obs_volume":
            db = self.continuous_engine.midi_to_db(int(midi_value), cfg or {})
            value_text = "Silencio · 0%" if int(midi_value) <= 0 else f"{db:.1f} dB · {percent}%"
        else:
            value_text = f"{percent}%"
        self.osd.show_knob(
            label=label,
            percent=percent,
            value_text=value_text,
            duration_ms=int(workspace.get("knob_osd_duration_ms", 950)),