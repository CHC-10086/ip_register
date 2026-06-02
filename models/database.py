import sqlite3
import os
from flask import g, current_app

def get_db():
    """获取数据库连接"""
    if 'db' not in g:
        db_path = current_app.config['DATABASE']
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        g.db = sqlite3.connect(db_path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

def close_db(e=None):
    """关闭数据库连接"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def _migrate_db(db):
    """数据库迁移：添加新字段"""
    # 检查 port 字段是否存在
    columns = [row[1] for row in db.execute("PRAGMA table_info(devices)").fetchall()]
    if 'port' not in columns:
        db.execute("ALTER TABLE devices ADD COLUMN port TEXT")
        db.commit()


def init_db():
    """初始化数据库表"""
    db = get_db()
    db.executescript('''
        -- 设备表
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL UNIQUE,
            mac_address TEXT,
            port TEXT,
            device_name TEXT,
            user_name TEXT,
            department TEXT,
            purpose TEXT,
            os_info TEXT,
            status TEXT DEFAULT '未登记',
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            remark TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- 扫描记录表
        CREATE TABLE IF NOT EXISTS scan_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_found INTEGER,
            new_devices INTEGER,
            conflict_count INTEGER,
            duration_seconds REAL
        );

        -- 告警表
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT,
            device_id INTEGER,
            message TEXT,
            is_read BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
        );

        -- 创建索引
        CREATE INDEX IF NOT EXISTS idx_devices_ip ON devices(ip_address);
        CREATE INDEX IF NOT EXISTS idx_devices_mac ON devices(mac_address);
        CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
        CREATE INDEX IF NOT EXISTS idx_alerts_read ON alerts(is_read);
        CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);
    ''')
    db.commit()

def init_app(app):
    """注册数据库初始化到 Flask 应用"""
    app.teardown_appcontext(close_db)
    with app.app_context():
        init_db()
        _migrate_db(get_db())
