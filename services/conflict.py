from models.database import get_db
from models.device import DeviceRepository


class ConflictDetector:
    """IP 冲突检测服务"""

    def detect(self):
        """检测所有冲突"""
        conflicts = []
        conflicts.extend(self._detect_ip_conflicts())
        return conflicts

    def _detect_ip_conflicts(self):
        """检测同一 IP 对应多个设备的情况（通过 IP 历史表）"""
        db = get_db()
        rows = db.execute('''
            SELECT ip_address, COUNT(DISTINCT mac_address) as mac_count
            FROM device_ips
            WHERE mac_address IS NOT NULL AND mac_address != ''
            GROUP BY ip_address
            HAVING mac_count > 1
        ''').fetchall()

        conflicts = []
        for row in rows:
            ip = row['ip_address']
            # 获取使用该 IP 的所有设备
            mac_rows = db.execute('''
                SELECT DISTINCT mac_address FROM device_ips WHERE ip_address = ?
            ''', (ip,)).fetchall()

            mac_list = []
            device_ids = []
            for mac_row in mac_rows:
                mac = mac_row['mac_address']
                device = DeviceRepository.get_by_mac(mac)
                if device:
                    mac_list.append(mac)
                    device_ids.append(device.id)

            if mac_list:
                conflicts.append({
                    'type': 'ip_conflict',
                    'ip': ip,
                    'message': f'IP {ip} 被多个设备使用: {", ".join(mac_list)}',
                    'devices': device_ids,
                })
                # 标记为冲突状态
                for device_id in device_ids:
                    DeviceRepository.update(device_id, status='冲突')

        return conflicts

    def get_conflict_summary(self):
        """获取冲突摘要"""
        db = get_db()

        # IP 冲突：同一 IP 被多个 MAC 使用
        ip_conflicts = db.execute('''
            SELECT COUNT(*) FROM (
                SELECT ip_address
                FROM device_ips
                GROUP BY ip_address
                HAVING COUNT(DISTINCT mac_address) > 1
            )
        ''').fetchone()[0]

        return {
            'ip_conflicts': ip_conflicts,
            'mac_conflicts': 0,  # MAC 冲突在新架构中不存在（MAC 是唯一主键）
            'total': ip_conflicts,
        }
