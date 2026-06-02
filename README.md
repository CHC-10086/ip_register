# IP Register - LAN IP Registration System

A Flask-based LAN IP address management system with automatic device discovery, port scanning, and conflict detection.

## Features

- **Auto Scan**: ARP/Ping scan to discover devices, get IP, MAC, vendor info
- **Port Scan**: 170+ common ports across 18 categories
- **Device Registration**: Auto-fill from scan results, manual edit
- **Conflict Detection**: IP/MAC conflict alerts
- **Web Dashboard**: Device list, quick access to services
- **System Tray**: Run in background with tray icon
- **Auto Start**: Windows boot startup control

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run

**With System Tray Icon (Recommended):**
```
Double-click start.bat
```
- Blue "IP" icon appears in system tray (bottom-right)
- Double-click icon or right-click -> "Open Dashboard"
- Right-click -> "Quit" to exit

**Console mode:**
```bash
python app.py
```

**Stop:**
```
Right-click tray icon -> Quit
```
Or double-click `stop.bat`

### 3. Access

Open browser: http://127.0.0.1:8088

## System Tray

When running with `start.bat`:
- A blue "IP" icon appears in the system tray
- **Double-click**: Open dashboard in browser
- **Right-click menu**:
  - Open Dashboard
  - Quit

## Auto Start

Control from dashboard:
- Toggle "Auto Start" switch in the "Service Control" card
- This adds/removes Windows registry entry for boot startup
- App will start with system tray icon on boot

## Npcap (Optional)

For ARP scanning (gets MAC address and vendor info):

1. Download: https://npcap.com/#download
2. Install with "WinPcap API-compatible Mode" enabled
3. Restart the application

Or run: `install_npcap.bat`

Without Npcap, the system uses Ping scanning (no MAC info).

## Project Structure

```
ip_register/
├── app.py                  # Flask entry point
├── tray.py                 # System tray icon
├── config.py               # Configuration
├── requirements.txt        # Python dependencies
├── start.bat               # Start with tray icon
├── stop.bat                # Stop service
├── install_npcap.bat       # Npcap installer
├── README.md
├── models/
│   ├── database.py         # SQLite database
│   └── device.py           # Device model & CRUD
├── services/
│   ├── scanner.py          # ARP/Ping/Port scanner
│   ├── conflict.py         # IP conflict detection
│   ├── notification.py     # Alert service
│   └── mac_vendor.py       # MAC vendor lookup
├── routes/
│   ├── api.py              # REST API endpoints
│   └── views.py            # Page routes
├── templates/              # HTML templates
└── utils/
    └── network.py          # Network utilities
```

## Configuration

Edit `config.py`:

```python
SCAN_SUBNET = '192.168.1.0/24'  # Default scan subnet
SCAN_TIMEOUT = 2                 # Scan timeout (seconds)
PORT_SCAN_TIMEOUT = 0.5          # Port scan timeout
CUSTOM_PORTS = '9100,9200'       # Additional custom ports
```

## Notes

- ARP scan requires admin/root privileges
- Ping scan works without special permissions
- Port scan covers 170+ common ports
- Data stored in SQLite: `data/ip_register.db`
