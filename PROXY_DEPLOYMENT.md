# NetWake 代理容器部署方案

## 目的

NetWake 的主应用必须使用 Linux `network_mode: host`，这样 ARP 扫描、广播探测和 Wake-on-LAN 可以直接使用 NAS 的物理局域网网卡。Docker 管理器因此无法从主应用容器的端口列表生成“打开连接”按钮。

项目现在采用双容器方案：

```text
浏览器
  │
  ├─ NAS:26665/HTTP
  └─ NAS:26666/HTTPS
        │
        ▼
netwake-link（bridge，Nginx，带 ports 映射）
        │
        ▼
netwake（host，NetWake + Caddy + LAN 扫描）
        ├─ backend HTTP 18081
        └─ backend HTTPS 18082
```

`netwake` 保持 host 网络和 `NET_RAW` 能力；`netwake-link` 只负责把公开端口转发到主机上的后端端口。这样不会改变扫描路径，同时飞牛 Docker 界面会在 `netwake-link` 行显示可点击连接。

## 使用方式

直接使用仓库中的主 Compose 文件：

```bash
docker compose config --quiet
docker compose up -d
docker compose ps
```

`.env` 中使用以下端口变量：

```dotenv
PUBLIC_HTTP_PORT=26665
PUBLIC_HTTPS_PORT=26666
BACKEND_HTTP_PORT=18081
BACKEND_HTTPS_PORT=18082
APP_PORT=18080
TLS_HOST=192.168.0.111
SCAN_INTERFACE=enp3s0
```

访问地址保持不变：

- `http://192.168.0.111:26665`
- `https://192.168.0.111:26666`

## 重要约束

- 不要给 `netwake` 添加 `ports:`；它必须继续使用 `network_mode: host`。
- 不要把 `SCAN_INTERFACE` 改成 `docker0`、`eth0` 等未经 NAS 主机确认的名称；应使用实际 LAN 网卡，例如 `enp3s0`。
- 不要执行 `docker compose down -v`，以免删除 SQLite 数据或 TLS 命名卷。
- `18081` 和 `18082` 是后端端口，不应作为用户访问入口；用户入口始终是 `26665/26666`。
- Docker 界面中的可点击连接显示在 `netwake-link`，而不是 host 网络的 `netwake` 行，这是预期行为。

## 验收

```bash
docker compose ps
curl -fsS http://127.0.0.1:26665/healthz
curl -kfsS https://192.168.0.111:26666/healthz
docker inspect netwake --format '{{.HostConfig.NetworkMode}}'
docker inspect netwake-link --format '{{json .NetworkSettings.Ports}}'
```

预期结果：`netwake` 为 `host` 网络且 healthy；`netwake-link` 显示 `26665`、`26666` 端口映射；两个健康检查均返回 `"ok":true`。
