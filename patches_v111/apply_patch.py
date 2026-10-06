from __future__ import annotations

import sys
from pathlib import Path
import re

root = Path(sys.argv[1]).resolve()

def read(rel: str):
    p = root / rel
    if not p.exists():
        raise SystemExit(f"Missing required file: {p}")
    return p, p.read_text(encoding="utf-8")

def write(rel: str, text: str):
    (root / rel).write_text(text, encoding="utf-8")

p, s = read("app_source/app/version.py")
p.write_text('__version__ = "1.1.1 Stable"\n', encoding="utf-8")

p, s = read("app_source/app/ui/main_window.py")
s = s.replace("top_bar.setFixedHeight(76)", "top_bar.setFixedHeight(60)")
s = s.replace("layout.setContentsMargins(22, 0, 22, 0)", "layout.setContentsMargins(18, 0, 18, 0)")
s = s.replace('self.app_subtitle = QLabel(f"Centro de control MIDI · {__version__}")', 'self.app_subtitle = QLabel(__version__)')
if "self.app_subtitle.setVisible(False)" not in s:
    s = s.replace("title_block.addWidget(self.app_subtitle)\n", "title_block.addWidget(self.app_subtitle)\n        self.app_subtitle.setVisible(False)\n", 1)
s = s.replace("self.profile_combo.setMinimumWidth(180)", "self.profile_combo.setMinimumWidth(165)")
s = s.replace("layout.setContentsMargins(16, 16, 16, 16)\n        layout.setSpacing(14)", "layout.setContentsMargins(12, 12, 12, 12)\n        layout.setSpacing(10)", 1)
s = s.replace("layout.setContentsMargins(16, 16, 16, 16)\n        layout.setSpacing(12)", "layout.setContentsMargins(14, 12, 14, 12)\n        layout.setSpacing(9)", 1)
s = s.replace("""        heading.addWidget(title)
        heading.addStretch()
        heading.addWidget(self.device_status_icon)
        heading.addWidget(self.device_status)
        heading.addWidget(self.reload_midi_button)

        bank_row = QHBoxLayout()""", """        heading.addWidget(title)
        heading.addStretch()

        bank_row = QHBoxLayout()""")
s = s.replace("""        layout_label = QLabel("Layout")
        layout_label.setObjectName("Muted")
        layout_value = QPushButton("Clásico 4×2")
        layout_value.setEnabled(False)
        bank_row.addWidget(self.bank_a_button)
        bank_row.addWidget(self.bank_b_button)
        bank_row.addStretch()
        bank_row.addWidget(layout_label)
        bank_row.addWidget(layout_value)""", """        bank_row.addWidget(self.bank_a_button)
        bank_row.addWidget(self.bank_b_button)
        bank_row.addStretch()
        bank_row.addWidget(self.device_status_icon)
        bank_row.addWidget(self.device_status)
        bank_row.addWidget(self.reload_midi_button)""")
s = s.replace("grid.setContentsMargins(0, 4, 0, 4)\n        grid.setHorizontalSpacing(10)\n        grid.setVerticalSpacing(10)", "grid.setContentsMargins(0, 2, 0, 2)\n        grid.setHorizontalSpacing(8)\n        grid.setVerticalSpacing(8)")
s = s.replace("""        layout.addWidget(self.knob_panel)
        layout.addWidget(self.midi_monitor)
        layout.addStretch()
        return panel""", """        layout.addWidget(self.knob_panel)
        layout.addWidget(self.midi_monitor)
        return panel""", 1)
s = s.replace("self.app_subtitle.setVisible(not self.compact_mode)", "self.app_subtitle.setVisible(False)")
s = s.replace("self.profile_label.setVisible(not self.compact_mode)", "self.profile_label.setVisible(False)")
s = s.replace('self.setMinimumSize(560, 520)\n        self._restore_geometry("compact", 635, 850)', 'self.setMinimumSize(560, 500)\n        self._restore_geometry("compact", 635, 690)')
s = s.replace('self.setMinimumSize(560, 520)\n            self._restore_geometry("compact", 635, 850)', 'self.setMinimumSize(560, 500)\n            self._restore_geometry("compact", 635, 690)')
s = s.replace('self.setMinimumSize(560, 520)\n            self._restore_geometry("compact", 635, 690)', 'self.setMinimumSize(560, 500)\n            self._restore_geometry("compact", 635, 690)')
s = s.replace('self._restore_geometry("compact", 635, 850)', 'self._restore_geometry("compact", 635, 690)')
write("app_source/app/ui/main_window.py", s)

p, s = read("app_source/app/widgets/pad_widget.py")
s = s.replace("self.setMinimumSize(108, 100)\n        self.setMaximumHeight(112)", "self.setMinimumSize(108, 86)\n        self.setMaximumHeight(96)")
s = s.replace("layout.setContentsMargins(9, 7, 9, 7)\n        layout.setSpacing(3)", "layout.setContentsMargins(9, 6, 9, 6)\n        layout.setSpacing(2)")
s = s.replace("self.icon_label.setFixedHeight(27)", "self.icon_label.setFixedHeight(22)")
if "self.subtitle_label.setVisible(False)" not in s:
    s = s.replace("layout.addWidget(self.subtitle_label)\n", "layout.addWidget(self.subtitle_label)\n        self.subtitle_label.setVisible(False)\n", 1)
s = s.replace("border: 2px solid {border}; border-radius: 12px;", "border: 1px solid {border}; border-radius: 11px;")
write("app_source/app/widgets/pad_widget.py", s)

p, s = read("app_source/app/widgets/knob_panel.py")
s = s.replace("self.setMinimumSize(108, 74)\n        self.setMaximumHeight(82)", "self.setMinimumSize(108, 58)\n        self.setMaximumHeight(64)")
s = s.replace("layout.setContentsMargins(8, 7, 8, 7)\n        layout.setSpacing(2)", "layout.setContentsMargins(8, 5, 8, 5)\n        layout.setSpacing(1)")
s = s.replace('self.value = QLabel("0 · silencio")', 'self.value = QLabel("0")', 1)
before_card = s.split("class KnobCard", 1)[0]
if "self.action.setVisible(False)" not in before_card:
    s = s.replace('self.action.setObjectName("Muted")\n', 'self.action.setObjectName("Muted")\n        self.action.setVisible(False)\n', 1)
s = s.replace("        layout.addWidget(self.action)\n        self.setStyleSheet", "        self.setStyleSheet", 1)
s = s.replace("QFrame { background:#20252D; border:1px solid #323A47; border-radius:10px; }", "QFrame { background:#1B2028; border:1px solid #2C3440; border-radius:9px; }")
s = s.replace("outer.setContentsMargins(12, 10, 12, 10)\n        outer.setSpacing(8)", "outer.setContentsMargins(10, 8, 10, 8)\n        outer.setSpacing(6)")
if "self.summary.setVisible(False)" not in s:
    s = s.replace("header.addWidget(title)\n        header.addWidget(self.summary, 1)", "header.addWidget(title)\n        self.summary.setVisible(False)\n        header.addWidget(self.summary, 1)", 1)
s = s.replace("self.cards[int(knob)].value.setText(text)\n        self.minis[int(knob)].value.setText(text)", 'self.cards[int(knob)].value.setText(text)\n        mini_text = "0" if midi_value == 0 else (f"{percent}%" if db is None else f"{db:.1f} dB")\n        self.minis[int(knob)].value.setText(mini_text)')
write("app_source/app/widgets/knob_panel.py", s)

p, s = read("app_source/app/ui/osd.py")
s = s.replace("card_layout.setContentsMargins(11, 6, 11, 6)", "card_layout.setContentsMargins(13, 8, 13, 8)")
s = s.replace("        self.setFixedWidth(max(minimum, min(maximum, content_w)))", """        geo = self._screen_geometry()
        if geo is not None:
            maximum = min(maximum, max(minimum, geo.width() - 32))
        self.setFixedWidth(max(minimum, min(maximum, content_w)))""")
s = s.replace("""        if geo is not None:
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + geo.height() - self.height() - 72
            self.move(x, y)""", """        if geo is not None:
            safe = 16
            x = geo.x() + (geo.width() - self.width()) // 2
            y = geo.y() + geo.height() - self.height() - 72
            x = max(geo.left() + safe, min(x, geo.right() - self.width() - safe + 1))
            y = max(geo.top() + safe, min(y, geo.bottom() - self.height() - safe + 1))
            self.move(x, y)""")
write("app_source/app/ui/osd.py", s)

p, s = read("app_source/app/ui/theme.py")
s = s.replace("font-size: 19pt;", "font-size: 16pt;")
s = s.replace("""QFrame#Sidebar,
QFrame#EditorPanel,
QFrame#MonitorPanel {
    background-color: #171A20;
    border: 1px solid #2B303A;
    border-radius: 12px;
}""", """QFrame#Sidebar,
QFrame#EditorPanel {
    background-color: #15191F;
    border: 1px solid #272E38;
    border-radius: 11px;
}

QFrame#MonitorPanel {
    background-color: #15191F;
    border: 1px solid #242B34;
    border-radius: 10px;
}""")
s = s.replace("padding: 8px 14px;", "padding: 7px 12px;")
write("app_source/app/ui/theme.py", s)

p, s = read("MIDI_Premium_2_Setup.iss")
s = re.sub(r'#define MyAppVersion "[^"]+"', '#define MyAppVersion "1.1.1"', s)
s = re.sub(r'OutputBaseFilename=MIDI_Premium_2_Setup_v[0-9.]+', 'OutputBaseFilename=MIDI_Premium_2_Setup_v1.1.1', s)
write("MIDI_Premium_2_Setup.iss", s)

p, s = read("app_source/CHANGELOG.md")
entry = """## 1.1.1 Stable
- Interfaz principal más limpia y compacta.
- PADs más bajos, bordes más ligeros y BANK repetido oculto.
- Perillas K1–K8 simplificadas en modo compacto.
- Menos espacio vacío en la ventana compacta.
- Estado MIDI integrado junto a los bancos.
- OSD/overlay con márgenes seguros para evitar recortes en bordes/DPI.
- Se conservan perfiles, PADs y preferencias del usuario.

"""
if "## 1.1.1 Stable" not in s:
    s = s.replace("# Changelog\n", "# Changelog\n\n" + entry, 1) if s.startswith("# Changelog") else entry + s
write("app_source/CHANGELOG.md", s)

print("MIDI Premium 2 v1.1.1 visual patch applied")
