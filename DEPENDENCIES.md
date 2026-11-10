# 依赖与安装教程

## 系统要求与已验证版本

- Ubuntu 24.04 LTS（Playwright 官方也支持 Ubuntu 22.04/24.04；当前生产机为 24.04.4 x86_64）
- Python `>=3.11`，推荐 `3.12.x`（生产机已验证 `3.12.3`，测试环境已验证 `3.12.14`）
- uv：已验证 `0.12.21`
- Docker Engine：已验证 `29.4.2`（用于运行 NapCat）
- NapCat Docker：当前已验证镜像摘要
  `mlikiowa/napcat-docker@sha256:696e9574a0f6fb2f86cbecba8a32048f2a5823117dc9b13c6c02637ad890fa8b`

不要只执行 `playwright install chromium`：它只下载浏览器，不会保证 Linux
动态库齐全。必须执行下文的 `playwright install --with-deps chromium`。

## Python 依赖

本项目使用 [uv](https://docs.astral.sh/uv/) 管理依赖。

### Ubuntu 22.04/24.04 一次性安装命令

```bash
sudo apt-get update
sudo apt-get install -y \
  ca-certificates curl git build-essential \
  fonts-noto-cjk fonts-stix

# 固定 uv 版本，避免部署机之间行为漂移
curl -LsSf https://astral.sh/uv/0.12.21/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

cd ~/Code/kouhai-bot

# uv 可自行安装隔离的 Python，不依赖系统 Python 小版本
uv python install 3.12

# 严格使用仓库内 uv.lock，不在服务器上临时改依赖解析结果
uv sync --frozen

# 同时安装与当前 Playwright 版本匹配的 Chromium 和全部 Ubuntu 动态库。
# 这一步会通过 sudo/apt 安装 libatk、libgbm、libasound、X11 等依赖。
uv run playwright install-deps --dry-run chromium
uv run playwright install --with-deps chromium
```

NapCat 需要 Docker。全新 Ubuntu 服务器请使用 Docker 官方软件源安装 Engine 和
Compose 插件，不要混装 Ubuntu 的 `docker.io` / `docker-compose-v2` 包：

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt-get update
sudo apt-get install -y \
  docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo docker run --rm hello-world

# 让当前用户以后无需 sudo；执行后退出 SSH 并重新登录一次。
sudo usermod -aG docker "$USER"
```

如果机器已经在运行 Docker/NapCat，不要为照抄本节而卸载或重装；先用
`docker --version` 和 `docker compose version` 检查即可。

如果海外下载需要本机 mihomo（示例端口 7890），可只在安装阶段使用：

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
uv sync --frozen
uv run playwright install --with-deps chromium
unset HTTP_PROXY HTTPS_PROXY
```

### Python 直接依赖及版本要求

| 用途 | `pyproject.toml` 要求 | 当前 `uv.lock` 精确版本 |
|---|---:|---:|
| NapCat WebSocket | `websockets>=12.0` | `16.0` |
| HTTP/API | `aiohttp>=3.9` | `3.14.3` |
| Codeforces/Cloudflare 请求 | `cloudscraper>=1.2` | `1.2.71` |
| 浏览器抓取和题面长图 | `playwright>=1.45` | `1.61.0` |
| 图片降级渲染 | `Pillow>=10.0` | `12.3.0` |
| YAML 配置 | `pyyaml>=6.0` | `6.0.3` |
| LaTeX → MathML | `latex2mathml>=3.81.1` | `3.81.1` |
| 测试 | `pytest>=9.0` | `9.0.3` |
| 异步测试 | `pytest-asyncio>=1.0` | `1.3.0` |

传递依赖也全部记录在 `uv.lock` 中，由 `uv sync --frozen` 按哈希安装；不要在
服务器上逐个 `pip install`。升级 Playwright 后必须重新执行
`uv run playwright install --with-deps chromium`，因为不同 Playwright 版本需要匹配的浏览器二进制。

### 安装后强制自检

```bash
cd ~/Code/kouhai-bot

uv run python - <<'PY'
from importlib.metadata import version
for name in (
    "websockets", "aiohttp", "cloudscraper", "playwright",
    "Pillow", "PyYAML", "latex2mathml",
):
    print(name, version(name))
PY

uv run playwright install --list

# 真正启动一次 Chromium；这一步能提前发现 libatk/libgbm/libasound 等缺失。
uv run python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_content("<p>中文公式测试：x² + y²</p>")
    print(page.locator("p").inner_text())
    browser.close()
print("Chromium OK")
PY

# 验证 bot 代码与配置
uv run python -c "from kouhai_bot.config import get_config; print(get_config().bot_qq)"
uv run python -m pytest tests/ -q
```

浏览器必须由运行 bot 的同一 Linux 用户安装；Playwright 默认把二进制放在该用户的
`~/.cache/ms-playwright`。用 root 安装、再用普通用户运行会造成“明明装过却找不到浏览器”。

## NapCat 配置

NapCat 是 QQ NT 的 Bot 框架，提供 OneBot11 兼容接口。这是一个外部依赖，需要你自行部署。推荐使用 Docker。

### Docker 安装

在任意位置创建 NapCat 配置目录（例如 `~/napcat`），并编写 `docker-compose.yml`：

```yaml
version: '3'
services:
  napcat:
    # 已验证的 x86_64 镜像摘要；需要升级 NapCat 时先在测试机验证再更换。
    image: mlikiowa/napcat-docker@sha256:696e9574a0f6fb2f86cbecba8a32048f2a5823117dc9b13c6c02637ad890fa8b
    container_name: napcat
    environment:
      - ACCOUNT=你的QQ号
    ports:
      - "3000:3000"  # HTTP API
      - "6099:6099"  # WebUI
    volumes:
      - ./config:/usr/src/app/napcat/config
    restart: unless-stopped
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

### 配置反向 WebSocket

在 NapCat 配置目录下的 `config/onebot11.json` 中配置：

```json
{
  "network": {
    "httpServers": [
      {
        "enable": true,
        "name": "kouhai-http-api",
        "host": "0.0.0.0",
        "port": 3000,
        "enableCors": true,
        "enableWebsocket": false,
        "messagePostFormat": "array",
        "token": "",
        "debug": false
      }
    ],
    "websocketClients": [
      {
        "enable": true,
        "name": "kouhai-bot-reverse-ws",
        "url": "ws://host.docker.internal:8097",
        "messagePostFormat": "array",
        "reportSelfMessage": false,
        "reconnectInterval": 5000,
        "token": "",
        "debug": false,
        "heartInterval": 30000
      }
    ]
  }
}
```

**重要说明：**
- `url` 中的 `host.docker.internal` 指向宿主机，**不能用 `127.0.0.1`**
- 端口 `8097` 需要与 `config.yaml` 中的 `napcat_ws_port` 一致
- `extra_hosts` 配置确保 Docker 容器能解析 `host.docker.internal`

### 启动 NapCat

```bash
cd ~/napcat  # 或你的 NapCat 配置目录
docker compose up -d
```

### 首次登录

NapCat 首次启动时需要扫码登录 QQ。查看日志获取二维码：

```bash
docker logs -f napcat
```

登录成功后 token 会持久化，后续重启无需重新登录。

### 验证 NapCat

```bash
# 检查 HTTP API
curl -X POST http://127.0.0.1:3000/get_status \
  -H 'Content-Type: application/json' -d '{}'

# 应返回 {"status":"ok","data":{"online":true,"good":true}}
```

## 验证安装

```bash
# 测试导入
cd kouhai-bot
uv run python -c "from kouhai_bot.config import get_config; print(get_config().bot_qq)"

# 运行测试
uv run python -m pytest tests/ -v

# 启动 bot
uv run start
```

## 常见问题

### 1. NapCat 连不上 bot

**症状：** bot 日志显示 `NapCat connected from ...` 但消息不响应

**解决：** 检查 `napcat_ws_host` 是否为 `0.0.0.0`（不能用 `127.0.0.1`）

### 2. Docker 容器无法解析 host.docker.internal

**症状：** NapCat 日志显示 `getaddrinfo ENOTFOUND host.docker.internal`

**解决：** 确保 `docker-compose.yml` 中有 `extra_hosts` 配置

### 3. 端口冲突

**症状：** `uv run start` 失败，提示 `address already in use`

**解决：** 检查 `config.yaml` 中的 `napcat_ws_port` 是否与 NapCat 的 WebSocket server 端口冲突。NapCat 的 WebSocket **server** 端口（如 8095）和 bot 的 WebSocket **listen** 端口（如 8097）不能相同。

### 4. NapCat 每次重启都要扫码

**解决：** 在 `docker-compose.yml` 中设置 `ACCOUNT` 环境变量，格式为 QQ 号
