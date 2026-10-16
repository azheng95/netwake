# NetWake

面向 Linux NAS（包括飞牛 NAS）的局域网设备发现、设备管理和 Wake-on-LAN 工具。一个镜像、一个容器，内置 Web、LAN 能力和 Caddy HTTPS 代理。本文是 v1.0.0 的自包含部署说明，可供用户或 AI 部署助手直接使用，不需要获取项目源码。

## 1. 部署契约（供 AI 优先读取）

- 镜像：`azheng95/netwake:1.0.0`；滚动标签：`azheng95/netwake:latest`。生产部署优先固定版本。
- 当前已发布平台：`linux/amd64`（x86-64）。不要假定已提供 ARM64 镜像。
- 只有一个服务 `app` 和一个容器 `netwake`，不要另外部署 Web、Agent 或 Caddy 容器。
- Linux NAS 正式部署必须使用 `network_mode: host`，保留 `NET_RAW`，不需要 `privileged: true` 或 `NET_ADMIN`，不挂载 Docker socket。
- host 模式不要填写 `ports:`，自定义端口通过容器环境变量设置。
- HTTP 默认 `26665`，HTTPS 默认 `26666`，内部 Web 默认仅监听 `127.0.0.1:18080`。三者必须不同且未被占用。
- `TLS_HOST` 是访问用的单个 NAS IPv4 或域名，不含协议、路径或端口。当前启动器不支持 IPv6。
- `APP_TOKEN` 没有默认值，不会自动生成。必须在主机上生成至少 32 字符的随机令牌，不能使用示例占位符。
- `/data` 保存 SQLite 设备数据和首次设置状态，`/tls` 保存 TLS/CA 数据，`/config` 保存 Caddy 配置状态，都要持久化。
- 扫描和 WoL 面向同一二层局域网/VLAN，路由器能看到设备不代表容器能跨 VLAN 发现设备。
- 文中 `192.168.0.111`、网卡名和目录均为示例，部署前应读取目标 NAS 的实际值，不能直接猜测。
- 不要将令牌、CA 私钥、真实设备台账或主机日志发布到公开说明中。

## 2. 部署前检查

在 NAS 主机终端执行（不是在其他电脑或 bridge 容器内）：

```bash
uname -m
docker version
docker compose version
ip -4 addr show
ip -4 route show
ss -lnt
```

`x86_64` 对应当前镜像。选择拥有 NAS 局域网 IP 的实际网卡，例如 `eth0`、`bond0`、`br0`；不要选择 `docker0`、`veth*` 或回环网卡。确认 HTTP、HTTPS 和内部端口没有被 NAS 其他服务占用。

示例网络：路由器 `192.168.0.1`，NAS `192.168.0.111`，目标电脑 `192.168.0.101`，实际掩码为 `255.255.255.0` 时，扫描网段是 `192.168.0.0/24`，广播地址是 `192.168.0.255`。`/24` 表示前 24 位是网络位，不是设备数量；不能仅凭 IP 推断实际掩码。

## 3. 完整 Compose 部署

在 NAS 的持久化存储上创建项目目录，例如 `/vol1/1000/docker/netwake`（请按实际路径调整）。该目录中准备下面两个文件；飞牛 Docker 的 Compose 项目也可以使用相同配置。

### docker-compose.yml

```yaml
services:
  app:
    image: ${NETWAKE_IMAGE:-azheng95/netwake:1.0.0}
    container_name: netwake
    restart: unless-stopped
    init: true
    stop_grace_period: 15s
    network_mode: host
    cap_drop:
      - ALL
    cap_add:
      - NET_RAW
    environment:
      DB_PATH: /data/netwake.db
      APP_TOKEN: ${APP_TOKEN:?Set APP_TOKEN in .env}
      APP_PORT: ${APP_PORT:-18080}
      WEB_HTTP_PORT: ${WEB_HTTP_PORT:-26665}
      WEB_HTTPS_PORT: ${WEB_HTTPS_PORT:-26666}
      TLS_HOST: ${TLS_HOST:?Set TLS_HOST in .env}
      AGENT_NAME: ${AGENT_NAME:-nas-lan-agent}
      SCAN_INTERFACE: ${SCAN_INTERFACE:-}
      DEFAULT_CIDR: ${DEFAULT_CIDR:-192.168.0.0/24}
    volumes:
      - ./data:/data
      - caddy_data:/tls
      - caddy_config:/config

volumes:
  caddy_data:
  caddy_config:
```

### .env

```dotenv
NETWAKE_IMAGE=azheng95/netwake:1.0.0
APP_TOKEN=REPLACE_WITH_YOUR_RANDOM_TOKEN
TLS_HOST=192.168.0.111
WEB_HTTP_PORT=26665
WEB_HTTPS_PORT=26666
APP_PORT=18080
AGENT_NAME=nas-lan-agent
SCAN_INTERFACE=eth0
DEFAULT_CIDR=192.168.0.0/24
```

在主机上执行 `openssl rand -hex 32` 生成随机令牌，将结果写入 `.env` 的 `APP_TOKEN`；不要保留上述占位符，不要使用公开固定令牌或要求用户把令牌发到聊天中。若没有 OpenSSL，可用可信密码管理器生成至少 32 字符的随机字母数字串。

将 `TLS_HOST`、`SCAN_INTERFACE`、`DEFAULT_CIDR` 改成实际值。未指定 `SCAN_INTERFACE` 时会回退到 Scapy 默认网卡，多网卡 NAS 建议明确指定。

在该目录执行：

```bash
mkdir -p data
chmod 600 .env
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
```

如果 NAS 图形界面无法读取相邻 `.env` 文件，将这些变量填入项目环境变量设置，或直接替换 Compose 中的变量引用；令牌仍须保密。不要因模板变量错误改用空令牌。

访问示例：

- HTTP：<http://192.168.0.111:26665>
- HTTPS：<https://192.168.0.111:26666>

HTTP 和 HTTPS 并行提供服务，不会自动重定向。两种协议必须使用不同端口，不能把 HTTP 地址改成 HTTPS 协议却继续使用 HTTP 端口。

首次打开会弹出已配置的管理令牌，用户复制保存并确认后，初始令牌接口不再展示。**首次确认前，任何能访问管理服务的人都可能取得该令牌**，所以首次初始化必须在受信任局域网中进行，不要提前暴露到公网。展示令牌不等于自动生成令牌。

## 4. 环境变量和数据目录

| 变量 | 默认值/要求 | 含义 |
| --- | --- | --- |
| `APP_TOKEN` | 必填，无默认值 | 至少 32 字符的随机管理令牌；`replace-with-` 开头的值也会被拒绝 |
| `WEB_HTTP_PORT` | `26665` | HTTP 监听端口 |
| `WEB_HTTPS_PORT` | `26666` | HTTPS 监听端口 |
| `APP_PORT` | `18080` | 仅回环监听的内部 Web 端口，仍会占用 NAS 主机端口 |
| `TLS_HOST` | 镜像默认 `localhost` | NAS 上务必设为实际访问 IP/域名，证书按此签发 |
| `SCAN_INTERFACE` | 空 | LAN 网卡名；空值使用 Scapy 默认网卡 |
| `DEFAULT_CIDR` | `192.168.0.0/24` | 默认扫描范围，不是自动扫描整个家庭网络 |
| `AGENT_NAME` | 镜像默认 `netwake-agent` | LAN 模块显示名称，不代表独立容器 |
| `DB_PATH` | `/data/netwake.db` | SQLite 路径，建议保留 |
| `NETWAKE_IMAGE` | 由 Compose 模板定义 | 镜像标签选择，不是程序运行参数 |

端口取值范围为 1 到 65535；本模板收紧了权限，建议使用大于 1024 的空闲端口。旧 Compose 的 `WEB_PORT` 曾作为 HTTP 端口回退；新部署只使用明确的 `WEB_HTTP_PORT`，不要依赖旧别名。不再需要 `AGENT_TOKEN` 或 `AGENT_URL`。

自定义端口示例：`.env` 设置 `WEB_HTTP_PORT=27665`、`WEB_HTTPS_PORT=27666`，执行 `docker compose up -d --force-recreate app`，访问端口相应改变。不需要 `-p`。

持久化目录：`./data` 对应 `/data`，命名卷 `caddy_data` 对应 `/tls`，`caddy_config` 对应 `/config`。Compose 会给卷名添加项目名前缀。不要随意修改项目名或执行 `docker compose down -v`，否则可能创建新卷或删除证书状态。

## 5. HTTPS 与安全访问

默认是 Caddy 内部 CA 证书，并非公有 CA 证书。连接会加密，但访问设备未信任 CA 时会提示证书不受信任；不能宣称浏览器默认信任或自动取得公网证书。通过可信渠道导出公开根证书并安装到客户端信任存储：

```bash
docker cp netwake:/tls/caddy/pki/authorities/local/root.crt ./netwake-root.crt
```

只导出 `root.crt`，不要分享 `root.key` 或整个 `/tls` 目录。TLS/CA 卷备份含私钥，应加密保存。若需使用自有证书，可自定义 Caddyfile 并挂载证书；当前默认镜像不会自动使用 NAS 证书。

建议仅在受信任内网使用，远程管理通过 VPN 或受保护的反向代理，不要直接映射公网端口。HTTP 会明文传输令牌；仍建议通过主机防火墙限制访问来源。内部 Web 在主机回环上，NAS 本机其他进程也可访问。

## 6. 设备发现与唤醒

1. 在目标电脑开机且有线联网时执行扫描，选择实际 LAN 网卡及其直连网段。扫描发现的设备会保存到账本。
2. 主机名目前尽力通过 NetBIOS（UDP 137）查询，不保证每台设备都有名字，也不代表完整 DHCP/DNS/mDNS 发现。可手动改设备名称。
3. 手动添加设备最少只需 MAC，通常填写名称和 MAC；IP、广播地址可选。多网卡或广播不稳定时，建议填写实际网段广播地址。
4. 电脑 BIOS/UEFI、网卡和操作系统开启 WoL，关机后网卡仍有供电，NAS 与电脑位于同一二层 LAN/VLAN。
5. 点击唤醒，再用探测或实际连接确认是否开机。`packet_sent=true` 只表示发出了 Magic Packet，不保证目标已启动。

ARP 只能发现当前响应的在线设备，不能发现从未保存过的关机电脑。扫描范围仅支持私网/链路本地 IPv4，最多 4096 个地址，且必须在所选网卡的直连网络内；不要为了“多发现设备”盲目扩大到整个 `/16`。路由器客户端隔离、不同 VLAN、网卡驱动、Windows 快速启动和 BIOS 省电设置均可能影响结果。

## 7. API 约定（供自动化和 AI 集成）

管理 API 使用请求头 `X-Admin-Token`，不是 Bearer 认证。通过当前 HTTP/HTTPS 入口调用，不存在独立 Agent 服务地址。除明确公开接口外，下表接口均需令牌。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/healthz` | 公开进程存活检查，不验证物理局域网能力 |
| GET | `/api/config` | 公开版本和默认网段信息 |
| GET | `/api/agent/status` | 内置 LAN 模块状态，成功不等于 ARP/WoL 验收通过 |
| GET | `/api/discovery/interfaces` | 枚举网卡、IPv4 和可推荐网段 |
| POST | `/api/discovery/scan` | 请求体如 `{"cidr":"192.168.0.0/24","interface":"eth0"}`，扫描并更新设备账本 |
| GET / POST | `/api/devices` | 列表或新增，新增最小请求为 `{"mac":"AA:BB:CC:DD:EE:02"}` |
| PATCH / DELETE | `/api/devices/{id}` | 修改或删除记录 |
| POST | `/api/devices/{id}/wake` | 对已保存设备发送 WoL，无需请求体 |
| POST | `/api/devices/{id}/probe` | 探测保存设备的 IP，无需请求体 |
| GET | `/api/activity` | 操作日志 |

Web 和兼容 Agent 默认关闭 `/openapi.json`、`/docs` 和 `/redoc`，并由 Caddy 入口再次返回 404，避免把管理接口结构暴露给公网。

默认关闭 `/openapi.json`、`/docs` 和 `/redoc`，避免把管理接口结构暴露给公网。MAC 支持冒号、短横线或 12 位十六进制形式，必须是有效单播地址；IP 和广播地址限制在允许的私网/链路本地范围，WoL 广播另允许 `255.255.255.255`。重复 MAC 返回 409，未授权返回 401，输入校验失败通常返回 422。

首次设置令牌接口默认关闭。只有在受信任的局域网首次配置期间，显式设置 `ALLOW_INITIAL_TOKEN_ENDPOINT=true` 才会启用 `GET /api/setup/initial-token`；确认保存后接口仍会返回 404。生产环境建议保持关闭，并直接通过受保护的 `.env` 注入 `APP_TOKEN`。`POST /api/setup/token-saved` 始终需要管理员令牌；远程 API 不提供令牌重置。

扫描会更新设备在线状态、合并新发现设备，并可能把该扫描范围内未发现的已保存设备标为离线；不是纯只读操作。自动化执行扫描、唤醒、编辑、删除前，应遵循用户授权和目标网络范围。

## 8. 验收与排错

```bash
docker compose ps
docker compose logs --tail=100 app
curl -fsS http://127.0.0.1:26665/healthz
```

HTTPS 可使用已导出的 CA 验证，例如 `curl --cacert ./netwake-root.crt https://192.168.0.111:26666/healthz`，地址必须与 `TLS_HOST` 匹配。端口改过时相应替换。日志可能包含网络信息，分享前请脱敏。

| 现象 | 检查点 |
| --- | --- |
| 容器反复重启 | 令牌不足 32 字符、端口冲突、TLS_HOST 包含协议/端口、目录写权限；查看日志 |
| 页面能开但扫不到设备 | 是否在 Linux NAS、是否 host 网络、是否保留 NET_RAW、是否选择实际 LAN 网卡、目标是否在线 |
| 提示 Unknown network interface | `eth0` 只是示例，改成 NAS 实际网卡名 |
| 提示网段不直连 | 核对网卡 IP、掩码和路由，不要扫描另一个 VLAN 或扩大到非直连范围 |
| 只显示 MAC/IP | 设备未响应 NetBIOS，属于正常限制，可手动命名 |
| 提示 exec format error/no matching manifest | 核对 CPU 架构，当前发布平台为 linux/amd64 |
| 数据消失 | 核对 bind mount 的绝对路径、Compose 项目目录及卷名，没有挂载旧数据时会新建数据库 |
| 唤醒显示发送成功但未开机 | 核对有线 MAC、广播地址、BIOS/网卡配置和关机网卡供电，不要仅依据 API 返回判断已开机 |

Windows/macOS Docker Desktop 的 bridge 网络可用于查看管理页，但不能作为 NAS 物理二层扫描验收。默认不要推荐它替代 Linux LAN 部署。该平台仅测试管理页面时可改为 bridge 并显式映射 HTTP/HTTPS 同名端口；这不保证扫描或 WoL 能到达宿主机物理网络。

## 9. 更新、备份、迁移和令牌重置

更新前备份 `.env`（保密）、Compose 文件、`data` 和两个 Caddy 命名卷。SQLite 一致性备份应先停止应用再备份整个数据目录，不要在运行中只复制 `netwake.db` 而忽略 WAL。命名卷需另行完整备份，NAS 快照或 Docker 卷备份均可。备份完成后恢复运行。

```bash
docker compose stop app
# 在主机上备份 ./data、.env、Compose 文件和两个命名卷。
docker compose up -d
```

需要更新时修改 `NETWAKE_IMAGE`，执行：

```bash
docker compose pull
docker compose up -d
docker compose ps
```

`latest` 可能随发布改变，固定 `1.0.0` 不会自动跟随新版本。回滚镜像前确认数据库兼容性；需要时恢复与该版本配套的数据备份。不要把回滚等同于恢复数据库。

从旧 Web + Agent + Caddy 架构迁移：先备份，保留同一项目名、原 `./data` 和证书卷，改用本文单服务 Compose，再执行 `docker compose up -d --remove-orphans`。旧镜像仓库不再使用，无需配置 `AGENT_URL`/`AGENT_TOKEN`。

忘记管理令牌时，只允许通过有权限的 NAS 主机终端或 NAS 本机管理操作处理：生成新的随机令牌、修改 `.env` 的 `APP_TOKEN`，然后执行 `docker compose up -d --force-recreate app`。不要仅执行 `restart`，因为它不会载入修改后的容器环境变量。已有初始化状态会保留，不会再次弹出首次令牌窗口，请在主机上保存新令牌。**不要删除数据库或提供 Web 远程重置接口来绕过认证。**

## 10. AI 部署执行清单

AI 或自动化部署助手应按以下顺序执行，并在失败时停止，不要猜测 NAS 网卡、IP 或令牌：

```bash
mkdir -p /path/to/netwake/data
cd /path/to/netwake
cp .env.example .env
openssl rand -base64 36
# 将输出写入 .env 的 APP_TOKEN；按实际 NAS 地址修改 TLS_HOST
docker compose config
docker compose pull
docker compose up -d
docker compose ps
curl -fsS http://127.0.0.1:18080/healthz
curl -i http://127.0.0.1:26665/openapi.json
```

验收要求：健康检查返回 `ok=true`；`/openapi.json`、`/docs`、`/redoc` 必须返回 404；管理 API 未提供 `X-Admin-Token` 时必须返回 401。AI 不应把 `.env`、`APP_TOKEN`、Caddy 私钥、数据库或运行日志写入回答、工单或公开仓库。
