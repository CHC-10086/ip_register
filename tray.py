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
            import psutil
            if psutil.pid_exists(pid):
                return True
        except (ValueError, FileNotFoundError, ImportError):
            pass
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
    draw.ellipse([4, 4, width-4, height-4], fill='#0d6efd', outline='white', width=2)
    bbox = draw.textbbox((0, 0), "IP", anchor="lt")
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2 - 4
    draw.text((x, y), "IP", fill='white')
    return image


def start_flask():
    """Start Flask app on port 8088"""
    from app import create_app
    app = create_app()
    app.run(host='0.0.0.0', port=8088, debug=False, use_reloader=False)


def start_redirect():
    """Simple HTTP redirect on port 80"""
    import socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind(('0.0.0.0', 80))
        server.listen(5)
        while True:
            conn, addr = server.accept()
            try:
                conn.recv(1024)
                response = 'HTTP/1.1 302 Found\r\nLocation: http://ip.local:8088/\r\nConnection: close\r\n\r\n'
                conn.sendall(response.encode())
            except:
                pass
            finally:
                conn.close()
    except Exception as e:
        print(f"Port 80 redirect failed: {e}")
    finally:
        server.close()


def open_dashboard(icon=None, item=None):
    """Open dashboard in browser"""
    webbrowser.open('http://ip.local:8088')


def quit_app(icon=None, item=None):
    """Quit the application"""
    remove_lock()
    if icon:
        icon.stop()
    os._exit(0)


def setup_icon():
    """Setup system tray icon"""
    global icon, flask_thread

    if is_already_running():
        ctypes.windll.user32.MessageBoxW(
            0,
            "IP Register is already running.\nCheck the system tray icon.",
            "IP Register",
            0x40
        )
        sys.exit(0)

    write_lock()

    # Start Flask on 8088
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    # Start redirect on 80 (may fail if port is in use)
    redirect_thread = threading.Thread(target=start_redirect, daemon=True)
    redirect_thread.start()

    menu = pystray.Menu(
        MenuItem('Open Dashboard', open_dashboard, default=True),
        MenuItem('Quit', quit_app),
    )

    icon = Icon(
        'IPRegister',
        create_icon_image(),
        'IP Register - Running',
        menu
    )

    icon.run()


if __name__ == '__main__':
    setup_icon()
