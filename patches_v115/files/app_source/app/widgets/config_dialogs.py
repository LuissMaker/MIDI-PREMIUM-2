from __future__ import annotations

from pathlib import Path
import shutil

from PySide6.QtCore import Qt, Signal, QSize, QUrl, QTimer
from PySide6.QtGui import QIcon, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QTabWidget, QVBoxLayout, QWidget, QButtonGroup, QScrollArea,
)

from app.widgets.action_editor import ActionEditor
from app.widgets.obs_panel import ObsPanel

DEV_ROOT = Path(__file__).resolve().parents[2]
PAD_ICON_DIR = DEV_ROOT / "assets" / "pad_icons"
PROFILE_ICON_DIR = DEV_ROOT / "assets" / "profile_icons"


class IconPickerDialog(QDialog):
    def __init__(self, current: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Elegir icono del PAD")
        self.resize(620, 450)
        self.selected_icon = current
        layout = QVBoxLayout(self)
        note = QLabel("Biblioteca de iconos para personalizar los PAD. Puedes buscar, importar SVG o abrir la colección completa Icona Moon Bold UI.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        search_row = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar icono…")
        self.search.textChanged.connect(self._filter_icons)
        import_button = QPushButton("Importar SVG…"); import_button.clicked.connect(self._import_svg)
        web_button = QPushButton("Colección completa"); web_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://www.svgrepo.com/collection/icona-moon-bold-ui-icons/")))
        search_row.addWidget(self.search, 1); search_row.addWidget(import_button); search_row.addWidget(web_button)
        layout.addLayout(search_row)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setIconSize(QSize(42, 42))
        self.list.setGridSize(QSize(125, 92))
        self.list.setSpacing(6)
        none = QListWidgetItem("Sin icono")
        none.setData(Qt.ItemDataRole.UserRole, "")
        self.list.addItem(none)
        for path in sorted(PAD_ICON_DIR.glob("*.svg"), key=lambda p: p.name.lower()):
            label = path.stem.replace("-svgrepo-com", "").replace("-", " ").title()
            item = QListWidgetItem(QIcon(str(path)), label)
            item.setData(Qt.ItemDataRole.UserRole, path.name)
            self.list.addItem(item)
            if path.name == current:
                self.list.setCurrentItem(item)
        if not self.list.currentItem():
            self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(lambda *_: self.accept())
        layout.addWidget(self.list, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _filter_icons(self, text: str) -> None:
        query = text.strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(query) and query not in item.text().lower())

    def _import_svg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar icono SVG", "", "Iconos SVG (*.svg)")
        if not path:
            return
        src = Path(path)
        dest = PAD_ICON_DIR / src.name
        if dest.exists():
            stem, suffix = src.stem, src.suffix
            n = 2
            while dest.exists():
                dest = PAD_ICON_DIR / f"{stem}-{n}{suffix}"; n += 1
        shutil.copy2(src, dest)
        item = QListWidgetItem(QIcon(str(dest)), dest.stem.replace("-svgrepo-com", "").replace("-", " ").title())
        item.setData(Qt.ItemDataRole.UserRole, dest.name)
        self.list.addItem(item); self.list.setCurrentItem(item)

    def accept(self) -> None:
        item = self.list.currentItem()
        self.selected_icon = str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
        super().accept()


class PsdElementPickerDialog(QDialog):
    _recent_paths: list[tuple[str, ...]] = []
    _favorite_paths: set[tuple[str, ...]] = set()

    def __init__(self, items: list[dict], title: str = "Insertar desde PSD", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(560)
        self.resize(620, max(360, min(610, 260 + min(len(items), 10) * 31)))
        self.selected_paths: list[list[str]] = []
        self.selected_path: list[str] = []
        self._items = list(items)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        note = QLabel("Selecciona las capas o grupos que quieres insertar en el documento activo.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar capas o grupos…")
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)

        filter_row = QHBoxLayout(); filter_row.setSpacing(5)
        self.filter_group = QButtonGroup(self); self.filter_group.setExclusive(True)
        self.filter_buttons = {}
        for key, label in (("all","Todos"),("layer","Capas"),("group","Grupos"),("visible","Visibles"),("recent","Recientes")):
            btn = QPushButton(label); btn.setCheckable(True)
            self.filter_group.addButton(btn); self.filter_buttons[key] = btn; filter_row.addWidget(btn)
            btn.clicked.connect(self._filter)
        self.filter_buttons["all"].setChecked(True)
        filter_row.addStretch(1)
        self.favorite_only = QPushButton("★ Favoritos"); self.favorite_only.setCheckable(True)
        self.favorite_only.clicked.connect(self._filter); filter_row.addWidget(self.favorite_only)
        layout.addLayout(filter_row)

        tools = QHBoxLayout(); tools.setSpacing(5)
        self.select_all = QPushButton("Seleccionar visibles")
        self.clear_all = QPushButton("Quitar selección")
        self.favorite_current = QPushButton("☆ Marcar favorito")
        self.select_all.clicked.connect(self._check_visible)
        self.clear_all.clicked.connect(self._uncheck_all)
        self.favorite_current.clicked.connect(self._toggle_favorite_current)
        tools.addWidget(self.select_all); tools.addWidget(self.clear_all); tools.addStretch(1); tools.addWidget(self.favorite_current)
        layout.addLayout(tools)

        self.list = QListWidget()
        self.list.setSpacing(1)
        layout.addWidget(self.list, 1)
        for data in self._items:
            path = tuple(data.get("path", []) or [])
            kind = str(data.get("kind", "layer"))
            visible = bool(data.get("visible", True))
            label = str(data.get("label", ""))
            symbol = "▣" if kind == "group" else "▤"
            star = "★ " if path in self._favorite_paths else ""
            row = QListWidgetItem(f"{star}{symbol}  {label}")
            row.setData(Qt.ItemDataRole.UserRole, list(path))
            row.setData(Qt.ItemDataRole.UserRole + 1, kind)
            row.setData(Qt.ItemDataRole.UserRole + 2, visible)
            row.setData(Qt.ItemDataRole.UserRole + 3, label)
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Unchecked)
            if not visible:
                row.setToolTip("Oculto en el PSD")
            self.list.addItem(row)

        footer = QHBoxLayout()
        self.count_label = QLabel("0 seleccionados")
        self.count_label.setObjectName("Muted")
        footer.addWidget(self.count_label)
        footer.addStretch(1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.insert_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.insert_button.setText("Insertar")
        self.insert_button.setEnabled(False)
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        footer.addWidget(self.buttons)
        layout.addLayout(footer)

        self.search.textChanged.connect(self._filter)
        self.list.itemChanged.connect(lambda *_: self._update_count())
        self.list.currentItemChanged.connect(lambda *_: self._update_favorite_button())
        self.list.itemDoubleClicked.connect(self._insert_single)
        self._filter()
        QTimer.singleShot(0, self.search.setFocus)

    def _active_filter(self) -> str:
        for key, btn in self.filter_buttons.items():
            if btn.isChecked():
                return key
        return "all"

    def _filter(self, *_args) -> None:
        q = self.search.text().strip().lower()
        mode = self._active_filter()
        recent = set(self._recent_paths)
        for i in range(self.list.count()):
            item = self.list.item(i)
            path = tuple(item.data(Qt.ItemDataRole.UserRole) or [])
            kind = str(item.data(Qt.ItemDataRole.UserRole + 1) or "layer")
            visible = bool(item.data(Qt.ItemDataRole.UserRole + 2))
            label = str(item.data(Qt.ItemDataRole.UserRole + 3) or "")
            ok = (not q or q in label.lower())
            if mode == "layer": ok = ok and kind == "layer"
            elif mode == "group": ok = ok and kind == "group"
            elif mode == "visible": ok = ok and visible
            elif mode == "recent": ok = ok and path in recent
            if self.favorite_only.isChecked(): ok = ok and path in self._favorite_paths
            item.setHidden(not ok)
        self._update_count()

    def _check_visible(self) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.CheckState.Checked)

    def _uncheck_all(self) -> None:
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _update_count(self) -> None:
        count = sum(self.list.item(i).checkState() == Qt.CheckState.Checked for i in range(self.list.count()))
        self.count_label.setText(f"{count} seleccionado" if count == 1 else f"{count} seleccionados")
        self.insert_button.setEnabled(count > 0)
        self.insert_button.setText("Insertar" if count == 0 else ("Insertar 1 elemento" if count == 1 else f"Insertar {count} elementos"))

    def _update_favorite_button(self) -> None:
        item = self.list.currentItem()
        path = tuple(item.data(Qt.ItemDataRole.UserRole) or []) if item else ()
        self.favorite_current.setEnabled(bool(path))
        self.favorite_current.setText("★ Quitar favorito" if path in self._favorite_paths else "☆ Marcar favorito")

    def _toggle_favorite_current(self) -> None:
        item = self.list.currentItem()
        if not item: return
        path = tuple(item.data(Qt.ItemDataRole.UserRole) or [])
        if not path: return
        if path in self._favorite_paths: self._favorite_paths.remove(path)
        else: self._favorite_paths.add(path)
        label = str(item.data(Qt.ItemDataRole.UserRole + 3) or "")
        kind = str(item.data(Qt.ItemDataRole.UserRole + 1) or "layer")
        symbol = "▣" if kind == "group" else "▤"
        item.setText(f"{'★ ' if path in self._favorite_paths else ''}{symbol}  {label}")
        self._update_favorite_button(); self._filter()

    def _insert_single(self, item: QListWidgetItem) -> None:
        self._uncheck_all()
        item.setCheckState(Qt.CheckState.Checked)
        self.accept()

    def accept(self) -> None:
        selected = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                path = list(item.data(Qt.ItemDataRole.UserRole) or [])
                if path:
                    selected.append(path)
        if not selected:
            return
        self.selected_paths = selected
        self.selected_path = list(selected[0])
        for path in reversed(selected):
            key = tuple(path)
            if key in self._recent_paths:
                self._recent_paths.remove(key)
            self._recent_paths.insert(0, key)
        del self._recent_paths[12:]
        super().accept()


class ProfileIconPickerDialog(QDialog):
    def __init__(self, current: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Elegir icono del perfil")
        self.resize(580, 390)
        self.selected_icon = current
        PROFILE_ICON_DIR.mkdir(parents=True, exist_ok=True)
        layout = QVBoxLayout(self)
        note = QLabel("Selecciona un icono para identificar este perfil. También puedes importar tu propio SVG.")
        note.setObjectName("Muted")
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar icono…")
        self.search.textChanged.connect(self._filter_icons)
        import_button = QPushButton("Importar SVG…"); import_button.clicked.connect(self._import_svg)
        row.addWidget(self.search, 1); row.addWidget(import_button)
        layout.addLayout(row)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.ViewMode.IconMode)
        self.list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.list.setIconSize(QSize(44, 44))
        self.list.setGridSize(QSize(130, 92))
        self.list.setSpacing(6)
        none = QListWidgetItem("Sin icono")
        none.setData(Qt.ItemDataRole.UserRole, "")
        self.list.addItem(none)
        for path in sorted(PROFILE_ICON_DIR.glob("*.svg"), key=lambda x: x.name.lower()):
            label = path.stem.replace("-svgrepo-com", "").replace("-", " ").title()
            item = QListWidgetItem(QIcon(str(path)), label)
            item.setData(Qt.ItemDataRole.UserRole, path.name)
            self.list.addItem(item)
            if path.name == current:
                self.list.setCurrentItem(item)
        if not self.list.currentItem():
            self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(lambda *_: self.accept())
        layout.addWidget(self.list, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _filter_icons(self, text: str) -> None:
        query = text.strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(query) and query not in item.text().lower())

    def _import_svg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar icono SVG", "", "Iconos SVG (*.svg)")
        if not path:
            return
        src = Path(path)
        dest = PROFILE_ICON_DIR / src.name
        if dest.exists():
            stem, suffix = src.stem, src.suffix
            n = 2
            while dest.exists():
                dest = PROFILE_ICON_DIR / f"{stem}-{n}{suffix}"; n += 1
        shutil.copy2(src, dest)
        item = QListWidgetItem(QIcon(str(dest)), dest.stem.replace("-svgrepo-com", "").replace("-", " ").title())
        item.setData(Qt.ItemDataRole.UserRole, dest.name)
        self.list.addItem(item); self.list.setCurrentItem(item)

    def accept(self) -> None:
        item = self.list.currentItem()
        self.selected_icon = str(item.data(Qt.ItemDataRole.UserRole) or "") if item else ""
        super().accept()


class ProfileEditDialog(QDialog):
    def __init__(self, name: str, icon_name: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar perfil")
        self.setMinimumWidth(420)
        self.icon_name = str(icon_name or "")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(str(name or ""))
        form.addRow("Nombre", self.name_edit)
        layout.addLayout(form)

        icon_row = QHBoxLayout()
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(44, 44)
        self.icon_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label = QLabel()
        choose = QPushButton("Elegir icono…")
        choose.clicked.connect(self._choose_icon)
        remove = QPushButton("Quitar")
        remove.clicked.connect(self._remove_icon)
        icon_row.addWidget(self.icon_preview)
        icon_row.addWidget(self.icon_label, 1)
        icon_row.addWidget(choose)
        icon_row.addWidget(remove)
        layout.addLayout(icon_row)
        self._refresh_icon()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh_icon(self) -> None:
        if self.icon_name:
            path = PROFILE_ICON_DIR / self.icon_name
            if path.exists():
                self.icon_preview.setPixmap(QIcon(str(path)).pixmap(34, 34))
                self.icon_label.setText(path.stem.replace("-svgrepo-com", "").replace("-", " ").title())
                return
        self.icon_preview.clear()
        self.icon_label.setText("Sin icono")

    def _choose_icon(self) -> None:
        dlg = ProfileIconPickerDialog(self.icon_name, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.icon_name = dlg.selected_icon
            self._refresh_icon()

    def _remove_icon(self) -> None:
        self.icon_name = ""
        self._refresh_icon()

    def profile_name(self) -> str:
        return self.name_edit.text().strip()


class PadEditDialog(QDialog):
    obs_needed = Signal(bool)

    def __init__(self, display_number: int, bank: str, local_pad: int, data: dict,
                 obs_settings: dict, global_paths: dict | None = None,
                 dialog_size: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Editar PAD {display_number:02d}")
        size = dialog_size or {}
        self.resize(int(size.get("width", 680)), int(size.get("height", 720)))
        self.setMinimumSize(620, 590)
        self.icon_name = str(data.get("icon", "") or "")

        layout = QVBoxLayout(self)
        heading = QLabel(f"PAD {display_number:02d}")
        heading.setObjectName("SectionTitle")
        subtitle = QLabel(f"Bank {bank} · Posición física {local_pad}")
        subtitle.setObjectName("Muted")
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ejemplo: Pantalla completa")
        self.name_input.setText("" if data.get("name") == "Sin asignar" else str(data.get("name", "")))

        icon_row = QHBoxLayout()
        self.icon_preview = QPushButton()
        self.icon_preview.setFixedSize(54, 54)
        self.icon_preview.setIconSize(QSize(32, 32))
        self.icon_preview.clicked.connect(self.choose_icon)
        self.icon_text = QLabel()
        self.icon_text.setObjectName("Muted")
        choose_icon = QPushButton("Agregar / cambiar icono")
        choose_icon.clicked.connect(self.choose_icon)
        clear_icon = QPushButton("Quitar")
        clear_icon.clicked.connect(self.clear_icon)
        icon_row.addWidget(self.icon_preview)
        icon_row.addWidget(self.icon_text, 1)
        icon_row.addWidget(choose_icon)
        icon_row.addWidget(clear_icon)
        self._refresh_icon_preview()

        self.action_editor = ActionEditor(global_paths=global_paths or {})
        self.action_editor.set_action(data.get("action", {"type": "none"}))
        self.obs_panel = ObsPanel()
        self.obs_panel.set_settings(obs_settings)
        self.action_editor.action_type_changed.connect(self._action_type_changed)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Guardar cambios")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(heading)
        layout.addWidget(subtitle)
        layout.addWidget(QLabel("Nombre del pad"))
        layout.addWidget(self.name_input)
        layout.addWidget(QLabel("Icono del pad"))
        layout.addLayout(icon_row)
        layout.addWidget(QLabel("Tipo de acción"))
        layout.addWidget(self.action_editor, 1)
        layout.addWidget(self.obs_panel)
        layout.addWidget(buttons)
        self._action_type_changed(str(self.action_editor.action_combo.currentData()))

    @staticmethod
    def is_obs_action(action_type: str) -> bool:
        return str(action_type).startswith("obs_")

    def _action_type_changed(self, action_type: str) -> None:
        needed = self.is_obs_action(action_type)
        self.obs_panel.setVisible(needed)
        self.obs_needed.emit(needed)

    def choose_icon(self) -> None:
        picker = IconPickerDialog(self.icon_name, self)
        if picker.exec() == QDialog.DialogCode.Accepted:
            self.icon_name = picker.selected_icon
            self._refresh_icon_preview()

    def clear_icon(self) -> None:
        self.icon_name = ""
        self._refresh_icon_preview()

    def _refresh_icon_preview(self) -> None:
        path = PAD_ICON_DIR / self.icon_name if self.icon_name else None
        if path and path.exists():
            self.icon_preview.setIcon(QIcon(str(path)))
            self.icon_text.setText(path.stem.replace("-svgrepo-com", "").replace("-", " ").title())
        else:
            self.icon_preview.setIcon(QIcon())
            self.icon_text.setText("Sin icono")

    def result_data(self) -> dict:
        return {
            "name": self.name_input.text().strip() or "Sin asignar",
            "icon": self.icon_name,
            "action": self.action_editor.get_action(),
        }

    def saved_size(self) -> dict:
        return {"width": self.width(), "height": self.height()}


class KnobEditDialog(QDialog):
    def __init__(self, knob: int, config: dict, sources: list[str], dialog_size: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.knob = int(knob)
        self.setWindowTitle(f"Editar perilla K{knob}")
        size = dialog_size or {}
        self.resize(int(size.get("width", 500)), int(size.get("height", 390)))
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)

        title = QLabel(f"Perilla K{knob}")
        title.setObjectName("SectionTitle")
        note = QLabel("Configura la acción continua de esta perilla. En modo compacto, clic derecho vuelve a abrir este editor.")
        note.setWordWrap(True)
        note.setObjectName("Muted")
        layout.addWidget(title)
        layout.addWidget(note)

        form = QFormLayout()
        self.name = QLineEdit()
        self.name.setPlaceholderText(f"Ejemplo: Micrófono / Volumen K{knob}")
        self.action = QComboBox()
        self.action.addItem("Sin acción", "none")
        self.action.addItem("OBS: Volumen", "obs_volume")
        self.source = QComboBox(); self.source.addItems(sources)
        self.curve = QComboBox(); self.curve.addItem("OBS recomendada", "obs"); self.curve.addItem("Lineal en dB", "linear_db")
        self.invert = QCheckBox("Invertir")
        self.minimum = QDoubleSpinBox(); self.minimum.setRange(-100.0, 0.0); self.minimum.setDecimals(1); self.minimum.setSuffix(" dB")
        self.maximum = QDoubleSpinBox(); self.maximum.setRange(-60.0, 12.0); self.maximum.setDecimals(1); self.maximum.setSuffix(" dB")
        form.addRow("Nombre", self.name); form.addRow("Acción", self.action); form.addRow("Fuente OBS", self.source); form.addRow("Curva", self.curve); form.addRow("", self.invert); form.addRow("Mínimo", self.minimum); form.addRow("Máximo", self.maximum)
        layout.addLayout(form)

        self.name.setText(str(config.get("name", "")))
        idx = self.action.findData(str(config.get("type", "none"))); self.action.setCurrentIndex(max(0, idx))
        source = str(config.get("source", ""))
        if source and self.source.findText(source) < 0: self.source.addItem(source)
        self.source.setCurrentText(source)
        idx = self.curve.findData(str(config.get("curve", "obs"))); self.curve.setCurrentIndex(max(0, idx))
        self.invert.setChecked(bool(config.get("invert", False)))
        self.minimum.setValue(float(config.get("minimum_db", -60.0))); self.maximum.setValue(float(config.get("maximum_db", 0.0)))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Guardar"); buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def result_config(self) -> dict:
        return {"name": self.name.text().strip(), "type": str(self.action.currentData()), "source": self.source.currentText().strip(), "curve": str(self.curve.currentData()), "invert": self.invert.isChecked(), "minimum_db": self.minimum.value(), "maximum_db": self.maximum.value()}

    def saved_size(self) -> dict:
        return {"width": self.width(), "height": self.height()}


class AppSettingsDialog(QDialog):
    midi_learn_requested = Signal(str)
    joystick_detect_requested = Signal(str)
    check_updates_requested = Signal()

    def __init__(self, settings: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuración de MIDI Premium 2")
        self.resize(720, 500)
        self.setMinimumSize(680, 430)
        self.setMaximumHeight(620)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        tabs = QTabWidget()

        routes = QWidget(); form = QFormLayout(routes)
        paths = settings.get("paths", {})
        self.photoshop_exe = QLineEdit(str(paths.get("photoshop_exe", "")))
        psrow = QHBoxLayout(); psrow.addWidget(self.photoshop_exe, 1); psb = QPushButton("Examinar…"); psb.clicked.connect(self._browse_photoshop); psrow.addWidget(psb)
        self.photoshop_scripts = QLineEdit(str(paths.get("photoshop_scripts", "")))
        jsrow = QHBoxLayout(); jsrow.addWidget(self.photoshop_scripts, 1); jsb = QPushButton("Examinar…"); jsb.clicked.connect(self._browse_scripts); jsrow.addWidget(jsb)
        form.addRow("Photoshop.exe", psrow); form.addRow("Carpeta de scripts JSX", jsrow)
        hint = QLabel("Estas rutas son globales. Los PAD de Photoshop las reutilizan para no tener que elegir Photoshop.exe una y otra vez.")
        hint.setWordWrap(True); hint.setObjectName("Muted"); form.addRow(hint)
        routes_scroll = QScrollArea()
        routes_scroll.setWidgetResizable(True)
        routes_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        routes_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        routes_scroll.setWidget(routes)
        tabs.addTab(routes_scroll, "Rutas")

        behavior = QWidget(); bform = QFormLayout(behavior)
        workspace = settings.get("workspace", {})
        self.minimize_to_tray = QCheckBox("Al minimizar, ocultar en la bandeja del sistema")
        self.minimize_to_tray.setChecked(bool(workspace.get("minimize_to_tray", True)))
        bform.addRow(self.minimize_to_tray)
        self.start_with_windows = QCheckBox("Iniciar MIDI Premium 2 con Windows")
        self.start_with_windows.setChecked(bool(workspace.get("start_with_windows", False)))
        self.start_with_windows.setToolTip("Inicia la aplicación automáticamente al entrar a Windows. Usa el usuario actual, sin permisos de administrador.")
        bform.addRow(self.start_with_windows)
        self.start_hidden_to_tray = QCheckBox("Iniciar oculto en la bandeja")
        self.start_hidden_to_tray.setChecked(bool(workspace.get("start_hidden_to_tray", True)))
        self.start_hidden_to_tray.setToolTip("Al abrir MIDI Premium 2 no muestra la ventana principal; queda ejecutándose desde la bandeja del sistema.")
        bform.addRow(self.start_hidden_to_tray)

        feedback_title = QLabel("Feedback en pantalla")
        feedback_title.setStyleSheet("font-weight:700; margin-top:8px;")
        bform.addRow(feedback_title)
        self.show_action_osd = QCheckBox("Mostrar acciones de PAD en pantalla")
        self.show_action_osd.setChecked(bool(workspace.get("show_action_osd", True)))
        bform.addRow(self.show_action_osd)
        self.show_knob_osd = QCheckBox("Mostrar perillas en pantalla")
        self.show_knob_osd.setChecked(bool(workspace.get("show_knob_osd", True)))
        bform.addRow(self.show_knob_osd)
        self.osd_show_icon = QCheckBox("Mostrar icono del PAD")
        self.osd_show_icon.setChecked(bool(workspace.get("osd_show_icon", True)))
        bform.addRow(self.osd_show_icon)
        self.osd_show_bank = QCheckBox("Mostrar BANK en acciones de PAD")
        self.osd_show_bank.setChecked(bool(workspace.get("osd_show_bank", True)))
        bform.addRow(self.osd_show_bank)
        self.osd_duration = QDoubleSpinBox()
        self.osd_duration.setRange(0.5, 4.0)
        self.osd_duration.setSingleStep(0.1)
        self.osd_duration.setDecimals(1)
        self.osd_duration.setSuffix(" s")
        self.osd_duration.setValue(float(workspace.get("osd_duration_ms", 1400)) / 1000.0)
        bform.addRow("Duración PAD", self.osd_duration)
        self.knob_osd_duration = QDoubleSpinBox()
        self.knob_osd_duration.setRange(0.4, 3.0)
        self.knob_osd_duration.setSingleStep(0.1)
        self.knob_osd_duration.setDecimals(1)
        self.knob_osd_duration.setSuffix(" s")
        self.knob_osd_duration.setValue(float(workspace.get("knob_osd_duration_ms", 950)) / 1000.0)
        bform.addRow("Duración perilla", self.knob_osd_duration)

        persistence_hint = QLabel("Los presets, PAD, perillas y ajustes se guardan en una carpeta de datos compartida entre versiones de MIDI Premium 2.")
        persistence_hint.setWordWrap(True); persistence_hint.setObjectName("Muted"); bform.addRow(persistence_hint)
        behavior_scroll = QScrollArea()
        behavior_scroll.setWidgetResizable(True)
        behavior_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        behavior_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        behavior_scroll.setWidget(behavior)
        tabs.addTab(behavior_scroll, "Aplicación")

        updates_tab = QWidget(); uform = QFormLayout(updates_tab)
        updates_cfg = settings.get("updates", {})
        self.check_updates_on_start = QCheckBox("Buscar actualizaciones al iniciar")
        self.check_updates_on_start.setChecked(bool(updates_cfg.get("check_on_start", True)))
        uform.addRow(self.check_updates_on_start)
        self.current_version_label = QLabel("La aplicación consulta GitHub Releases y descarga el instalador oficial cuando hay una versión nueva.")
        self.current_version_label.setWordWrap(True); self.current_version_label.setObjectName("Muted")
        uform.addRow(self.current_version_label)
        self.check_updates_button = QPushButton("Buscar actualizaciones ahora…")
        self.check_updates_button.clicked.connect(lambda _=False: self.check_updates_requested.emit())
        uform.addRow(self.check_updates_button)
        updates_tab_scroll = QScrollArea()
        updates_tab_scroll.setWidgetResizable(True)
        updates_tab_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        updates_tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        updates_tab_scroll.setWidget(updates_tab)
        tabs.addTab(updates_tab_scroll, "Actualizaciones")

        # Controles MIDI globales: permiten usar botones físicos que no sean PAD.
        midi_tab = QWidget(); mform = QFormLayout(midi_tab)
        midi_cfg = settings.get("midi", {})
        bindings = dict(midi_cfg.get("bindings", {}) or {})
        self.binding_edits = {}
        labels = [
            ("profile_prev", "Preset anterior"),
            ("profile_next", "Preset siguiente"),
            ("bank_a", "Ir a BANK A"),
            ("bank_b", "Ir a BANK B"),
            ("bank_toggle", "Alternar BANK A/B"),
            ("show_hide", "Mostrar / ocultar aplicación"),
        ]
        for key, label in labels:
            row = QHBoxLayout()
            edit = QLineEdit(str(bindings.get(key, "")))
            edit.setReadOnly(True)
            edit.setPlaceholderText("Sin asignar")
            learn = QPushButton("Aprender…")
            clear = QPushButton("Quitar")
            learn.clicked.connect(lambda _=False, k=key: self._request_midi_learn(k))
            clear.clicked.connect(lambda _=False, k=key: self.binding_edits[k].clear())
            row.addWidget(edit, 1); row.addWidget(learn); row.addWidget(clear)
            self.binding_edits[key] = edit
            mform.addRow(label, row)
        midi_hint = QLabel("Pulsa ‘Aprender…’ y después presiona un botón físico del controlador. Esto sirve para probar PAD CONTROLS, PROG SELECT u otros botones sin gastar un PAD.")
        midi_hint.setWordWrap(True); midi_hint.setObjectName("Muted"); mform.addRow(midi_hint)

        joystick_title = QLabel("Palanca / Joystick")
        joystick_title.setStyleSheet("font-weight:700; margin-top:12px;")
        mform.addRow(joystick_title)
        joystick_help = QLabel("Detecta los ejes de la palanca y asigna una acción a cada dirección. Una inclinación solo dispara una acción hasta que la palanca vuelve al centro.")
        joystick_help.setWordWrap(True); joystick_help.setObjectName("Muted"); mform.addRow(joystick_help)
        joystick = dict(midi_cfg.get("joystick", {}) or {})
        self.joystick_axis_edits = {}
        for axis, label in (("horizontal", "Eje horizontal"), ("vertical", "Eje vertical")):
            row = QHBoxLayout()
            edit = QLineEdit(str(joystick.get(f"{axis}_signature", "")))
            edit.setReadOnly(True); edit.setPlaceholderText("Sin detectar")
            detect = QPushButton("Detectar…")
            detect.clicked.connect(lambda _=False, a=axis: self._request_joystick_detect(a))
            clear = QPushButton("Quitar")
            clear.clicked.connect(lambda _=False, a=axis: self.joystick_axis_edits[a].clear())
            row.addWidget(edit, 1); row.addWidget(detect); row.addWidget(clear)
            self.joystick_axis_edits[axis] = edit
            mform.addRow(label, row)

        action_options = [
            ("none", "Sin acción"),
            ("profile_prev", "Perfil anterior"),
            ("profile_next", "Perfil siguiente"),
            ("bank_a", "BANK A"),
            ("bank_b", "BANK B"),
            ("bank_toggle", "Alternar BANK A/B"),
            ("show_hide", "Mostrar / ocultar aplicación"),
        ]
        self.joystick_action_combos = {}
        defaults = {"left":"profile_prev", "right":"profile_next", "up":"bank_a", "down":"bank_b"}
        for direction, label in (("left","Izquierda"), ("right","Derecha"), ("up","Arriba"), ("down","Abajo")):
            combo = QComboBox()
            for value, text in action_options: combo.addItem(text, value)
            current = str(joystick.get(f"{direction}_action", defaults[direction]))
            idx = combo.findData(current); combo.setCurrentIndex(max(0, idx))
            self.joystick_action_combos[direction] = combo
            mform.addRow(label, combo)

        self.joystick_threshold = QDoubleSpinBox()
        self.joystick_threshold.setRange(0.35, 0.95); self.joystick_threshold.setSingleStep(0.05); self.joystick_threshold.setDecimals(2)
        self.joystick_threshold.setValue(float(joystick.get("threshold", 0.65)))
        self.joystick_threshold.setToolTip("Cuánto debes inclinar la palanca antes de disparar una acción.")
        mform.addRow("Umbral", self.joystick_threshold)
        self.joystick_deadzone = QDoubleSpinBox()
        self.joystick_deadzone.setRange(0.05, 0.35); self.joystick_deadzone.setSingleStep(0.01); self.joystick_deadzone.setDecimals(2)
        self.joystick_deadzone.setValue(float(joystick.get("center_deadzone", 0.18)))
        self.joystick_deadzone.setToolTip("Zona alrededor del centro que vuelve a armar la palanca para el siguiente movimiento.")
        mform.addRow("Zona central", self.joystick_deadzone)
        self.joystick_cooldown = QDoubleSpinBox()
        self.joystick_cooldown.setRange(0.10, 1.50); self.joystick_cooldown.setSingleStep(0.05); self.joystick_cooldown.setDecimals(2); self.joystick_cooldown.setSuffix(" s")
        self.joystick_cooldown.setValue(float(joystick.get("cooldown_ms", 300)) / 1000.0)
        mform.addRow("Cooldown", self.joystick_cooldown)

        tester_title = QLabel("Comprobador MIDI")
        tester_title.setStyleSheet("font-weight:700; margin-top:12px;")
        mform.addRow(tester_title)
        tester_help = QLabel("Actívalo para inspeccionar botones del controlador. Mientras escucha, los mensajes se muestran aquí y no ejecutan acciones normales.")
        tester_help.setWordWrap(True); tester_help.setObjectName("Muted"); mform.addRow(tester_help)
        tester_row = QHBoxLayout()
        self.midi_test_toggle = QPushButton("Iniciar escucha")
        self.midi_test_toggle.setCheckable(True)
        self.midi_test_toggle.toggled.connect(self._toggle_midi_test)
        self.midi_test_clear = QPushButton("Limpiar")
        self.midi_test_clear.clicked.connect(self._clear_midi_test)
        tester_row.addWidget(self.midi_test_toggle); tester_row.addWidget(self.midi_test_clear); tester_row.addStretch(1)
        mform.addRow(tester_row)
        self.midi_test_last = QLabel("Sin mensajes detectados")
        self.midi_test_last.setWordWrap(True)
        self.midi_test_last.setStyleSheet("font-weight:700;")
        mform.addRow("Último mensaje", self.midi_test_last)
        self.midi_test_history = QListWidget()
        self.midi_test_history.setMaximumHeight(150)
        mform.addRow("Historial", self.midi_test_history)

        midi_tab_scroll = QScrollArea()
        midi_tab_scroll.setWidgetResizable(True)
        midi_tab_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        midi_tab_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        midi_tab_scroll.setWidget(midi_tab)
        tabs.addTab(midi_tab_scroll, "Controles MIDI")

        layout.addWidget(tabs)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Guardar")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def _browse_photoshop(self) -> None:
        p, _ = QFileDialog.getOpenFileName(self, "Seleccionar Photoshop.exe", "", "Aplicaciones (*.exe);;Todos los archivos (*.*)")
        if p: self.photoshop_exe.setText(p)

    def _browse_scripts(self) -> None:
        p = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de scripts JSX", self.photoshop_scripts.text().strip())
        if p: self.photoshop_scripts.setText(p)

    def _request_midi_learn(self, key: str) -> None:
        edit = self.binding_edits.get(key)
        if edit is not None:
            edit.setText("Esperando entrada MIDI…")
        self.midi_learn_requested.emit(key)

    def set_learned_binding(self, key: str, signature: str, description: str = "") -> None:
        edit = self.binding_edits.get(key)
        if edit is not None:
            edit.setText(signature)
            edit.setToolTip(description or signature)

    def _request_joystick_detect(self, axis: str) -> None:
        # El comprobador consume los mensajes mientras escucha; detenerlo para detectar el eje.
        if getattr(self, "midi_test_toggle", None) is not None and self.midi_test_toggle.isChecked():
            self.midi_test_toggle.setChecked(False)
        edit = self.joystick_axis_edits.get(axis)
        if edit is not None:
            edit.setText("Mueve ahora la palanca…")
        self.joystick_detect_requested.emit(axis)

    def set_joystick_axis(self, axis: str, signature: str, description: str = "") -> None:
        edit = self.joystick_axis_edits.get(axis)
        if edit is not None:
            edit.setText(signature)
            edit.setToolTip(description or signature)

    def _toggle_midi_test(self, enabled: bool) -> None:
        self.midi_test_toggle.setText("Detener escucha" if enabled else "Iniciar escucha")
        if enabled:
            self.midi_test_last.setText("Esperando mensaje MIDI…")

    def _clear_midi_test(self) -> None:
        self.midi_test_last.setText("Sin mensajes detectados")
        self.midi_test_history.clear()

    def is_midi_test_listening(self) -> bool:
        return bool(getattr(self, "midi_test_toggle", None) and self.midi_test_toggle.isChecked())

    def append_midi_test_event(self, event) -> None:
        if not self.is_midi_test_listening():
            return
        try:
            summary = event.summary()
        except Exception:
            summary = str(event)
        self.midi_test_last.setText(summary)
        self.midi_test_history.insertItem(0, summary)
        while self.midi_test_history.count() > 10:
            self.midi_test_history.takeItem(self.midi_test_history.count() - 1)

    def result_settings(self) -> dict:
        return {
            "paths": {"photoshop_exe": self.photoshop_exe.text().strip(), "photoshop_scripts": self.photoshop_scripts.text().strip()},
            "workspace": {
                "minimize_to_tray": self.minimize_to_tray.isChecked(),
                "start_with_windows": self.start_with_windows.isChecked(),
                "start_hidden_to_tray": self.start_hidden_to_tray.isChecked(),
                "show_action_osd": self.show_action_osd.isChecked(),
                "show_knob_osd": self.show_knob_osd.isChecked(),
                "osd_duration_ms": int(self.osd_duration.value() * 1000),
                "knob_osd_duration_ms": int(self.knob_osd_duration.value() * 1000),
                "osd_show_icon": self.osd_show_icon.isChecked(),
                "osd_show_bank": self.osd_show_bank.isChecked(),
            },
            "updates": {
                "check_on_start": self.check_updates_on_start.isChecked(),
            },
            "midi": {
                "bindings": {k: e.text().strip() if e.text().strip() != "Esperando entrada MIDI…" else "" for k, e in self.binding_edits.items()},
                "joystick": {
                    "horizontal_signature": self.joystick_axis_edits["horizontal"].text().strip() if "Mueve ahora" not in self.joystick_axis_edits["horizontal"].text() else "",
                    "vertical_signature": self.joystick_axis_edits["vertical"].text().strip() if "Mueve ahora" not in self.joystick_axis_edits["vertical"].text() else "",
                    "left_action": str(self.joystick_action_combos["left"].currentData()),
                    "right_action": str(self.joystick_action_combos["right"].currentData()),
                    "up_action": str(self.joystick_action_combos["up"].currentData()),
                    "down_action": str(self.joystick_action_combos["down"].currentData()),
                    "threshold": float(self.joystick_threshold.value()),
                    "center_deadzone": float(self.joystick_deadzone.value()),
                    "cooldown_ms": int(self.joystick_cooldown.value() * 1000),
                },
            },
        }