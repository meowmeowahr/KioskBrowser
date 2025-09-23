from typing import Any

from PySide6.QtCore import Signal, QSettings, QSize
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QTableWidget,
    QHeaderView,
    QAbstractItemView,
    QPushButton,
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QVBoxLayout,
    QSpinBox,
    QLineEdit,
    QHBoxLayout,
    QTableWidgetItem,
    QDialog,
    QFileDialog,
)
from loguru import logger
import platform

from qtawesome import icon as qta_icon


class KioskBrowserSettings:
    """Manages the settings using QSettings."""

    DEFAULT_SETTINGS = {
        "urls": [],
        "windowBranding": "Kiosk Browser",
        "fullscreen": True,
        "topbar": True,
        "topbar_12hr": True,
        "topbar_battery": False,
        "topbar_cpu": False,
        "topbar_mem": False,
        "topbar_update_speed": 1000,
        "lockdown": False,
        "lockdown_always_on_top": False,
        "lockdown_windows_hide_taskbar": False,
        "linux_wayland_experimental": False,
    }

    @classmethod
    def load_settings(cls) -> dict[str, Any]:
        """Loads settings using QSettings and applies defaults for missing keys."""
        settings = QSettings("meowmeowahr", "KioskBrowser")
        loaded_settings = {
            key: settings.value(key, default, type=type(default))
            for key, default in cls.DEFAULT_SETTINGS.items()
        }
        logger.debug("Settings loaded: {}", loaded_settings)
        return loaded_settings

    @classmethod
    def save_settings(cls, settings: dict[str, Any]) -> None:
        """Saves the given settings using QSettings."""
        qsettings = QSettings("meowmeowahr", "KioskBrowser")
        for key, value in settings.items():
            qsettings.setValue(key, value)
        logger.info("Settings saved: {}", settings)


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


class SettingsPage(QWidget):
    rebuild = Signal()

    def __init__(self, parent=None):
        super().__init__()
        self.settings = KioskBrowserSettings.load_settings()

        self.window = parent

        self.setWindowTitle("Settings")

        # URL Configuration Section
        self.url_label = QLabel("URL Config:")
        self.url_table = QTableWidget(0, 2)  # 2 columns: URL, Label
        self.url_table.setHorizontalHeaderLabels(["URL", "Label"])
        self.url_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.url_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectItems
        )
        self.url_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._populate_url_table()

        self.add_url_button = QPushButton("Add URL")
        self.add_url_button.setIcon(qta_icon("mdi6.plus"))
        self.add_url_button.setIconSize(QSize(22, 22))
        self.add_url_button.clicked.connect(self._add_url)

        self.remove_url_button = QPushButton("Remove Selected")
        self.remove_url_button.setIcon(qta_icon("mdi6.delete"))
        self.remove_url_button.setIconSize(QSize(22, 22))
        self.remove_url_button.clicked.connect(self._remove_selected_urls)

        self.move_up_button = QPushButton("Move Up")
        self.move_up_button.setIcon(qta_icon("mdi6.triangle"))
        self.move_up_button.setIconSize(QSize(22, 22))
        self.move_up_button.clicked.connect(self._move_up)

        self.move_down_button = QPushButton("Move Down")
        self.move_down_button.setIcon(qta_icon("mdi6.triangle-down"))
        self.move_down_button.setIconSize(QSize(22, 22))
        self.move_down_button.clicked.connect(self._move_down)

        # Other Settings
        self.window_branding_label = QLabel("Window Branding:")
        self.window_branding_input = QLineEdit(
            self.settings.get("windowBranding", "Kiosk Browser")
        )

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

        self.topbar_battery = QCheckBox("Laptop Battery")
        self.topbar_battery.setChecked(self.settings.get("topbar_battery", False))
        self.topbar_layout.addWidget(self.topbar_battery, 1, 0)

        self.topbar_cpu = QCheckBox("CPU Usage")
        self.topbar_cpu.setChecked(self.settings.get("topbar_cpu", False))
        self.topbar_layout.addWidget(self.topbar_cpu, 2, 0)

        self.topbar_mem = QCheckBox("Memory Usage")
        self.topbar_mem.setChecked(self.settings.get("topbar_mem", False))
        self.topbar_layout.addWidget(self.topbar_mem, 3, 0)

        self.topbar_update = LabeledSpinBox("Top Bar Update Speed")
        self.topbar_update.setRange(500, 10000)
        self.topbar_update.setSingleStep(500)
        self.topbar_update.setSuffix("ms")
        self.topbar_update.spin_box.setMaximumWidth(240)
        self.topbar_update.setValue(self.settings.get("topbar_update_speed", 1000))
        self.topbar_layout.addWidget(self.topbar_update, 5, 0)

        # Lockdown Group
        self.lockdown_group = QGroupBox("System Lockdown")
        self.lockdown_group.setCheckable(True)
        self.lockdown_group.setChecked(self.settings.get("lockdown", False))
        self.lockdown_layout = QGridLayout()
        self.lockdown_group.setLayout(self.lockdown_layout)
        self.lockdown_notice = QLabel(
            "Changes to lockdown settings require an application restart to take effect."
        )
        self.lockdown_layout.addWidget(self.lockdown_notice, 0, 0, 1, 2)

        self.lockdown_items: list[QWidget] = []

        self.lockdown_always_on_top = QCheckBox("Always on Top")
        self.lockdown_always_on_top.setChecked(
            self.settings.get("lockdown_always_on_top", False)
        )
        self.lockdown_items.append(self.lockdown_always_on_top)

        if platform.system() == "Windows":
            self.lockdown_windows_hide_taskbar = QCheckBox("Hide Taskbar")
            self.lockdown_windows_hide_taskbar.setChecked(
                self.settings.get("lockdown_windows_hide_taskbar", False)
            )
            self.lockdown_items.append(self.lockdown_windows_hide_taskbar)

        for i, item in enumerate(self.lockdown_items):
            self.lockdown_layout.addWidget(item, i // 2 + 1, i % 2)

        self.linux_wayland_experimental = QCheckBox("Linux Wayland Experimental")
        self.linux_wayland_experimental.setChecked(
            self.settings.get("linux_wayland_experimental", False)
        )
        self.linux_wayland_experimental.setVisible(platform.system() == "Linux")

        # Save Button
        self.save_button = QPushButton("Save")
        self.save_button.setIcon(qta_icon("mdi6.content-save-cog"))
        self.save_button.setIconSize(QSize(22, 22))
        self.save_button.clicked.connect(self.save)

        # #############
        # Main Layout
        # #############
        main_layout = QHBoxLayout(self)

        # Left column
        left_column = QWidget()
        left_layout = QVBoxLayout(left_column)
        main_layout.addWidget(left_column)

        url_buttons_layout = QHBoxLayout()
        url_buttons_layout.addWidget(self.add_url_button)
        url_buttons_layout.addWidget(self.remove_url_button)
        url_buttons_layout.addWidget(self.move_up_button)
        url_buttons_layout.addWidget(self.move_down_button)

        left_layout.addWidget(self.url_label)
        left_layout.addWidget(self.url_table)
        left_layout.addLayout(url_buttons_layout)

        # Right column
        right_column = QWidget()
        right_layout = QVBoxLayout(right_column)
        main_layout.addWidget(right_column)

        right_layout.addWidget(self.window_branding_label)
        right_layout.addWidget(self.window_branding_input)
        right_layout.addWidget(self.fullscreen_checkbox)
        right_layout.addWidget(self.topbar_group)
        right_layout.addWidget(self.lockdown_group)
        right_layout.addWidget(self.linux_wayland_experimental)
        right_layout.addStretch()
        right_layout.addWidget(self.save_button)

    def _populate_url_table(self):
        """Populate the URL table with current settings."""
        self.url_table.setRowCount(0)
        for url, label, *_ in self.settings["urls"]: # *_ is kept for backward compatibility with >1.0.0
            row = self.url_table.rowCount()
            self.url_table.insertRow(row)
            self.url_table.setRowHeight(row, 48)
            self.url_table.verticalHeader().setSectionResizeMode(
                row, QHeaderView.ResizeMode.Fixed
            )
            self.url_table.setItem(row, 0, QTableWidgetItem(url))
            self.url_table.setItem(row, 1, QTableWidgetItem(label))

    def _add_url(self):
        """Add a new URL entry."""
        dialog = URLConfigDialog(self.window)
        if dialog.exec():
            url, label = dialog.get_data()
            row = self.url_table.rowCount()
            self.url_table.insertRow(row)
            self.url_table.setRowHeight(row, 48)
            self.url_table.verticalHeader().setSectionResizeMode(
                row, QHeaderView.ResizeMode.Fixed
            )
            self.url_table.setItem(row, 0, QTableWidgetItem(url))
            self.url_table.setItem(row, 1, QTableWidgetItem(label))

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
            urls.append([url, label, "@pageicon"])
        self.settings["urls"] = urls

        # Update other settings
        self.settings["windowBranding"] = self.window_branding_input.text()
        self.settings["fullscreen"] = self.fullscreen_checkbox.isChecked()
        self.settings["topbar"] = self.topbar_group.isChecked()
        self.settings["topbar_12hr"] = self.topbar_12hr.isChecked()
        self.settings["topbar_battery"] = self.topbar_battery.isChecked()
        self.settings["topbar_cpu"] = self.topbar_cpu.isChecked()
        self.settings["topbar_mem"] = self.topbar_mem.isChecked()
        self.settings["topbar_update_speed"] = self.topbar_update.spin_box.value()

        # Update lockdown settings
        self.settings["lockdown"] = self.lockdown_group.isChecked()
        self.settings["lockdown_always_on_top"] = self.lockdown_always_on_top.isChecked()
        if platform.system() == "Windows":
            self.settings[
                "lockdown_windows_hide_taskbar"
            ] = self.lockdown_windows_hide_taskbar.isChecked()

        self.settings["linux_wayland_experimental"] = self.linux_wayland_experimental.isChecked()

        # Save settings
        KioskBrowserSettings.save_settings(self.settings)

        # Trigger page rebuild if callback is set
        self.rebuild.emit()


class URLConfigDialog(QDialog):
    """Dialog for adding or editing a URL entry."""

    def __init__(self, parent=None, url="", label=""):
        super().__init__(parent=parent)
        self.setWindowTitle("URL Configuration")

        # Inputs for URL and Label
        self.url_input = QLineEdit(url)
        self.label_input = QLineEdit(label)

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
        layout.addWidget(self.ok_button, 2, 0)
        layout.addWidget(self.cancel_button, 2, 1)
        self.setLayout(layout)

        self._apply_styling()

    def _apply_styling(self):
        try:
            with open("style.qss", "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            pass  # If style.qss is not found, skip applying styling

    def get_data(self):
        """Retrieve the entered data."""
        return self.url_input.text(), self.label_input.text()
