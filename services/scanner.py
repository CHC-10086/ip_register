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
from services.os_detect import OSDetector

# Windows subprocess flag to hide console windows
CREATE_NO_WINDOW = 0x08000000 if platform.system().lower() == 'windows' else 0

# 常用端口服务名映射
PORT_NAMES = {
    20: 'FTP-Data', 21: 'FTP', 22: 'SSH', 23: 'Telnet', 25: 'SMTP',
    53: 'DNS', 80: 'HTTP', 110: 'POP3', 135: 'RPC', 139: 'NetBIOS',
    143: 'IMAP', 443: 'HTTPS', 445: 'SMB', 993: 'IMAPS', 995: 'POP3S',
    1433: 'MSSQL', 1521: 'Oracle', 3306: 'MySQL', 3389: 'RDP',
    5432: 'PostgreSQL', 5900: 'VNC', 6379: 'Redis',
    8080: 'HTTP-Alt', 8443: 'HTTPS-Alt', 8888: 'HTTP-Alt',
    9090: 'Console', 11211: 'Memcached', 27017: 'MongoDB',
}


class PortScanner:
    """端口扫描器"""

    CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config_ports.json')

    def __init__(self, timeout=0.3, max_workers=200):
        self.timeout = timeout
        self.max_workers = max_workers
        self.use_custom_only = True  # 默认仅扫描自定义端口
        self.ports = []
        self._load_config()

    def _load_config(self):
        """从配置文件加载端口"""
        try:
            if os.path.exists(self.CONFIG_FILE):
                with open(self.CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                self.ports = config.get('ports', [])
                self.use_custom_only = config.get('use_custom_only', True)
        except Exception:
            pass

        # 如果没有配置，使用默认端口
        if not self.ports:
            self.ports = [22, 80, 443, 3389, 3306, 5432, 6379, 8080, 8443, 8888, 27017]
            self.save_config()

    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump({
                    'ports': sorted(self.ports),
                    'use_custom_only': self.use_custom_only
                }, f, indent=2)
        except Exception:
            pass

    def scan_port(self, ip, port):
        """检测单个端口是否开放"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return port if result == 0 else None
        except Exception:
            return None

    def scan_ports(self, ip, ports=None):
        """扫描指定 IP 的端口"""
        if ports is None:
            ports = self.ports
        if not ports:
            return []

        open_ports = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.scan_port, ip, port): port for port in ports}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
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
        except (ValueError, TypeError):
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
        except (ValueError, TypeError):
            pass
        return False

    def get_config(self):
        """获取当前配置"""
        return {
            'ports': self.ports,
            'use_custom_only': self.use_custom_only,
        }


class ARPScanner:
    """ARP 扫描服务"""

    def __init__(self, app=None):
        self.app = app
        self.is_scanning = False
        self.last_scan_result = None
        self.mac_vendor = MacVendorLookup()
        self.os_detector = OSDetector()
        self.port_scanner = PortScanner()
        self._lock = threading.Lock()
        self.scan_mode = 'unknown'

        if SCAPY_AVAILABLE:
            conf.verb = 0

    def _arp_scan(self, subnet, timeout):
        """ARP 扫描"""
        arp_request = ARP(pdst=subnet)
        broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = broadcast / arp_request
        answered, _ = srp(packet, timeout=timeout, verbose=False)

        devices = []
        for sent, received in answered:
            devices.append({
                'ip': received.psrc,
                'mac': received.hwsrc,
                'vendor': self.mac_vendor.lookup(received.hwsrc),
            })
        return devices

    def _ping_single(self, ip):
        """Ping 单个 IP（无黑框）"""
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
        timeout_val = '500' if platform.system().lower() == 'windows' else '0.5'

        try:
            result = subprocess.run(
                ['ping', param, '1', timeout_param, timeout_val, str(ip)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
                creationflags=CREATE_NO_WINDOW
            )
            return str(ip) if result.returncode == 0 else None
        except Exception:
            return None

    def _get_mac_from_arp_table(self, ip):
        """从 ARP 表获取 MAC"""
        try:
            result = subprocess.run(
                ['arp', '-a', str(ip)],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=CREATE_NO_WINDOW
            )
            for line in result.stdout.split('\n'):
                if str(ip) in line:
                    parts = line.split()
                    for part in parts:
                        if '-' in part and len(part) == 17:
                            return part.upper().replace('-', ':')
                        elif ':' in part and len(part) == 17:
                            return part.upper()
        except Exception:
            pass
        return None

    def _ping_scan(self, subnet, timeout):
        """Ping 扫描"""
        network = ipaddress.ip_network(subnet, strict=False)
        ips = [str(ip) for ip in network.hosts()]

        if len(ips) > 1024:
            ips = ips[:1024]

        alive_ips = []
        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = {executor.submit(self._ping_single, ip): ip for ip in ips}
            for future in as_completed(futures):
                result = future.result()
                if result:
                    alive_ips.append(result)

        devices = []
        for ip in alive_ips:
            mac = self._get_mac_from_arp_table(ip)
            vendor = self.mac_vendor.lookup(mac) if mac else ''
            devices.append({
                'ip': ip,
                'mac': mac or '',
                'vendor': vendor,
            })
        return devices

    def scan(self, subnet=None, scan_ports=True):
        """执行扫描"""
        if not SCAPY_AVAILABLE:
            return {'success': False, 'error': 'scapy 未安装'}

        with self._lock:
            if self.is_scanning:
                return {'success': False, 'error': '扫描正在进行中'}
            self.is_scanning = True

        try:
            if subnet is None:
                subnet = self.app.config['SCAN_SUBNET'] if self.app else '192.168.1.0/24'

            timeout = self.app.config['SCAN_TIMEOUT'] if self.app else 2
            start_time = time.time()

            try:
                devices = self._arp_scan(subnet, timeout)
                self.scan_mode = 'arp'
            except Exception as e:
                if 'winpcap' in str(e).lower() or 'npcap' in str(e).lower() or 'layer 2' in str(e).lower():
                    devices = self._ping_scan(subnet, timeout)
                    self.scan_mode = 'ping'
                else:
                    raise

            if scan_ports and devices:
                self._scan_device_ports(devices)

            duration = time.time() - start_time

            new_devices = 0
            if self.app:
                with self.app.app_context():
                    new_devices = self._process_scan_results(devices)
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
                result['notice'] = 'Ping 模式（无 Npcap），无法获取 MAC'

            self.last_scan_result = result
            return result

        except PermissionError:
            return {'success': False, 'error': '需要管理员权限'}
        except Exception as e:
            return {'success': False, 'error': f'扫描失败: {str(e)}'}
        finally:
            self.is_scanning = False

    def _scan_device_ports(self, devices):
        """扫描设备端口和操作系统"""
        def scan_one(device):
            ip = device['ip']
            open_ports = self.port_scanner.scan_ports(ip)
            device['open_ports'] = open_ports
            device['ports_str'] = ','.join(str(p) for p in open_ports)
            device['port_details'] = [{'port': p, 'service': PORT_NAMES.get(p, '')} for p in open_ports]
            device['os_info'] = self.os_detector.detect(ip, open_ports)

        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(scan_one, devices))

    def scan_async(self, subnet=None, scan_ports=True):
        """异步扫描"""
        threading.Thread(target=self.scan, args=(subnet, scan_ports), daemon=True).start()
        return {'success': True, 'message': '扫描已启动'}

    def _process_scan_results(self, devices):
        """处理扫描结果"""
        new_count = 0
        alert_service = NotificationService(self.app)
        conflict_detector = ConflictDetector()

        for device in devices:
            ip = device['ip']
            mac = device.get('mac', '')
            ports_str = device.get('ports_str', '')
            os_info = device.get('os_info', '')
            vendor = device.get('vendor', '')

            if not mac:
                continue

            existing = DeviceRepository.get_by_mac(mac)

            if existing:
                updates = {'current_ip': ip}
                if ports_str:
                    old_ports = set(existing.port.split(',')) if existing.port else set()
                    new_ports = set(ports_str.split(','))
                    merged = sorted(old_ports | new_ports, key=lambda x: int(x) if x.isdigit() else 0)
                    updates['port'] = ','.join(merged)
                if os_info and (not existing.os_info or existing.os_info == 'Unknown'):
                    updates['os_info'] = os_info
                if vendor and not existing.vendor:
                    updates['vendor'] = vendor
                DeviceRepository.update(existing.id, **updates)
                DeviceRepository.update_last_seen(existing.id, ip)
                DeviceRepository.add_ip_history(mac, ip)

                if existing.status == '已下线':
                    new_status = '已登记' if existing.device_name else '未登记'
                    DeviceRepository.update(existing.id, status=new_status)
            else:
                device_id = DeviceRepository.create(mac, ip, vendor, status='未登记')
                update_data = {}
                if ports_str:
                    update_data['port'] = ports_str
                if os_info:
                    update_data['os_info'] = os_info
                if update_data:
                    DeviceRepository.update(device_id, **update_data)
                new_count += 1
                alert_service.notify_new_device(ip, mac, vendor)

        conflicts = conflict_detector.detect()
        for conflict in conflicts:
            alert_service.notify_conflict(conflict)

        return new_count

    def _log_scan(self, total, new_devices, duration):
        """记录扫描日志"""
        db = get_db()
        conflict_count = db.execute("SELECT COUNT(*) FROM devices WHERE status = '冲突'").fetchone()[0]
        db.execute(
            "INSERT INTO scan_logs (total_found, new_devices, conflict_count, duration_seconds) VALUES (?, ?, ?, ?)",
            (total, new_devices, conflict_count, round(duration, 2))
        )
        db.commit()

    def get_last_result(self):
        return self.last_scan_result

    def get_scan_logs(self, limit=10):
        db = get_db()
        rows = db.execute("SELECT * FROM scan_logs ORDER BY scan_time DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]


def get_port_categories():
    """获取端口分类（兼容旧代码）"""
    return []
