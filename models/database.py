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
    """数据库迁移"""
    # 检查旧表结构，如果存在则迁移
    try:
        columns = [row[1] for row in db.execute("PRAGMA table_info(devices)").fetchall()]
        if 'ip_address' in columns and 'mac_address' in columns:
            # 旧结构，需要迁移
            _migrate_old_schema(db)
    except Exception:
        pass

def _migrate_old_schema(db):
    """从旧的 IP 主导结构迁移到 MAC 主导结构"""
    try:
        # 创建新表
        db.executescript('''
            CREATE TABLE IF NOT EXISTS devices_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac_address TEXT NOT NULL UNIQUE,
                current_ip TEXT,
                port TEXT,
                device_name TEXT,
                user_name TEXT,
                department TEXT,
                purpose TEXT,
                os_info TEXT,
                vendor TEXT,
                status TEXT DEFAULT '未登记',
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                remark TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS device_ips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mac_address TEXT NOT NULL,
                ip_address TEXT NOT NULL,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (mac_address) REFERENCES devices_new(mac_address) ON DELETE CASCADE,
                UNIQUE(mac_address, ip_address)
            );
        ''')

        # 迁移数据
        old_devices = db.execute("SELECT * FROM devices").fetchall()
        for d in old_devices:
            mac = d['mac_address'] or f"unknown_{d['id']}"
            ip = d['ip_address']

            # 插入新设备表
            db.execute('''INSERT OR IGNORE INTO devices_new
                (mac_address, current_ip, port, device_name, user_name, department, purpose, os_info, status, first_seen, last_seen, remark)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (mac, ip, d['port'], d['device_name'], d['user_name'], d['department'],
                 d['purpose'], d['os_info'], d['status'], d['first_seen'], d['last_seen'], d['remark']))

            # 插入 IP 记录
            db.execute('''INSERT OR IGNORE INTO device_ips (mac_address, ip_address, first_seen, last_seen)
                VALUES (?, ?, ?, ?)''', (mac, ip, d['first_seen'], d['last_seen']))

        # 删除旧表，重命名新表
        db.execute("DROP TABLE IF EXISTS devices_old")
        db.execute("ALTER TABLE devices RENAME TO devices_old")
        db.execute("ALTER TABLE devices_new RENAME TO devices")

        # 更新告警表外键
        db.execute('''CREATE TABLE IF NOT EXISTS alerts_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT,
            device_id INTEGER,
            message TEXT,
            is_read BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
        )''')
        db.execute("INSERT INTO alerts_new SELECT * FROM alerts")
        db.execute("DROP TABLE alerts")
        db.execute("ALTER TABLE alerts_new RENAME TO alerts")

        db.commit()
    except Exception as e:
        print(f"Migration error: {e}")
        db.rollback()


def init_db():
    """初始化数据库表"""
    db = get_db()
    db.executescript('''
        -- 设备表（MAC 地址为主键）
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mac_address TEXT NOT NULL UNIQUE,
            current_ip TEXT,
            port TEXT,
            device_name TEXT,
            user_name TEXT,
            department TEXT,
            purpose TEXT,
            os_info TEXT,
            vendor TEXT,
            status TEXT DEFAULT '未登记',
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            remark TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        -- IP 历史记录表
        CREATE TABLE IF NOT EXISTS device_ips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mac_address TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (mac_address) REFERENCES devices(mac_address) ON DELETE CASCADE,
            UNIQUE(mac_address, ip_address)
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
        CREATE INDEX IF NOT EXISTS idx_devices_mac ON devices(mac_address);
        CREATE INDEX IF NOT EXISTS idx_devices_ip ON devices(current_ip);
        CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
        CREATE INDEX IF NOT EXISTS idx_device_ips_mac ON device_ips(mac_address);
        CREATE INDEX IF NOT EXISTS idx_device_ips_ip ON device_ips(ip_address);
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
