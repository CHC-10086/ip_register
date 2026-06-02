import os
from flask import Flask
from config import Config
from models.database import init_app


def create_app(config_class=Config):
    """创建 Flask 应用"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # 初始化数据库
    init_app(app)

    # 注册蓝图
    from routes.views import views_bp
    from routes.api import api_bp

    app.register_blueprint(views_bp)
    app.register_blueprint(api_bp)

    # 注册模板过滤器
    @app.template_filter('datetime')
    def datetime_filter(value):
        """格式化日期时间"""
        if not value:
            return ''
        if isinstance(value, str):
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(value)
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, TypeError):
                return value
        return value.strftime('%Y-%m-%d %H:%M:%S')

    # 上下文处理器
    @app.context_processor
    def inject_globals():
        """注入全局变量到模板"""
        from services.notification import NotificationService
        try:
            ns = NotificationService(app)
            unread_count = ns.get_unread_count()
        except Exception:
            unread_count = 0
        return {
            'unread_count': unread_count,
            'config': app.config,
        }

    # 错误处理
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Not Found'}, 404

    @app.errorhandler(500)
    def internal_error(error):
        return {'error': 'Internal Server Error'}, 500

    return app


if __name__ == '__main__':
    app = create_app()

    # Windows 下需要管理员权限运行扫描
    print("=" * 50)
    print("局域网 IP 登记系统")
    print("=" * 50)
    print(f"访问地址: http://127.0.0.1:8088")
    print(f"扫描网段: {app.config['SCAN_SUBNET']}")
    print("注意: ARP 扫描需要管理员权限运行")
    print("=" * 50)

    app.run(host='0.0.0.0', port=8088, debug=True)
