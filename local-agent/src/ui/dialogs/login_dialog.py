"""Login dialog for API token authentication."""

from typing import Optional

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from src.config import settings


class LoginDialog(QDialog):
    """Dialog for entering API token and server URL.

    Allows users to authenticate with the AnkiRAG backend
    by entering their API token.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the login dialog.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Login to AnkiRAG")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            "Enter your AnkiRAG API token.\n"
            "You can get this from your AnkiRAG account settings."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Form
        form_layout = QFormLayout()

        self.token_input = QLineEdit()
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_input.setPlaceholderText("Paste your API token here")
        form_layout.addRow("API Token:", self.token_input)

        self.api_url_input = QLineEdit()
        self.api_url_input.setText(settings.api_base_url)
        self.api_url_input.setPlaceholderText("https://api.ankirag.com")
        form_layout.addRow("API URL:", self.api_url_input)

        layout.addLayout(form_layout)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_token(self) -> str:
        """Get the entered token.

        Returns:
            The token string, stripped of whitespace.
        """
        return self.token_input.text().strip()

    def get_api_url(self) -> str:
        """Get the entered API URL.

        Returns:
            The API URL string, stripped of whitespace.
        """
        return self.api_url_input.text().strip()
