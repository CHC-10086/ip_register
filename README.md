# IP Register - 局域网 IP 登记系统

基于 Flask 的局域网设备管理系统，以 MAC 地址为核心标识，支持自动扫描、端口检测、操作系统识别。

## 功能特性

- **设备发现**：ARP/Ping 扫描发现局域网设备
- **端口扫描**：自定义端口列表，持久化配置，重启不丢失
- **端口跳转**：点击端口直接打开浏览器访问对应服务
- **操作系统识别**：通过 TTL 自动识别 Windows/Linux/macOS
- **MAC 主标识**：MAC 地址唯一标识设备，IP 变化自动记录历史
- **快速登记**：扫描结果一键登记，端口自动填充
- **批量登记**：一键登记所有未录入设备
- **系统托盘**：后台运行，右下角图标控制
- **域名访问**：配置 hosts 后输入 `http://ip` 即可访问

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置域名（可选，推荐）

右键 `setup_domain.bat` → 以管理员身份运行

之后输入 `http://ip` 即可访问，无需记 IP 和端口。

### 3. 启动

**带托盘图标（推荐）：**
```
双击 start.bat
```
- 右下角出现蓝色 "IP" 图标
- 双击图标打开仪表盘
- 右键 → Quit 退出

**命令行：**
```bash
python app.py
```

### 4. 访问

- 域名访问：http://ip
- IP 访问：http://127.0.0.1:8088

## 使用流程

1. 启动后在扫描页面点击「开始扫描」
2. 发现设备后点击「登记」填写信息
3. 端口会自动填充，也可以手动添加
4. 保存后在设备列表点击端口即可访问服务

## 端口管理

在扫描页面管理扫描端口：

- **添加端口**：输入端口号，点添加
- **删除端口**：点端口上的 ×
- **仅自定义端口**：开启后只扫描你添加的端口

配置保存在 `config_ports.json`，重启不丢失。

默认端口：22, 80, 443, 3389, 3306, 5432, 6379, 8080, 8443, 8888, 27017

## 操作系统识别

通过 TTL 值自动识别：

| TTL 范围 | 系统 |
|---------|------|
| ≤ 64 | Linux/macOS |
| ≤ 128 | Windows |

## 项目结构

```
ip_register/
├── app.py                  # Flask 入口
├── tray.py                 # 系统托盘
├── config.py               # 配置
├── config_ports.json       # 端口配置（持久化）
├── requirements.txt        # 依赖
├── start.bat               # 启动
├── stop.bat                # 停止
├── setup_domain.bat        # 域名配置
├── remove_domain.bat       # 移除域名
├── install_npcap.bat       # Npcap 安装
├── models/
│   ├── database.py         # SQLite 数据库
│   └── device.py           # 设备模型（MAC 主键）
├── services/
│   ├── scanner.py          # 扫描服务
│   ├── conflict.py         # 冲突检测
│   ├── notification.py     # 告警服务
│   ├── mac_vendor.py       # MAC 厂商查询
│   └── os_detect.py        # 系统识别
├── routes/
│   ├── api.py              # REST API
│   └── views.py            # 页面路由
└── templates/              # HTML 模板
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/devices | 设备列表 |
| POST | /api/devices | 创建设备 |
| PUT | /api/devices/{id} | 更新设备 |
| DELETE | /api/devices/{id} | 删除设备 |
| POST | /api/scan | 启动扫描 |
| GET | /api/ports | 获取端口配置 |
| POST | /api/ports | 更新端口配置 |
| POST | /api/auto-start | 开机自启开关 |

## 配置说明

**config.py：**
```python
SCAN_SUBNET = '192.168.1.0/24'  # 扫描网段
SCAN_TIMEOUT = 2                 # 扫描超时
```

**config_ports.json：**
```json
{
  "ports": [22, 80, 443, 3389, 3306],
  "use_custom_only": true
}
```

## 注意事项

- ARP 扫描需要管理员权限
- Ping 扫描不需要特殊权限
- 端口扫描超时 0.3 秒，速度快
- 数据存储在 `data/ip_register.db`
- 端口跳转使用 `window.open` 方式，避免浏览器拦截

## 技术栈

- **后端**：Python + Flask
- **数据库**：SQLite
- **扫描**：scapy + socket
- **前端**：Bootstrap 5
- **托盘**：pystray + Pillow

## 许可证

MIT License
