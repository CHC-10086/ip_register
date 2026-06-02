import os
import sys
import threading
import webbrowser
import ctypes
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem, Icon

# Global reference
flask_thread = None
icon = None
LOCK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.lock')


def is_already_running():
    """Check if another instance is already running"""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            # Check if process is still alive
            import psutil
            if psutil.pid_exists(pid):
                return True
        except (ValueError, FileNotFoundError, ImportError):
            pass
        # Lock file exists but process is dead, remove it
        try:
            os.remove(LOCK_FILE)
        except:
            pass
    return False


def write_lock():
    """Write current PID to lock file"""
    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(str(os.getpid()))
    except:
        pass


def remove_lock():
    """Remove lock file"""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except:
        pass


def create_icon_image():
    """Create a simple icon image"""
    width = 64
    height = 64
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # Draw a blue circle with "IP" text
    draw.ellipse([4, 4, width-4, height-4], fill='#0d6efd', outline='white', width=2)

    # Draw "IP" text
    bbox = draw.textbbox((0, 0), "IP", anchor="lt")
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2 - 4
    draw.text((x, y), "IP", fill='white')

    return image


def start_flask():
    """Start Flask app in background thread"""
    from app import create_app
    app = create_app()
    app.run(host='0.0.0.0', port=8088, debug=False, use_reloader=False)


def start_redirect():
    """Start redirect server on port 80"""
    try:
        from redirect import app as redirect_app
        redirect_app.run(host='0.0.0.0', port=80, debug=False)
    except Exception:
        pass  # Port 80 may be in use, ignore


def open_dashboard(icon=None, item=None):
    """Open dashboard in browser"""
    webbrowser.open('http://127.0.0.1:8088')


def quit_app(icon=None, item=None):
    """Quit the application"""
    remove_lock()
    if icon:
        icon.stop()
    os._exit(0)


def setup_icon():
    """Setup system tray icon"""
    global icon, flask_thread

    # Check if already running
    if is_already_running():
        # Show message and exit
        ctypes.windll.user32.MessageBoxW(
            0,
            "IP Register is already running.\nCheck the system tray icon.",
            "IP Register",
            0x40  # MB_ICONINFORMATION
        )
        sys.exit(0)

    # Write lock file
    write_lock()

    # Start Flask in background
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    # Start redirect server on port 80
    redirect_thread = threading.Thread(target=start_redirect, daemon=True)
    redirect_thread.start()

    # Create menu
    menu = pystray.Menu(
        MenuItem('Open Dashboard', open_dashboard, default=True),
        MenuItem('Quit', quit_app),
    )

    # Create icon
    icon = Icon(
        'IPRegister',
        create_icon_image(),
        'IP Register - Running',
        menu
    )

    # Run icon
    icon.run()


if __name__ == '__main__':
    setup_icon()
