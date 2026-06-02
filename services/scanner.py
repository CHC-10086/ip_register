import os
import json
import time
import socket
import threading
import subprocess
import platform
import ipaddress
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from scapy.all import ARP, Ether, srp, conf
    SCAPY_AVAILABLE = True
except ImportError:
    SCAPY_AVAILABLE = False

from models.database import get_db
from models.device import DeviceRepository
from services.mac_vendor import MacVendorLookup
from services.conflict import ConflictDetector
from services.notification import NotificationService

# Windows subprocess flag
CREATE_NO_WINDOW = 0x08000000 if platform.system().lower() == 'windows' else 0

# 端口服务名
PORT_NAMES = {
    21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP', 53: 'DNS',
    80: 'HTTP', 110: 'POP3', 135: 'RPC', 139: 'NetBIOS', 143: 'IMAP',
    443: 'HTTPS', 445: 'SMB', 993: 'IMAPS', 995: 'POP3S',
    1433: 'MSSQL', 1521: 'Oracle', 3306: 'MySQL', 3389: 'RDP',
    5432: 'PostgreSQL', 5900: 'VNC', 6379: 'Redis',
    8080: 'HTTP', 8443: 'HTTPS', 8888: 'HTTP',
    9090: 'Console', 11211: 'Memcached', 27017: 'MongoDB',
}


class PortScanner:
    """端口扫描器"""

    CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config_ports.json')

    def __init__(self):
        self.ports = []
        self.use_custom_only = True
        self.load_config()

    def load_config(self):
        """加载配置"""
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                self.ports = config.get('ports', [])
                self.use_custom_only = config.get('use_custom_only', True)
        except Exception:
            pass

        if not self.ports:
            self.ports = [22, 80, 443, 3389, 3306, 5432, 6379, 8080, 8443, 8888, 27017]
            self.save_config()

    def save_config(self):
        """保存配置"""
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump({'ports': self.ports, 'use_custom_only': self.use_custom_only}, f, indent=2)
        except Exception:
            pass

    def scan_port(self, ip, port):
        """扫描单个端口"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)  # 1秒超时，更准确
            result = sock.connect_ex((ip, port))
            sock.close()
            return port if result == 0 else None
        except:
            return None

    def scan(self, ip):
        """扫描指定 IP 的所有端口"""
        if not self.ports:
            return []

        open_ports = []
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(self.scan_port, ip, p): p for p in self.ports}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    open_ports.append(result)
        return sorted(open_ports)

    def add_port(self, port):
        """添加端口"""
        try:
            port = int(port)
            if 1 <= port <= 65535 and port not in self.ports:
                self.ports.append(port)
                self.ports.sort()
                self.save_config()
                return True
        except:
            pass
        return False

    def remove_port(self, port):
        """删除端口"""
        try:
            port = int(port)
            if port in self.ports:
                self.ports.remove(port)
                self.save_config()
                return True
        except:
            pass
        return False

    def get_config(self):
        return {'ports': self.ports, 'use_custom_only': self.use_custom_only}


def detect_os(ip):
    """检测操作系统（简化版，更可靠）"""
    # 1. 尝试 NetBIOS（最可靠的 Windows 检测）
    if platform.system().lower() == 'windows':
        try:
            result = subprocess.run(
                ['nbtstat', '-A', ip],
                capture_output=True, text=True, timeout=3,
                creationflags=CREATE_NO_WINDOW
            )
            if 'Registered' in result.stdout:
                for line in result.stdout.split('\n'):
                    if 'UNIQUE' in line:
                        parts = line.split()
                        if len(parts) >= 2 and parts[0] not in ('<00>', '<01>', '<03>'):
                            return f'Windows ({parts[0]})'
                return 'Windows'
        except:
            pass

    # 2. 尝试 TTL 检测
    try:
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        result = subprocess.run(
            ['ping', param, '1', '-w', '1000' if platform.system().lower() == 'windows' else '-W', '1', ip],
            capture_output=True, text=True, timeout=3,
            creationflags=CREATE_NO_WINDOW
        )
        import re
        match = re.search(r'TTL=(\d+)', result.stdout, re.IGNORECASE)
        if match:
            ttl = int(match.group(1))
            if ttl <= 64:
                return 'Linux/macOS'
            elif ttl <= 128:
                return 'Windows'
    except:
        pass

    return 'Unknown'


class ARPScanner:
    """扫描服务"""

    def __init__(self, app=None):
        self.app = app
        self.is_scanning = False
        self.last_scan_result = None
        self.mac_vendor = MacVendorLookup()
        self.port_scanner = PortScanner()
        self._lock = threading.Lock()
        self.scan_mode = 'unknown'

        if SCAPY_AVAILABLE:
            conf.verb = 0

    def _arp_scan(self, subnet, timeout):
        """ARP 扫描"""
        arp = ARP(pdst=subnet)
        ether = Ether(dst="ff:ff:ff:ff:ff:ff")
        answered, _ = srp(ether / arp, timeout=timeout, verbose=False)
        return [{'ip': r.psrc, 'mac': r.hwsrc, 'vendor': self.mac_vendor.lookup(r.hwsrc)} for s, r in answered]

    def _ping_scan(self, subnet, timeout):
        """Ping 扫描"""
        network = ipaddress.ip_network(subnet, strict=False)
        ips = [str(ip) for ip in network.hosts()][:256]  # 限制 256 个

        alive = []
        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = {}
            for ip in ips:
                param = '-n' if platform.system().lower() == 'windows' else '-c'
                cmd = ['ping', param, '1', '-w', '500' if platform.system().lower() == 'windows' else '-W', '0.5', ip]
                futures[executor.submit(subprocess.run, cmd, capture_output=True, timeout=2, creationflags=CREATE_NO_WINDOW)] = ip

            for future in as_completed(futures):
                ip = futures[future]
                try:
                    if future.result().returncode == 0:
                        alive.append(ip)
                except:
                    pass

        devices = []
        for ip in alive:
            mac = self._get_mac(ip)
            devices.append({'ip': ip, 'mac': mac or '', 'vendor': self.mac_vendor.lookup(mac) if mac else ''})
        return devices

    def _get_mac(self, ip):
        """从 ARP 表获取 MAC"""
        try:
            result = subprocess.run(['arp', '-a', ip], capture_output=True, text=True, timeout=3, creationflags=CREATE_NO_WINDOW)
            for line in result.stdout.split('\n'):
                if ip in line:
                    for part in line.split():
                        if '-' in part and len(part) == 17:
                            return part.upper().replace('-', ':')
                        elif ':' in part and len(part) == 17:
                            return part.upper()
        except:
            pass
        return None

    def scan(self, subnet=None, scan_ports=True):
        """执行扫描"""
        if not SCAPY_AVAILABLE:
            return {'success': False, 'error': 'scapy 未安装'}

        with self._lock:
            if self.is_scanning:
                return {'success': False, 'error': '扫描中'}
            self.is_scanning = True

        try:
            subnet = subnet or (self.app.config['SCAN_SUBNET'] if self.app else '192.168.1.0/24')
            timeout = self.app.config['SCAN_TIMEOUT'] if self.app else 2
            start = time.time()

            # 尝试 ARP，失败则 Ping
            try:
                devices = self._arp_scan(subnet, timeout)
                self.scan_mode = 'arp'
            except Exception as e:
                if 'npcap' in str(e).lower() or 'winpcap' in str(e).lower() or 'layer 2' in str(e).lower():
                    devices = self._ping_scan(subnet, timeout)
                    self.scan_mode = 'ping'
                else:
                    raise

            # 扫描端口和操作系统
            if scan_ports and devices:
                for device in devices:
                    ip = device['ip']
                    open_ports = self.port_scanner.scan(ip)
                    device['open_ports'] = open_ports
                    device['ports_str'] = ','.join(str(p) for p in open_ports)
                    device['port_details'] = [{'port': p, 'service': PORT_NAMES.get(p, '')} for p in open_ports]
                    device['os_info'] = detect_os(ip)

            duration = time.time() - start

            # 保存结果
            new_devices = 0
            if self.app:
                with self.app.app_context():
                    new_devices = self._save_results(devices)
                    self._log_scan(len(devices), new_devices, duration)
                    DeviceRepository.mark_offline()

            result = {
                'success': True,
                'scan_mode': self.scan_mode,
                'total_found': len(devices),
                'new_devices': new_devices,
                'duration': round(duration, 2),
                'devices': devices,
                'scan_time': datetime.now().isoformat(),
            }

            if self.scan_mode == 'ping':
                result['notice'] = 'Ping 模式（无 Npcap），无法获取 MAC 地址'

            self.last_scan_result = result
            return result

        except PermissionError:
            return {'success': False, 'error': '需要管理员权限'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            self.is_scanning = False

    def scan_async(self, subnet=None, scan_ports=True):
        threading.Thread(target=self.scan, args=(subnet, scan_ports), daemon=True).start()
        return {'success': True, 'message': '扫描已启动'}

    def _save_results(self, devices):
        """保存扫描结果到数据库"""
        new_count = 0
        alert_service = NotificationService(self.app)

        for device in devices:
            mac = device.get('mac', '')
            if not mac:
                continue

            ip = device['ip']
            ports_str = device.get('ports_str', '')
            os_info = device.get('os_info', '')
            vendor = device.get('vendor', '')

            existing = DeviceRepository.get_by_mac(mac)

            if existing:
                updates = {'current_ip': ip}
                if ports_str:
                    old = set(existing.port.split(',')) if existing.port else set()
                    new = set(ports_str.split(','))
                    updates['port'] = ','.join(sorted(old | new))
                if os_info and os_info != 'Unknown' and (not existing.os_info or existing.os_info == 'Unknown'):
                    updates['os_info'] = os_info
                if vendor and not existing.vendor:
                    updates['vendor'] = vendor
                DeviceRepository.update(existing.id, **updates)
                DeviceRepository.update_last_seen(existing.id, ip)
                DeviceRepository.add_ip_history(mac, ip)
                if existing.status == '已下线':
                    DeviceRepository.update(existing.id, status='已登记' if existing.device_name else '未登记')
            else:
                device_id = DeviceRepository.create(mac, ip, vendor, status='未登记')
                update = {}
                if ports_str:
                    update['port'] = ports_str
                if os_info and os_info != 'Unknown':
                    update['os_info'] = os_info
                if update:
                    DeviceRepository.update(device_id, **update)
                new_count += 1
                alert_service.notify_new_device(ip, mac, vendor)

        return new_count

    def _log_scan(self, total, new_devices, duration):
        db = get_db()
        conflicts = db.execute("SELECT COUNT(*) FROM devices WHERE status = '冲突'").fetchone()[0]
        db.execute("INSERT INTO scan_logs (total_found, new_devices, conflict_count, duration_seconds) VALUES (?, ?, ?, ?)",
                   (total, new_devices, conflicts, round(duration, 2)))
        db.commit()

    def get_last_result(self):
        return self.last_scan_result

    def get_scan_logs(self, limit=10):
        db = get_db()
        return [dict(r) for r in db.execute("SELECT * FROM scan_logs ORDER BY scan_time DESC LIMIT ?", (limit,)).fetchall()]


def get_port_categories():
    return []
