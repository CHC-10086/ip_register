import socket
import struct


def get_local_ip():
    """获取本机局域网 IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


def get_local_subnet():
    """获取本机网段（/24）"""
    ip = get_local_ip()
    parts = ip.split('.')
    return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"


def ip_to_int(ip):
    """IP 地址转整数"""
    return struct.unpack("!I", socket.inet_aton(ip))[0]


def int_to_ip(num):
    """整数转 IP 地址"""
    return socket.inet_ntoa(struct.pack("!I", num))


def get_subnet_ips(subnet):
    """获取网段内所有 IP"""
    if '/' not in subnet:
        return [subnet]

    network, prefix = subnet.split('/')
    prefix = int(prefix)

    network_int = ip_to_int(network)
    mask = (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF
    network_int = network_int & mask

    ips = []
    for i in range(1, (1 << (32 - prefix)) - 1):
        ips.append(int_to_ip(network_int + i))

    return ips


def is_valid_ip(ip):
    """验证 IP 地址格式"""
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False


def is_valid_mac(mac):
    """验证 MAC 地址格式"""
    import re
    pattern = r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$'
    return bool(re.match(pattern, mac))


def normalize_mac(mac):
    """标准化 MAC 地址格式（大写冒号分隔）"""
    if not mac:
        return ''
    return mac.upper().replace('-', ':')
