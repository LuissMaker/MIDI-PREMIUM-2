DARK_STYLESHEET = """
QWidget {
    background-color: #101318;
    color: #F2F4F8;
    font-family: "Segoe UI";
    font-size: 10pt;
}

QMainWindow {
    background-color: #101318;
}

QFrame#TopBar {
    background-color: #171A20;
    border-bottom: 1px solid #2B303A;
}

QFrame#TopBar QLabel {
    background: transparent;
    border: none;
}

QFrame#Sidebar {
    background-color: transparent;
    border: none;
}

QFrame#EditorPanel {
    background-color: #15191F;
    border: 1px solid #272E38;
    border-radius: 11px;
}

QFrame#MonitorPanel {
    background-color: #15191F;
    border: 1px solid #242B34;
    border-radius: 10px;
}

QFrame#KnobCard {
    background-color: #1D222B;
    border: 1px solid #343C49;
    border-radius: 10px;
}

QLabel#AppTitle {
    background: transparent;
    border: none;
    font-size: 16pt;
    font-weight: 700;
}

QLabel#SectionTitle {
    font-size: 12pt;
    font-weight: 700;
}

QLabel#Muted {
    color: #95A0B5;
}

QLineEdit,
QComboBox,
QPlainTextEdit {
    background-color: #212630;
    border: 1px solid #363E4C;
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: #2E7CF6;
}

QComboBox::drop-down {
    border: none;
    width: 26px;
}

QPushButton {
    background-color: #242A35;
    border: 1px solid #3A4251;
    border-radius: 8px;
    padding: 7px 12px;
}

QPushButton:hover {
    background-color: #2B3340;
}

QPushButton:pressed {
    background-color: #1D222B;
}

QPushButton:checked,
QPushButton[activeBank="true"] {
    background-color: #2D7DFF;
    border-color: #2D7DFF;
    color: white;
}

QStatusBar {
    background-color: #14181E;
    color: #8F9BAD;
    border-top: 1px solid #242B34;
    font-size: 8.5pt;
}

QScrollBar:vertical {
    background: #151920;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #4B5465;
    min-height: 30px;
    border-radius: 5px;
}
"""