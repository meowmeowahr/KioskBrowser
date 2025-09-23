import ctypes

SW_HIDE = 0
SW_SHOW = 5

FindWindow = ctypes.windll.user32.FindWindowW
ShowWindow = ctypes.windll.user32.ShowWindow

taskbar = FindWindow("Shell_TrayWnd", None)
Start = FindWindow("Button", None)

def windows_api_hide_taskbar():
    ShowWindow(taskbar, SW_HIDE)
    ShowWindow(Start, SW_HIDE)

def windows_api_show_taskbar():
    ShowWindow(taskbar, SW_SHOW)
    ShowWindow(Start, SW_SHOW)
