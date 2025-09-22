import os.path

from loguru import logger
import sys

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QStackedWidget,
    QSizePolicy,
    QMainWindow,
)
from PySide6.QtCore import (
    QUrl,
    QSize,
    Qt,
    QTimer,
    QFile,
    QIODevice,
)
from PySide6.QtGui import (
    QIcon,
    QKeySequence,
    QShortcut,
    QPixmap,
    QImage,
    QPalette,
    QColor,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEnginePage

from qtawesome import icon as qta_icon

from kioskbrowser.topbar import TopBarIconItem, get_battery, get_time_string, get_cpu, get_mem
from kioskbrowser.settings import KioskBrowserSettings, SettingsPage

from kioskbrowser.resources import qInitResources

VERSION = "1.0.0"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = KioskBrowserSettings.load_settings()

        self.setObjectName("MainWindow")
        self.setWindowTitle(self.settings["windowBranding"])
        self.setWindowIcon(QIcon(":/images/icon.png"))

        self.set_fullscreen(self.settings.get("fullscreen", True))

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

        self.top_bar_mem = TopBarIconItem(*get_mem())
        self.top_bar_mem.setObjectName("MemWidget")
        self.top_bar_mem.setVisible(self.settings.get("topbar_mem", False))
        self.top_bar_layout.addWidget(self.top_bar_mem)

        self.top_bar_cpu = TopBarIconItem(*get_cpu())
        self.top_bar_cpu.setObjectName("CpuWidget")
        self.top_bar_cpu.setVisible(self.settings.get("topbar_cpu", False))
        self.top_bar_layout.addWidget(self.top_bar_cpu)

        self.top_bar_battery = TopBarIconItem(*get_battery())
        self.top_bar_battery.setObjectName("BatteryWidget")
        self.top_bar_battery.setVisible(self.settings.get("topbar_battery", False))
        self.top_bar_layout.addWidget(self.top_bar_battery)

        self.top_bar_clock = QLabel(
            get_time_string(self.settings.get("topbar_12hr", True))
        )
        self.top_bar_clock.setObjectName("ClockWidget")
        self.top_bar_layout.addWidget(self.top_bar_clock)

        self.pages_layout = QHBoxLayout()
        self.pages_layout.setContentsMargins(
            3, 0 if self.settings.get("topbar", True) else 3, 3, 0
        )
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
        self.settings_back.setIcon(qta_icon("mdi6.arrow-left"))
        self.settings_back.setIconSize(QSize(22, 22))
        self.settings_top_bar.addWidget(self.settings_back)

        self.settings_top_bar.addStretch()

        self.settings_top_bar_version = QLabel(f"Version: {VERSION}")
        self.settings_top_bar.addWidget(self.settings_top_bar_version)

        # Create settings page with callback to rebuild pages
        self.settings_pane = SettingsPage(self)
        self.settings_pane.rebuild.connect(self._rebuild_pages)
        self.settings_layout.addWidget(self.settings_pane)

        self.root_stack.addWidget(self.settings_widget)

        # Shared profile for web pages
        self.shared_profile = QWebEngineProfile("KioskProfile", self)
        self.shared_profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies
        )
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
        self.clock_timer.timeout.connect(self.topbar_update)
        self.clock_timer.start()

    def topbar_update(self):
        self.top_bar_clock.setText(
            get_time_string(self.settings.get("topbar_12hr", True))
        )
        self.top_bar_battery.modify(*get_battery())
        self.top_bar_cpu.modify(*get_cpu())
        self.top_bar_mem.modify(*get_mem())

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
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            button.setObjectName("WebTab")
            self.pages_layout.addWidget(button)

            no_page_widget = QWidget()
            no_page_layout = QVBoxLayout(no_page_widget)

            no_page_icon = QLabel()
            no_page_icon.setPixmap(
                QPixmap(":/images/icon.png").scaled(
                    512, 512, mode=Qt.TransformationMode.SmoothTransformation
                )
            )
            no_page_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_page_layout.addWidget(no_page_icon)

            no_page_text = QLabel(
                "Welcome to KioskBrowser\nUse Shift+F1 to open settings and add pages"
            )
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
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
            button.setObjectName("WebTab")
            self.pages_layout.addWidget(button)

            # Set up the web engine page
            web_page = QWebEngineView()
            page = QWebEnginePage(self.shared_profile, web_page)
            web_page.setPage(page)
            page.iconChanged.connect(
                lambda icon, b=button, l=label: self._update_button_icon(b, icon, l)
            )
            button.setIcon(qta_icon("mdi6.web"))  # Default icon

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
        self.top_bar_battery.setVisible(self.settings.get("topbar_battery", False))
        self.top_bar_cpu.setVisible(self.settings.get("topbar_cpu", False))
        self.top_bar_mem.setVisible(self.settings.get("topbar_mem", False))
        self.pages_layout.setContentsMargins(
            3, 0 if self.settings.get("topbar", True) else 3, 3, 0
        )
        self._setup_pages()

    def _update_button_icon(self, button: QPushButton, icon: QIcon, label: str):
        """Update button icon when page icon changes."""
        if not icon.isNull():
            button.setIcon(icon)
            logger.info(f"Fetched page icon for {label}")

    def _switch_page(self, index: int):
        logger.debug(f"Switching to page {index}")
        self.web_stack.setCurrentIndex(index)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Shift+F1"), self).activated.connect(self._show_settings)

    def _apply_styling(self):
        file = QFile(":/styles/style.qss")
        if file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
            self.setStyleSheet(bytes(file.readAll().data()).decode("utf-8"))
            file.close()

    def _show_settings(self):
        logger.info("Opening settings window.")
        self.root_stack.setCurrentIndex(1)

    def changeEvent(self, event):
        if self.settings.get("fullscreen", True):
            if not self.isFullScreen():
                self.showFullScreen()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    qInitResources()

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    app.setPalette(palette)
    app.setStyle("Fusion")

    win = MainWindow()
    sys.exit(app.exec())
