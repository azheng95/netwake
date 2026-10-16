# NetWake：AI 可执行部署说明

本文是 NetWake 当前版本的自包含部署合同，面向 Linux NAS、Docker Compose 和 AI 部署助手。它描述的是仓库当前实现，不要求再部署独立的 Web、Agent 或 Caddy 容器。

> 版本基线：1.0.0
> 默认镜像：azheng95/netwake:1.0.0
> 当前发布平台：linux/amd64（x86-64）

## 0. 给 AI 的执行规则

AI 在执行任何命令前，必须从目标 NAS 主机读取并确认下面的事实；未知值不能猜测：

| 必须确认 | 示例 | 不能猜测的原因 |
| --- | --- | --- |
| CPU 架构 | x86_64 | 当前镜像只保证 linux/amd64 |
| 安装目录 | /volume1/docker/netwake | 目录错误会导致数据库或证书“丢失” |
| NAS 访问地址 | 192.168.0.111 或内网域名 | 用于 HTTPS 证书和访问地址 |
| LAN 网卡 | eth0、bond0、br0 | ARP 扫描必须使用实际局域网网卡 |
| 直连网段 | 192.168.0.0/24 | 扫描不支持任意跨 VLAN 网段 |
| HTTP/HTTPS/内部端口 | 26665/26666/18080 | 三个端口必须不同且未被占用 |
| 管理令牌 | 主机本地生成 | 不能由 AI 猜测、回显或要求用户发到聊天中 |

执行过程中遇到以下情况应立即停止并报告原因，不要用猜测值继续：

- 不是 Linux 主机、CPU 不是 x86_64，或 Docker/Compose 不可用；
- 无法确定 NAS 的实际 LAN 网卡、IP、掩码或直连网段；
- 端口冲突，或 TLS_HOST 含有协议、路径或端口；
- 无法安全生成和保存 APP_TOKEN；
- 用户要求把管理令牌、.env、数据库、CA 私钥或原始日志写入回答、工单或公开仓库。

AI 不得执行 docker compose down -v、删除 data、删除 caddy_data/caddy_config，也不得为了“修复”问题暴露公网端口或开启 privileged: true。

## 1. 部署模型和硬性约束

NetWake 是一个容器：

~~~text
浏览器 ── HTTP/HTTPS ──> Caddy ──> 127.0.0.1:APP_PORT ──> Web + LAN 模块
                                              │
                                  SQLite、ARP、NetBIOS、TCP/ICMP、WoL
~~~

- 正式 Linux NAS 部署必须使用 network_mode: host；host 模式下不要配置 ports:。
- 只保留 NET_RAW，不需要 privileged: true、NET_ADMIN 或 Docker socket。
- Web、LAN 能力和 Caddy 都在同一个 netwake 容器内，不要重复部署旧版 Agent 或代理容器。
- /data 保存 SQLite 数据；/tls 保存 Caddy CA/证书状态；/config 保存 Caddy 配置状态，三者都必须持久化。
- 当前镜像面向 linux/amd64。Windows/macOS Docker Desktop 的 bridge 网络只适合验证管理页面，不代表 NAS 的二层 ARP/WoL 能力。
- 扫描和 WoL 只面向容器所在的直连私网/VLAN。路由器能看到某台设备，不等于容器能跨 VLAN 发现或唤醒它。

## 2. 部署前检查（必须在 NAS 主机执行）

不要在另一台电脑、Docker Desktop 或 bridge 容器内执行下面的检查：

~~~bash
uname -m
docker version
docker compose version
ip -br -4 addr
ip -4 route
ss -lnt
~~~

AI 应根据输出记录：

1. uname -m 是否为 x86_64；
2. 哪个网卡拥有 NAS 的局域网 IPv4（例如 eth0、bond0、br0）；
3. 该网卡的掩码和直连网段，例如 192.168.0.111/24 对应 192.168.0.0/24；
4. 26665、26666、18080 是否空闲。

不能把 docker0、veth* 或 lo 当作 LAN 网卡。不能只凭 IP 猜测掩码；例如 192.168.0.111 可能不是 /24。

## 3. 创建部署目录和配置

以下示例假定安装目录为 /volume1/docker/netwake。AI 必须替换为用户确认过的实际路径：

~~~bash
install -d -m 700 /volume1/docker/netwake/data
cd /volume1/docker/netwake
~~~

### 3.1 docker-compose.yml

使用仓库中的 docker-compose.yml，或创建内容完全等价的文件：

~~~yaml
services:
  app:
    image: \${NETWAKE_IMAGE:-azheng95/netwake:1.0.0}
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
      APP_TOKEN: \${APP_TOKEN:?Set APP_TOKEN in .env}
      ALLOW_INITIAL_TOKEN_ENDPOINT: \${ALLOW_INITIAL_TOKEN_ENDPOINT:-false}
      APP_PORT: \${APP_PORT:-18080}
      WEB_HTTP_PORT: \${WEB_HTTP_PORT:-26665}
      WEB_HTTPS_PORT: \${WEB_HTTPS_PORT:-26666}
      TLS_HOST: \${TLS_HOST:?Set TLS_HOST in .env}
      AGENT_NAME: \${AGENT_NAME:-netwake-agent}
      SCAN_INTERFACE: \${SCAN_INTERFACE:-}
      DEFAULT_CIDR: \${DEFAULT_CIDR:-192.168.0.0/24}
    volumes:
      - ./data:/data
      - caddy_data:/tls
      - caddy_config:/config

volumes:
  caddy_data:
  caddy_config:
~~~

与仓库旧版 Compose 合并前，确认没有重复的 web、agent、caddy 服务，也没有遗留 AGENT_URL、AGENT_TOKEN 或 ports:。

### 3.2 .env

创建 .env，并只在 NAS 主机上编辑：

~~~dotenv
NETWAKE_IMAGE=azheng95/netwake:1.0.0
APP_TOKEN=在主机本地生成的随机令牌
TLS_HOST=192.168.0.111
WEB_HTTP_PORT=26665
WEB_HTTPS_PORT=26666
APP_PORT=18080
ALLOW_INITIAL_TOKEN_ENDPOINT=false
AGENT_NAME=nas-lan-agent
SCAN_INTERFACE=eth0
DEFAULT_CIDR=192.168.0.0/24
~~~

替换 TLS_HOST、SCAN_INTERFACE 和 DEFAULT_CIDR 为第 2 节检查得到的真实值。TLS_HOST 只能是一个 IPv4 地址或域名，例如 192.168.0.111 或 nas.home.arpa；不能写成 https://192.168.0.111:26666。

在主机上生成管理令牌，不要把输出写进聊天记录：

~~~bash
umask 077
openssl rand -hex 32
~~~

将输出写入 APP_TOKEN。令牌至少 32 个字符，不能保留 replace-with- 或“示例令牌”。然后锁定文件权限：

~~~bash
chmod 600 .env
~~~

如果没有 OpenSSL，使用可信密码管理器生成至少 32 个字符的随机字符串。AI 不应代用户生成一个公开固定令牌，也不应通过 Web 接口提供远程重置令牌。

## 4. 启动和验收

在项目目录执行，失败时保留输出并停止，不要盲目重复启动：

~~~bash
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
~~~

检查容器状态和日志：

~~~bash
docker compose ps
docker compose logs --tail=100 app
~~~

### 4.1 健康检查

APP_PORT 只在 NAS 主机回环监听，先执行：

~~~bash
curl -fsS http://127.0.0.1:18080/healthz
~~~

预期 JSON 中包含 "ok":true。如果修改了 APP_PORT，替换命令中的端口。

再从受信任客户端检查外部入口：

~~~bash
curl -fsS http://192.168.0.111:26665/healthz
curl -i http://192.168.0.111:26665/openapi.json
curl -i http://192.168.0.111:26665/api/devices
~~~

预期结果：

- /healthz 返回成功和 ok=true；
- /openapi.json、/docs、/redoc 返回 404；
- 未提供 X-Admin-Token 的管理 API 返回 401；
- 不能仅凭健康检查判断物理 LAN 扫描或 WoL 已成功。

浏览器地址为：

- HTTP：http://192.168.0.111:26665
- HTTPS：https://192.168.0.111:26666

将示例地址替换为实际 TLS_HOST 和端口。HTTP 与 HTTPS 并行提供，不会自动重定向。

### 4.2 首次登录和设备流程

1. 在受信任内网打开管理页面，输入 APP_TOKEN。
2. 目标电脑开机且有线联网时，先选择实际网卡和直连网段执行扫描。
3. 扫描结果会保存到设备台账；关机电脑不会凭空出现在新的 ARP 扫描中。
4. 确认 BIOS/UEFI、网卡和操作系统已启用 WoL，且关机后网卡仍供电。
5. 点击唤醒后，用“探测”或实际连接确认是否上线。packet_sent=true 只表示 NAS 发出了 102 字节 Magic Packet，不代表电脑已开机。

主机名是通过 NetBIOS（UDP 137）尽力查询的，设备不响应时只显示 IP/MAC 属于正常限制。扫描范围最多 4096 个 IPv4 地址，并且必须是所选网卡的允许私网/链路本地直连范围。

## 5. API 约定（供 AI 自动化）

管理接口通过当前 HTTP/HTTPS 入口访问，认证请求头是 X-Admin-Token，不是 Bearer：

| 方法 | 路径 | 是否需要令牌 | 说明 |
| --- | --- | --- | --- |
| GET | /healthz | 否 | 进程存活检查 |
| GET | /api/config | 否 | 版本和默认网段 |
| GET | /api/agent/status | 是 | 内置 LAN 模块状态 |
| GET | /api/discovery/interfaces | 是 | 网卡、IPv4 和推荐网段 |
| POST | /api/discovery/scan | 是 | 例如 {"cidr":"192.168.0.0/24","interface":"eth0"} |
| GET/POST | /api/devices | 是 | 列表或新增；新增最少需要 mac |
| PATCH/DELETE | /api/devices/{id} | 是 | 修改或删除设备 |
| POST | /api/devices/{id}/wake | 是 | 发送 WoL，无请求体 |
| POST | /api/devices/{id}/probe | 是 | 探测设备 IP，无请求体 |
| GET | /api/activity | 是 | 操作日志 |

自动化示例（令牌只从本地受保护环境变量读取，不要写入脚本输出）：

~~~bash
export NETWAKE_URL='http://192.168.0.111:26665'
read -r NETWAKE_TOKEN
curl -fsS "$NETWAKE_URL/api/discovery/interfaces" \
  -H "X-Admin-Token: $NETWAKE_TOKEN"
curl -fsS -X POST "$NETWAKE_URL/api/discovery/scan" \
  -H "X-Admin-Token: $NETWAKE_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"cidr":"192.168.0.0/24","interface":"eth0"}'
~~~

扫描不是纯只读操作：它会合并新设备，并可能把扫描范围内未发现的已保存设备标记为离线。AI 在扫描、唤醒、编辑或删除前必须得到用户授权并确认目标网络范围。

首次令牌接口默认关闭。只有在受信任局域网的首次初始化期间，才可临时设置 ALLOW_INITIAL_TOKEN_ENDPOINT=true；确认令牌保存后应改回 false 并执行 docker compose up -d --force-recreate app。生产环境建议始终保持关闭。

## 6. HTTPS、备份和更新

默认 HTTPS 使用 Caddy 内部 CA。连接会加密，但客户端未信任该 CA 时会显示证书警告。只导出公开根证书，不要导出私钥：

~~~bash
docker cp netwake:/tls/caddy/pki/authorities/local/root.crt ./netwake-root.crt
~~~

不要分享 root.key 或整个 /tls。正式对外使用时，应使用受信任域名和证书，并通过 VPN、内网反向代理或 NAS 防火墙限制访问；不要直接映射公网端口。

更新前先停止并备份：

~~~bash
docker compose stop app
# 备份 .env、docker-compose.yml、./data 以及 caddy_data/caddy_config 两个命名卷
docker compose up -d
~~~

更新固定版本镜像：

~~~bash
docker compose pull
docker compose up -d
docker compose ps
~~~

latest 可能随发布变化，生产环境优先固定版本。SQLite 一致性备份应停止应用后复制整个 data 目录，不要只复制运行中的 netwake.db 而忽略 WAL 文件。不要执行 docker compose down -v，否则可能删除证书和配置卷。

忘记令牌时，只能在有权限的 NAS 主机上生成新随机令牌、修改 .env，然后执行：

~~~bash
docker compose up -d --force-recreate app
~~~

不要只执行 restart（它不会重新载入修改后的环境变量），也不要删除数据库绕过认证。

## 7. 本地管理页测试（不用于 LAN 验收）

Windows/macOS Docker Desktop 可用 bridge 覆盖文件查看管理页面：

~~~bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --remove-orphans
~~~

本地 .env 使用 TLS_HOST=localhost，访问 http://localhost:26665 或 https://localhost:26666。该模式不保证 ARP 扫描和 WoL 到达宿主机物理网络；Linux NAS 正式部署只使用主 docker-compose.yml。

## 8. 排错矩阵

| 现象 | 优先检查 |
| --- | --- |
| 容器反复重启 | APP_TOKEN 是否至少 32 字符、三个端口是否冲突、TLS_HOST 是否含协议/端口、docker compose logs app |
| 页面能打开但扫描不到 | 是否在 Linux NAS、是否 host 网络、是否有 NET_RAW、是否选了实际 LAN 网卡、目标是否在线 |
| Unknown network interface | eth0 只是示例，改成 ip -br -4 addr 显示的真实网卡 |
| 网段不直连 | 核对网卡 IP、掩码和路由；不要扫描其他 VLAN 或盲目扩大到 /16 |
| 只显示 MAC/IP | 目标未响应 NetBIOS，属于正常限制，可手动命名 |
| exec format error 或 no matching manifest | 当前镜像为 linux/amd64，检查 uname -m |
| 数据或证书消失 | 检查当前 Compose 项目目录、./data 挂载和命名卷，不要更改项目名或执行 down -v |
| 唤醒显示发送成功但未开机 | 核对有线 MAC、广播地址、BIOS/网卡 WoL、关机供电和二层网络；不要把 API 成功当作开机确认 |

## 9. AI 最终执行清单

AI 只有在用户已经确认主机事实后，才按此顺序执行：

~~~bash
cd /volume1/docker/netwake
install -d -m 700 data
# 创建 .env，并在主机本地写入随机 APP_TOKEN、真实 TLS_HOST、SCAN_INTERFACE、DEFAULT_CIDR
chmod 600 .env
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
curl -fsS http://127.0.0.1:18080/healthz
curl -i http://127.0.0.1:26665/openapi.json
~~~

验收通过的最低条件：健康检查返回 ok=true；API 文档路径返回 404；无令牌管理请求返回 401；docker compose ps 显示容器正常运行。AI 不得把 .env、APP_TOKEN、Caddy 私钥、数据库、完整日志或真实设备信息写入回答、工单或公开仓库。
