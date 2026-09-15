# 智能线上商城(VESTA.OnlineMall)

一个前后端分离的**智能线上商城**, 实现智能客服AI Agent, 用户注册登录, 商品浏览/搜索/管理, 购物车, 余额充值, 下单结算等核心电商闭环能力

> 📦 快速部署: **[部署文档 (Docker 一键上云)](docs/DEPLOYMENT.md)** ｜ 🛠 开发文档: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) ｜ 🔌 接口文档: [docs/API.md](docs/API.md)

- 后端: FastAPI + SQLAlchemy 2.0 + MySQL, JWT 鉴权, 分层架构 (`routes → services → dao → models/schemas`)
- 前端: Vue 3 `<script setup>` + Vite + Pinia + Vue Router + Axios + Tailwind CSS

## 项目预览

![首页效果图](./docs/screenshots/home.png)

![智能客服悬浮窗-页面效果](./docs/screenshots/chat_view.png)

![智能客服悬浮窗-推荐卡片](./docs/screenshots/chat_recommend.png)

![智能客服悬浮窗-代劳服务](./docs/screenshots/chat_services.png)

![商品详情页](./docs/screenshots/detail.png)

![购物车页面](./docs/screenshots/cart.png)

![订单页面](./docs/screenshots/order.png)

![个人主页](./docs/screenshots/profile.png)

![商品管理页面](./docs/screenshots/products.png)

![新增商品](./docs/screenshots/upload.png)

![登录页面](./docs/screenshots/login.png)

![注册页面](./docs/screenshots/register.png)

## 功能特性

- 用户认证: 注册, 登录(支持用户名/邮箱/手机号), JWT 鉴权, `refresh_token` 自动续期, 忘记密码(账号+手机号验证重置)
- 商品: 分页列表, 搜索, 详情; 管理员新增/编辑/删除
- 购物车: 增删改查, 勾选/全选结算
- 订单: 下单生成待支付订单(20 分钟未支付自动取消), 余额支付, 手动取消, 删除已取消订单
- 账户: 余额查询, 充值, 修改密码, 修改用户名/邮箱/手机号
- 智能客服: 在本项目中由 DeepSeek 驱动, SSE 流式回复, 多轮记忆, 可查询订单/商品/购物车并代改购物车, 支持商品/订单卡片对话
- 角色权限: 普通用户 / 管理员

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端框架 | FastAPI 0.109 |
| ASGI 服务器 | uvicorn 0.27 |
| ORM | SQLAlchemy 2.0 |
| 数据校验 | Pydantic 2.6 / pydantic-settings 2.1 |
| 鉴权 | python-jose (JWT)+ passlib (bcrypt) |
| 数据库驱动 | PyMySQL 1.1 |
| 前端框架 | Vue 3.4 |
| 状态管理 | Pinia 2.1 |
| 路由 | Vue Router 4.3 |
| HTTP 客户端 | Axios 1.6 |
| 样式 | Tailwind CSS 3.4 |
| 构建工具 | Vite 5.2 |

完整依赖见 [requirements.txt](requirements.txt) (后端) 与 [frontend/package.json](frontend/package.json) (前端)

## 目录结构

```text
vesta‑ecommerce/
├── app/                        # 后端应用
│   ├── main.py                 # 应用入口: 生命周期, CORS, 全局异常, 路由挂载
│   ├── config.py               # 配置 (读取 .env)
│   ├── database.py             # 数据库引擎, 会话工厂, Base
│   ├── api/
│   │   ├── deps.py             # 依赖注入: 当前用户 / 超级管理员
│   │   └── v1/
│   │       ├── router.py       # v1 路由汇总
│   │       ├── routes/         # 路由层 (auth / products / cart / users)
│   │       └── schemas/        # Pydantic 请求/响应模型
│   ├── services/               # 业务逻辑层
│   ├── dao/                    # 数据访问层
│   ├── models/                 # SQLAlchemy ORM 模型
│   ├── tools/                  # 智能客服工具层
│   ├── utils/                  # 通用工具(JWT, 密码)
│   └── prompts/                # 智能客服系统提示词(System Prompt)
├── frontend/                   # 前端应用
│   └── src/
│       ├── api/                # Axios 封装与接口定义
│       ├── stores/             # Pinia 状态 (user / cart)
│       ├── router/             # 路由与守卫
│       ├── components/         # 通用组件
│       └── views/              # 页面
├── scripts/                    # 脚本 (管理员初始化等)
├── docs/                       # 项目文档
└── static/                     # 静态资源 (商品图片等)
```

## 快速开始

### 前置要求

- Python 3.12
- Node.js 18+
- MySQL

### 1. 后端

```bash
# 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # Linux / macOS
pip install -r requirements.txt

# 配置环境变量
copy .env.example .env      # Windows
# cp .env.example .env      # Linux / macOS
# 编辑 .env, 填入数据库连接信息与随机的 SECRET_KEY

# 初始化管理员账号 (可选)
python scripts/init_db.py

# 初始化示例商品 (可选, 含商品图, 幂等可重复执行)
python scripts/seed_products.py

# 启动后端 (默认 http://localhost:8000)
uvicorn app.main:app --reload
```

应用启动时会自动建表 (`Base.metadata.create_all`)

### 2. 前端

```bash
cd frontend
npm install
npm run dev                 # 默认 http://localhost:3000
```

开发环境下, 前端已将 `/api` 与 `/static` 代理到 `http://localhost:8000`

### 3. 初始化管理员

```bash
python scripts/init_db.py
```

默认账号 `admin / admin123`, 首次登录后请立即修改密码

### 4. 初始化示例商品

```bash
python scripts/seed_products.py
```

内置 10 件示例商品与商品图, 按名称去重, 可重复执行不会产生重复数据

## 访问地址

| 地址 | 说明 |
| --- | --- |
| http://localhost:3000 | 前端页面 |
| http://localhost:8000/docs | 后端 Swagger 接口文档 |
| http://localhost:8000/health | 健康检查 |

## 统一响应结构

所有业务接口统一返回: 

```json
{ "code": 200, "message": "success", "data": {} }
```

- `code`: 状态码, 成功为 `200`, 失败与 HTTP 状态码一致
- `message`: 提示信息
- `data`: 业务数据, 无数据时为 `null`

鉴权使用 Bearer Token, 请求头携带: 

```http
Authorization: Bearer <access_token>
```

## 项目文档

- [开发文档](docs/DEVELOPMENT.md): 技术栈, 分层架构约定, 代码规范, 本地开发
- [API 文档](docs/API.md): 接口说明, 请求/响应示例, 数据模型
- [部署文档](docs/DEPLOYMENT.md): Nginx + uvicorn + MySQL 生产部署

## 部署

生产部署采用 Nginx 托管前端静态资源并反向代理后端, 详见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
