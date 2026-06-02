import os

class Config:
    # 基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'ip-register-secret-key-change-me')
    DEBUG = True

    # 数据库配置
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE = os.path.join(BASE_DIR, 'data', 'ip_register.db')

    # 扫描配置
    SCAN_SUBNET = os.environ.get('SCAN_SUBNET', '192.168.1.0/24')  # 默认扫描网段
    SCAN_TIMEOUT = 2  # 扫描超时（秒）
    SCAN_INTERVAL = 300  # 自动扫描间隔（秒），默认5分钟

    # 端口扫描配置
    # 自定义额外端口（在默认列表基础上追加），用逗号分隔
    # 例如: '9100,9200,9300,10000'
    CUSTOM_PORTS = os.environ.get('CUSTOM_PORTS', '')
    # 端口扫描超时（秒）
    PORT_SCAN_TIMEOUT = 0.5
    # 端口扫描并发数
    PORT_SCAN_WORKERS = 100

    # 通知配置
    NOTIFY_NEW_DEVICE = True  # 新设备提醒
    NOTIFY_CONFLICT = True  # IP冲突提醒

    # 分页配置
    PER_PAGE = 20
