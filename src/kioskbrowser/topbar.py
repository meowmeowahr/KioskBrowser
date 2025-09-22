from datetime import datetime
from sys import maxsize

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from psutil import sensors_battery, cpu_percent, virtual_memory

from qtawesome import icon as qta_icon


def get_time_string(twelve: bool = True):
    dt = datetime.now()
    return dt.strftime("%I:%M %p") if twelve else dt.strftime("%H:%M")


def get_battery():
    battery = sensors_battery()
    if not battery:
        return qta_icon("mdi6.battery-off"), "??%"

    percent = round(battery.percent)
    charging = battery.power_plugged

    if percent > 90:
        icon = qta_icon(
            f"mdi6.battery{'-charging' if charging else ''}",
            color="#4CAF50" if charging else "#FFFFFF",
        )
    elif percent > 80:
        icon = qta_icon(
            f"mdi6.battery{'-charging' if charging else ''}-90",
            color="#4CAF50" if charging else "#FFFFFF",
        )
    elif percent > 70:
        icon = qta_icon(
            f"mdi6.battery{'-charging' if charging else ''}-80",
            color="#4CAF50" if charging else "#FFFFFF",
        )
    elif percent > 60:
        icon = qta_icon(
            f"mdi6.battery{'-charging' if charging else ''}-70",
            color="#4CAF50" if charging else "#FFFFFF",
        )
    elif percent > 50:
        icon = qta_icon(
            f"mdi6.battery{'-charging' if charging else ''}-60",
            color="#4CAF50" if charging else "#FFFFFF",
        )
    elif percent > 40:
        icon = qta_icon(
            f"mdi6.battery{'-charging' if charging else ''}-50",
            color="#4CAF50" if charging else "#FFFFFF",
        )
    elif percent > 30:
        icon = qta_icon(
            f"mdi6.battery{'-charging' if charging else ''}-40",
            color="#4CAF50" if charging else "#FFFFFF",
        )
    elif percent > 20:
        icon = qta_icon(
            f"mdi6.battery{'-charging' if charging else ''}-30",
            color="#4CAF50" if charging else "#FFFFFF",
        )
    elif percent > 10 and not charging:
        icon = qta_icon("mdi6.battery-20", color="#F44336")
    elif percent > 10 and charging:
        icon = qta_icon("mdi6.battery-charging-20", color="#4CAF50")
    else:
        icon = qta_icon("mdi6.battery-alert", color="#F44336")

    return icon, f"{percent}%"


def get_cpu():
    return qta_icon(
        "mdi6.cpu-64-bit" if maxsize > 2**32 else "mdi6.cpu-32-bit"
    ), f"{round(cpu_percent())}%"

def get_mem():
    return qta_icon("mdi6.memory"), f"{round(virtual_memory().percent)}%"


class TopBarIconItem(QWidget):
    IconSize = (20, 20)

    def __init__(self, ico: QIcon, text: str = ""):
        super().__init__()

        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.icon = QLabel()
        self.icon.setPixmap(ico.pixmap(*self.IconSize))

        self.text = QLabel(text)

        layout.addWidget(self.icon)
        layout.addWidget(self.text)

    def modify(self, ico: QIcon, text: str):
        self.icon.setPixmap(ico.pixmap(*self.IconSize))
        self.text.setText(text)
