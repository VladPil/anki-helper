"""Background worker for sync operations."""

import logging

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.models import SyncResult
from src.core.sync_service import SyncService

logger = logging.getLogger(__name__)


class SyncWorker(QThread):
    """Background worker for running sync operations.

    Runs sync in a separate thread to keep the UI responsive.

    Signals:
        progress: Emitted with progress message string.
        finished: Emitted with SyncResult when sync completes.
        error: Emitted with error message string on failure.
    """

    progress = pyqtSignal(str)
    finished = pyqtSignal(object)  # SyncResult
    error = pyqtSignal(str)

    def __init__(self, sync_service: SyncService) -> None:
        """Initialize the worker.

        Args:
            sync_service: Configured sync service to use.
        """
        super().__init__()
        self.sync_service = sync_service

    def run(self) -> None:
        """Execute the sync operation."""
        try:
            self.progress.emit("Starting sync...")
            result: SyncResult = self.sync_service.sync(
                progress_callback=self.progress.emit
            )
            self.finished.emit(result)
        except Exception as e:
            logger.exception("Sync failed")
            self.error.emit(str(e))
