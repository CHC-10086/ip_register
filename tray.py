import os
import sys
import threading
import webbrowser
import ctypes
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem, Icon

LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.lock')


def is_already_running():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            import psutil
            if psutil.pid_exists(pid):
                return True
        except:
            pass
        try:
            os.remove(LOCK_FILE)
        except:
            pass
    return False


def write_lock():
    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except:
        pass


def remove_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except:
        pass


def create_icon_image():
    width = 64
    height = 64
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse([4, 4, width-4, height-4], fill='#0d6efd', outline='white', width=2)
    bbox = draw.textbbox((0, 0), "IP", anchor="lt")
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2 - 4
    draw.text((x, y), "IP", fill='white')
    return image


def start_flask():
    from app import create_app
    app = create_app()
    app.run(host='0.0.0.0', port=80, debug=False, use_reloader=False)


def open_dashboard(icon=None, item=None):
    webbrowser.open('http://ip')


def quit_app(icon=None, item=None):
    remove_lock()
    if icon:
        icon.stop()
    os._exit(0)


def setup_icon():
    if is_already_running():
        ctypes.windll.user32.MessageBoxW(0, "IP Register is already running.", "IP Register", 0x40)
        sys.exit(0)

    write_lock()

    threading.Thread(target=start_flask, daemon=True).start()

    menu = pystray.Menu(
        MenuItem('Open Dashboard', open_dashboard, default=True),
        MenuItem('Quit', quit_app),
    )

    icon = Icon('IPRegister', create_icon_image(), 'IP Register', menu)
    icon.run()


if __name__ == '__main__':
    setup_icon()
