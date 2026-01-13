"""Settings dialog for application configuration."""

from typing import Optional

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.config import settings, token_manager


class SettingsDialog(QDialog):
    """Dialog for configuring application settings.

    Allows users to configure:
    - AnkiConnect URL and default deck/model
    - Sync interval
    - API URL and logout
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the settings dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(450)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Anki Settings Group
        anki_group = QGroupBox("Anki Settings")
        anki_layout = QFormLayout()

        self.anki_url_input = QLineEdit()
        self.anki_url_input.setText(settings.anki_connect_url)
        anki_layout.addRow("AnkiConnect URL:", self.anki_url_input)

        self.default_deck_input = QLineEdit()
        self.default_deck_input.setText(settings.default_deck)
        anki_layout.addRow("Default Deck:", self.default_deck_input)

        self.default_model_input = QComboBox()
        self.default_model_input.setEditable(True)
        self.default_model_input.addItems([
            "Basic",
            "Basic (and reversed card)",
            "Cloze",
        ])
        self.default_model_input.setCurrentText(settings.default_model)
        anki_layout.addRow("Default Model:", self.default_model_input)

        anki_group.setLayout(anki_layout)
        layout.addWidget(anki_group)

        # Sync Settings Group
        sync_group = QGroupBox("Sync Settings")
        sync_layout = QFormLayout()

        self.sync_interval_input = QSpinBox()
        self.sync_interval_input.setRange(0, 1440)
        self.sync_interval_input.setValue(settings.sync_interval_minutes)
        self.sync_interval_input.setSuffix(" minutes")
        self.sync_interval_input.setSpecialValueText("Disabled")
        sync_layout.addRow("Auto-sync Interval:", self.sync_interval_input)

        sync_group.setLayout(sync_layout)
        layout.addWidget(sync_group)

        # API Settings Group
        api_group = QGroupBox("API Settings")
        api_layout = QFormLayout()

        self.api_url_input = QLineEdit()
        self.api_url_input.setText(settings.api_base_url)
        api_layout.addRow("API Base URL:", self.api_url_input)

        # Logout button
        self.logout_button = QPushButton("Logout / Clear Token")
        self.logout_button.clicked.connect(self._on_logout)
        api_layout.addRow("", self.logout_button)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _on_logout(self) -> None:
        """Handle logout button click."""
        reply = QMessageBox.question(
            self,
            "Confirm Logout",
            "Are you sure you want to clear your API token?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            token_manager.delete_token()
            QMessageBox.information(self, "Logged Out", "API token has been cleared.")

    def get_settings(self) -> dict[str, str | int]:
        """Get the configured settings.

        Returns:
            Dictionary with setting names and values.
        """
        return {
            "anki_connect_url": self.anki_url_input.text().strip(),
            "default_deck": self.default_deck_input.text().strip(),
            "default_model": self.default_model_input.currentText().strip(),
            "sync_interval_minutes": self.sync_interval_input.value(),
            "api_base_url": self.api_url_input.text().strip(),
        }
