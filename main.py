"""main.py – Point d'entrée de Shimeji Desk."""
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon


def main() -> None:
    import os
    os.chdir(Path(__file__).resolve().parent)
    app = QApplication(sys.argv)
    app.setApplicationName("Shimeji Desk")
    app.setApplicationVersion("1.0.0")
    app.setQuitOnLastWindowClosed(False)

    # Icône globale
    icon_path = Path("assets/tray.png")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    from config import Config
    config = Config.load("config.json")

    from core.mascot_controller import MascotController
    controller = MascotController(config)

    from ui.tray_icon import TrayIcon
    tray = TrayIcon(controller, app)
    tray.show()

    # Intégration asyncio + Qt — doit être avant spawn_mascot (ensure_future)
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    from PyQt6.QtCore import QTimer
    pump = QTimer()
    pump.setInterval(16)  # ~60fps

    def _pump_asyncio():
        loop.call_soon(loop.stop)
        loop.run_forever()

    pump.timeout.connect(_pump_asyncio)
    pump.start()

    # Spawn après la loop (ensure_future disponible)
    if len(controller.mascots) == 0:
        if not Path(config.character_path).exists():
            print(
                f"[Main] ⚠ Dossier '{config.character_path}' introuvable.\n"
                "       Crée le dossier assets/default/ avec un pack Shimeji,\n"
                "       ou modifie 'character_path' dans config.json."
            )
        else:
            controller.spawn_mascot(config.character_path)

    def _on_quit():
        pump.stop()
        try:
            loop.run_until_complete(controller.ai_client.close())
        except Exception:
            pass
        try:
            loop.close()
        except Exception:
            pass
        try:
            controller.memory.close()
        except Exception:
            pass

    app.aboutToQuit.connect(_on_quit)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
