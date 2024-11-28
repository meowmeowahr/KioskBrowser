#!/usr/bin/python

"""
KioskBrowser

A Simple Web Browser that can only browse a single website.
The website is defined in a setings.json file.
You can change the settings by pressing Alt+F1.

"""


from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWebEngineWidgets import *
import sys
import os
import json
import ctypes
import favicon
import requests
import platform
import re


SETTINGS = json.load(open(os.path.dirname(os.path.realpath(__file__)) + "/settings.json"))

VERSION = "0.6.2"

if platform.system() == "Windows" and SETTINGS["useCustomAppString"]:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("KisokBrowser")

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.webEngineView = QWebEngineView(self)
        self.webEngineView.load(QUrl(SETTINGS["urls"][0][0]))
        self.setObjectName("MainWindow")

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.pages = QHBoxLayout()
        self.layout.addLayout(self.pages)

        # load style.qss
        with open(os.path.dirname(os.path.realpath(__file__)) + "/style.qss", "r") as f:
            self.setStyleSheet(f.read())

        # buttons with the pages to switch to
        for i in range(len(SETTINGS["urls"])):
            self.pages.addWidget(QPushButton(SETTINGS["urls"][i][1]))
            self.pages.itemAt(i).widget().clicked.connect(lambda: self.switchPage())
            if SETTINGS["urls"][i][2] == "@pageicon" and not os.path.exists(os.path.dirname(os.path.realpath(__file__)) + "/iconcache"):
                os.makedirs(os.path.dirname(os.path.realpath(__file__)) + "/iconcache")
            
            if SETTINGS["urls"][i][2] == "@pageicon":
                try:
                    filename = SETTINGS["urls"][i][1].replace(" ", "_")
                    # remove all non-alphanumeric characters
                    filename = re.sub(r'\W+', '', filename)
                    if not os.path.exists(os.path.dirname(os.path.realpath(__file__)) + "/iconcache/" + filename + ".png") or os.path.exists(os.path.dirname(os.path.realpath(__file__)) + "/iconcache/" + filename + ".ico"):
                        print("DEBUG: downloading icon for : " + SETTINGS["urls"][i][0])
                        # get the favicon of the page
                        icons = favicon.get(SETTINGS["urls"][i][0])
                        icon = icons[0]
                        # save the icon
                        response = requests.get(icon.url, stream=True)
                        with open(os.path.dirname(os.path.realpath(__file__)) + "/iconcache/" + filename + "." + icon.format, 'wb') as image:
                            for chunk in response.iter_content(1024):
                                image.write(chunk)
                except:
                    print("DEBUG: failed to download icon for : " + SETTINGS["urls"][i][0])

            # set the icon of the button
            # try png
            filename = SETTINGS["urls"][i][1].replace(" ", "_")
            # remove all non-alphanumeric characters
            filename = re.sub(r'\W+', '', filename)

            if os.path.exists(os.path.dirname(os.path.realpath(__file__)) + "/iconcache/" + filename + ".png"):
                self.pages.itemAt(i).widget().setIcon(QIcon(os.path.dirname(os.path.realpath(__file__)) + "/iconcache/" + filename + ".png"))
            elif os.path.exists(os.path.dirname(os.path.realpath(__file__)) + "/iconcache/" + filename + ".ico"):
                self.pages.itemAt(i).widget().setIcon(QIcon(os.path.dirname(os.path.realpath(__file__)) + "/iconcache/" + filename + ".ico"))
            elif SETTINGS["urls"][i][2] != "@pageicon":
                self.pages.itemAt(i).widget().setIcon(QIcon(SETTINGS["urls"][i][2]))
            else:
                self.pages.itemAt(i).widget().setIcon(QIcon(os.path.dirname(os.path.realpath(__file__)) + "/icon.png"))

            # set icon size
            self.pages.itemAt(i).widget().setIconSize(QSize(SETTINGS["iconSize"], SETTINGS["iconSize"]))


        self.layout.addWidget(self.webEngineView)

        if SETTINGS["windowBranding"] == "@pagetitle":
            self.webEngineView.loadFinished.connect(lambda: self.setWindowTitle(self.webEngineView.page().title()))
        else:
            self.setWindowTitle(SETTINGS["windowBranding"])

        if SETTINGS["windowIcon"] == "@pageicon":
            self.webEngineView.iconChanged.connect(lambda: self.setWindowIcon(self.webEngineView.icon()))


        # create a keyboard shortcut for Alt+F1 and Alt+F3 (F2 is taken by the Raspberry Pi OS Run Prompt)
        self.altF1 = QShortcut(QKeySequence("Alt+F1"), self)
        self.altF1.activated.connect(self.showSettings)

        self.altF3 = QShortcut(QKeySequence("Alt+F3"), self)
        self.altF3.activated.connect(self.showDbg)


    def showSettings(self):
        settings.show()

    def showDbg(self):
        debugwindow.show()

    def switchPage(self):
        # get the index of the button that was clicked
        index = self.pages.indexOf(self.sender())
        print("DEBUG: switching to page " + str(index))
        self.webEngineView.load(QUrl(SETTINGS["urls"][index][0]))

class SplashScreen(QMainWindow):
    # A splash screen that for the app that lasts SETTINGS["splashTime"] seconds
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        pixmap = QPixmap(os.path.dirname(os.path.realpath(__file__)) + "/splash.svg")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        print("DEBUG: Page Loading")
        self.setFixedSize(pixmap.width(), pixmap.height())
        img = QLabel()
        img.setPixmap(pixmap)
        self.setCentralWidget(img)
        self.center()

        # show app version at bottom of splash (640x480)
        self.versionLabel = QLabel(self)
        self.versionLabel.setText("Version: " + VERSION)
        # size of version label
        self.versionLabel.setStyleSheet("font-size: 14px;")
        self.versionLabel.move(640 - self.versionLabel.width(), 480 - self.versionLabel.height())

        # programed site
        self.siteLabel = QLabel(self)
        self.siteLabel.setText("Site: " + SETTINGS["urls"][0][0])
        self.siteLabel.setMinimumWidth(300)
        self.siteLabel.setStyleSheet("font-size: 14px;")
        # move to left of version label
        self.siteLabel.move(10, 480 - self.siteLabel.height())

        
        # show for SETTINGS["splashTime"] seconds
        self.show()
        QTimer.singleShot(SETTINGS["splashTime"]*1000, self.done)

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def done(self):
        print("DEBUG: Window Opened")
        # open window
        if SETTINGS["fullscreen"]:
            window.showFullScreen()
        else:
            window.show()
        # close splash screen
        self.close()

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Settings")

        self.windowBrandingLabel = QLabel("Window Branding:")
        self.windowBrandingLineEdit = QLineEdit()
        self.windowBrandingLineEdit.setText(SETTINGS["windowBranding"])
        self.windowBrandingLineEdit.setPlaceholderText("Kiosk Browser")

        self.windowIconLabel = QLabel("Window Icon:")
        self.windowIconLineEdit = QLineEdit()
        self.windowIconLineEdit.setText(SETTINGS["windowIcon"])
        self.windowIconLineEdit.setPlaceholderText("@pageicon")

        self.urlLabel = QLabel("URL Config:")

        self.urlButton = QPushButton("Comming Soon")
        self.urlButton.setEnabled(False)
        self.urlButton.clicked.connect(self.openUrlConfig)

        self.fullscreenCheckBox = QCheckBox("Fullscreen")
        self.fullscreenCheckBox.setChecked(SETTINGS["fullscreen"])

        self.saveButton = QPushButton("Save")
        self.saveButton.clicked.connect(self.saveSettings)

        layout = QGridLayout()
        layout.addWidget(self.urlLabel, 0, 0)
        layout.addWidget(self.urlButton, 0, 1)
        layout.addWidget(self.windowBrandingLabel, 1, 0)
        layout.addWidget(self.windowBrandingLineEdit, 1, 1)
        layout.addWidget(self.windowIconLabel, 2, 0)
        layout.addWidget(self.windowIconLineEdit, 2, 1)
        layout.addWidget(self.fullscreenCheckBox, 3, 0)
        layout.addWidget(self.saveButton, 4, 0, 1, 2)
        self.setLayout(layout)

    def saveSettings(self):
        SETTINGS["windowBranding"] = self.windowBrandingLineEdit.text()
        SETTINGS["windowIcon"] = self.windowIconLineEdit.text()
        SETTINGS["fullscreen"] = self.fullscreenCheckBox.isChecked()
        json.dump(SETTINGS, open("settings.json", "w"), indent=4)
        self.close()

    def openUrlConfig(self):
        #urlconfig.show()
        pass

class DebugingWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # a way to refresh the page, minimize, maximize, and close the window
        self.setWindowTitle("Debuging Window")

        self.layout = QGridLayout()
        self.setLayout(self.layout)

        self.refreshButton = QPushButton("Refresh")
        self.refreshButton.clicked.connect(lambda: window.webEngineView.reload())
        self.layout.addWidget(self.refreshButton, 0, 0)

        self.minimizeButton = QPushButton("Minimize")
        self.minimizeButton.clicked.connect(lambda: window.showMinimized())
        self.layout.addWidget(self.minimizeButton, 0, 1)

        self.maximizeButton = QPushButton("Maximize (No FS)")
        self.maximizeButton.clicked.connect(lambda: window.showMaximized())
        self.layout.addWidget(self.maximizeButton, 0, 2)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    splash = SplashScreen()
    settings = SettingsPage()
    debugwindow = DebugingWindow()
    sys.exit(app.exec_())