# IP Register - 局域网 IP 登记系统

基于 Flask 的局域网 IP 地址管理系统，支持自动扫描发现设备、端口扫描、操作系统识别、冲突检测等功能。

## 功能特性

- **自动扫描**：ARP/Ping 扫描发现局域网设备，获取 IP、MAC、厂商信息
- **端口扫描**：170+ 常用端口，覆盖 18 个类别（Web、数据库、远程管理等）
- **操作系统识别**：通过 TTL、NetBIOS、SSH、HTTP 等方式自动识别系统类型
- **设备登记**：扫描结果一键登记，自动填充 IP/MAC/端口
- **冲突检测**：IP/MAC 冲突自动告警
- **系统托盘**：后台运行，右下角图标控制
- **开机自启**：Web 页面一键开关
- **快速访问**：点击端口直接跳转到对应服务

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动

**带托盘图标启动（推荐）：**
```
双击 start.bat
```
- 右下角出现蓝色 "IP" 图标
- 双击图标打开仪表盘
- 右键图标 → Quit 退出

**命令行启动：**
```bash
python app.py
```

**停止：**
```
右键托盘图标 → Quit
```
或双击 `stop.bat`

### 3. 访问

浏览器打开：http://127.0.0.1:8088

## 系统托盘

使用 `start.bat` 启动时：
- 右下角显示蓝色 "IP" 图标
- **双击**：打开仪表盘
- **右键菜单**：
  - Open Dashboard：打开仪表盘
  - Quit：退出程序

## 开机自启

在仪表盘页面「服务控制」卡片中：
- 打开「开机自启」开关
- 系统会自动写入 Windows 注册表
- 开机后自动启动并显示托盘图标

## Npcap 安装（可选）

安装 Npcap 可以获取 MAC 地址和厂商信息：

1. 下载：https://npcap.com/#download
2. 安装时勾选「Install Npcap in WinPcap API-compatible Mode」
3. 重启应用

或运行：`install_npcap.bat`

不安装 Npcap 也可以使用 Ping 扫描（无法获取 MAC）。

## 端口扫描

扫描 170+ 常用端口，按类别分组：

| 类别 | 端口示例 |
|------|---------|
| Web 服务 | 80, 443, 8080, 8443, 8888 |
| 远程管理 | 22(SSH), 3389(RDP), 5900(VNC) |
| 数据库 | 3306(MySQL), 5432(PG), 6379(Redis), 27017(MongoDB) |
| 消息队列 | 5672(RabbitMQ), 9092(Kafka), 1883(MQTT) |
| 容器/编排 | 2375(Docker), 6443(K8s), 2379(etcd) |
| 监控日志 | 3000(Grafana), 9200(ES), 9090(Prometheus) |
| 游戏服务器 | 25565(MC), 27015(Source), 8211(Palworld) |
| VPN/隧道 | 1194(OpenVPN), 51820(WireGuard) |
| 存储/NAS | 445(SMB), 2049(NFS), 5000(Synology) |

支持在扫描时添加自定义端口。

## 操作系统识别

通过多种方式识别设备操作系统：

| 方式 | 说明 |
|------|------|
| TTL 值 | Windows=128, Linux=64 |
| NetBIOS | 查询 Windows 计算机名 |
| SSH Banner | 读取 SSH 服务系统信息 |
| HTTP Server | 读取 Web 服务器头部 |
| SMB 端口 | 445 端口开放=Windows |

## 项目结构

```
ip_register/
├── app.py                  # Flask 入口
├── tray.py                 # 系统托盘图标
├── config.py               # 配置文件
├── requirements.txt        # Python 依赖
├── start.bat               # 后台启动
├── stop.bat                # 停止服务
├── install_npcap.bat       # Npcap 安装脚本
├── README.md               # 说明文档
├── models/
│   ├── database.py         # SQLite 数据库
│   └── device.py           # 设备模型
├── services/
│   ├── scanner.py          # 扫描服务
│   ├── conflict.py         # 冲突检测
│   ├── notification.py     # 告警服务
│   ├── mac_vendor.py       # MAC 厂商查询
│   └── os_detect.py        # 操作系统识别
├── routes/
│   ├── api.py              # REST API
│   └── views.py            # 页面路由
├── templates/              # HTML 模板
└── utils/
    └── network.py          # 网络工具
```

## 配置说明

编辑 `config.py`：

```python
SCAN_SUBNET = '192.168.1.0/24'  # 默认扫描网段
SCAN_TIMEOUT = 2                 # 扫描超时（秒）
PORT_SCAN_TIMEOUT = 0.5          # 端口扫描超时
CUSTOM_PORTS = '9100,9200'       # 自定义额外端口
```

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/devices | 获取设备列表 |
| GET | /api/devices/{id} | 获取单个设备 |
| POST | /api/devices | 创建设备 |
| PUT | /api/devices/{id} | 更新设备 |
| DELETE | /api/devices/{id} | 删除设备 |
| GET | /api/stats | 获取统计数据 |
| POST | /api/scan | 启动扫描 |
| GET | /api/alerts | 获取告警列表 |
| POST | /api/auto-start | 切换开机自启 |

## 注意事项

- ARP 扫描需要**管理员权限**运行
- Ping 扫描不需要特殊权限
- 端口扫描覆盖 170+ 常用端口
- 数据存储在 SQLite：`data/ip_register.db`
- 系统托盘使用 pystray 库实现

## 技术栈

- **后端**：Python + Flask
- **数据库**：SQLite
- **扫描**：scapy + socket
- **前端**：Bootstrap 5 + Jinja2
- **托盘**：pystray + Pillow

## 许可证

MIT License
