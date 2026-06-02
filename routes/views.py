import os
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file
from models.device import DeviceRepository
from models.database import get_db
from services.scanner import ARPScanner, get_port_categories
from services.notification import NotificationService
from services.conflict import ConflictDetector

views_bp = Blueprint('views', __name__)
scanner = ARPScanner()


@views_bp.route('/')
def index():
    """仪表盘首页"""
    stats = DeviceRepository.get_stats()
    conflict_detector = ConflictDetector()
    conflict_summary = conflict_detector.get_conflict_summary()

    notification_service = NotificationService(current_app._get_current_object())
    unread_count = notification_service.get_unread_count()

    # 最近扫描日志
    scan_logs = scanner.get_scan_logs(limit=5)

    # 最近告警
    alerts, _ = notification_service.get_alerts(per_page=5)

    # 已登记设备（带端口的优先显示）
    registered_devices, _ = DeviceRepository.get_all(per_page=100, status='已登记')
    if not registered_devices:
        # 如果没有已登记的，显示所有有端口的设备
        all_devices, _ = DeviceRepository.get_all(per_page=100)
        registered_devices = [d for d in all_devices if d.port]

    # 检查自启状态
    auto_start_enabled = _check_auto_start()

    return render_template('index.html',
                           stats=stats,
                           conflicts=conflict_summary,
                           unread_count=unread_count,
                           scan_logs=scan_logs,
                           recent_alerts=alerts,
                           registered_devices=registered_devices[:10],
                           auto_start_enabled=auto_start_enabled)


def _check_auto_start():
    """检查是否设置了开机自启"""
    import sys
    if sys.platform != 'win32':
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ
        )
        winreg.QueryValueEx(key, "IPRegister")
        winreg.CloseKey(key)
        return True
    except (WindowsError, FileNotFoundError):
        return False


@views_bp.route('/devices')
def device_list():
    """设备列表页"""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('PER_PAGE', 20)
    status = request.args.get('status', '')
    keyword = request.args.get('keyword', '')

    devices, total = DeviceRepository.get_all(
        page=page,
        per_page=per_page,
        status=status if status else None,
        keyword=keyword if keyword else None
    )

    total_pages = (total + per_page - 1) // per_page

    return render_template('devices.html',
                           devices=devices,
                           page=page,
                           total_pages=total_pages,
                           total=total,
                           status=status,
                           keyword=keyword)


@views_bp.route('/devices/<int:device_id>')
def device_detail(device_id):
    """设备详情页"""
    device = DeviceRepository.get_by_id(device_id)
    if not device:
        flash('设备不存在', 'error')
        return redirect(url_for('views.device_list'))

    return render_template('device_edit.html', device=device, mode='view')


@views_bp.route('/devices/<int:device_id>/edit', methods=['GET', 'POST'])
def device_edit(device_id):
    """编辑设备信息"""
    device = DeviceRepository.get_by_id(device_id)
    if not device:
        flash('设备不存在', 'error')
        return redirect(url_for('views.device_list'))

    if request.method == 'POST':
        updates = {
            'device_name': request.form.get('device_name', '').strip(),
            'user_name': request.form.get('user_name', '').strip(),
            'department': request.form.get('department', '').strip(),
            'purpose': request.form.get('purpose', '').strip(),
            'os_info': request.form.get('os_info', '').strip(),
            'status': request.form.get('status', device.status),
            'remark': request.form.get('remark', '').strip(),
            'port': request.form.get('port', '').strip(),
        }

        DeviceRepository.update(device_id, **updates)
        flash('设备信息已更新', 'success')
        return redirect(url_for('views.device_detail', device_id=device_id))

    return render_template('device_edit.html', device=device, mode='edit')


@views_bp.route('/devices/add', methods=['GET', 'POST'])
def device_add():
    """手动添加设备"""
    if request.method == 'POST':
        ip = request.form.get('ip_address', '').strip()
        mac = request.form.get('mac_address', '').strip()

        if not ip:
            flash('IP 地址不能为空', 'error')
            return render_template('device_edit.html', device=None, mode='add')

        existing = DeviceRepository.get_by_ip(ip)
        if existing:
            flash('该 IP 地址已存在', 'error')
            return render_template('device_edit.html', device=None, mode='add')

        device_id = DeviceRepository.create(ip, mac if mac else None, status='已登记')

        # 更新其他信息
        updates = {
            'device_name': request.form.get('device_name', '').strip(),
            'user_name': request.form.get('user_name', '').strip(),
            'department': request.form.get('department', '').strip(),
            'purpose': request.form.get('purpose', '').strip(),
            'os_info': request.form.get('os_info', '').strip(),
            'remark': request.form.get('remark', '').strip(),
            'port': request.form.get('port', '').strip(),
        }
        DeviceRepository.update(device_id, **updates)

        flash('设备已添加', 'success')
        return redirect(url_for('views.device_list'))

    return render_template('device_edit.html', device=None, mode='add')


@views_bp.route('/devices/<int:device_id>/delete', methods=['POST'])
def device_delete(device_id):
    """删除设备"""
    device = DeviceRepository.get_by_id(device_id)
    if not device:
        flash('设备不存在', 'error')
    else:
        DeviceRepository.delete(device_id)
        flash('设备已删除', 'success')

    return redirect(url_for('views.device_list'))


@views_bp.route('/devices/add-from-scan', methods=['GET', 'POST'])
def device_add_from_scan():
    """从扫描结果快速登记设备"""
    # 支持 GET 和 POST 两种方式获取参数
    if request.method == 'POST':
        ip = request.form.get('ip', '').strip()
        mac = request.form.get('mac', '').strip()
        ports = request.form.get('ports', '').strip()
    else:
        ip = request.args.get('ip', '').strip()
        mac = request.args.get('mac', '').strip()
        ports = request.args.get('ports', '').strip()

    # 检查是否已存在
    existing = DeviceRepository.get_by_ip(ip)
    if existing:
        flash(f'设备 {ip} 已存在，进入编辑模式', 'info')
        return redirect(url_for('views.device_edit', device_id=existing.id))

    # 创建一个临时对象用于表单预填
    class ScanDevice:
        def __init__(self, ip, mac, ports):
            self.id = None
            self.ip_address = ip
            self.mac_address = mac
            self.port = ports
            self.device_name = ''
            self.user_name = ''
            self.department = ''
            self.purpose = ''
            self.os_info = ''
            self.status = '未登记'
            self.remark = ''

    device = ScanDevice(ip, mac, ports)
    return render_template('device_edit.html', device=device, mode='add')


@views_bp.route('/scan/register-all', methods=['POST'])
def scan_register_all():
    """批量登记扫描结果中的未录入设备"""
    scan_data = request.form.get('scan_data', '[]')
    try:
        devices = json.loads(scan_data)
    except (json.JSONDecodeError, TypeError):
        devices = []

    registered = 0
    for device in devices:
        ip = device.get('ip', '')
        if not ip:
            continue
        existing = DeviceRepository.get_by_ip(ip)
        if existing:
            # 更新端口信息
            ports_str = device.get('ports_str', '')
            if ports_str:
                old_ports = set(existing.port.split(',')) if existing.port else set()
                new_ports = set(ports_str.split(','))
                merged = sorted(old_ports | new_ports, key=lambda x: int(x) if x.isdigit() else 0)
                DeviceRepository.update(existing.id, port=','.join(merged))
            continue

        mac = device.get('mac', '')
        ports_str = device.get('ports_str', '')
        device_id = DeviceRepository.create(ip, mac if mac else None, status='未登记')
        if ports_str:
            DeviceRepository.update(device_id, port=ports_str)
        registered += 1

    if registered > 0:
        flash(f'成功登记 {registered} 个新设备', 'success')
    else:
        flash('没有新设备需要登记', 'info')

    return redirect(url_for('views.scan_page'))


@views_bp.route('/scan')
def scan_page():
    """扫描页面"""
    scan_logs = scanner.get_scan_logs(limit=20)
    last_result = scanner.get_last_result()
    port_count = len(scanner.port_scanner.ports)
    port_categories = get_port_categories()

    return render_template('scan.html',
                           scan_logs=scan_logs,
                           last_result=last_result,
                           is_scanning=scanner.is_scanning,
                           port_count=port_count,
                           port_categories=port_categories)


@views_bp.route('/scan/start', methods=['POST'])
def scan_start():
    """启动扫描"""
    subnet = request.form.get('subnet', '').strip()
    if not subnet:
        subnet = None
    scan_ports = request.form.get('scan_ports') == '1'
    custom_ports = request.form.get('custom_ports', '').strip()

    # 处理自定义端口
    if custom_ports:
        extra_ports = [p.strip() for p in custom_ports.split(',') if p.strip()]
        for p in extra_ports:
            try:
                port = int(p)
                if 1 <= port <= 65535 and port not in scanner.port_scanner.ports:
                    scanner.port_scanner.ports.append(port)
            except (ValueError, TypeError):
                pass
        scanner.port_scanner.ports.sort()

    result = scanner.scan(subnet, scan_ports=scan_ports)

    if result.get('success'):
        flash(f'扫描完成，发现 {result["total_found"]} 个设备，新增 {result["new_devices"]} 个', 'success')
    else:
        flash(f'扫描失败: {result.get("error", "未知错误")}', 'error')

    return redirect(url_for('views.scan_page'))


@views_bp.route('/scan/async', methods=['POST'])
def scan_async():
    """异步启动扫描"""
    subnet = request.form.get('subnet', '').strip()
    if not subnet:
        subnet = None
    scan_ports = request.form.get('scan_ports') == '1'
    custom_ports = request.form.get('custom_ports', '').strip()

    # 处理自定义端口
    if custom_ports:
        extra_ports = [p.strip() for p in custom_ports.split(',') if p.strip()]
        for p in extra_ports:
            try:
                port = int(p)
                if 1 <= port <= 65535 and port not in scanner.port_scanner.ports:
                    scanner.port_scanner.ports.append(port)
            except (ValueError, TypeError):
                pass
        scanner.port_scanner.ports.sort()

    result = scanner.scan_async(subnet, scan_ports=scan_ports)
    flash('扫描已在后台启动', 'info')
    return redirect(url_for('views.scan_page'))


@views_bp.route('/alerts')
def alert_list():
    """告警列表页"""
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('PER_PAGE', 20)
    unread_only = request.args.get('unread', '') == '1'

    notification_service = NotificationService(current_app._get_current_object())
    alerts, total = notification_service.get_alerts(
        page=page,
        per_page=per_page,
        unread_only=unread_only
    )

    total_pages = (total + per_page - 1) // per_page
    unread_count = notification_service.get_unread_count()

    return render_template('alerts.html',
                           alerts=alerts,
                           page=page,
                           total_pages=total_pages,
                           total=total,
                           unread_count=unread_count,
                           unread_only=unread_only)


@views_bp.route('/alerts/<int:alert_id>/read', methods=['POST'])
def alert_read(alert_id):
    """标记告警为已读"""
    notification_service = NotificationService(current_app._get_current_object())
    notification_service.mark_as_read(alert_id)
    return redirect(request.referrer or url_for('views.alert_list'))


@views_bp.route('/alerts/read-all', methods=['POST'])
def alert_read_all():
    """标记所有告警为已读"""
    notification_service = NotificationService(current_app._get_current_object())
    notification_service.mark_all_as_read()
    flash('所有告警已标记为已读', 'success')
    return redirect(url_for('views.alert_list'))


@views_bp.route('/alerts/<int:alert_id>/delete', methods=['POST'])
def alert_delete(alert_id):
    """删除告警"""
    notification_service = NotificationService(current_app._get_current_object())
    notification_service.delete_alert(alert_id)
    flash('告警已删除', 'success')
    return redirect(url_for('views.alert_list'))


@views_bp.route('/export/csv')
def export_csv():
    """导出设备列表为 CSV"""
    import csv
    from io import StringIO
    from flask import Response

    devices, _ = DeviceRepository.get_all(per_page=10000)

    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['ID', 'IP地址', '端口', 'MAC地址', '设备名称', '使用者', '部门', '用途', '操作系统', '状态', '首次发现', '最后发现', '备注'])

    for d in devices:
        writer.writerow([
            d.id, d.ip_address, d.port or '', d.mac_address or '',
            d.device_name or '', d.user_name or '',
            d.department or '', d.purpose or '',
            d.os_info or '', d.status,
            d.first_seen, d.last_seen, d.remark or ''
        ])

    output = si.getvalue()
    si.close()

    return Response(
        '﻿' + output,  # BOM for Excel
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=devices.csv'}
    )


@views_bp.route('/install_npcap.bat')
def download_npcap_script():
    """下载 Npcap 安装脚本"""
    bat_path = os.path.join(current_app.config['BASE_DIR'], 'install_npcap.bat')
    if os.path.exists(bat_path):
        return send_file(bat_path, as_attachment=True, download_name='install_npcap.bat')
    flash('安装脚本不存在', 'error')
    return redirect(url_for('views.scan_page'))
