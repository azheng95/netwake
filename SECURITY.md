# 安全与敏感信息发布注意事项

NetWake 会使用管理令牌、TLS/CA 文件、设备台账和运行日志。以下内容属于敏感信息，**不要提交到 GitHub、打包进 Docker 镜像，或发布到 Docker Hub**：

- 管理员账号、密码、`APP_TOKEN`、`AGENT_TOKEN`、API 密钥和其他访问令牌；
- TLS/CA 私钥（例如 `root.key`、`privkey.pem`）、包含私钥的证书目录和备份；
- 真实设备台账（MAC/IP/主机名）、网络拓扑、内网地址清单和 DHCP/DNS 信息；
- 包含请求头、令牌、账号、路径或网络信息的日志、截图、录屏和故障报告；
- 生产环境的 `.env`、数据库、Docker volume 导出文件和配置备份。

## 提交或构建前检查

1. 使用 `.env.example` 作为模板；真实配置只保存在部署主机的 `.env` 或密码管理器中。
2. 不要把密钥写入 `Dockerfile`、Compose 文件、源码、镜像层、构建参数、镜像标签或 README 示例。示例值必须是明显的占位符。
3. 发布源码前检查 `git diff --cached` 和 `git ls-files`；构建镜像前检查构建上下文和 Dockerfile，确认没有把 `.env`、`data/`、`certs/` 或备份文件带入镜像。
4. 发布日志、截图或 API 示例前，先删除 `X-Admin-Token`、Cookie、Authorization、账号密码、真实 IP/MAC 和私钥内容。
5. Docker Hub 只发布不含任何真实配置和用户数据的镜像。镜像标签、描述、构建日志和 README 也不能包含令牌或密码。

本项目的 `.gitignore` 和 `.dockerignore` 已默认排除 `.env`、数据库、证书目录及缓存文件；请不要为了让构建通过而取消这些排除规则，也不要使用真实配置替换 `.env.example`。

## 发现泄露后的处理

如果令牌、密码或私钥曾经进入 Git、GitHub、Docker Hub、构建日志或聊天记录，应立即：

1. 在部署主机上生成并替换新的令牌/密码，撤销旧凭据；
2. 更换受影响的 TLS/CA 私钥或其他密钥，并重建镜像；
3. 从 Git 历史和 Docker Hub 标签中清理泄露内容。仅删除当前文件或覆盖标签并不能保证历史层已清除；
4. 检查访问日志和仓库下载记录，确认是否存在未授权访问。

安全问题请通过私下渠道报告，不要在公开 Issue 中粘贴凭据、完整日志或生产配置。
