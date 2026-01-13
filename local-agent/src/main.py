"""AnkiRAG Agent entry point."""

import logging
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from src.ui import MainWindow


def setup_logging() -> None:
    """Configure logging to both file and console."""
    # Create logs directory in the local-agent folder
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # Log file with date
    log_file = log_dir / f"agent_{datetime.now().strftime('%Y-%m-%d')}.log"

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # File handler - detailed logs
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    # Console handler - less verbose
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)

    # Add handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Log startup
    logging.info("=" * 60)
    logging.info("AnkiRAG Agent starting")
    logging.info(f"Log file: {log_file}")
    logging.info("=" * 60)


def main() -> None:
    """Launch the AnkiRAG Agent application."""
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        app = QApplication(sys.argv)
        app.setApplicationName("AnkiRAG Agent")

        logger.info("Creating main window")
        window = MainWindow()
        window.show()

        logger.info("Application started successfully")
        sys.exit(app.exec())
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
