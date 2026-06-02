import socket
import subprocess
import platform
import re
from concurrent.futures import ThreadPoolExecutor, as_completed


class OSDetector:
    """Operating System Detection"""

    def __init__(self, timeout=2):
        self.timeout = timeout

    def detect(self, ip, ports=None):
        """Detect OS using multiple methods"""
        results = {}

        # Method 1: TTL detection
        ttl_os = self._detect_by_ttl(ip)
        if ttl_os:
            results['ttl'] = ttl_os

        # Method 2: NetBIOS (Windows)
        netbios_os = self._detect_by_netbios(ip)
        if netbios_os:
            results['netbios'] = netbios_os

        # Method 3: HTTP Server header
        if ports:
            http_os = self._detect_by_http(ip, ports)
            if http_os:
                results['http'] = http_os

            # Method 4: SSH Banner
            ssh_os = self._detect_by_ssh(ip, ports)
            if ssh_os:
                results['ssh'] = ssh_os

            # Method 5: SMB/OS Version
            smb_os = self._detect_by_smb(ip, ports)
            if smb_os:
                results['smb'] = smb_os

        # Combine results
        return self._combine_results(results)

    def detect_batch(self, devices):
        """Detect OS for multiple devices"""
        def detect_one(device):
            ip = device.get('ip', '')
            ports = device.get('open_ports', [])
            os_info = self.detect(ip, ports)
            device['os_info'] = os_info
            return device

        with ThreadPoolExecutor(max_workers=20) as executor:
            list(executor.map(detect_one, devices))

        return devices

    def _detect_by_ttl(self, ip):
        """Detect OS by TTL value"""
        try:
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
            timeout_val = '2000' if platform.system().lower() == 'windows' else '2'

            result = subprocess.run(
                ['ping', param, '1', timeout_param, timeout_val, ip],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                output = result.stdout
                # Extract TTL value
                ttl_match = re.search(r'TTL=(\d+)', output, re.IGNORECASE)
                if ttl_match:
                    ttl = int(ttl_match.group(1))

                    if ttl <= 64:
                        # Linux/Unix/macOS default TTL is 64
                        # Could be Linux, macOS, Android, etc.
                        return 'Linux/Unix/macOS'
                    elif ttl <= 128:
                        # Windows default TTL is 128
                        return 'Windows'
                    elif ttl <= 255:
                        # Some network devices use 255
                        return 'Network Device'
        except Exception:
            pass

        return None

    def _detect_by_netbios(self, ip):
        """Detect OS by NetBIOS query (Windows devices)"""
        try:
            # Use nbtstat on Windows
            if platform.system().lower() == 'windows':
                result = subprocess.run(
                    ['nbtstat', '-A', ip],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                output = result.stdout

                if 'Registered' in output:
                    # Extract computer name and type
                    lines = output.split('\n')
                    for line in lines:
                        if 'UNIQUE' in line or 'GROUP' in line:
                            parts = line.split()
                            if len(parts) >= 2:
                                name = parts[0].strip()
                                if name and name not in('<00>', '<01>', '<03>', '<1E>', '<20>'):
                                    return f'Windows ({name})'
                    return 'Windows'
        except Exception:
            pass

        return None

    def _detect_by_http(self, ip, ports):
        """Detect OS by HTTP Server header"""
        http_ports = [p for p in ports if p in [80, 443, 8080, 8443, 8888, 8000, 8001, 9090]]

        for port in http_ports[:3]:  # Check first 3 HTTP ports
            try:
                import ssl
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)

                if port in [443, 8443]:
                    context = ssl.create_default_context()
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE
                    ssock = context.wrap_socket(sock, server_hostname=ip)
                    ssock.connect((ip, port))
                    ssock.sendall(f'HEAD / HTTP/1.1\r\nHost: {ip}\r\nConnection: close\r\n\r\n'.encode())
                    response = ssock.recv(1024).decode('utf-8', errors='ignore')
                    ssock.close()
                else:
                    sock.connect((ip, port))
                    sock.sendall(f'HEAD / HTTP/1.1\r\nHost: {ip}\r\nConnection: close\r\n\r\n'.encode())
                    response = sock.recv(1024).decode('utf-8', errors='ignore')
                    sock.close()

                # Extract Server header
                for line in response.split('\n'):
                    if line.lower().startswith('server:'):
                        server = line.split(':', 1)[1].strip()
                        if server:
                            return f'HTTP: {server}'
            except Exception:
                pass

        return None

    def _detect_by_ssh(self, ip, ports):
        """Detect OS by SSH banner"""
        if 22 not in ports:
            return None

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((ip, 22))

            banner = sock.recv(256).decode('utf-8', errors='ignore').strip()
            sock.close()

            if banner:
                # Parse SSH banner
                # Common: SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.1
                if 'OpenSSH' in banner:
                    if 'Ubuntu' in banner:
                        return 'Ubuntu Linux'
                    elif 'Debian' in banner:
                        return 'Debian Linux'
                    elif 'CentOS' in banner or 'RHEL' in banner:
                        return 'CentOS/RHEL Linux'
                    elif 'FreeBSD' in banner:
                        return 'FreeBSD'
                    elif 'Windows' in banner:
                        return 'Windows (OpenSSH)'
                    else:
                        return f'Linux/Unix ({banner.split()[1] if len(banner.split()) > 1 else "OpenSSH"})'
                elif 'Dropbear' in banner:
                    return 'Embedded Linux (Dropbear)'
                elif 'libssh' in banner:
                    return 'Network Device'
                else:
                    return f'SSH: {banner[:50]}'
        except Exception:
            pass

        return None

    def _detect_by_smb(self, ip, ports):
        """Detect OS by SMB (port 445)"""
        if 445 not in ports:
            return None

        try:
            # Try to connect to SMB and get info
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, 445))
            sock.close()

            if result == 0:
                # Port 445 open = Windows with high probability
                return 'Windows (SMB)'
        except Exception:
            pass

        return None

    def _combine_results(self, results):
        """Combine detection results into final OS string"""
        if not results:
            return 'Unknown'

        # Priority: SMB > NetBIOS > SSH > HTTP > TTL
        if 'smb' in results:
            return results['smb']
        if 'netbios' in results:
            return results['netbios']
        if 'ssh' in results:
            return results['ssh']
        if 'http' in results:
            return results['http']
        if 'ttl' in results:
            return results['ttl']

        return 'Unknown'

    def get_os_icon(self, os_info):
        """Get icon class for OS type"""
        if not os_info:
            return 'bi-question-circle'

        os_lower = os_info.lower()

        if 'windows' in os_lower:
            return 'bi-windows'
        elif 'ubuntu' in os_lower or 'debian' in os_lower:
            return 'bi-ubuntu'
        elif 'centos' in os_lower or 'rhel' in os_lower or 'red hat' in os_lower:
            return 'bi-centos'
        elif 'linux' in os_lower:
            return 'bi-linux'
        elif 'macos' in os_lower or 'mac os' in os_lower or 'darwin' in os_lower:
            return 'bi-apple'
        elif 'android' in os_lower:
            return 'bi-android2'
        elif 'router' in os_lower or 'switch' in os_lower or 'network' in os_lower:
            return 'bi-router'
        elif 'embedded' in os_lower:
            return 'bi-cpu'
        else:
            return 'bi-pc'
