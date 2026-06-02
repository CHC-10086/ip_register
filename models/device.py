from datetime import datetime
from models.database import get_db


class Device:
    """设备模型"""

    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.ip_address = kwargs.get('ip_address')
        self.mac_address = kwargs.get('mac_address')
        self.port = kwargs.get('port')
        self.device_name = kwargs.get('device_name')
        self.user_name = kwargs.get('user_name')
        self.department = kwargs.get('department')
        self.purpose = kwargs.get('purpose')
        self.os_info = kwargs.get('os_info')
        self.status = kwargs.get('status', '未登记')
        self.first_seen = kwargs.get('first_seen')
        self.last_seen = kwargs.get('last_seen')
        self.remark = kwargs.get('remark')
        self.created_at = kwargs.get('created_at')
        self.updated_at = kwargs.get('updated_at')

    @staticmethod
    def from_row(row):
        """从数据库行创建设备对象"""
        if row is None:
            return None
        return Device(**dict(row))

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'mac_address': self.mac_address,
            'port': self.port,
            'device_name': self.device_name,
            'user_name': self.user_name,
            'department': self.department,
            'purpose': self.purpose,
            'os_info': self.os_info,
            'status': self.status,
            'first_seen': self.first_seen,
            'last_seen': self.last_seen,
            'remark': self.remark,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


class DeviceRepository:
    """设备数据访问层"""

    @staticmethod
    def get_all(page=1, per_page=20, status=None, keyword=None):
        """获取设备列表（分页）"""
        db = get_db()
        query = "SELECT * FROM devices WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM devices WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            count_query += " AND status = ?"
            params.append(status)

        if keyword:
            query += " AND (ip_address LIKE ? OR mac_address LIKE ? OR device_name LIKE ? OR user_name LIKE ? OR department LIKE ?)"
            count_query += " AND (ip_address LIKE ? OR mac_address LIKE ? OR device_name LIKE ? OR user_name LIKE ? OR department LIKE ?)"
            like_keyword = f"%{keyword}%"
            params.extend([like_keyword] * 5)

        # 获取总数
        total = db.execute(count_query, params).fetchone()[0]

        # 分页查询
        query += " ORDER BY last_seen DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])

        rows = db.execute(query, params).fetchall()
        devices = [Device.from_row(row) for row in rows]

        return devices, total

    @staticmethod
    def get_by_id(device_id):
        """根据ID获取设备"""
        db = get_db()
        row = db.execute("SELECT * FROM devices WHERE id = ?", (device_id,)).fetchone()
        return Device.from_row(row)

    @staticmethod
    def get_by_ip(ip_address):
        """根据IP获取设备"""
        db = get_db()
        row = db.execute("SELECT * FROM devices WHERE ip_address = ?", (ip_address,)).fetchone()
        return Device.from_row(row)

    @staticmethod
    def get_by_mac(mac_address):
        """根据MAC获取设备"""
        db = get_db()
        rows = db.execute("SELECT * FROM devices WHERE mac_address = ?", (mac_address,)).fetchall()
        return [Device.from_row(row) for row in rows]

    @staticmethod
    def create(ip_address, mac_address=None, status='未登记'):
        """创建设备"""
        db = get_db()
        now = datetime.now().isoformat()
        cursor = db.execute(
            "INSERT INTO devices (ip_address, mac_address, status, first_seen, last_seen, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ip_address, mac_address, status, now, now, now, now)
        )
        db.commit()
        return cursor.lastrowid

    @staticmethod
    def update(device_id, **kwargs):
        """更新设备信息"""
        db = get_db()
        allowed_fields = ['device_name', 'user_name', 'department', 'purpose', 'os_info', 'status', 'remark', 'mac_address', 'port']
        updates = []
        params = []

        for field in allowed_fields:
            if field in kwargs:
                updates.append(f"{field} = ?")
                params.append(kwargs[field])

        if not updates:
            return False

        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(device_id)

        db.execute(f"UPDATE devices SET {', '.join(updates)} WHERE id = ?", params)
        db.commit()
        return True

    @staticmethod
    def update_last_seen(device_id):
        """更新最后发现时间"""
        db = get_db()
        db.execute(
            "UPDATE devices SET last_seen = ?, updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), datetime.now().isoformat(), device_id)
        )
        db.commit()

    @staticmethod
    def delete(device_id):
        """删除设备"""
        db = get_db()
        db.execute("DELETE FROM devices WHERE id = ?", (device_id,))
        db.commit()
        return True

    @staticmethod
    def get_stats():
        """获取设备统计"""
        db = get_db()
        total = db.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        registered = db.execute("SELECT COUNT(*) FROM devices WHERE status = '已登记'").fetchone()[0]
        unregistered = db.execute("SELECT COUNT(*) FROM devices WHERE status = '未登记'").fetchone()[0]
        offline = db.execute("SELECT COUNT(*) FROM devices WHERE status = '已下线'").fetchone()[0]
        conflict = db.execute("SELECT COUNT(*) FROM devices WHERE status = '冲突'").fetchone()[0]

        # 最近24小时在线
        recent = db.execute(
            "SELECT COUNT(*) FROM devices WHERE last_seen >= datetime('now', '-1 day')"
        ).fetchone()[0]

        return {
            'total': total,
            'registered': registered,
            'unregistered': unregistered,
            'offline': offline,
            'conflict': conflict,
            'recent_online': recent,
        }

    @staticmethod
    def mark_offline(hours=24):
        """标记长时间未发现的设备为下线"""
        db = get_db()
        db.execute(
            "UPDATE devices SET status = '已下线', updated_at = ? WHERE last_seen < datetime('now', ?) AND status != '已下线'",
            (datetime.now().isoformat(), f'-{hours} hours')
        )
        db.commit()
