from datetime import datetime
from models.database import get_db


class NotificationService:
    """通知服务"""

    def __init__(self, app=None):
        self.app = app

    def notify_new_device(self, ip, mac, vendor=''):
        """新设备接入通知"""
        if self.app and not self.app.config.get('NOTIFY_NEW_DEVICE', True):
            return

        message = f'发现新设备: IP={ip}, MAC={mac}'
        if vendor:
            message += f', 厂商={vendor}'

        self._create_alert('new_device', None, message)

    def notify_conflict(self, conflict):
        """IP 冲突通知"""
        if self.app and not self.app.config.get('NOTIFY_CONFLICT', True):
            return

        alert_type = 'ip_conflict' if conflict['type'] == 'ip_conflict' else 'mac_conflict'
        device_id = conflict.get('devices', [None])[0]
        self._create_alert(alert_type, device_id, conflict['message'])

    def notify_device_offline(self, ip, device_name=None):
        """设备下线通知"""
        name = device_name or ip
        message = f'设备已下线: {name} ({ip})'
        self._create_alert('offline', None, message)

    def _create_alert(self, alert_type, device_id, message):
        """创建告警记录"""
        try:
            db = get_db()
            db.execute(
                "INSERT INTO alerts (alert_type, device_id, message) VALUES (?, ?, ?)",
                (alert_type, device_id, message)
            )
            db.commit()
        except Exception:
            pass  # 告警创建失败不影响主流程

    def get_alerts(self, page=1, per_page=20, unread_only=False):
        """获取告警列表"""
        db = get_db()
        query = "SELECT * FROM alerts WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM alerts WHERE 1=1"
        params = []

        if unread_only:
            query += " AND is_read = 0"
            count_query += " AND is_read = 0"

        total = db.execute(count_query, params).fetchone()[0]

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])

        rows = db.execute(query, params).fetchall()
        return [dict(row) for row in rows], total

    def get_unread_count(self):
        """获取未读告警数量"""
        db = get_db()
        return db.execute("SELECT COUNT(*) FROM alerts WHERE is_read = 0").fetchone()[0]

    def mark_as_read(self, alert_id):
        """标记告警为已读"""
        db = get_db()
        db.execute("UPDATE alerts SET is_read = 1 WHERE id = ?", (alert_id,))
        db.commit()

    def mark_all_as_read(self):
        """标记所有告警为已读"""
        db = get_db()
        db.execute("UPDATE alerts SET is_read = 1 WHERE is_read = 0")
        db.commit()

    def delete_alert(self, alert_id):
        """删除告警"""
        db = get_db()
        db.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        db.commit()

    def clear_read_alerts(self):
        """清除已读告警"""
        db = get_db()
        db.execute("DELETE FROM alerts WHERE is_read = 1")
        db.commit()
