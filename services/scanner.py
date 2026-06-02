import os
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

# ==================== 端口定义（按类别分组） ====================

PORT_CATEGORIES = {
    'Web 服务': {
        80: 'HTTP', 443: 'HTTPS', 8000: 'HTTP-Dev', 8001: 'HTTP-Alt',
        8002: 'HTTP-Alt', 8008: 'HTTP-Alt', 8009: 'AJP', 8010: 'HTTP-Alt',
        8080: 'HTTP-Alt', 8081: 'HTTP-Alt', 8082: 'HTTP-Alt', 8083: 'HTTP-Alt',
        8085: 'HTTP-Alt', 8088: 'HTTP-Alt', 8090: 'HTTP-Alt', 8443: 'HTTPS-Alt',
        8880: 'HTTP-Alt', 8888: 'HTTP-Alt', 9000: 'HTTP-Alt', 9001: 'HTTP-Alt',
        9080: 'HTTP-Alt', 9090: 'Web-Console', 9091: 'HTTP-Alt', 9443: 'HTTPS-Alt',
        9999: 'HTTP-Alt', 10000: 'Webmin',
    },
    '远程管理': {
        22: 'SSH', 23: 'Telnet', 3389: 'RDP', 5900: 'VNC',
        5901: 'VNC-1', 5902: 'VNC-2', 5938: 'TeamViewer',
        4899: 'Radmin', 9100: 'JetDirect',
    },
    '文件传输': {
        20: 'FTP-Data', 21: 'FTP', 69: 'TFTP', 989: 'FTPS-Data',
        990: 'FTPS', 992: 'TelnetS', 873: 'Rsync',
    },
    '邮件服务': {
        25: 'SMTP', 110: 'POP3', 143: 'IMAP', 465: 'SMTPS',
        587: 'SMTP-Sub', 993: 'IMAPS', 995: 'POP3S',
    },
    '数据库': {
        1433: 'MSSQL', 1434: 'MSSQL-Mon', 1521: 'Oracle', 2049: 'NFS',
        3306: 'MySQL', 3307: 'MySQL-Alt', 33060: 'MySQL-X',
        5432: 'PostgreSQL', 5433: 'PostgreSQL-Alt',
        5984: 'CouchDB', 6379: 'Redis', 6380: 'Redis-Alt',
        7474: 'Neo4j', 8529: 'ArangoDB', 9042: 'Cassandra',
        11211: 'Memcached', 27017: 'MongoDB', 27018: 'MongoDB-2',
        50000: 'DB2',
    },
    '消息队列/中间件': {
        5672: 'RabbitMQ', 15672: 'RabbitMQ-Mgmt',
        9092: 'Kafka', 9093: 'Kafka-SSL',
        2181: 'Zookeeper', 2888: 'Zookeeper', 3888: 'Zookeeper',
        61616: 'ActiveMQ', 8161: 'ActiveMQ-Web',
        1883: 'MQTT', 8883: 'MQTT-SSL',
        5252: 'MQTT-Alt',
    },
    'DNS/网络': {
        53: 'DNS', 67: 'DHCP', 68: 'DHCP', 123: 'NTP',
        161: 'SNMP', 162: 'SNMP-Trap', 389: 'LDAP', 636: 'LDAPS',
        1723: 'PPTP', 1080: 'SOCKS', 4500: 'IPSec-NAT',
        500: 'IPSec',
    },
    '系统服务': {
        135: 'RPC', 137: 'NetBIOS-NS', 138: 'NetBIOS-DGM',
        139: 'NetBIOS-SSN', 445: 'SMB', 514: 'Syslog',
        515: 'LPD', 631: 'CUPS', 1099: 'RMI',
        2049: 'NFS', 2375: 'Docker', 2376: 'Docker-TLS',
        4443: 'HTTPS-Alt', 5060: 'SIP', 5061: 'SIP-TLS',
    },
    '容器/编排': {
        2375: 'Docker', 2376: 'Docker-TLS',
        6443: 'K8s-API', 10250: 'Kubelet', 10255: 'Kubelet-RO',
        2379: 'etcd', 2380: 'etcd-Peer',
        8500: 'Consul', 8600: 'Consul-DNS',
        4646: 'Nomad', 8300: 'Serf',
    },
    '监控/日志': {
        3000: 'Grafana', 3001: 'Grafana-Alt',
        5601: 'Kibana', 9200: 'Elasticsearch', 9300: 'ES-Transport',
        9090: 'Prometheus', 9093: 'Alertmanager', 9100: 'Node-Exp',
        12201: 'GELF', 1514: 'Syslog-TCP',
        24224: 'Fluentd', 24225: 'Fluentd-Mon',
        4244: 'Loki',
    },
    '开发工具': {
        3000: 'Grafana/Node', 3001: 'Grafana-Alt',
        4200: 'Angular-Dev', 4000: 'HTTP-Alt', 4001: 'HTTP-Alt',
        4505: 'SaltStack', 4506: 'SaltStack',
        5000: 'Docker-Reg', 5001: 'Docker-Reg',
        6060: 'Pprof', 9090: 'Prometheus',
        15000: 'Hydra',
    },
    'VPN/隧道': {
        1194: 'OpenVPN', 1723: 'PPTP', 4500: 'IPSec-NAT',
        500: 'IPSec', 51820: 'WireGuard',
        8291: 'Mikrotik',
    },
    '游戏服务器': {
        25565: 'Minecraft', 27015: 'Source', 27016: 'Source-2',
        7777: 'Terraria', 8211: 'Palworld',
        25575: 'RCON', 27020: 'RCON-2',
        19132: 'Bedrock', 19133: 'Bedrock-2',
        28015: 'Rust', 28016: 'Rust-2',
        7000: 'Avorion', 28960: 'Ark',
        16261: 'DayZ', 16262: 'DayZ-2',
        8766: 'Satisfactory', 15777: 'Satisfactory-2',
    },
    'VoIP/通信': {
        5060: 'SIP', 5061: 'SIP-TLS',
        10000: 'RTP', 10001: 'RTP-2',
        5222: 'XMPP', 5269: 'XMPP-S2S',
        6666: 'IRC', 6667: 'IRC', 6697: 'IRC-SSL',
    },
    '安全设备': {
        8443: 'FortiGate', 443: 'Firewall-Web',
        8080: 'Proxy', 3128: 'Squid',
        8008: 'Proxy-Alt', 9090: 'Proxy-Alt',
        10000: 'Webmin', 2083: 'cPanel', 2087: 'cPanel-Alt',
        2082: 'cPanel', 2086: 'WHM',
    },
    '打印/扫描': {
        9100: 'JetDirect', 515: 'LPD', 631: 'IPP',
        3389: 'RDP',
    },
    '存储/NAS': {
        139: 'NetBIOS', 445: 'SMB', 548: 'AFP',
        111: 'Portmapper', 2049: 'NFS',
        8080: 'Synology', 5000: 'Synology-Web',
        5001: 'Synology-HTTPS', 5005: 'Synology-Web',
        5006: 'Synology-HTTPS',
    },
    'IoT/智能设备': {
        1883: 'MQTT', 8883: 'MQTT-SSL',
        5683: 'CoAP', 5684: 'CoAPS',
        80: 'HTTP', 443: 'HTTPS',
        8080: 'HTTP-Alt', 8888: 'HTTP-Alt',
        9999: 'HTTP-Alt',
    },
}

# 合并所有端口（去重）
COMMON_PORTS = sorted(set(
    port for cat in PORT_CATEGORIES.values() for port in cat.keys()
))

# 合并所有端口名称（去重）
PORT_NAMES = {}
for cat in PORT_CATEGORIES.values():
    PORT_NAMES.update(cat)

# 获取端口分类信息（用于展示）
def get_port_categories():
    """获取端口分类信息"""
    result = []
    for category, ports in PORT_CATEGORIES.items():
        port_list = []
        for port, service in sorted(ports.items()):
            port_list.append({'port': port, 'service': service})
        result.append({
            'name': category,
            'count': len(port_list),
            'ports': port_list,
        })
    return result


class PortScanner:
    """端口扫描器"""

    CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config_ports.json')

    def __init__(self, timeout=0.5, max_workers=100, custom_ports=None):
        self.timeout = timeout
        self.max_workers = max_workers
        self.use_custom_only = False
        self.ports = self._load_ports(custom_ports)

    def _load_ports(self, custom_ports=None):
        """从配置文件加载端口"""
        config = self._read_config()
        self.use_custom_only = config.get('use_custom_only', False)
        saved_ports = config.get('ports', [])

        if self.use_custom_only and saved_ports:
            # 仅使用自定义端口
            return sorted(set(saved_ports))

        # 使用默认端口 + 自定义端口
        all_ports = list(set(COMMON_PORTS))
        if saved_ports:
            all_ports.extend(saved_ports)
        if custom_ports:
            for p in custom_ports:
                try:
                    port = int(p)
                    if 1 <= port <= 65535:
                        all_ports.append(port)
                except (ValueError, TypeError):
                    pass
        return sorted(set(all_ports))

    def _read_config(self):
        """读取配置文件"""
        try:
            if os.path.exists(self.CONFIG_FILE):
                import json
                with open(self.CONFIG_FILE, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return {'ports': [], 'use_custom_only': False}

    def _write_config(self):
        """写入配置文件"""
        try:
            import json
            config = self._read_config()
            config['ports'] = sorted(self.ports)
            config['use_custom_only'] = self.use_custom_only
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass

    def add_port(self, port):
        """添加端口"""
        try:
            port = int(port)
            if 1 <= port <= 65535 and port not in self.ports:
                self.ports.append(port)
                self.ports.sort()
                self._write_config()
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
                self._write_config()
                return True
        except (ValueError, TypeError):
            pass
        return False

    def set_custom_only(self, enabled):
        """设置是否仅扫描自定义端口"""
        self.use_custom_only = enabled
        self._write_config()

    def get_config(self):
        """获取当前配置"""
        return {
            'ports': self.ports,
            'use_custom_only': self.use_custom_only,
        }

    def scan_port(self, ip, port):
        """检测单个端口是否开放"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            if result == 0:
                return port
        except Exception:
            pass
        return None

    def scan_ports(self, ip, ports=None):
        """扫描指定 IP 的端口"""
        if ports is None:
            ports = self.ports

        open_ports = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.scan_port, ip, port): port for port in ports}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    open_ports.append(result)

        return sorted(open_ports)

    def format_ports(self, ports):
        """格式化端口列表为字符串"""
        if not ports:
            return ''
        return ','.join(str(p) for p in ports)

    def get_port_details(self, ports):
        """获取端口详情（带服务名）"""
        details = []
        for port in ports:
            name = PORT_NAMES.get(port, 'Unknown')
            details.append({'port': port, 'service': name})
        return details


class ARPScanner:
    """ARP 扫描服务（自动降级为 ping 扫描）"""

    def __init__(self, app=None):
        self.app = app
        self.is_scanning = False
        self.last_scan_result = None
        self.mac_vendor = MacVendorLookup()
        self.os_detector = OSDetector()
        self._lock = threading.Lock()
        self.scan_mode = 'unknown'  # arp / ping
        self._init_port_scanner()

        if SCAPY_AVAILABLE:
            conf.verb = 0  # 关闭 scapy 输出

    def _init_port_scanner(self):
        """初始化端口扫描器"""
        timeout = 0.5
        workers = 100
        custom_ports = []

        if self.app:
            timeout = self.app.config.get('PORT_SCAN_TIMEOUT', 0.5)
            workers = self.app.config.get('PORT_SCAN_WORKERS', 100)
            custom_str = self.app.config.get('CUSTOM_PORTS', '')
            if custom_str:
                custom_ports = [p.strip() for p in custom_str.split(',') if p.strip()]

        self.port_scanner = PortScanner(
            timeout=timeout,
            max_workers=workers,
            custom_ports=custom_ports
        )

    def _arp_scan(self, subnet, timeout):
        """ARP 扫描（需要 Npcap）"""
        arp_request = ARP(pdst=subnet)
        broadcast = Ether(dst="ff:ff:ff:ff:ff:ff")
        packet = broadcast / arp_request
        answered, _ = srp(packet, timeout=timeout, verbose=False)

        devices = []
        for sent, received in answered:
            ip = received.psrc
            mac = received.hwsrc
            vendor = self.mac_vendor.lookup(mac)
            devices.append({
                'ip': ip,
                'mac': mac,
                'vendor': vendor,
            })
        return devices

    def _ping_single(self, ip):
        """Ping 单个 IP"""
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
        timeout_val = '1000' if platform.system().lower() == 'windows' else '1'

        try:
            result = subprocess.run(
                ['ping', param, '1', timeout_param, timeout_val, str(ip)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3
            )
            if result.returncode == 0:
                return str(ip)
        except (subprocess.TimeoutExpired, Exception):
            pass
        return None

    def _get_mac_from_arp_table(self, ip):
        """从系统 ARP 表获取 MAC 地址"""
        try:
            result = subprocess.run(
                ['arp', '-a', str(ip)],
                capture_output=True,
                text=True,
                timeout=5
            )
            output = result.stdout
            for line in output.split('\n'):
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
        """Ping 扫描（不需要 Npcap）"""
        network = ipaddress.ip_network(subnet, strict=False)
        ips = [str(ip) for ip in network.hosts()]

        if len(ips) > 1024:
            ips = ips[:1024]

        alive_ips = []
        max_workers = min(50, len(ips))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
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
        """执行扫描（自动选择 ARP 或 Ping）"""
        if not SCAPY_AVAILABLE:
            return {'success': False, 'error': 'scapy 未安装，请运行: pip install scapy'}

        with self._lock:
            if self.is_scanning:
                return {'success': False, 'error': '扫描正在进行中'}
            self.is_scanning = True

        try:
            if subnet is None:
                subnet = self.app.config['SCAN_SUBNET'] if self.app else '192.168.1.0/24'

            timeout = self.app.config['SCAN_TIMEOUT'] if self.app else 2
            start_time = time.time()

            # 尝试 ARP 扫描，失败则降级为 Ping 扫描
            try:
                devices = self._arp_scan(subnet, timeout)
                self.scan_mode = 'arp'
            except Exception as e:
                error_msg = str(e)
                if 'winpcap' in error_msg.lower() or 'npcap' in error_msg.lower() or 'layer 2' in error_msg.lower():
                    devices = self._ping_scan(subnet, timeout)
                    self.scan_mode = 'ping'
                else:
                    raise

            # 端口扫描
            if scan_ports and devices:
                self._scan_device_ports(devices)

            duration = time.time() - start_time

            # 处理扫描结果
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
                result['notice'] = '当前使用 Ping 扫描模式（未安装 Npcap），无法获取 MAC 地址。安装 Npcap 后可使用 ARP 扫描获取完整信息。'

            self.last_scan_result = result
            return result

        except PermissionError:
            return {'success': False, 'error': '需要管理员权限运行扫描（Windows 下请以管理员身份运行）'}
        except Exception as e:
            return {'success': False, 'error': f'扫描失败: {str(e)}'}
        finally:
            self.is_scanning = False

    def _scan_device_ports(self, devices):
        """并发扫描所有设备的端口和操作系统"""
        def scan_one(device):
            ip = device['ip']
            open_ports = self.port_scanner.scan_ports(ip)
            device['open_ports'] = open_ports
            device['ports_str'] = self.port_scanner.format_ports(open_ports)
            device['port_details'] = self.port_scanner.get_port_details(open_ports)
            # Detect OS
            device['os_info'] = self.os_detector.detect(ip, open_ports)

        with ThreadPoolExecutor(max_workers=10) as executor:
            list(executor.map(scan_one, devices))

    def scan_async(self, subnet=None, scan_ports=True):
        """异步执行扫描"""
        thread = threading.Thread(target=self.scan, args=(subnet, scan_ports), daemon=True)
        thread.start()
        return {'success': True, 'message': '扫描已启动'}

    def _process_scan_results(self, devices):
        """处理扫描结果，更新数据库（MAC 为主标识）"""
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
                # 没有 MAC 地址的设备跳过（Ping 扫描模式）
                continue

            # 根据 MAC 查找设备
            existing = DeviceRepository.get_by_mac(mac)

            if existing:
                # 设备已存在，更新信息
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
                # 新设备
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
        """获取上次扫描结果"""
        return self.last_scan_result

    def get_scan_logs(self, limit=10):
        """获取扫描日志"""
        db = get_db()
        rows = db.execute(
            "SELECT * FROM scan_logs ORDER BY scan_time DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(row) for row in rows]
