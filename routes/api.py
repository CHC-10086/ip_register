from flask import Blueprint, jsonify, request, current_app
from models.device import DeviceRepository
from services.scanner import ARPScanner
from services.notification import NotificationService
from services.conflict import ConflictDetector

api_bp = Blueprint('api', __name__, url_prefix='/api')
scanner = ARPScanner()


@api_bp.route('/devices', methods=['GET'])
def get_devices():
    """获取设备列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', '')
    keyword = request.args.get('keyword', '')

    devices, total = DeviceRepository.get_all(
        page=page,
        per_page=per_page,
        status=status if status else None,
        keyword=keyword if keyword else None
    )

    return jsonify({
        'success': True,
        'data': {
            'devices': [d.to_dict() for d in devices],
            'total': total,
            'page': page,
            'per_page': per_page,
        }
    })


@api_bp.route('/devices/<int:device_id>', methods=['GET'])
def get_device(device_id):
    """获取单个设备"""
    device = DeviceRepository.get_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'error': '设备不存在'}), 404

    return jsonify({
        'success': True,
        'data': device.to_dict()
    })


@api_bp.route('/devices', methods=['POST'])
def create_device():
    """创建设备"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '无效的请求数据'}), 400

    ip = data.get('ip_address', '').strip()
    if not ip:
        return jsonify({'success': False, 'error': 'IP 地址不能为空'}), 400

    existing = DeviceRepository.get_by_ip(ip)
    if existing:
        return jsonify({'success': False, 'error': '该 IP 地址已存在'}), 400

    mac = data.get('mac_address', '').strip()
    device_id = DeviceRepository.create(ip, mac if mac else None, status='已登记')

    updates = {
        'device_name': data.get('device_name', '').strip(),
        'user_name': data.get('user_name', '').strip(),
        'department': data.get('department', '').strip(),
        'purpose': data.get('purpose', '').strip(),
        'os_info': data.get('os_info', '').strip(),
        'remark': data.get('remark', '').strip(),
        'port': data.get('port', '').strip(),
    }
    DeviceRepository.update(device_id, **updates)

    device = DeviceRepository.get_by_id(device_id)
    return jsonify({
        'success': True,
        'data': device.to_dict()
    }), 201


@api_bp.route('/devices/<int:device_id>', methods=['PUT'])
def update_device(device_id):
    """更新设备"""
    device = DeviceRepository.get_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'error': '设备不存在'}), 404

    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': '无效的请求数据'}), 400

    updates = {}
    for field in ['device_name', 'user_name', 'department', 'purpose', 'os_info', 'status', 'remark', 'mac_address', 'port']:
        if field in data:
            updates[field] = data[field].strip() if isinstance(data[field], str) else data[field]

    DeviceRepository.update(device_id, **updates)

    device = DeviceRepository.get_by_id(device_id)
    return jsonify({
        'success': True,
        'data': device.to_dict()
    })


@api_bp.route('/devices/<int:device_id>', methods=['DELETE'])
def delete_device(device_id):
    """删除设备"""
    device = DeviceRepository.get_by_id(device_id)
    if not device:
        return jsonify({'success': False, 'error': '设备不存在'}), 404

    DeviceRepository.delete(device_id)
    return jsonify({'success': True, 'message': '设备已删除'})


@api_bp.route('/stats', methods=['GET'])
def get_stats():
    """获取统计数据"""
    stats = DeviceRepository.get_stats()
    conflict_detector = ConflictDetector()
    conflict_summary = conflict_detector.get_conflict_summary()

    notification_service = NotificationService(current_app._get_current_object())
    unread_count = notification_service.get_unread_count()

    return jsonify({
        'success': True,
        'data': {
            'devices': stats,
            'conflicts': conflict_summary,
            'unread_alerts': unread_count,
        }
    })


@api_bp.route('/scan', methods=['POST'])
def start_scan():
    """启动扫描"""
    data = request.get_json() or {}
    subnet = data.get('subnet', '').strip() or None
    scan_ports = data.get('scan_ports', True)
    custom_ports = data.get('custom_ports', [])

    # 处理自定义端口
    if custom_ports and isinstance(custom_ports, list):
        for p in custom_ports:
            try:
                port = int(p)
                if 1 <= port <= 65535 and port not in scanner.port_scanner.ports:
                    scanner.port_scanner.ports.append(port)
            except (ValueError, TypeError):
                pass
        scanner.port_scanner.ports.sort()

    # 同步扫描
    result = scanner.scan(subnet, scan_ports=scan_ports)
    return jsonify(result)


@api_bp.route('/scan/async', methods=['POST'])
def start_scan_async():
    """异步启动扫描"""
    data = request.get_json() or {}
    subnet = data.get('subnet', '').strip() or None
    scan_ports = data.get('scan_ports', True)
    custom_ports = data.get('custom_ports', [])

    # 处理自定义端口
    if custom_ports and isinstance(custom_ports, list):
        for p in custom_ports:
            try:
                port = int(p)
                if 1 <= port <= 65535 and port not in scanner.port_scanner.ports:
                    scanner.port_scanner.ports.append(port)
            except (ValueError, TypeError):
                pass
        scanner.port_scanner.ports.sort()

    result = scanner.scan_async(subnet, scan_ports=scan_ports)
    return jsonify(result)


@api_bp.route('/scan/status', methods=['GET'])
def scan_status():
    """获取扫描状态"""
    return jsonify({
        'success': True,
        'data': {
            'is_scanning': scanner.is_scanning,
            'last_result': scanner.get_last_result(),
        }
    })


@api_bp.route('/scan/logs', methods=['GET'])
def get_scan_logs():
    """获取扫描日志"""
    limit = request.args.get('limit', 10, type=int)
    logs = scanner.get_scan_logs(limit=limit)
    return jsonify({
        'success': True,
        'data': logs
    })


@api_bp.route('/alerts', methods=['GET'])
def get_alerts():
    """获取告警列表"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    unread_only = request.args.get('unread', '') == '1'

    notification_service = NotificationService(current_app._get_current_object())
    alerts, total = notification_service.get_alerts(
        page=page,
        per_page=per_page,
        unread_only=unread_only
    )

    return jsonify({
        'success': True,
        'data': {
            'alerts': alerts,
            'total': total,
            'page': page,
            'per_page': per_page,
        }
    })


@api_bp.route('/alerts/<int:alert_id>/read', methods=['POST'])
def mark_alert_read(alert_id):
    """标记告警为已读"""
    notification_service = NotificationService(current_app._get_current_object())
    notification_service.mark_as_read(alert_id)
    return jsonify({'success': True})


@api_bp.route('/alerts/read-all', methods=['POST'])
def mark_all_alerts_read():
    """标记所有告警为已读"""
    notification_service = NotificationService(current_app._get_current_object())
    notification_service.mark_all_as_read()
    return jsonify({'success': True})


@api_bp.route('/conflicts', methods=['GET'])
def get_conflicts():
    """获取冲突信息"""
    conflict_detector = ConflictDetector()
    conflicts = conflict_detector.detect()
    summary = conflict_detector.get_conflict_summary()

    return jsonify({
        'success': True,
        'data': {
            'conflicts': conflicts,
            'summary': summary,
        }
    })


@api_bp.route('/auto-start', methods=['POST'])
def toggle_auto_start():
    """切换开机自启"""
    import sys
    if sys.platform != 'win32':
        return jsonify({'success': False, 'error': 'Only supported on Windows'})

    data = request.get_json() or {}
    enabled = data.get('enabled', False)

    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )

        if enabled:
            # 获取启动脚本路径
            import os
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            tray_path = os.path.join(base_dir, 'tray.py')
            pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
            winreg.SetValueEx(key, "IPRegister", 0, winreg.REG_SZ, f'"{pythonw}" "{tray_path}"')
        else:
            try:
                winreg.DeleteValue(key, "IPRegister")
            except FileNotFoundError:
                pass

        winreg.CloseKey(key)
        return jsonify({'success': True, 'enabled': enabled})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@api_bp.route('/ports', methods=['GET'])
def get_ports():
    """获取端口配置"""
    return jsonify({
        'success': True,
        'data': scanner.port_scanner.get_config()
    })


@api_bp.route('/ports', methods=['POST'])
def update_ports():
    """更新端口配置"""
    data = request.get_json() or {}
    action = data.get('action')

    if action == 'add':
        port = data.get('port')
        if scanner.port_scanner.add_port(port):
            return jsonify({'success': True, 'message': f'Port {port} added'})
        return jsonify({'success': False, 'error': 'Invalid port'}), 400

    elif action == 'remove':
        port = data.get('port')
        if scanner.port_scanner.remove_port(port):
            return jsonify({'success': True, 'message': f'Port {port} removed'})
        return jsonify({'success': False, 'error': 'Invalid port'}), 400

    elif action == 'set_custom_only':
        enabled = data.get('enabled', False)
        scanner.port_scanner.set_custom_only(enabled)
        return jsonify({'success': True, 'custom_only': enabled})

    elif action == 'set_ports':
        ports = data.get('ports', [])
        scanner.port_scanner.ports = sorted(set(int(p) for p in ports if 1 <= int(p) <= 65535))
        scanner.port_scanner._write_config()
        return jsonify({'success': True, 'ports': scanner.port_scanner.ports})

    return jsonify({'success': False, 'error': 'Invalid action'}), 400
