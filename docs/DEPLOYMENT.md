# 部署文档

## 1. 部署概览

本项目为前后端分离架构, 推荐生产部署方案: 

- **云服务器首选: Docker Compose 一键部署**, 见 [第 11 章 全流程](#11-云服务器-docker-部署全流程推荐)
- 传统手动部署(宿主机 Nginx + venv + uvicorn) 见第 4~8 章

- **后端**: FastAPI 应用由 `uvicorn` 运行, 通过 Nginx 反向代理对外提供服务
- **前端**: Vite 构建出静态文件, 由 Nginx 直接托管并代理 `/api`, `/static` 请求到后端
- **数据库**: MySQL

```text
浏览器
  │
  ▼
Nginx (前端静态资源 + 反向代理)
  ├── /                → frontend/dist (静态资源)
  ├── /api             → uvicorn (127.0.0.1:8000)
  └── /static          → uvicorn (127.0.0.1:8000)
                            │
                            ▼
                        MySQL
```

## 2. 环境要求

| 组件 | 版本要求 |
| --- | --- |
| 操作系统 | Linux (推荐)或 Windows Server |
| Python | 3.12 |
| Node.js | 18+ (仅构建前端时需要) |
| MySQL | 5.1+ / 8.0 |
| Nginx | 1.18+ |

## 3. 配置准备

### 3.1 环境变量

复制 `.env.example` 为 `.env`, 并填写生产配置**生产环境务必修改以下项**: 

```ini
# 数据库
DATABASE_HOST=your_database_host
DATABASE_PORT=3306
DATABASE_USER=your_database_user
DATABASE_PASSWORD=<强密码>
DATABASE_NAME=your_database_name

# 应用
DEBUG=False
# 必须改为随机长字符串 (可用 python -c "import secrets;print(secrets.token_hex(32))" 生成)
SECRET_KEY=<随机密钥>

# 服务器
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
```

> 安全提示: `.env` 已加入 `.gitignore`, 切勿将真实密钥提交到版本库

### 3.2 数据库初始化

应用启动时会通过 `Base.metadata.create_all` 自动建表, 确保已创建数据库并授权

## 4. 后端部署

### 4.1 安装依赖

```bash
cd /opt/vesta‑ecommerce
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4.2 启动服务

```bash
# 前台启动 (调试用)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 生产推荐: 多 worker (注意: 本项目为无状态服务, 可安全使用多进程)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 5. 前端构建

```bash
cd /opt/vesta‑ecommerce/frontend
npm install
npm run build          # 产物输出到 frontend/dist
```

将 `frontend/dist` 作为 Nginx 静态资源目录

## 6. Nginx 配置

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态资源
    root /opt/vesta‑ecommerce/frontend/dist;
    index index.html;

    # 前端 SPA 路由回退
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 后端静态资源 (商品图片等)
    location /static/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
    }
}
```

校验并重载: 

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 7. 初始化管理员

首次部署后, 执行一次管理员初始化: 

```bash
cd /opt/vesta‑ecommerce
source .venv/bin/activate
python scripts/init_db.py
# 默认 admin / admin123, 登录后请立即修改密码
```

如需内置示例商品(10 件含商品图, 幂等可重复执行):

```bash
python scripts/seed_products.py
```

## 8. 部署验证

1. 健康检查: `curl http://127.0.0.1:8000/health` (后端直接访问, 返回 `{"status":"healthy"}`)
2. 打开 Swagger 文档: `http://127.0.0.1:8000/docs` (应用根路径)
3. 前端页面可正常访问, 登录, 浏览商品, 加入购物车并结算

> 说明: `/health` 与 `/docs` 挂载在应用根路径 (未加 `/api/v1` 前缀)如需通过 Nginx 对外暴露, 可额外增加对应的 `location` 代理配置

## 9. 常见问题

| 问题 | 排查方向 |
| --- | --- |
| 后端无法连接数据库 | 检查 `.env` 数据库地址/账号/密码; 确认 MySQL 已授权远程/本地访问 |
| 前端请求 404 | 确认 Nginx `/api/` 与 `/static/` 代理配置正确 |
| 前端刷新页面 404 | 确认 Nginx 配置了 `try_files ... /index.html` |
| 登录后 Token 频繁失效 | 检查 `SECRET_KEY` 是否稳定, `ACCESS_TOKEN_EXPIRE_MINUTES` 配置 |
| 商品图片不显示 | 确认图片已放入 `static/upload/`, 且 `/static/` 代理正常 |
| 无法并发结算 | 本项目结算已加行锁防超卖; 检查 MySQL 引擎为 InnoDB |

## 10. 安全加固建议

- 使用强随机 `SECRET_KEY`, 不要使用示例值
- 生产环境 `DEBUG=False`
- 数据库账号仅授予所需库的最小权限
- 建议启用 HTTPS (可配合 Let's Encrypt 证书)
- 定期备份数据库, 尤其是 `users`, `products`, `cart_items` 表

## 11. 云服务器 Docker 部署全流程(推荐)

三个容器一键编排：`mysql` + `backend` + `frontend`(Nginx 托管前端并反代 `/api`、`/static`), 宿主机无需安装 Python/Node/MySQL。以下是从一台全新云服务器到网站可访问的完整过程。

### 11.1 连接服务器并安装 Docker

```bash
# SSH 登录云服务器(以 root 为例, 建议使用普通用户 + sudo)
ssh root@服务器IP

# 安装 Docker(官方脚本, 适用于 Ubuntu/Debian/CentOS)
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker

# 验证
docker -v
docker compose version
```

> 服务器配置建议：2 核 2G 起步(2G 内存请把 `.env` 中 `UVICORN_WORKERS` 设为 1)。国内服务器若拉取镜像慢, 自行配置 Docker 镜像加速器。

### 11.2 获取代码

```bash
# 方式一：git clone(推荐)
cd /opt
git clone https://github.com/<你的用户名>/<仓库名>.git vesta-ecommerce
cd vesta-ecommerce

# 方式二：本地打包上传(在本地执行后传到服务器同目录)
# scp -r 项目目录 root@服务器IP:/opt/vesta-ecommerce
```

### 11.3 配置 `.env`

```bash
cp .env.example .env
vi .env
```

必须核对/修改的项：

```ini
# ===== 数据库(Docker 环境固定写法)=====
DATABASE_HOST=mysql          # 容器网络内用服务名访问, 不是 localhost
DATABASE_USER=shop_user      # 不能是 root(compose 首次启动自动建库建用户)
DATABASE_PASSWORD=<强密码>
DATABASE_NAME=shop_cart_sys_v2_0

# ===== 应用 =====
DEBUG=False
SECRET_KEY=<随机长字符串>     # python -c "import secrets;print(secrets.token_hex(32))"
DEEPSEEK_API_KEY=<你的Key>    # 不填则智能客服停用, 主站不受影响

# ===== 火山引擎语音(智能客服语音通话; 不填则语音按钮提示未启用)=====
VOLCANO_API_KEY=<火山控制台API Key>
VOLCANO_TTS_SPEAKER=zh_female_xiaohe_uranus_bigtts
VOLCANO_TTS_SPEECH_RATE=15  # 语速[-50,100], 100=2.0倍速, 0=原生; 15≈豆包App语速

# ===== Docker 专用 =====
MYSQL_ROOT_PASSWORD=<强随机密码>
FRONTEND_PORT=80             # 对外端口, 80 被占用可改 8080
UVICORN_WORKERS=2            # 2G 内存建议 1
```

### 11.4 云控制台放行端口

在云厂商控制台的**安全组 / 防火墙**中放行：`80/TCP`(前端入口)。页面打不开九成是这一步漏了。SSH 的 22 端口一般默认已放行。

### 11.5 构建与启动

```bash
docker compose up -d --build
docker compose ps            # 三个容器应为 running / healthy
```

- MySQL 首次启动自动建库建用户, 数据持久化在命名卷 `mysql-data`
- 商品图片目录以 `./static` 挂载到后端容器, 宿主机直接管理

### 11.6 初始化管理员与示例商品

```bash
docker compose exec backend python scripts/init_db.py
# 默认 admin / admin123, 登录后请立即修改密码
# 内置 10 件示例商品与商品图, 幂等可重复执行
docker compose exec backend python scripts/seed_products.py
```

### 11.7 访问验证

| 项目 | 地址 |
| --- | --- |
| 前端 | `http://服务器IP` |
| Swagger 文档 | `http://服务器IP/api/v1/docs`(经 Nginx 反代) |
| 登录验证 | admin 登录 → 商品浏览 → 加购 → 结算 全流程 |

至此部署完成。可选进阶：把域名 A 记录解析到服务器 IP, 并用 Certbot(`docker run --rm -p 80:80 certbot/certbot ...`)或宿主机 Nginx 加一层 HTTPS。

### 11.8 常用运维指令速查

| 场景 | 命令 |
| --- | --- |
| 查看容器状态 | `docker compose ps` |
| 跟踪后端日志 | `docker compose logs -f backend` |
| 查看全部容器日志 | `docker compose logs -f` |
| 重启某个服务 | `docker compose restart backend` |
| 停止 / 启动全部 | `docker compose stop` / `docker compose start` |
| **更新代码后重新部署** | `git pull && docker compose up -d --build` |
| 备份数据库 | `docker compose exec mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" $MYSQL_DATABASE' > backup.sql` |
| 恢复数据库 | `docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" $MYSQL_DATABASE' < backup.sql` |
| 进入后端容器调试 | `docker compose exec backend sh` |
| 进入 MySQL 命令行 | `docker compose exec mysql mysql -u<用户名> -p <库名>` |
| 重新执行种子脚本 | `docker compose exec backend python scripts/seed_products.py` |
| 查看资源占用 | `docker stats` |
| 清理悬空镜像 | `docker image prune -f` |
| **危险：彻底重置(含数据)** | `docker compose down -v`(删除全部数据卷, 慎用) |

### 11.9 Docker 环境常见问题

| 问题 | 排查方向 |
| --- | --- |
| 页面打不开 | 云安全组未放行 80; `FRONTEND_PORT` 是否被占用(`ss -tlnp \| grep 80`) |
| 后端起不来连不上库 | `docker compose logs backend`; 确认 `.env` 中 `DATABASE_HOST=mysql` |
| 首页能开但接口 502 | 后端未就绪或崩溃, 看 backend 日志与健康检查 |
| 客服 SSE 不流式 | 确认流量直达 frontend 容器, 中间无额外 CDN/代理开启缓冲 |
| 拉取镜像超时 | 配置 Docker 镜像加速器后重试 |
| 磁盘占满 | `docker system df` 查看, `docker system prune -f` 清理 |

### 11.10 语音通话与 HTTPS(启用语音功能必读)

智能客服的**语音通话**(麦克风输入 + AI 语音应答)依赖浏览器麦克风权限, 而麦克风**只在 HTTPS(或 localhost)下开放**——纯 `http://IP` 部署无法使用语音, 文字客服不受影响。

启用步骤：

1. **域名解析**：将域名 A 记录指向服务器 IP
2. **火山引擎配置**：在 [火山引擎控制台](https://console.volcengine.com/speech) 开通「豆包流式语音识别」与「语音合成大模型」, 创建 API Key 填入 `.env` 的 `VOLCANO_API_KEY`(ASR/TTS 按用量计费)
3. **HTTPS 证书**：宿主机安装 Certbot 签发免费证书后, 在前端容器前加一层宿主机 Nginx 做 443 终结, 或直接在前端容器挂载证书配置 443
4. **WebSocket 转发**：若使用宿主机 Nginx 终结 HTTPS, `/api/` 的 location 必须支持 WebSocket 升级：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8080;   # frontend 容器映射端口
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_buffering off;
    proxy_read_timeout 300s;
}
```

验证：打开客服面板 → 点「语音通话」→ 浏览器询问麦克风权限 → 页面顶部出现半透明悬浮通话条并显示「我在听, 请讲」即接通。通话期间可正常浏览商城, 建议佩戴耳机(回声消除依赖浏览器 AEC)。
