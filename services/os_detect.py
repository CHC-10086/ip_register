import socket
import subprocess
import platform
import re


class OSDetector:
    """操作系统检测"""

    def __init__(self, timeout=1):
        self.timeout = timeout

    def detect(self, ip, ports=None):
        """检测操作系统"""
        # 1. TTL 检测（最可靠）
        ttl_os = self._detect_by_ttl(ip)

        # 2. NetBIOS 检测（Windows）
        netbios_os = self._detect_by_netbios(ip)
        if netbios_os and 'Windows' in netbios_os:
            return netbios_os

        # 3. SMB 检测（Windows）
        if ports and 445 in ports:
            return 'Windows'

        # 4. SSH Banner 检测
        if ports and 22 in ports:
            ssh_os = self._detect_by_ssh(ip)
            if ssh_os and self._is_valid_os(ssh_os):
                return ssh_os

        # 5. 返回 TTL 结果
        if ttl_os:
            return ttl_os

        return 'Unknown'

    def _is_valid_os(self, os_str):
        """检查是否是有效的操作系统名称（排除 Python 等误报）"""
        invalid_keywords = [
            'python', 'paramiko', 'aiohttp', 'flask', 'django',
            'node', 'ruby', 'java', 'go-', 'rust', 'libssh',
            'dropbear', 'cisco', 'mikrotik'
        ]
        os_lower = os_str.lower()
        for keyword in invalid_keywords:
            if keyword in os_lower:
                return False
        return True

    def _detect_by_ttl(self, ip):
        """通过 TTL 值检测操作系统"""
        try:
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
            timeout_val = '1000' if platform.system().lower() == 'windows' else '1'

            result = subprocess.run(
                ['ping', param, '1', timeout_param, timeout_val, ip],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=0x08000000 if platform.system().lower() == 'windows' else 0
            )

            if result.returncode == 0:
                ttl_match = re.search(r'TTL=(\d+)', result.stdout, re.IGNORECASE)
                if ttl_match:
                    ttl = int(ttl_match.group(1))
                    if ttl <= 64:
                        return 'Linux/macOS'
                    elif ttl <= 128:
                        return 'Windows'
                    elif ttl <= 255:
                        return 'Network Device'
        except Exception:
            pass
        return None

    def _detect_by_netbios(self, ip):
        """通过 NetBIOS 检测 Windows"""
        if platform.system().lower() != 'windows':
            return None
        try:
            result = subprocess.run(
                ['nbtstat', '-A', ip],
                capture_output=True,
                text=True,
                timeout=3,
                creationflags=0x08000000
            )
            if 'Registered' in result.stdout:
                for line in result.stdout.split('\n'):
                    if 'UNIQUE' in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            name = parts[0].strip()
                            if name and name not in ('<00>', '<01>', '<03>', '<1E>', '<20>'):
                                return f'Windows ({name})'
                return 'Windows'
        except Exception:
            pass
        return None

    def _detect_by_ssh(self, ip):
        """通过 SSH Banner 检测操作系统"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((ip, 22))
            banner = sock.recv(256).decode('utf-8', errors='ignore').strip()
            sock.close()

            if not banner:
                return None

            # 跳过非系统 SSH（Python、Paramiko 等）
            if not self._is_valid_os(banner):
                return None

            banner_lower = banner.lower()

            # 解析系统信息
            if 'ubuntu' in banner_lower:
                return 'Ubuntu'
            elif 'debian' in banner_lower:
                return 'Debian'
            elif 'centos' in banner_lower:
                return 'CentOS'
            elif 'rhel' in banner_lower or 'red hat' in banner_lower:
                return 'RHEL'
            elif 'fedora' in banner_lower:
                return 'Fedora'
            elif 'freebsd' in banner_lower:
                return 'FreeBSD'
            elif 'openssh' in banner_lower:
                # 提取版本号
                version_match = re.search(r'OpenSSH[_\s](\d+\.\d+)', banner)
                if version_match:
                    return f'Linux (OpenSSH {version_match.group(1)})'
                return 'Linux'
        except Exception:
            pass
        return None
