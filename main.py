from loguru import logger
import sys
import re
import requests
import favicon
from typing import Dict, Any

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox, QStackedWidget, QSizePolicy, QTableWidget, QHeaderView, QTableWidgetItem,
    QMessageBox, QDialog, QMainWindow
)
from PySide6.QtCore import QUrl, QSize, Qt, QSettings, QThreadPool, QRunnable
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QPixmap, QImage
from PySide6.QtWebEngineWidgets import QWebEngineView

logger.add("kiosk_browser.log", format="{time} {level} {message}", level="DEBUG")

VERSION = "dev"

class KioskBrowserSettings:
    """Manages the settings using QSettings."""
    DEFAULT_SETTINGS = {
        "urls": [["https://example.com", "Example", "@pageicon"]],
        "windowBranding": "Kiosk Browser",
        "fullscreen": False,
        "iconSize": 32,
    }

    @classmethod
    def load_settings(cls) -> Dict[str, Any]:
        """Loads settings using QSettings and applies defaults for missing keys."""
        settings = QSettings("meowmeowahr", "KioskBrowser")
        loaded_settings = {key: settings.value(key, default, type=type(default)) for key, default in cls.DEFAULT_SETTINGS.items()}
        logger.debug("Settings loaded: {}", loaded_settings)
        return loaded_settings

    @classmethod
    def save_settings(cls, settings: Dict[str, Any]) -> None:
        """Saves the given settings using QSettings."""
        qsettings = QSettings("meowmeowahr", "KioskBrowser")
        for key, value in settings.items():
            qsettings.setValue(key, value)
        logger.info("Settings saved: {}", settings)


class IconFetchWorker(QRunnable):
    """Worker to fetch the page icon asynchronously."""
    def __init__(self, url: str, callback: callable):
        super().__init__()
        self.url = url
        self.callback = callback  # Function to call when the icon is fetched

    def run(self):
        try:
            # Fetch the favicon
            icons = favicon.get(self.url)
            if icons:
                icon = icons[0]
                print(icons)
                response = requests.get(icon.url, stream=True)
                if response.status_code == 200:
                    # Pass the icon data back to the callback
                    self.callback(QIcon(QPixmap(QImage.fromData(response.content)).scaled(32, 32, mode=Qt.TransformationMode.SmoothTransformation)))
                    return
        except Exception as e:
            logger.warning(f"Failed to fetch page icon for {self.url}: {e}")

        # If we fail to fetch the icon, call the callback with None
        self.callback(None)


class MainWindow(QMainWindow):
    def __init__(self, settings: Dict[str, Any]):
        super().__init__()
        self.settings = settings
        self.settings_pane = SettingsPage(settings)

        self.thread_pool = QThreadPool()

        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(self.settings["windowBranding"])
        self.root_stack = QStackedWidget()
        self.setCentralWidget(self.root_stack)

        self.main_widget = QWidget()
        self.root_stack.addWidget(self.main_widget)

        self.settings_widget = QWidget()
        self.settings_layout = QVBoxLayout()
        self.settings_widget.setLayout(self.settings_layout)

        self.settings_top_bar = QHBoxLayout()
        self.settings_layout.addLayout(self.settings_top_bar)

        self.settings_back = QPushButton("Back")
        self.settings_back.clicked.connect(lambda: self.root_stack.setCurrentIndex(0))
        self.settings_top_bar.addWidget(self.settings_back)

        self.settings_top_bar.addStretch()

        self.settings_layout.addWidget(self.settings_pane)

        self.root_stack.addWidget(self.settings_widget)

        self.main_layout = QVBoxLayout(self)
        self.main_widget.setLayout(self.main_layout)

        self.pages_layout = QHBoxLayout()
        self.main_layout.addLayout(self.pages_layout)

        self.web_stack = QStackedWidget(self)
        self.main_layout.addWidget(self.web_stack)

        self._setup_pages()
        self._setup_shortcuts()
        self._apply_styling()

        self.setWindowIcon(QIcon("icon.png"))

    def _setup_pages(self):
        for index, (url, label, icon_path) in enumerate(self.settings["urls"]):
            button = QPushButton()
            button.clicked.connect(lambda _, idx=index: self._switch_page(idx))
            button.setText(label)
            button.setIconSize(QSize(32, 32))
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            button.setObjectName("WebTab")
            self.pages_layout.addWidget(button)
            self._set_button_icon(button, label, icon_path)

            # Add a new web page to the stack
            web_page = QWebEngineView()
            web_page.load(QUrl(url))
            self.web_stack.addWidget(web_page)

    def _set_button_icon(self, button: QPushButton, label: str, icon_path: str):
        if icon_path == "@pageicon":
            # Fetch icon asynchronously
            url = self.settings["urls"][self.web_stack.count()][0]
            self._fetch_icon_async(button, label, url)
        else:
            # Use a local icon directly
            button.setIcon(QIcon(icon_path))

    def _fetch_icon_async(self, button: QPushButton, label: str, url: str):
        def update_button_icon(icon: QIcon):
            """Update the button with the fetched icon."""
            if icon:
                button.setIcon(icon)
                logger.info(f"Fetched page icon for {label}")
            else:
                logger.warning(f"No icon available for {label}")

        # Start the worker to fetch the icon
        worker = IconFetchWorker(url, update_button_icon)
        self.thread_pool.start(worker)

    def _switch_page(self, index: int):
        logger.debug(f"Switching to page {index}")
        self.web_stack.setCurrentIndex(index)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Alt+F1"), self).activated.connect(self._show_settings)

    def _apply_styling(self):
        with open("style.qss", "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

    def _show_settings(self):
        logger.info("Opening settings window.")
        self.root_stack.setCurrentIndex(1)

class SettingsPage(QWidget):
    """Settings configuration window."""
    def __init__(self, settings: Dict[str, Any]):
        super().__init__()
        self.settings = settings
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("Settings")

        # URL Configuration Section
        self.url_label = QLabel("URL Config:")
        self.url_table = QTableWidget(0, 3)  # 3 columns: URL, Label, Icon
        self.url_table.setHorizontalHeaderLabels(["URL", "Label", "Icon"])
        self.url_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._populate_url_table()

        self.add_url_button = QPushButton("Add URL")
        self.add_url_button.clicked.connect(self._add_url)

        self.remove_url_button = QPushButton("Remove Selected")
        self.remove_url_button.clicked.connect(self._remove_selected_urls)

        # Other Settings
        self.window_branding_label = QLabel("Window Branding:")
        self.window_branding_input = QLineEdit(self.settings["windowBranding"])

        self.fullscreen_checkbox = QCheckBox("Fullscreen")
        self.fullscreen_checkbox.setChecked(self.settings["fullscreen"])

        # Save Button
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._save_settings)

        # Layout
        layout = QVBoxLayout()
        url_layout = QHBoxLayout()
        url_layout.addWidget(self.add_url_button)
        url_layout.addWidget(self.remove_url_button)

        layout.addWidget(self.url_label)
        layout.addWidget(self.url_table)
        layout.addLayout(url_layout)
        layout.addWidget(self.window_branding_label)
        layout.addWidget(self.window_branding_input)
        layout.addWidget(self.fullscreen_checkbox)
        layout.addWidget(self.save_button)
        self.setLayout(layout)

    def _populate_url_table(self):
        """Populate the URL table with current settings."""
        self.url_table.setRowCount(0)
        for url, label, icon in self.settings["urls"]:
            row = self.url_table.rowCount()
            self.url_table.insertRow(row)
            self.url_table.setItem(row, 0, QTableWidgetItem(url))
            self.url_table.setItem(row, 1, QTableWidgetItem(label))
            self.url_table.setItem(row, 2, QTableWidgetItem(icon))

    def _add_url(self):
        """Add a new URL entry."""
        dialog = URLConfigDialog()
        if dialog.exec():
            url, label, icon = dialog.get_data()
            row = self.url_table.rowCount()
            self.url_table.insertRow(row)
            self.url_table.setItem(row, 0, QTableWidgetItem(url))
            self.url_table.setItem(row, 1, QTableWidgetItem(label))
            self.url_table.setItem(row, 2, QTableWidgetItem(icon))

    def _remove_selected_urls(self):
        """Remove selected URLs from the table."""
        selected_rows = set(item.row() for item in self.url_table.selectedItems())
        for row in sorted(selected_rows, reverse=True):
            self.url_table.removeRow(row)

    def _save_settings(self):
        """Save all settings, including the updated URL list."""
        # Update URL list
        urls = []
        for row in range(self.url_table.rowCount()):
            url = self.url_table.item(row, 0).text()
            label = self.url_table.item(row, 1).text()
            icon = self.url_table.item(row, 2).text()
            urls.append([url, label, icon])
        self.settings["urls"] = urls

        # Update other settings
        self.settings["windowBranding"] = self.window_branding_input.text()
        self.settings["fullscreen"] = self.fullscreen_checkbox.isChecked()

        KioskBrowserSettings.save_settings(self.settings)
        QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully.")


class URLConfigDialog(QDialog):
    """Dialog for adding or editing a URL entry."""
    def __init__(self, url="", label="", icon=""):
        super().__init__()
        self.setWindowTitle("URL Configuration")

        self.url_input = QLineEdit(url)
        self.label_input = QLineEdit(label)
        self.icon_input = QLineEdit(icon)

        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        layout = QGridLayout()
        layout.addWidget(QLabel("URL:"), 0, 0)
        layout.addWidget(self.url_input, 0, 1)
        layout.addWidget(QLabel("Label:"), 1, 0)
        layout.addWidget(self.label_input, 1, 1)
        layout.addWidget(QLabel("Icon:"), 2, 0)
        layout.addWidget(self.icon_input, 2, 1)
        layout.addWidget(self.ok_button, 3, 0)
        layout.addWidget(self.cancel_button, 3, 1)
        self.setLayout(layout)

    def get_data(self):
        """Retrieve the entered data."""
        return self.url_input.text(), self.label_input.text(), self.icon_input.text()


# Integrate the dialog into the main application workflow
def main():
    app = QApplication(sys.argv)
    settings = KioskBrowserSettings.load_settings()
    window = MainWindow(settings)

    if settings.get("fullscreen", False):
        window.showFullScreen()
    else:
        window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
