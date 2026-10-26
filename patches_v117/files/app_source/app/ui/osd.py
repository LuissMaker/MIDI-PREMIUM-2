from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QFontMetrics
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QSizePolicy, QVBoxLayout, QWidget


class ActionOsd(QWidget):
    """OSD determinista: primero mide y fija geometría, después se muestra."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        try:
            self.setWindowFlag(Qt.WindowType.WindowTransparentForInput, True)
        except Exception:
            pass

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.card = QFrame()
        self.card.setObjectName("OsdCard")
        self.card.setStyleSheet(
            """
            QFrame#OsdCard {
                background: rgba(28, 33, 42, 246);
                border: 1px solid rgba(92, 106, 125, 215);
                border-radius: 14px;
            }
            QLabel { background: transparent; border: none; color: #F5F8FC; }
            QProgressBar {
                background: #11161D;
                border: 1px solid #394352;
                border-radius: 4px;
                min-height: 8px;
                max-height: 8px;
                text-align: center;
                color: transparent;
            }
            QProgressBar::chunk {
                background: #4D9BFF;
                border-radius: 4px;
            }
            """
        )
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(14, 9, 14, 9)
        card_layout.setSpacing(3)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(7)
        header.addStretch(1)

        self.icon = QLabel()
        self.icon.setFixedSize(22, 22)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.title = QLabel()
        self.title.setStyleSheet("font-size: 10.5pt; font-weight: 800;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        header.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.title, 0, Qt.AlignmentFlag.AlignVCenter)
        header.addStretch(1)

        self.subtitle = QLabel()
        self.subtitle.setStyleSheet("color:#AFC4DF; font-size:8pt; font-weight:600;")
        self.subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)

        self.value = QLabel()
        self.value.setStyleSheet("color:#CFE2FA; font-size:9pt; font-weight:700;")
        self.value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card_layout.addLayout(header)
        card_layout.addWidget(self.subtitle)
        card_layout.addWidget(self.progress)
        card_layout.addWidget(self.value)
        root.addWidget(self.card)
        self.hide()

    def _screen_geometry(self):
        try:
            from PySide6.QtGui import QCursor
            screen = QGuiApplication.screenAt(QCursor.pos())
        except Exception:
            screen = None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen else None

    @staticmethod
    def _font_width(widget: QLabel, text: str | None = None) -> int:
        """Mide aunque el widget o su padre estén ocultos."""
        widget.ensurePolished()
        value = widget.text() if text is None else str(text)
        metrics = QFontMetrics(widget.font())
        return max(0, metrics.horizontalAdvance(value))

    def _layout_width(self, minimum: int, maximum: int) -> int:
        margins = self.card.layout().contentsMargins()
        outer = margins.left() + margins.right()
        icon_w = self.icon.width() if not self.icon.isHidden() else 0
        title_w = self._font_width(self.title)
        gap = 7 if icon_w and title_w else 0
        header_w = icon_w + gap + title_w
        subtitle_w = self._font_width(self.subtitle) if not self.subtitle.isHidden() else 0
        value_w = self._font_width(self.value) if not self.value.isHidden() else 0
        progress_w = 210 if not self.progress.isHidden() else 0
        safety = 12

        target = max(minimum, header_w + outer + safety, subtitle_w + outer + safety, value_w + outer + safety, progress_w + outer)
        geo = self._screen_geometry()
        if geo is not None:
            maximum = min(maximum, max(minimum, geo.width() - 48))
        return max(minimum, min(maximum, target))

    def _apply_geometry(self, minimum: int = 96, maximum: int = 560) -> None:
        """Calcula un tamaño final sin depender de una presentación previa."""
        target_w = self._layout_width(minimum, maximum)

        # Si el título realmente supera el ancho máximo, elide de forma limpia.
        margins = self.card.layout().contentsMargins()
        icon_w = self.icon.width() if not self.icon.isHidden() else 0
        title_available = max(40, target_w - margins.left() - margins.right() - icon_w - 26)
        metrics = QFontMetrics(self.title.font())
        if metrics.horizontalAdvance(self.title.text()) > title_available:
            self.title.setText(metrics.elidedText(self.title.text(), Qt.TextElideMode.ElideRight, title_available))

        self.setMinimumSize(0, 0)
        self.setMaximumSize(16777215, 16777215)
        self.setFixedWidth(target_w)
        self.card.setFixedWidth(target_w)
        self.card.layout().activate()

        # sizeHint funciona con el padre oculto; solo ignora widgets explícitamente ocultos.
        height = max(42, self.card.sizeHint().height())
        self.card.setFixedHeight(height)
        self.setFixedHeight(height)

    def _position(self) -> None:
        geo = self._screen_geometry()
        if geo is None:
            return
        safe_x = 20
        safe_bottom = 30
        x = geo.x() + (geo.width() - self.width()) // 2
        y = geo.bottom() - self.height() - safe_bottom + 1
        x = max(geo.left() + safe_x, min(x, geo.right() - self.width() - safe_x + 1))
        y = max(geo.top() + 20, min(y, geo.bottom() - self.height() - safe_bottom + 1))
        self.move(x, y)

    def _present(self, duration_ms: int, minimum: int = 96, maximum: int = 560) -> None:
        self._hide_timer.stop()
        self._apply_geometry(minimum, maximum)
        self._position()
        self.show()
        self.raise_()
        self._hide_timer.start(max(300, int(duration_ms)))

    def _set_icon(self, *, icon_path=None, icon_text: str = "", show_icon: bool = True) -> None:
        self.icon.clear()
        self.icon.setStyleSheet("background:transparent; color:#8FB9EA; font-size:11pt; font-weight:700;")
        pix = None
        if show_icon and icon_path:
            path = Path(icon_path)
            if path.exists():
                pix = QIcon(str(path)).pixmap(20, 20)
        if pix is not None and not pix.isNull():
            self.icon.setPixmap(pix)
            self.icon.setVisible(True)
        elif show_icon and icon_text:
            self.icon.setText(str(icon_text))
            self.icon.setVisible(True)
        elif show_icon:
            self.icon.setText("●")
            self.icon.setVisible(True)
        else:
            self.icon.setVisible(False)

    def show_pad(self, name: str, bank: str = "", icon_path=None, duration_ms: int = 1400, show_icon: bool = True, show_bank: bool = True) -> None:
        self.title.setText(str(name or "Acción"))
        subtitle = f"BANK {bank}" if show_bank and bank else ""
        self.subtitle.setText(subtitle)
        self.subtitle.setVisible(bool(subtitle))
        self.progress.setVisible(False)
        self.value.setVisible(False)
        self._set_icon(icon_path=icon_path, show_icon=show_icon)
        self._present(duration_ms, 96, 520)

    def show_message(self, title: str, subtitle: str = "", duration_ms: int = 1100, icon_text: str = "", icon_path=None) -> None:
        self.title.setText(str(title or ""))
        self.subtitle.setText(str(subtitle or ""))
        self.subtitle.setVisible(bool(subtitle))
        self.progress.setVisible(False)
        self.value.setVisible(False)
        self._set_icon(icon_path=icon_path, icon_text=icon_text, show_icon=bool(icon_path or icon_text))
        self._present(duration_ms, 88, 520)

    def show_knob(self, label: str, percent: int, value_text: str = "", duration_ms: int = 950) -> None:
        self.title.setText(str(label or "Perilla"))
        self.subtitle.setVisible(False)
        self.progress.setVisible(True)
        self.progress.setValue(max(0, min(100, int(percent))))
        self.value.setText(str(value_text or f"{percent}%"))
        self.value.setVisible(True)
        self._set_icon(icon_text="◉", show_icon=True)
        self._present(duration_ms, 210, 340)