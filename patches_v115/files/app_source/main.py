from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path
from logging.handlers import RotatingFileHandler

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from app.actions.engine import ActionEngine
from app.continuous.engine import ContinuousActionEngine
from app.core.paths import AppPaths
from app.core.profile_store import ProfileStore
from app.core.settings import SettingsManager
from app.midi.engine import MidiEngine
from app.obs.engine import ObsEngine
from app.ui.main_window import MainWindow
from app.ui.theme import DARK_STYLESHEET

APP_ICON_PATH = Path(__file__).resolve().parent / "assets" / "app_icon.ico"


def configure_logging(paths: AppPaths) -> logging.Logger:
    logger = logging.getLogger("midi_premium_2")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    handler = RotatingFileHandler(
        paths.logs / "latest.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        )
    )
    logger.addHandler(handler)
    return logger


def main() -> int:
    paths = AppPaths.detect()
    paths.ensure()
    logger = configure_logging(paths)

    app = QApplication(sys.argv)
    app.setApplicationName("MIDI Premium 2")
    if APP_ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    app.setStyleSheet(DARK_STYLESHEET)

    try:
        settings = SettingsManager(paths.config / "settings.json")
        profiles = ProfileStore(paths.profiles)
        midi_settings = settings.data.setdefault("midi", {})
        midi_engine = MidiEngine(
            logger=logger,
            reconnect_interval_ms=int(
                midi_settings.get("reconnect_interval_ms", 3000)
            ),
        )
        obs_settings = settings.data.setdefault("obs", {})
        obs_engine = ObsEngine(
            logger=logger,
            reconnect_interval_ms=int(
                obs_settings.get(
                    "reconnect_interval_ms",
                    5000,
                )
            ),
        )
        action_engine = ActionEngine(logger=logger,obs_engine=obs_engine)
        continuous_engine = ContinuousActionEngine(obs_engine=obs_engine,logger=logger,update_interval_ms=33)
        window = MainWindow(settings,profiles,midi_engine,action_engine,obs_engine,continuous_engine)
        start_hidden = bool(settings.data.setdefault("workspace", {}).get("start_hidden_to_tray", True))
        if start_hidden and window.tray_icon.isVisible():
            window.hide()
            logger.info("MIDI Premium 2 iniciado oculto en la bandeja.")
        else:
            window.show()
            logger.info("Interfaz UI Base iniciada.")
        return app.exec()
    except Exception:
        details = traceback.format_exc()
        logger.exception("Fallo al iniciar.")
        QMessageBox.critical(
            None,
            "MIDI Premium 2",
            details,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())