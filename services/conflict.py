from models.database import get_db
from models.device import DeviceRepository


class ConflictDetector:
    """IP 冲突检测服务"""

    def detect(self):
        """检测所有冲突"""
        conflicts = []
        conflicts.extend(self._detect_ip_conflicts())
        conflicts.extend(self._detect_mac_conflicts())
        return conflicts

    def _detect_ip_conflicts(self):
        """检测同一 IP 对应多个 MAC 的情况"""
        db = get_db()
        rows = db.execute('''
            SELECT ip_address, COUNT(DISTINCT mac_address) as mac_count
            FROM devices
            WHERE mac_address IS NOT NULL AND mac_address != ''
            GROUP BY ip_address
            HAVING mac_count > 1
        ''').fetchall()

        conflicts = []
        for row in rows:
            ip = row['ip_address']
            devices = DeviceRepository.get_by_ip(ip)
            if devices:
                mac_list = [d.mac_address for d in devices if d.mac_address]
                conflicts.append({
                    'type': 'ip_conflict',
                    'ip': ip,
                    'message': f'IP {ip} 对应多个 MAC: {", ".join(mac_list)}',
                    'devices': [d.id for d in devices],
                })
                # 标记为冲突状态
                for d in devices:
                    DeviceRepository.update(d.id, status='冲突')

        return conflicts

    def _detect_mac_conflicts(self):
        """检测同一 MAC 对应多个 IP 的情况"""
        db = get_db()
        rows = db.execute('''
            SELECT mac_address, COUNT(DISTINCT ip_address) as ip_count
            FROM devices
            WHERE mac_address IS NOT NULL AND mac_address != ''
            GROUP BY mac_address
            HAVING ip_count > 1
        ''').fetchall()

        conflicts = []
        for row in rows:
            mac = row['mac_address']
            devices = DeviceRepository.get_by_mac(mac)
            if len(devices) > 1:
                ip_list = [d.ip_address for d in devices]
                conflicts.append({
                    'type': 'mac_conflict',
                    'mac': mac,
                    'message': f'MAC {mac} 对应多个 IP: {", ".join(ip_list)}',
                    'devices': [d.id for d in devices],
                })
                # 标记为冲突状态
                for d in devices:
                    DeviceRepository.update(d.id, status='冲突')

        return conflicts

    def get_conflict_summary(self):
        """获取冲突摘要"""
        db = get_db()
        ip_conflicts = db.execute('''
            SELECT COUNT(*) FROM (
                SELECT ip_address
                FROM devices
                WHERE mac_address IS NOT NULL AND mac_address != ''
                GROUP BY ip_address
                HAVING COUNT(DISTINCT mac_address) > 1
            )
        ''').fetchone()[0]

        mac_conflicts = db.execute('''
            SELECT COUNT(*) FROM (
                SELECT mac_address
                FROM devices
                WHERE mac_address IS NOT NULL AND mac_address != ''
                GROUP BY mac_address
                HAVING COUNT(DISTINCT ip_address) > 1
            )
        ''').fetchone()[0]

        return {
            'ip_conflicts': ip_conflicts,
            'mac_conflicts': mac_conflicts,
            'total': ip_conflicts + mac_conflicts,
        }
