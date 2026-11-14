# 部署踩坑记录

在 Windows 11 + Docker Desktop 上从零部署 Dify 1.18 的真实过程。网上大部分教程没写这些坑。

## 1. 磁盘：镜像数据默认写 C 盘

Docker Desktop 的虚拟磁盘默认在 `C:\Users\<user>\AppData\Local\Docker\wsl`，能长到几十 GB。

安装时要**同时指定程序和数据的路径**：

```cmd
start /w "" "Docker Desktop Installer.exe" install --accept-license ^
  --installation-dir="D:\Docker\Docker" ^
  --wsl-default-data-root="D:\Docker\data"
```

只改 `--installation-dir` 没用，占空间的是数据目录。

⚠️ 不要加 `--windows-containers-default-data-root`——如果安装时选的是 per-user 模式，这个参数会和 `--user` 冲突，安装器直接抛异常退出，一个文件都不装（日志在 `C:\Users\<user>\AppData\Local\Docker\install-log.txt`）。

## 2. WSL：不是开了功能就能用

Win11 24H2 起，WSL 是独立的应用包。只在"启用或关闭 Windows 功能"里勾选不够，`wsl --install` 在国内还常被 403 挡掉。

可靠做法：

1. 启用「适用于 Linux 的 Windows 子系统」+「虚拟机平台」，重启
2. 从 GitHub 下载 WSL 的 msi 包手动安装（`microsoft/WSL` releases），不依赖微软商店

## 3. 镜像：并发拉取会卡死

`docker compose up -d` 会同时拉 12 个镜像。国内免费加速源对并发连接限速严重，结果是**整夜只成功 2 个**。

改成逐个拉：

```bash
for img in postgres:15-alpine redis:6-alpine busybox:latest \
           langgenius/qdrant:v1.8.3 langgenius/dify-sandbox:0.2.15 \
           langgenius/dify-plugin-daemon:0.6.11-local \
           langgenius/dify-agent-backend:1.18.0 \
           langgenius/dify-agent-local-sandbox:1.18.0 \
           langgenius/dify-web:1.18.0 langgenius/dify-api:1.18.0; do
  docker pull "$img"
done
```

拉完再 `docker compose up -d --pull never`，速度正常（约 2MB/s，10 个镜像 13 分钟）。

`~/.docker/daemon.json` 里配加速源：

```json
{
  "registry-mirrors": [
    "https://docker.1panel.live",
    "https://docker.m.daocloud.io"
  ]
}
```

## 4. 向量库：weaviate 拉不到就换 qdrant

Dify 默认用 weaviate，但它的镜像在 `cr.weaviate.io`（不是 Docker Hub），国内加速器管不到，直接解析失败。

换成 qdrant——它挂在 Docker Hub 上，走加速器，而且检索性能更好。

改 `.env` 三行：

```ini
VECTOR_STORE=qdrant
QDRANT_URL=http://qdrant:6333
QDRANT_API_KEY=difyai123456
```

`docker-compose.yaml` 里 `COMPOSE_PROFILES=${VECTOR_STORE}` 会自动切换要启动的服务，不用改 compose 文件。

## 5. local_sandbox 反复重启

Dify 1.18 新增的 Agent 运行时，`.env` 里这个字段是空的：

```ini
DIFY_AGENT_LOCAL_SANDBOX_AUTH_TOKEN=
```

导致 `local_sandbox` 报 `shellctl: auth token is required` 不断重启，连带 `agent_backend` 抛 pydantic 校验错误。

填一个随机串即可：

```ini
DIFY_AGENT_LOCAL_SANDBOX_AUTH_TOKEN=your-random-token-here
```

## 6. 重启后引擎不会自动起

Docker Desktop 默认不随系统启动，导致 `http://localhost` 打不开、容器全部消失。

设置 → General → 勾选 **Start Docker Desktop when you sign in**。

容器本身是 `restart: always`，引擎起来后会自己恢复，不用手动 `compose up`。

## 最终状态

15 个容器，全部 healthy：

```
api  db_postgres  redis  qdrant  web  nginx  worker  worker_beat
sandbox  local_sandbox  plugin_daemon  agent_backend
ssrf_proxy  agent_ssrf_proxy  api_websocket
```
