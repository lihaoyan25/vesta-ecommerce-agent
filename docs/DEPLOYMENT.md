# 部署文档

## 1. 部署概览

本项目为前后端分离架构, 推荐生产部署方案: 

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

## 11. Docker 部署（推荐）

三个容器一键编排：`mysql` + `backend` + `frontend`（Nginx 托管前端并反代 `/api`、`/static`），宿主机无需安装 Python/Node/MySQL。

### 11.1 前置条件

- 服务器已安装 Docker 与 Compose 插件（验证：`docker -v` 与 `docker compose version`）
- **云控制台安全组放行 80 端口（TCP）**——打不开页面九成是这一步漏了
- MySQL 首次启动自动建库建用户：`.env` 中 `DATABASE_USER` **不能是 root**，`DATABASE_NAME` 不要含特殊字符

### 11.2 配置准备

代码上传服务器后编辑 `.env`：

```ini
DATABASE_HOST=mysql          # 容器网络内用服务名访问，不是 localhost
DATABASE_USER=shop_user      # 不能是 root
DATABASE_NAME=your_database_name
# ===== Docker 专用（compose 读取）=====
MYSQL_ROOT_PASSWORD=<强随机密码>
FRONTEND_PORT=80             # 对外端口，80 被占用可改 8080
UVICORN_WORKERS=2            # 2G 内存小服务器建议 1
```

`MYSQL_ROOT_PASSWORD`、`FRONTEND_PORT`、`UVICORN_WORKERS` 三个变量在 `.env.example` 中有模板。

### 11.3 构建与启动

```bash
docker compose up -d --build
```

- MySQL 数据持久化在命名卷 `mysql-data`，删除容器不丢数据
- 商品图片目录以 `./static` 挂载到后端容器，宿主机直接管理

### 11.4 初始化管理员

```bash
docker compose exec backend python scripts/init_db.py
```

### 11.5 访问验证

| 项目 | 地址 |
| --- | --- |
| 前端 | `http://服务器IP` |
| Swagger 文档 | `http://服务器IP/api/v1/docs`（经 Nginx 反代） |
| 容器状态 | `docker compose ps` |
| 后端日志 | `docker compose logs -f backend` |

### 11.6 常用运维

```bash
# 更新代码后重新构建启动
git pull && docker compose up -d --build

# 备份数据库
docker compose exec mysql sh -c 'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" $MYSQL_DATABASE' > backup.sql

# 恢复备份
docker compose exec -T mysql sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" $MYSQL_DATABASE' < backup.sql
```

### 11.7 Docker 环境常见问题

| 问题 | 排查方向 |
| --- | --- |
| 页面打不开 | 云安全组未放行 80；`FRONTEND_PORT` 是否被占用 |
| 后端起不来连不上库 | `docker compose logs backend`；确认 `.env` 中 `DATABASE_HOST=mysql` |
| 首页能开但接口 502 | 后端未就绪或崩溃，看 backend 日志与健康检查 |
| 客服 SSE 不流式 | 确认流量直达 frontend 容器，中间无额外 CDN/代理开启缓冲 |
| 数据想重置 | `docker compose down -v`（**会删除全部数据卷**，慎用） |
