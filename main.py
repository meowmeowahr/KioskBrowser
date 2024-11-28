"""
KioskBrowser

A simple web browser that can only browse a single website.
The website is defined in a settings.json file.
You can change the settings by pressing Alt+F1.
"""

import os
import sys
import json
import re
import requests
import favicon
from typing import List, Dict, Any

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QLineEdit,
    QCheckBox
)
from PySide6.QtCore import QUrl, QSize
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWebEngineWidgets import QWebEngineView

VERSION = "dev"

class KioskBrowserSettings:
    """Manages application settings with type hints and validation."""
    DEFAULT_SETTINGS = {
        "urls": [["https://example.com", "Example", "@pageicon"]],
        "windowBranding": "Kiosk Browser",
        "windowIcon": "@pageicon",
        "fullscreen": False,
        "iconSize": 32
    }

    @classmethod
    def load_settings(cls) -> Dict[str, Any]:
        """Load settings with fallback to default settings."""
        settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
        try:
            with open(settings_path, 'r') as f:
                settings = json.load(f)

            # Validate and merge with default settings
            for key, default_value in cls.DEFAULT_SETTINGS.items():
                if key not in settings:
                    settings[key] = default_value

            return settings
        except (FileNotFoundError, json.JSONDecodeError):
            # Create default settings file if it doesn't exist
            settings = cls.DEFAULT_SETTINGS.copy()
            try:
                with open(settings_path, 'w') as f:
                    json.dump(settings, f, indent=4)
            except IOError:
                print("Warning: Could not create settings file.")
            return settings

    @classmethod
    def save_settings(cls, settings: Dict[str, Any]) -> None:
        """Save settings to file."""
        settings_path = os.path.join(os.path.dirname(__file__), "settings.json")
        try:
            with open(settings_path, 'w') as f:
                json.dump(settings, f, indent=4)
        except IOError:
            print("Error: Could not save settings file.")

class MainWindow(QWidget):
    """Main application window for the Kiosk Browser."""
    def __init__(self, settings: Dict[str, Any]):
        super().__init__()
        self.settings = settings
        self._init_ui()
        self._setup_page_buttons()
        self._setup_shortcuts()
        self._apply_styling()

    def _init_ui(self):
        """Initialize the main user interface."""
        self.setObjectName("MainWindow")

        # Main layout
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Page buttons layout
        self.pages = QHBoxLayout()
        self.layout.addLayout(self.pages)

        # Web view
        self.web_engine_view = QWebEngineView(self)
        self.web_engine_view.load(QUrl(self.settings["urls"][0][0]))
        self.layout.addWidget(self.web_engine_view)

        # Window branding and icon
        self._set_window_title_and_icon()

    def _setup_page_buttons(self):
        """Create and configure page buttons."""
        for i, (url, label, icon_path) in enumerate(self.settings["urls"]):
            # Create button
            button = QPushButton(label)
            button.clicked.connect(self._switch_page)
            self.pages.addWidget(button)

            # Set button icon
            self._set_button_icon(button, label, icon_path)

            # Set icon size
            button.setIconSize(QSize(self.settings.get("iconSize", 32),
                                      self.settings.get("iconSize", 32)))

    def _set_button_icon(self, button: QPushButton, label: str, icon_path: str):
        """Set icon for a page button."""
        icon_cache_dir = os.path.join(os.path.dirname(__file__), "iconcache")
        os.makedirs(icon_cache_dir, exist_ok=True)

        # Sanitize filename
        filename = re.sub(r'\W+', '', label.replace(" ", "_"))

        # Try to download favicon if @pageicon is specified
        if icon_path == "@pageicon":
            try:
                icons = favicon.get(self.settings["urls"][self.pages.count()-1][0])
                print(icons)
                icon = icons[0]
                icon_file_path = os.path.join(icon_cache_dir, f"{filename}.{icon.format}")

                # Download and save icon
                response = requests.get(icon.url, stream=True)
                with open(icon_file_path, 'wb') as image:
                    for chunk in response.iter_content(1024):
                        image.write(chunk)
            except requests.exceptions.ConnectionError as e:
                print(f"DEBUG: Failed to download icon: {e}")
                icon_file_path = None
        else:
            icon_file_path = icon_path

        # Set button icon
        if icon_file_path:
            if os.path.exists(f"{os.path.join(icon_cache_dir, filename)}.png"):
                button.setIcon(QIcon(f"{os.path.join(icon_cache_dir, filename)}.png"))
            elif os.path.exists(f"{os.path.join(icon_cache_dir, filename)}.ico"):
                button.setIcon(QIcon(f"{os.path.join(icon_cache_dir, filename)}.ico"))
            elif icon_path != "@pageicon":
                button.setIcon(QIcon(icon_path))
            else:
                button.setIcon(QIcon(os.path.join(os.path.dirname(__file__), "icon.png")))

    def _set_window_title_and_icon(self):
        """Set window title and icon based on settings."""
        if self.settings["windowBranding"] == "@pagetitle":
            self.web_engine_view.loadFinished.connect(
                lambda: self.setWindowTitle(self.web_engine_view.page().title())
            )
        else:
            self.setWindowTitle(self.settings["windowBranding"])

        if self.settings["windowIcon"] == "@pageicon":
            self.web_engine_view.iconChanged.connect(
                lambda: self.setWindowIcon(self.web_engine_view.icon())
            )

    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        self.alt_f1 = QKeySequence("Alt+F1")
        self.alt_f1_shortcut = QShortcut(self.alt_f1, self)
        self.alt_f1_shortcut.activated.connect(self._show_settings)

        self.alt_f3 = QKeySequence("Alt+F3")
        self.alt_f3_shortcut = QShortcut(self.alt_f3, self)
        self.alt_f3_shortcut.activated.connect(self._show_debug)

    def _apply_styling(self):
        """Apply external stylesheet."""
        style_path = os.path.join(os.path.dirname(__file__), "style.qss")
        try:
            with open(style_path, "r") as f:
                self.setStyleSheet(f.read())
        except IOError:
            print("Warning: Could not load stylesheet.")

    def _switch_page(self):
        """Switch to the selected page."""
        index = self.pages.indexOf(self.sender())
        print(f"DEBUG: switching to page {index}")
        self.web_engine_view.load(QUrl(self.settings["urls"][index][0]))

    def _show_settings(self):
        """Show settings window."""
        settings_window.show()

    def _show_debug(self):
        """Show debug window."""
        debug_window.show()

class SettingsPage(QWidget):
    """Settings configuration window."""
    def __init__(self, settings: Dict[str, Any]):
        super().__init__()
        self.settings = settings
        self._init_ui()

    def _init_ui(self):
        """Initialize settings UI."""
        self.setWindowTitle("Settings")

        # Window Branding
        self.window_branding_label = QLabel("Window Branding:")
        self.window_branding_input = QLineEdit()
        self.window_branding_input.setText(self.settings["windowBranding"])
        self.window_branding_input.setPlaceholderText("Kiosk Browser")

        # Window Icon
        self.window_icon_label = QLabel("Window Icon:")
        self.window_icon_input = QLineEdit()
        self.window_icon_input.setText(self.settings["windowIcon"])
        self.window_icon_input.setPlaceholderText("@pageicon")

        # URL Configuration (Placeholder)
        self.url_label = QLabel("URL Config:")
        self.url_button = QPushButton("Coming Soon")
        self.url_button.setEnabled(False)
        # self.url_button.clicked.connect(self.open_url_config)  # Uncomment when implemented

        # Fullscreen Option
        self.fullscreen_checkbox = QCheckBox("Fullscreen")
        self.fullscreen_checkbox.setChecked(self.settings["fullscreen"])

        # Save Button
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._save_settings)

        # Layout
        layout = QGridLayout()
        layout.addWidget(self.url_label, 0, 0)
        layout.addWidget(self.url_button, 0, 1)
        layout.addWidget(self.window_branding_label, 1, 0)
        layout.addWidget(self.window_branding_input, 1, 1)
        layout.addWidget(self.window_icon_label, 2, 0)
        layout.addWidget(self.window_icon_input, 2, 1)
        layout.addWidget(self.fullscreen_checkbox, 3, 0)
        layout.addWidget(self.save_button, 4, 0, 1, 2)
        self.setLayout(layout)

    def _save_settings(self):
        """Save settings from the UI."""
        self.settings["windowBranding"] = self.window_branding_input.text()
        self.settings["windowIcon"] = self.window_icon_input.text()
        self.settings["fullscreen"] = self.fullscreen_checkbox.isChecked()

        KioskBrowserSettings.save_settings(self.settings)
        self.close()

class DebugWindow(QWidget):
    """Debugging control window."""
    def __init__(self, main_window: MainWindow):
        super().__init__()
        self.main_window = main_window
        self._init_ui()

    def _init_ui(self):
        """Initialize debugging UI."""
        self.setWindowTitle("Debugging Window")

        layout = QGridLayout()
        self.setLayout(layout)

        # Refresh Button
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self._refresh_page)
        layout.addWidget(refresh_button, 0, 0)

        # Minimize Button
        minimize_button = QPushButton("Minimize")
        minimize_button.clicked.connect(self._minimize_window)
        layout.addWidget(minimize_button, 0, 1)

        # Maximize Button
        maximize_button = QPushButton("Maximize (No FS)")
        maximize_button.clicked.connect(self._maximize_window)
        layout.addWidget(maximize_button, 0, 2)

    def _refresh_page(self):
        """Refresh the main window's web page."""
        self.main_window.web_engine_view.reload()

    def _minimize_window(self):
        """Minimize the main window."""
        self.main_window.showMinimized()

    def _maximize_window(self):
        """Maximize the main window."""
        self.main_window.showMaximized()

def main():
    """Main application entry point."""
    app = QApplication(sys.argv)

    # Load settings
    settings = KioskBrowserSettings.load_settings()

    # Create main window
    global window
    window = MainWindow(settings)

    # Create settings and debug windows
    global settings_window
    settings_window = SettingsPage(settings)

    global debug_window
    debug_window = DebugWindow(window)

    # Set fullscreen if enabled
    if settings.get("fullscreen", False):
        window.showFullScreen()
    else:
        window.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()