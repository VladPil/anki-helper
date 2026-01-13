"""Main application window for AnkiRAG Agent."""

import logging
from datetime import datetime
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QCloseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.clients import AnkiConnectClient, BackendAPIClient
from src.config import settings, token_manager
from src.core import SyncResult
from src.core.sync_service import SyncService
from src.ui.dialogs import LoginDialog, SettingsDialog
from src.ui.workers import SyncWorker

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window.

    Provides the primary UI for:
    - Viewing connection status
    - Triggering manual sync
    - Configuring settings
    - System tray integration
    """

    def __init__(self) -> None:
        """Initialize the main window."""
        super().__init__()
        self.setWindowTitle("AnkiRAG Agent")
        self.setMinimumSize(500, 400)

        self._sync_worker: Optional[SyncWorker] = None
        self._auto_sync_timer: Optional[QTimer] = None

        self._setup_ui()
        self._setup_tray()
        self._update_status()
        self._setup_auto_sync()

    def _setup_ui(self) -> None:
        """Set up the main UI."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Status Group
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()

        self._anki_status_label = QLabel("Anki: Checking...")
        self._api_status_label = QLabel("API: Checking...")
        self._auth_status_label = QLabel("Auth: Checking...")

        status_layout.addWidget(self._anki_status_label)
        status_layout.addWidget(self._api_status_label)
        status_layout.addWidget(self._auth_status_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Sync Group
        sync_group = QGroupBox("Sync")
        sync_layout = QVBoxLayout()

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(False)
        self._progress_bar.hide()
        sync_layout.addWidget(self._progress_bar)

        self._progress_label = QLabel("")
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sync_layout.addWidget(self._progress_label)

        button_layout = QHBoxLayout()
        self._sync_button = QPushButton("Sync Now")
        self._sync_button.clicked.connect(self._on_sync)
        button_layout.addWidget(self._sync_button)

        self._refresh_button = QPushButton("Refresh Status")
        self._refresh_button.clicked.connect(self._update_status)
        button_layout.addWidget(self._refresh_button)

        sync_layout.addLayout(button_layout)
        sync_group.setLayout(sync_layout)
        layout.addWidget(sync_group)

        # Log Group
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout()

        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(150)
        log_layout.addWidget(self._log_text)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Bottom buttons
        bottom_layout = QHBoxLayout()

        self._login_button = QPushButton("Login")
        self._login_button.clicked.connect(self._on_login)
        bottom_layout.addWidget(self._login_button)

        self._settings_button = QPushButton("Settings")
        self._settings_button.clicked.connect(self._on_settings)
        bottom_layout.addWidget(self._settings_button)

        layout.addLayout(bottom_layout)

    def _setup_tray(self) -> None:
        """Set up system tray icon and menu."""
        self._tray_icon = QSystemTrayIcon(self)

        tray_menu = QMenu()

        show_action = QAction("Show", self)
        show_action.triggered.connect(self._show_window)
        tray_menu.addAction(show_action)

        sync_action = QAction("Sync Now", self)
        sync_action.triggered.connect(self._on_sync)
        tray_menu.addAction(sync_action)

        tray_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.setToolTip("AnkiRAG Agent")
        self._tray_icon.show()

    def _setup_auto_sync(self) -> None:
        """Set up automatic sync timer."""
        if settings.sync_interval_minutes > 0:
            self._auto_sync_timer = QTimer(self)
            self._auto_sync_timer.timeout.connect(self._on_sync)
            self._auto_sync_timer.start(settings.sync_interval_minutes * 60 * 1000)
            self._log(f"Auto-sync enabled every {settings.sync_interval_minutes} minutes")

    def _update_status(self) -> None:
        """Update connection status indicators."""
        # Check Anki connection
        try:
            anki_client = AnkiConnectClient(settings.anki_connect_url)
            decks = anki_client.get_deck_names()
            self._anki_status_label.setText(f"Anki: Connected ({len(decks)} decks)")
            self._anki_status_label.setStyleSheet("color: green")
        except Exception:
            self._anki_status_label.setText("Anki: Not connected")
            self._anki_status_label.setStyleSheet("color: red")

        # Check auth status
        if token_manager.has_token():
            self._auth_status_label.setText("Auth: Token stored")
            self._auth_status_label.setStyleSheet("color: green")
            self._login_button.setText("Re-login")

            # Check API connection
            try:
                api_client = BackendAPIClient(
                    settings.api_base_url,
                    token_manager.get_token(),
                )
                if api_client.verify_token():
                    self._api_status_label.setText("API: Connected")
                    self._api_status_label.setStyleSheet("color: green")
                else:
                    self._api_status_label.setText("API: Token invalid")
                    self._api_status_label.setStyleSheet("color: orange")
            except Exception:
                self._api_status_label.setText("API: Connection failed")
                self._api_status_label.setStyleSheet("color: red")
        else:
            self._auth_status_label.setText("Auth: Not logged in")
            self._auth_status_label.setStyleSheet("color: orange")
            self._api_status_label.setText("API: Not authenticated")
            self._api_status_label.setStyleSheet("color: gray")
            self._login_button.setText("Login")

    def _log(self, message: str) -> None:
        """Add message to activity log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._log_text.append(f"[{timestamp}] {message}")

    def _on_login(self) -> None:
        """Show login dialog."""
        dialog = LoginDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            token = dialog.get_token()
            api_url = dialog.get_api_url()

            if token:
                try:
                    api_client = BackendAPIClient(api_url, token)
                    if api_client.verify_token():
                        token_manager.set_token(token)
                        self._log("Login successful")
                        QMessageBox.information(
                            self,
                            "Success",
                            "Login successful! Token has been saved.",
                        )
                    else:
                        self._log("Login failed: Invalid token")
                        QMessageBox.warning(
                            self,
                            "Login Failed",
                            "The provided token is invalid.",
                        )
                except Exception as e:
                    self._log(f"Login failed: {e}")
                    QMessageBox.warning(
                        self,
                        "Login Failed",
                        f"Could not verify token: {e}",
                    )
            else:
                QMessageBox.warning(self, "Error", "Please enter a valid token.")

            self._update_status()

    def _on_settings(self) -> None:
        """Show settings dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_settings = dialog.get_settings()

            settings.anki_connect_url = str(new_settings["anki_connect_url"])
            settings.default_deck = str(new_settings["default_deck"])
            settings.default_model = str(new_settings["default_model"])
            settings.sync_interval_minutes = int(new_settings["sync_interval_minutes"])
            settings.api_base_url = str(new_settings["api_base_url"])

            self._log("Settings updated")
            self._update_status()

            # Restart auto-sync timer
            if self._auto_sync_timer:
                self._auto_sync_timer.stop()
            self._setup_auto_sync()

    def _on_sync(self) -> None:
        """Start sync operation."""
        if not token_manager.has_token():
            QMessageBox.warning(
                self,
                "Not Logged In",
                "Please login before syncing.",
            )
            return

        if self._sync_worker and self._sync_worker.isRunning():
            self._log("Sync already in progress")
            return

        try:
            anki_client = AnkiConnectClient(settings.anki_connect_url)
            api_client = BackendAPIClient(
                settings.api_base_url,
                token_manager.get_token(),
            )
            sync_service = SyncService(
                anki_client=anki_client,
                api_client=api_client,
                default_deck=settings.default_deck,
                default_model=settings.default_model,
            )
        except Exception as e:
            self._log(f"Failed to initialize sync: {e}")
            QMessageBox.warning(self, "Sync Error", f"Failed to initialize: {e}")
            return

        self._sync_worker = SyncWorker(sync_service)
        self._sync_worker.progress.connect(self._on_sync_progress)
        self._sync_worker.finished.connect(self._on_sync_finished)
        self._sync_worker.error.connect(self._on_sync_error)

        self._sync_button.setEnabled(False)
        self._progress_bar.setRange(0, 0)  # Indeterminate
        self._progress_bar.show()

        self._sync_worker.start()

    def _on_sync_progress(self, message: str) -> None:
        """Handle sync progress update."""
        self._progress_label.setText(message)
        self._log(message)

    def _on_sync_finished(self, result: SyncResult) -> None:
        """Handle sync completion."""
        self._sync_button.setEnabled(True)
        self._progress_bar.hide()
        self._progress_label.setText("")

        self._log(
            f"Sync completed: {result.cards_synced} cards synced, "
            f"{result.cards_failed} failed"
        )

        if result.errors:
            error_msg = "\n".join(result.errors[:5])
            if len(result.errors) > 5:
                error_msg += f"\n... and {len(result.errors) - 5} more errors"
            QMessageBox.warning(self, "Sync Completed with Errors", error_msg)
        else:
            self._tray_icon.showMessage(
                "Sync Complete",
                f"Synced {result.cards_synced} cards",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )

    def _on_sync_error(self, error: str) -> None:
        """Handle sync error."""
        self._sync_button.setEnabled(True)
        self._progress_bar.hide()
        self._progress_label.setText("")

        self._log(f"Sync error: {error}")
        QMessageBox.critical(self, "Sync Failed", f"Sync failed: {error}")

    def _on_tray_activated(
        self,
        reason: QSystemTrayIcon.ActivationReason,
    ) -> None:
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_window()

    def _show_window(self) -> None:
        """Show and raise the main window."""
        self.show()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close - minimize to tray instead."""
        if self._tray_icon.isVisible():
            self.hide()
            self._tray_icon.showMessage(
                "AnkiRAG Agent",
                "Application minimized to tray. Double-click to open.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            event.ignore()
        else:
            event.accept()

    def _quit_app(self) -> None:
        """Quit the application."""
        if self._sync_worker and self._sync_worker.isRunning():
            self._sync_worker.quit()
            self._sync_worker.wait()

        self._tray_icon.hide()
        QApplication.quit()
