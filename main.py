import os.path

from loguru import logger
import sys
import requests
import favicon

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
    QThreadPool,
    QRunnable,
    QTimer,
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

from topbar import TopBarIconItem, get_battery, get_time_string, get_cpu
from settings import KioskBrowserSettings, SettingsPage

VERSION = "1.0.0"


def resource_path(relative_path) -> str | bytes:
    """Get absolute path to resource, works for dev and PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores files there
        # noinspection PyUnresolvedReferences
        # noinspection PyProtectedMember
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


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
                    self.callback(
                        QIcon(
                            QPixmap(QImage.fromData(response.content)).scaled(
                                32, 32, mode=Qt.TransformationMode.SmoothTransformation
                            )
                        )
                    )
                    return
        except Exception as e:
            logger.warning(f"Failed to fetch page icon for {self.url}: {e}")

        # If we fail to fetch the icon, call the callback with None
        self.callback(None)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = KioskBrowserSettings.load_settings()

        self.setObjectName("MainWindow")
        self.setWindowTitle(self.settings["windowBranding"])
        self.setWindowIcon(QIcon(resource_path("icon.png")))

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
                QPixmap(resource_path("icon.png")).scaled(
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
            button.setIcon(qta_icon("mdi6.web"))
            button.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
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
        self.top_bar_battery.setVisible(self.settings.get("topbar_battery", False))
        self.top_bar_cpu.setVisible(self.settings.get("topbar_cpu", False))
        self.pages_layout.setContentsMargins(
            3, 0 if self.settings.get("topbar", True) else 3, 3, 0
        )
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
            button.setIcon(qta_icon("mdi6.web"))

    def _fetch_icon_async(self, button: QPushButton, label: str, url: str):
        def update_button_icon(ico: QIcon):
            """Update the button with the fetched icon."""
            if ico:
                button.setIcon(ico)
                logger.info(f"Fetched page icon for {label}")
            else:
                logger.warning(f"No icon available for {label}")
                button.setIcon(qta_icon("mdi6.web"))

        # Start the worker to fetch the icon
        worker = IconFetchWorker(url, update_button_icon)
        self.thread_pool.start(worker)

    def _switch_page(self, index: int):
        logger.debug(f"Switching to page {index}")
        self.web_stack.setCurrentIndex(index)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Shift+F1"), self).activated.connect(self._show_settings)

    def _apply_styling(self):
        with open(resource_path("style.qss"), "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())

    def _show_settings(self):
        logger.info("Opening settings window.")
        self.root_stack.setCurrentIndex(1)

    def changeEvent(self, event):
        if self.settings.get("fullscreen", True):
            if not self.isFullScreen():
                self.showFullScreen()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
    app.setPalette(palette)
    app.setStyle("Fusion")

    win = MainWindow()
    sys.exit(app.exec())
