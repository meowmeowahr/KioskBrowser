import os.path

from loguru import logger
import sys
import requests
import favicon
import datetime
from typing import Dict, Any

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox, QStackedWidget, QSizePolicy, QTableWidget, QHeaderView, QTableWidgetItem,
    QDialog, QMainWindow, QAbstractItemView, QFileDialog, QGroupBox, QSpinBox
)
from PySide6.QtCore import QUrl, QSize, Qt, QSettings, QThreadPool, QRunnable, Signal, QTimer
from PySide6.QtGui import QIcon, QKeySequence, QShortcut, QPixmap, QImage, QPalette, QColor
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

from qtawesome import icon as qtaicon

VERSION = "dev"


def get_time_string(twelve: bool = True):
    dt = datetime.datetime.now()
    return dt.strftime("%I:%M %p") if twelve else dt.strftime("%H:%M")

class KioskBrowserSettings:
    """Manages the settings using QSettings."""
    DEFAULT_SETTINGS = {
        "urls": [],
        "windowBranding": "Kiosk Browser",
        "fullscreen": True,
        "topbar": True,
        "topbar_12hr": True,
        "topbar_update_speed": 1000,
    }

    @classmethod
    def load_settings(cls) -> Dict[str, Any]:
        """Loads settings using QSettings and applies defaults for missing keys."""
        settings = QSettings("meowmeowahr", "KioskBrowser")
        loaded_settings = {key: settings.value(key, default, type=type(default)) for key, default in
                           cls.DEFAULT_SETTINGS.items()}
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
                response = requests.get(icons[0].url, stream=True)
                if response.status_code == 200:
                    # Pass the icon data back to the callback
                    self.callback(QIcon(QPixmap(QImage.fromData(response.content)).scaled(32, 32,
                                                                                          mode=Qt.TransformationMode.SmoothTransformation)))
                    return
        except Exception as e:
            logger.warning(f"Failed to fetch page icon for {self.url}: {e}")

        # If we fail to fetch the icon, call the callback with None
        self.callback(None)


class LabeledSpinBox(QWidget):
    def __init__(self, label_text: str, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)

        # Create label and spin box
        self.label = QLabel(label_text)
        self.spin_box = QSpinBox()

        # Add widgets to the layout
        layout.addWidget(self.label)
        layout.addWidget(self.spin_box)

        # Set the layout to the widget
        self.setLayout(layout)

        self.setValue = self.spin_box.setValue
        self.setRange = self.spin_box.setRange
        self.setSingleStep = self.spin_box.setSingleStep
        self.setSuffix = self.spin_box.setSuffix
        self.setPrefix = self.spin_box.setPrefix

    def set_text(self, text: str):
        """Set the text of the label."""
        self.label.setText(text)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = KioskBrowserSettings.load_settings()

        self.setObjectName("MainWindow")
        self.setWindowTitle(self.settings["windowBranding"])
        self.setWindowIcon(QIcon("icon.png"))

        self.set_fullscreen(self.settings.get("fullscreen", True))

        self.thread_pool = QThreadPool()

        self.root_stack = QStackedWidget()
        self.setCentralWidget(self.root_stack)

        self.main_widget = QWidget()
        self.root_stack.addWidget(self.main_widget)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_widget.setLayout(self.main_layout)

        self.top_bar_widget = QWidget()
        self.top_bar_widget.setVisible(self.settings.get("topbar", True))
        self.main_layout.addWidget(self.top_bar_widget)

        self.top_bar_layout = QHBoxLayout()
        self.top_bar_layout.setContentsMargins(12, 6, 12, 0)
        self.top_bar_widget.setLayout(self.top_bar_layout)

        # Top Bar Items
        self.top_bar_layout.addStretch()

        self.top_bar_clock = QLabel(get_time_string(self.settings.get("topbar_12hr", True)))
        self.top_bar_clock.setObjectName("ClockWidget")
        self.top_bar_layout.addWidget(self.top_bar_clock)

        self.pages_layout = QHBoxLayout()
        self.pages_layout.setContentsMargins(3, 0 if self.settings.get("topbar", True) else 3, 3, 0)
        self.main_layout.addLayout(self.pages_layout)

        self.web_stack = QStackedWidget()
        self.main_layout.addWidget(self.web_stack)

        # Create settings page
        self.settings_widget = QWidget()
        self.settings_layout = QVBoxLayout()
        self.settings_widget.setLayout(self.settings_layout)

        self.settings_top_bar = QHBoxLayout()
        self.settings_layout.addLayout(self.settings_top_bar)

        self.settings_back = QPushButton("Back")
        self.settings_back.clicked.connect(self.exit_settings)
        self.settings_back.setIcon(qtaicon("mdi6.arrow-left"))
        self.settings_back.setIconSize(QSize(22, 22))
        self.settings_top_bar.addWidget(self.settings_back)

        self.settings_top_bar.addStretch()

        # Create settings page with callback to rebuild pages
        self.settings_pane = SettingsPage()
        self.settings_pane.rebuild.connect(self._rebuild_pages)
        self.settings_layout.addWidget(self.settings_pane)

        self.root_stack.addWidget(self.settings_widget)

        # Shared profile for web pages
        self.shared_profile = QWebEngineProfile("KioskProfile", self)
        self.shared_profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
        logger.info(f"Storage path: {self.shared_profile.persistentStoragePath()}")
        logger.info(f"Cache path: {self.shared_profile.cachePath()}")

        self.web_stack.setFocus()

        # Initial page setup
        self._setup_pages()
        self._setup_shortcuts()
        self._apply_styling()

        # Timers
        self.clock_timer = QTimer()
        self.clock_timer.setInterval(self.settings.get("topbar_update_speed", 1000))
        self.clock_timer.timeout.connect(lambda: self.top_bar_clock.setText(get_time_string(self.settings.get("topbar_12hr", True))))
        self.clock_timer.start()


    def exit_settings(self):
        self.root_stack.setCurrentIndex(0)
        self.settings_pane.save()

    def set_fullscreen(self, fs: bool):
        if fs:
            self.showFullScreen()
        else:
            if self.isFullScreen():
                self.showNormal()
            self.show()

    def _setup_pages(self):
        # Clear existing pages and buttons
        while self.web_stack.count():
            self.web_stack.removeWidget(self.web_stack.widget(0))

        # Clear existing buttons
        for i in reversed(range(self.pages_layout.count())):
            widget = self.pages_layout.itemAt(i).widget()
            self.pages_layout.removeWidget(widget)
            widget.deleteLater()

        if len(self.settings["urls"]) == 0:
            # no pages
            button = QPushButton()
            button.clicked.connect(lambda: self._switch_page(0))
            button.setText("KioskBrowser")
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            button.setObjectName("WebTab")
            self.pages_layout.addWidget(button)

            no_page_widget = QWidget()
            no_page_layout = QVBoxLayout(no_page_widget)

            no_page_icon = QLabel()
            no_page_icon.setPixmap(QPixmap("icon.png").scaled(512, 512, mode=Qt.TransformationMode.SmoothTransformation))
            no_page_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_page_layout.addWidget(no_page_icon)

            no_page_text = QLabel("Welcome to KioskBrowser\nUse Alt+F1 to open settings and add pages")
            no_page_text.setObjectName("NoPagesText")
            no_page_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_page_layout.addWidget(no_page_text)

            self.web_stack.addWidget(no_page_widget)

        # Create new pages and buttons
        for index, (url, label, icon_path) in enumerate(self.settings["urls"]):
            button = QPushButton()
            button.clicked.connect(lambda _, idx=index: self._switch_page(idx))
            button.setText(label)
            button.setIconSize(QSize(16, 16))
            button.setIcon(qtaicon("mdi6.web"))
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            button.setObjectName("WebTab")
            self.pages_layout.addWidget(button)
            self._set_button_icon(button, label, icon_path)

            # Set up the web engine page
            web_page = QWebEngineView()
            page = QWebEnginePage(self.shared_profile, web_page)
            web_page.setPage(page)
            page.load(QUrl(url))

            # Add to the widget stack
            self.web_stack.addWidget(web_page)

        # Ensure the first page is selected initially
        if self.web_stack.count() > 0:
            self._switch_page(0)

    def _rebuild_pages(self):
        """Rebuild pages when settings change."""
        self.settings = KioskBrowserSettings.load_settings()
        self.setWindowTitle(self.settings.get("windowBranding", "Kiosk Browser"))
        self.set_fullscreen(self.settings.get("fullscreen", True))
        self.top_bar_widget.setVisible(self.settings.get("topbar", True))
        self.pages_layout.setContentsMargins(3, 0 if self.settings.get("topbar", True) else 3, 3, 0)
        self._setup_pages()

    def _set_button_icon(self, button: QPushButton, label: str, icon_path: str):
        if icon_path == "@pageicon":
            # Fetch icon asynchronously
            url = self.settings["urls"][self.web_stack.count()][0]
            self._fetch_icon_async(button, label, url)
        elif os.path.exists(icon_path):
            # Use a local icon directly
            button.setIcon(QIcon(icon_path))
        else:
            button.setIcon(qtaicon("mdi6.web"))

    def _fetch_icon_async(self, button: QPushButton, label: str, url: str):
        def update_button_icon(ico: QIcon):
            """Update the button with the fetched icon."""
            if ico:
                button.setIcon(ico)
                logger.info(f"Fetched page icon for {label}")
            else:
                logger.warning(f"No icon available for {label}")
                button.setIcon(qtaicon("mdi6.web"))

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
    rebuild = Signal()

    def __init__(self):
        super().__init__()
        self.settings = KioskBrowserSettings.load_settings()

        self.setWindowTitle("Settings")

        # URL Configuration Section
        self.url_label = QLabel("URL Config:")
        self.url_table = QTableWidget(0, 3)  # 3 columns: URL, Label, Icon
        self.url_table.setHorizontalHeaderLabels(["URL", "Label", "Icon"])
        self.url_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.url_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.url_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._populate_url_table()

        self.add_url_button = QPushButton("Add URL")
        self.add_url_button.setIcon(qtaicon("mdi6.plus"))
        self.add_url_button.setIconSize(QSize(22, 22))
        self.add_url_button.clicked.connect(self._add_url)

        self.remove_url_button = QPushButton("Remove Selected")
        self.remove_url_button.setIcon(qtaicon("mdi6.delete"))
        self.remove_url_button.setIconSize(QSize(22, 22))
        self.remove_url_button.clicked.connect(self._remove_selected_urls)

        self.move_up_button = QPushButton("Move Up")
        self.move_up_button.setIcon(qtaicon("mdi6.triangle"))
        self.move_up_button.setIconSize(QSize(22, 22))
        self.move_up_button.clicked.connect(self._move_up)

        self.move_down_button = QPushButton("Move Down")
        self.move_down_button.setIcon(qtaicon("mdi6.triangle-down"))
        self.move_down_button.setIconSize(QSize(22, 22))
        self.move_down_button.clicked.connect(self._move_down)

        # Other Settings
        self.window_branding_label = QLabel("Window Branding:")
        self.window_branding_input = QLineEdit(self.settings.get("windowBranding", "Kiosk Browser"))

        self.fullscreen_checkbox = QCheckBox("Fullscreen")
        self.fullscreen_checkbox.setChecked(self.settings.get("fullscreen", True))

        self.topbar_group = QGroupBox("Top Bar")
        self.topbar_group.setCheckable(True)
        self.topbar_group.setChecked(self.settings.get("topbar", True))

        self.topbar_layout = QGridLayout()
        self.topbar_group.setLayout(self.topbar_layout)

        self.topbar_12hr = QCheckBox("12-Hour Clock")
        self.topbar_12hr.setChecked(self.settings.get("topbar_12hr", True))
        self.topbar_layout.addWidget(self.topbar_12hr, 0, 0)

        self.topbar_update = LabeledSpinBox("Top Bar Update Speed")
        self.topbar_update.setRange(500, 10000)
        self.topbar_update.setSingleStep(500)
        self.topbar_update.setSuffix("ms")
        self.topbar_update.spin_box.setMaximumWidth(240)
        self.topbar_update.setValue(self.settings.get("topbar_update_speed", 1000))
        self.topbar_layout.addWidget(self.topbar_update, 0, 1)

        # Save Button
        self.save_button = QPushButton("Save")
        self.save_button.setIcon(qtaicon("mdi6.content-save-cog"))
        self.save_button.setIconSize(QSize(22, 22))
        self.save_button.clicked.connect(self.save)

        # Layout
        layout = QVBoxLayout(self)

        url_layout = QHBoxLayout()
        url_layout.addWidget(self.add_url_button)
        url_layout.addWidget(self.remove_url_button)
        url_layout.addWidget(self.move_up_button)
        url_layout.addWidget(self.move_down_button)

        layout.addWidget(self.url_label)
        layout.addWidget(self.url_table)
        layout.addLayout(url_layout)
        layout.addWidget(self.window_branding_label)
        layout.addWidget(self.window_branding_input)
        layout.addWidget(self.fullscreen_checkbox)
        layout.addWidget(self.topbar_group)
        layout.addWidget(self.save_button)

    def _populate_url_table(self):
        """Populate the URL table with current settings."""
        self.url_table.setRowCount(0)
        for url, label, icon in self.settings["urls"]:
            row = self.url_table.rowCount()
            self.url_table.insertRow(row)
            self.url_table.setRowHeight(row, 48)
            self.url_table.verticalHeader().setSectionResizeMode(row, QHeaderView.ResizeMode.Fixed)
            self.url_table.setItem(row, 0, QTableWidgetItem(url))
            self.url_table.setItem(row, 1, QTableWidgetItem(label))
            self.url_table.setItem(row, 2, QTableWidgetItem(icon))

    def _add_url(self):
        """Add a new URL entry."""
        dialog = URLConfigDialog(win)
        if dialog.exec():
            url, label, icon = dialog.get_data()
            row = self.url_table.rowCount()
            self.url_table.insertRow(row)
            self.url_table.setRowHeight(row, 48)
            self.url_table.verticalHeader().setSectionResizeMode(row, QHeaderView.ResizeMode.Fixed)
            self.url_table.setItem(row, 0, QTableWidgetItem(url))
            self.url_table.setItem(row, 1, QTableWidgetItem(label))
            self.url_table.setItem(row, 2, QTableWidgetItem(icon))

    def _remove_selected_urls(self):
        """Remove selected URLs from the table."""
        selected_rows = set(item.row() for item in self.url_table.selectedItems())
        for row in sorted(selected_rows, reverse=True):
            self.url_table.removeRow(row)

    def _move_up(self):
        """Move the selected row up."""
        current_row = self.url_table.currentRow()

        if current_row == -1:
            return

        if current_row > 0:
            self._swap_rows(current_row, current_row - 1)
            self.url_table.selectRow(current_row - 1)

    def _move_down(self):
        """Move the selected row down."""
        current_row = self.url_table.currentRow()

        if current_row == -1:
            return

        if current_row < self.url_table.rowCount() - 1:
            self._swap_rows(current_row, current_row + 1)
            self.url_table.selectRow(current_row + 1)

    def _swap_rows(self, row1, row2):
        """Swap two rows in the table."""
        for col in range(self.url_table.columnCount()):
            item1 = self.url_table.takeItem(row1, col)
            item2 = self.url_table.takeItem(row2, col)
            self.url_table.setItem(row1, col, item2)
            self.url_table.setItem(row2, col, item1)

    def save(self):
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
        self.settings["topbar"] = self.topbar_group.isChecked()
        self.settings["topbar_12hr"] = self.topbar_12hr.isChecked()
        self.settings["topbar_update_speed"] = self.topbar_update.spin_box.value()

        # Save settings
        KioskBrowserSettings.save_settings(self.settings)

        # Trigger page rebuild if callback is set
        self.rebuild.emit()

class URLConfigDialog(QDialog):
    """Dialog for adding or editing a URL entry."""

    def __init__(self, parent=None, url="", label="", icon=""):
        super().__init__(parent=parent)
        self.setWindowTitle("URL Configuration")

        # Inputs for URL and Label
        self.url_input = QLineEdit(url)
        self.label_input = QLineEdit(label)

        self.icon_group = QGroupBox("Icon Settings")

        self.use_favicon_checkbox = QCheckBox("Use Webpage Favicon")
        self.use_favicon_checkbox.setChecked(True)

        self.icon_input = QLineEdit(icon)
        self.icon_input.setEnabled(False)

        self.icon_button = QPushButton("Select Icon")
        self.icon_button.setEnabled(False)

        self.use_favicon_checkbox.toggled.connect(self.toggle_icon_settings)
        self.icon_button.clicked.connect(self.select_icon)

        icon_layout = QHBoxLayout()
        icon_layout.addWidget(self.icon_input)
        icon_layout.addWidget(self.icon_button)

        group_layout = QVBoxLayout()
        group_layout.addWidget(self.use_favicon_checkbox)
        group_layout.addLayout(icon_layout)
        self.icon_group.setLayout(group_layout)

        # OK and Cancel buttons
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        # Layout setup
        layout = QGridLayout()
        layout.addWidget(QLabel("URL:"), 0, 0)
        layout.addWidget(self.url_input, 0, 1)
        layout.addWidget(QLabel("Label:"), 1, 0)
        layout.addWidget(self.label_input, 1, 1)
        layout.addWidget(self.icon_group, 2, 0, 1, 2)
        layout.addWidget(self.ok_button, 3, 0)
        layout.addWidget(self.cancel_button, 3, 1)
        self.setLayout(layout)

        self._apply_styling()

    def _apply_styling(self):
        try:
            with open("style.qss", "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            pass  # If style.qss is not found, skip applying styling

    def toggle_icon_settings(self, checked):
        """Enable or disable icon input and button based on the checkbox state."""
        self.icon_input.setEnabled(not checked)
        self.icon_button.setEnabled(not checked)

    def select_icon(self):
        """Open a file dialog to select an icon."""
        icon_path, _ = QFileDialog.getOpenFileName(
            self, "Select Icon", "",
            "Image Files (*.svg *.png *.jpg *.jpeg *.bmp *.xbm)"
        )
        if icon_path:
            self.icon_input.setText(icon_path)

    def get_data(self):
        """Retrieve the entered data."""
        if self.use_favicon_checkbox.isChecked():
            self.icon_input.setText("@pageicon")

        return self.url_input.text(), self.label_input.text(), self.icon_input.text()

if __name__ == "__main__":
    app = QApplication(sys.argv)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    app.setPalette(palette)

    app.setStyle('Fusion')
    win = MainWindow()
    sys.exit(app.exec())
