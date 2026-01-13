"""AnkiRAG Agent entry point."""

import sys

from PyQt6.QtWidgets import QApplication

from src.ui import MainWindow


def main() -> None:
    """Launch the AnkiRAG Agent application."""
    app = QApplication(sys.argv)
    app.setApplicationName("AnkiRAG Agent")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
