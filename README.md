# NetWake

NetWake 是一个面向家庭 NAS 和小型办公室的局域网设备发现、设备台账和 Wake-on-LAN 管理工具。Web 管理端和 LAN Agent 能力打包在同一个应用镜像中，适合部署在能访问目标网段的 Linux NAS 上。

面向用户和 AI 部署助手的独立镜像部署说明见 [DOCKERHUB.md](DOCKERHUB.md)，包含不依赖源码的 Compose、参数表、API 和排错约定。

## 架构

```text
浏览器
   │ HTTP / HTTPS
   ▼
NetWake 单容器
   ├─ Caddy（TLS 终止、反向代理）
   │ 本机 HTTP
   ▼
Web + LAN 模块（同一容器，host network）
   ├─ Web 管理端（SQLite、设备台账、操作日志）
   └─ LAN 能力（ARP 扫描、连通性探测、Magic Packet）
   │
   ├─ ARP 广播发现当前在线设备，并尝试通过 NetBIOS 查询 Windows 主机名
   ├─ UDP 广播发送 WoL Magic Packet
   └─ TCP/ICMP 探测指定设备是否上线
```

代码按职责分层：

- `agent/services/discovery.py`、`probe.py`、`wol.py`：局域网能力模块，由 Web 应用直接调用。
- `agent/schemas.py`、`security.py`：Agent 请求输入校验。
- `web/app/api/`：HTTP 路由。
- `web/app/services/`：发现结果合并、WoL/探测编排。
- `web/app/repository.py`、`database.py`：SQLite 设备台账和活动日志。
- `web/static/`：轻量 Web 管理界面。

## 在 `192.168.0.111` NAS 部署

把项目复制到 NAS 后执行：

```bash
cd /path/to/netwake
cp .env.example .env
```

编辑 `.env`，修改管理令牌、NAS 地址和扫描网卡：

```dotenv
WEB_HTTP_PORT=26665
WEB_HTTPS_PORT=26666
TLS_HOST=192.168.0.111
APP_TOKEN=替换为至少32字符的随机管理令牌
ALLOW_INITIAL_TOKEN_ENDPOINT=false
AGENT_NAME=nas-lan-agent
SCAN_INTERFACE=eth0
DEFAULT_CIDR=192.168.0.0/24
NETWAKE_IMAGE=azheng95/netwake:1.0.0
```

网卡名请以 NAS 上 `ip link` 的实际结果为准，例如 `eth0`、`bond0` 或 `br0`。

启动单容器（Web、LAN 和 HTTPS 代理均在镜像内）：

```bash
docker compose up -d
```

浏览器访问：

- HTTP：`http://192.168.0.111:26665`
- HTTPS：`https://192.168.0.111:26666`

`WEB_HTTP_PORT` 和 `WEB_HTTPS_PORT` 是监听端口，可按需修改；`TLS_HOST` 必须与浏览器地址栏使用的 NAS IP 或内网域名一致。单容器使用 host 网络，内置 Caddy 通过回环地址 `127.0.0.1:18080` 访问 Web；Agent 与 Web 不再需要跨容器通信。`APP_PORT` 可修改内部端口以避免 NAS 端口占用，三个端口必须不同。host 模式下不要再配置 Docker 端口映射。Linux NAS 上 host 网络使扫描模块能使用实际局域网网卡。

HTTPS 默认由 Caddy 内部 CA 签发证书，访问会加密，但浏览器/手机尚未信任该 CA 时会显示证书警告。要消除警告，需要把 Caddy 根证书导入并信任访问设备；证书保存在 Docker 卷 `caddy_data` 中。正式对外使用建议配置可信域名和受信任的证书。HTTP 与 HTTPS 两个入口都会保留，不会自动把 HTTP 重定向到 HTTPS。

如需使用已有证书，可复制 `proxy/Caddyfile`，把 `tls internal` 改为 `tls /certs/fullchain.pem /certs/privkey.pem`，在 `app.volumes` 加入 `./certs:/certs:ro` 和 `./proxy/Caddyfile:/etc/netwake/Caddyfile:ro`，重启应用。根证书只导出公开的 `root.crt`，不要导出 CA 私钥：

```bash
docker cp netwake:/tls/caddy/pki/authorities/local/root.crt ./netwake-root.crt
```

从原版迁移时保留 `./data` 和证书卷，执行 `docker compose up -d --remove-orphans` 移除旧 Web、Agent 和代理容器。旧 `AGENT_TOKEN`、`AGENT_URL` 可删除；不要依赖旧的 `WEB_PORT` 别名。源码构建可执行 `docker build -t azheng95/netwake:1.0.0 .`。

输入 `APP_TOKEN` 登录管理端。

生产环境默认不会通过 Web 接口返回管理令牌。请把 `.env` 中的 `APP_TOKEN` 保存到密码管理器后输入管理端。仅在受信任的局域网首次初始化期间，才临时设置 `ALLOW_INITIAL_TOKEN_ENDPOINT=true`；确认保存后立即改回 `false` 并重建容器。

页面右上角的 `?` 帮助图标只显示本地重置说明。出于安全考虑，管理页面不提供远程重置令牌；需要在部署主机上修改 `.env` 的 `APP_TOKEN`，然后执行：

```bash
docker compose up -d --force-recreate app
```

容器重启后使用新令牌登录。

## 你的示例是否可行

可以。只要：

1. NAS `192.168.0.111` 和电脑 `192.168.0.101` 在同一二层局域网/VLAN；
2. 应用容器使用 Linux `network_mode: host`，并绑定实际局域网网卡；
3. 电脑 BIOS/UEFI、网卡驱动和操作系统已经开启 WoL；
4. 先在电脑开机时扫描并保存 MAC，例如 `AA:BB:CC:DD:EE:FF`；
5. 电脑关机后，从设备列表发送 WoL。

扫描只能发现当前响应 ARP 的在线设备；关机电脑不会凭空出现在新扫描结果中，所以必须先保存设备记录。扫描会尽力查询在线设备的 NetBIOS 主机名（常见于 Windows）；如果设备不响应或网络隔离了 UDP 137，仍会显示 IP 和 MAC。发送成功只代表 NAS 发出了 102 字节 Magic Packet，不代表电脑已经开机；可随后点击“探测”确认 TCP/ICMP 是否上线。

路由器“能够发现和唤醒”NAS/电脑是有利条件，但决定本项目能否工作的是 **NetWake 应用是否直接处在目标网段的二层网络**。如果路由器启用了客户端隔离、目标电脑在不同 VLAN，ARP 广播和定向广播可能被隔离。

## 安全和边界

- Web API 需要 `X-Admin-Token`，令牌使用常量时间比较。局域网能力由应用内部调用，不再暴露独立 Agent API。
- Web 和兼容 Agent 的 `/openapi.json`、`/docs` 和 `/redoc` 默认关闭，并由 Caddy 入口再次拦截；不要通过公网端口转发暴露管理面板。
- 扫描限制为最多 4096 个 IPv4 地址，仅允许 RFC1918 私网和链路本地网段。
- WoL 广播地址和探测目标限制在私网/链路本地范围；请只扫描自己管理的网络。
- 建议通过 VPN、内网反向代理或 NAS 防火墙访问 Web。
- SQLite 数据在 `data/netwake.db`，备份时停止服务或复制 WAL 相关文件。

## 验证和已知限制

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s web/tests -v
```

当前测试覆盖设备 CRUD、鉴权、严格地址校验、扫描合并、Magic Packet 报文和 WoL 操作反馈。Windows/Docker Desktop 不能代表 Linux NAS 的物理二层网络，真实 ARP 扫描和唤醒请在 `192.168.0.111` NAS 上验收。

Windows Docker Desktop 本地查看管理页时，可使用 bridge 网络和端口映射（仍只有一个容器）：

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --remove-orphans
```

本地 `.env` 设置 `TLS_HOST=localhost`，访问 `http://localhost:26665` 或 `https://localhost:26666`。此模式只用于本地管理页验证，不保证发现和唤醒 Windows 主机所在物理局域网；飞牛 NAS 部署只使用主 `docker-compose.yml`，不要叠加这个本地配置。
