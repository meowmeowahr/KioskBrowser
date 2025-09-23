import platform


def lockdown(options: dict):
    if platform.system() == "Windows":
        from kioskbrowser.lockdown.winapi import windows_api_hide_taskbar
        if options.get("lockdown_windows_hide_taskbar", False):
            windows_api_hide_taskbar()

def unlock():
    if platform.system() == "Windows":
        from kioskbrowser.lockdown.winapi import windows_api_show_taskbar
        windows_api_show_taskbar()
