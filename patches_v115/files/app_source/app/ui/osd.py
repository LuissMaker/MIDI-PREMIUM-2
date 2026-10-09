from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QFontMetrics
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget


class ActionOsd(QWidget):
    """OSD ligero, sin foco, pensado para mostrarse encima de otras apps."""

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

        self.card = QFrame()
        self.card.setObjectName("OsdCard")
        self.card.setStyleSheet(
            """
            QFrame#OsdCard {
                background: rgba(28, 33, 42, 242);
                border: 1px solid rgba(92, 106, 125, 210);
                border-radius: 14px;
            }
            QLabel { background: transparent; border: none; color: #F5F8FC; }
            QProgressBar {
                background: #11161D;
                border: 1px solid #394352;
                border-radius: 4px;
                height: 9px;
                text-align: center;
                color: transparent;
            }
            QProgressBar::chunk {
                background: #4D9BFF;
                border-radius: 5px;
            }
            """
        )
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(13, 8, 13, 8)
        card_layout.setSpacing(3)

        header = QHBoxLayout()
        header.setSpacing(7)
        header.setContentsMargins(0, 0, 0, 0)
        self.icon = QLabel()
        self.icon.setFixedSize(22, 22)
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel()
        self.title.setStyleSheet("font-size: 10.5pt; font-weight: 800;")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addStretch(1)
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
        # Usar la pantalla donde está el cursor resulta más natural con varios monitores.
        try:
            from PySide6.QtGui import QCursor
            screen = QGuiApplication.screenAt(QCursor.pos())
        except Exception:
            screen = None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen else None

    def _text_width(self, widget: QLabel) -> int:
        if not widget.isVisible():
            return 0
        try:
            widget.ensurePolished()
        except Exception:
            pass
        metrics = QFontMetrics(widget.font())
        return max(widget.sizeHint().width(), metrics.horizontalAdvance(widget.text()) + 4)

    def _set_dynamic_width(self, minimum: int = 104, maximum: int = 560) -> None:
        """Mide el contenido real y reserva margen suficiente para DPI/escalado."""
        title_w = self._text_width(self.title)
        subtitle_w = self._text_width(self.subtitle)
        value_w = self._text_width(self.value)

        icon_w = self.icon.width() if self.icon.isVisible() else 0
        gap = 7 if icon_w and title_w else 0
        margins = self.card.layout().contentsMargins()
        horizontal_margins = margins.left() + margins.right()

        # Reserva adicional para estilos, redondeo de DPI y el borde de la cápsula.
        safety = 24
        header_w = icon_w + gap + title_w + horizontal_margins + safety
        content_w = max(header_w, subtitle_w + horizontal_margins + safety, value_w + horizontal_margins + safety, minimum)

        geo = self._screen_geometry()
        if geo is not None:
            maximum = min(maximum, max(minimum, geo.width() - 48))

        target = max(minimum, min(maximum, content_w))
        self.title.setMinimumWidth(min(title_w + 6, max(0, target - icon_w - gap - horizontal_margins - safety // 2)))
        self.setMinimumWidth(target)
        self.setMaximumWidth(target)
        self.resize(target, self.sizeHint().height())

    def _present(self, duration_ms: int) -> None:
        # Primera presentación: Qt todavía no siempre ha calculado las métricas
        # finales de icono/texto. Forzamos polish + layout antes de posicionar.
        self.ensurePolished()
        self.card.ensurePolished()
        if self.card.layout() is not None:
            self.card.layout().activate()
        if self.layout() is not None:
            self.layout().activate()
        self.card.adjustSize()
        self.adjustSize()
        QApplication.processEvents()
        if self.card.layout() is not None:
            self.card.layout().activate()
        self.card.adjustSize()
        self.adjustSize()
        geo = self._screen_geometry()
        if geo is not None:
            safe_x = 20
            safe_bottom = 28
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.bottom() - self.height() - safe_bottom + 1
            x = max(geo.left() + safe_x, min(x, geo.right() - self.width() - safe_x + 1))
            y = max(geo.top() + 20, min(y, geo.bottom() - self.height() - safe_bottom + 1))
            self.move(x, y)
        self.show()
        self.raise_()
        self._hide_timer.start(max(300, int(duration_ms)))

    def show_pad(
        self,
        name: str,
        bank: str = "",
        icon_path: str | Path | None = None,
        duration_ms: int = 1400,
        show_icon: bool = True,
        show_bank: bool = True,
    ) -> None:
        self.title.setText(str(name or "Acción"))
        subtitle = f"BANK {bank}" if show_bank and bank else ""
        self.subtitle.setText(subtitle)
        self.subtitle.setVisible(bool(subtitle))
        self.progress.setVisible(False)
        self.value.setVisible(False)

        pix = None
        if show_icon and icon_path:
            path = Path(icon_path)
            if path.exists():
                pix = QIcon(str(path)).pixmap(20, 20)
        if pix is not None and not pix.isNull():
            self.icon.setPixmap(pix)
            self.icon.setVisible(True)
        else:
            self.icon.clear()
            self.icon.setText("●")
            self.icon.setStyleSheet("color:#8FB9EA; font-size:12pt;")
            self.icon.setVisible(bool(show_icon))
        self._set_dynamic_width(minimum=96, maximum=520)
        self._present(duration_ms)

    def show_message(
        self,
        title: str,
        subtitle: str = "",
        duration_ms: int = 1100,
        icon_text: str = "",
        icon_path: str | Path | None = None,
    ) -> None:
        self.title.setText(str(title or ""))
        self.subtitle.setText(str(subtitle or ""))
        self.subtitle.setVisible(bool(subtitle))
        self.progress.setVisible(False)
        self.value.setVisible(False)
        self.icon.clear()
        pix = None
        if icon_path:
            path = Path(icon_path)
            if path.exists():
                pix = QIcon(str(path)).pixmap(20, 20)
        if pix is not None and not pix.isNull():
            self.icon.setPixmap(pix)
            self.icon.setStyleSheet("background:transparent;")
            self.icon.setVisible(True)
        elif icon_text:
            self.icon.setText(icon_text)
            self.icon.setStyleSheet("color:#8FB9EA; font-size:11pt;")
            self.icon.setVisible(True)
        else:
            self.icon.setVisible(False)
        self._set_dynamic_width(minimum=88, maximum=520)
        self._present(duration_ms)

    def show_knob(
        self,
        label: str,
        percent: int,
        value_text: str = "",
        duration_ms: int = 950,
    ) -> None:
        self.icon.clear()
        self.icon.setText("◉")
        self.icon.setStyleSheet("color:#8FB9EA; font-size:12pt;")
        self.icon.setVisible(True)
        self.title.setText(str(label or "Perilla"))
        self.subtitle.setVisible(False)
        self.progress.setVisible(True)
        self.progress.setValue(max(0, min(100, int(percent))))
        self.value.setText(str(value_text or f"{percent}%"))
        self.value.setVisible(True)
        self._set_dynamic_width(minimum=210, maximum=340)
        # Reiniciar el mismo timer hace que una perilla actualice el mismo OSD.
        self._present(duration_ms)