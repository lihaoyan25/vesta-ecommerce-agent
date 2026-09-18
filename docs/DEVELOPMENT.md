# 开发文档

## 1. 项目简介

本项目是一个前后端分离的**智能线上商城**, 采用 FastAPI + Vue 3 技术栈, 实现智能客服AI Agent(SSE streaming & tool calling), 用户注册登录(支持用户名/邮箱/手机号), 忘记密码, 商品浏览/搜索/管理, 购物车勾选结算, 订单与余额支付(20 分钟未支付自动取消), 余额充值, 个人资料与密码管理等核心电商闭环能力

- 后端: RESTful API, JWT 鉴权, 分层架构(`routes → services → dao → models/schemas`)
- 前端: Vue 3 `<script setup>` + Pinia + Vue Router + Axios + Tailwind CSS
- 数据库: MySQL(SQLAlchemy 2.0 ORM, PyMySQL 驱动)

## 2. 技术栈

| 层 | 技术 | 版本约束 |
| --- | --- | --- |
| 后端框架 | FastAPI | 0.109.x |
| ASGI 服务器 | uvicorn | 0.27.x |
| ORM | SQLAlchemy | 2.0.x |
| 数据校验 | Pydantic | 2.6.x |
| 配置管理 | pydantic-settings | 2.1.x |
| 鉴权 | python-jose + passli(bcrypt) | 3.3.0 / 1.7.4 |
| 数据库驱动 | PyMySQL | 1.1.x |
| 前端框架 | Vue | ^3.4 |
| 状态管理 | Pinia | ^2.1 |
| 路由 | Vue Router | ^4.3 |
| HTTP 客户端 | Axios | ^1.6 |
| 样式 | Tailwind CSS | ^3.4 |
| 构建工具 | Vite | ^5.2 |

完整依赖清单见根目录 `requirements.txt`(后端) 与 `frontend/package.json`(前端)

## 3. 目录结构

```text
vesta‑ecommerce/
├── app/                        # 后端应用
│   ├── main.py                 # 应用入口: 生命周期、CORS、全局异常、路由挂载
│   ├── config.py               # 配置(pydantic-settings 读取 .env)
│   ├── database.py             # 数据库引擎、会话工厂、Base
│   ├── api/
│   │   ├── deps.py             # 依赖注入: get_current_user / get_current_superuser
│   │   └── v1/
│   │       ├── router.py       # v1 路由汇总
│   │       ├── routes/         # 路由层(薄, 只做参数与响应编排)
│   │       └── schemas/        # Pydantic 请求/响应模型
│   ├── services/               # 业务逻辑层(事务边界)
│   ├── dao/                    # 数据访问层(不含 commit, 事务交给 service)
│   ├── models/                 # SQLAlchemy ORM 模型
│   ├── tools/                  # 智能客服工具层(LLM function calling, 复用 service 层)
│   ├── utils/                  # 通用工具(JWT、密码)
│   └── prompts/                # 智能客服系统提示词(System Prompt)
├── frontend/                   # 前端应用(Vite + Vue3)
│   ├── src/api/                # Axios 封装与接口定义
│   ├── src/stores/             # Pinia 状态
│   ├── src/router/             # 路由与守卫
│   ├── src/components/         # 通用组件
│   └── src/views/              # 页面
├── scripts/init_db.py          # 初始化管理员脚本
├── docs/                       # 项目文档
├── static/                     # 后端挂载的静态资源
├── .env / .env.example         # 环境变量
└── requirements.txt
```

## 4. 分层架构约定

项目遵循「职责单一」的分层原则, 调用方向严格为单向: 

```text
routes(路由) → services(业务) → dao(数据访问) → models(ORM)
                         ↘ schemas(入参/出参校验)
```

各层职责: 

- **routes**: 仅做参数接收、鉴权依赖注入、调用 service、统一响应包装不写业务逻辑
- **services**: 承载业务规则, **控制事务边界**(显式 `commi()` / `rollbac()`)
- **dao**: 只封装 SQLAlchemy 查询, **不自行 `commi()`**, 将事务提交权上交给 service
- **models**: 数据库表结构与关联关系定义
- **schemas**: 请求参数校验与响应序列化(Pydantic)

## 5. 关键约定

### 5.1 统一响应结构

所有业务接口成功时返回: 

```json
{ "code": 200, "message": "success", "data": { } }
```

错误时由全局异常处理器统一返回同构结构: 

```json
{ "code": 400, "message": "错误描述", "data": null }
```

- 成功 `code` 固定为 `200`
- 错误 `code` 与 HTTP 状态码一致(400/401/403/404/422/500 等)
- 后端统一使用 `success_response(data, message)` 辅助函数构造成功响应

### 5.2 阻塞型 DB 操作异步化

路由声明为 `async def`, 所有同步、阻塞的数据库调用必须通过线程池执行, 避免阻塞事件循环: 

```python
from fastapi.concurrency import run_in_threadpool

data = await run_in_threadpoo(cart_service.get_cart, current_user.user_id)
```

### 5.3 事务与并发安全

- DAO 不提交事务, Service 负责 `commit()`
- 订单创建与支付对商品/用户行加锁防超卖与并发透支, 使用 `SELECT ... FOR UPDATE`, 并通过 `populate_existing=True` 刷新最新值
- 订单 20 分钟未支付采用**惰性取消**: 查询/支付订单时判定 `expire_at`, 过期则置为已取消并回补库存, 无需后台定时任务
- 任何事务异常都需 `rollback()` 后重新抛出

### 5.4 鉴权

- 登录签发 `access_token`(短时)+ `refresh_token`(长时)
- `refresh_token` 用于换取新的 `access_token`, 前端在 401 时自动刷新并重放请求
- `SECRET_KEY` 必须通过环境变量/`.env` 提供, 禁止使用默认值

### 5.5 智能客服

- LLM 通过 `llm_client.py` 封装 DeepSeek(OpenAI 兼容)流式接口, 不引入智能体框架
- **系统提示词外置于 `app/prompts/system_prompt.md`**(含手写的工具清单与调用场景), 代码按 mtime 缓存热加载, 改文件即生效无需重启; 工具实现仍以注册表形式存在于 `app/tools/`
- 对话经 `chat_service.chat_stream` 编排: 保存用户消息 → 组装上下文(滑动窗口 20 条) → 流式输出 → 工具调用循环(最多 5 轮, 超限强制作答) → 助手消息落库
- 工具调用消息仅存在于单次请求的 LLM 上下文中, 不落库; `chat_messages` 只存用户/助手消息
- 工具执行结果统一兜底为 `{ok, data|error}`, 永远限定当前用户数据权限
- 商品查询为 **Text2SQL 统一工具**(`search_products`): 内部二次 LLM 生成 SQL(非流式+思考关闭+低温), 经 **sqlglot AST 硬校验**后执行——仅单条 SELECT、仅允许 `products` 表(含子查询/JOIN 全层级)、LIMIT 自动补齐/截断为 20; 订单/购物车查询仍走专用工具与 service 层, 不经 SQL 生成
- 商品/订单卡片随消息发送时, 后端生成快照文本注入上下文并随消息存库, 历史重建零额外查询
- 思考模式由 `.env` 的 `DEEPSEEK_THINKING` 开关控制, 请求体显式写入 `thinking.type`(V4 系列服务端默认 `enabled`, 必须显式覆盖), 不向前端暴露开关
- `DEEPSEEK_API_KEY` 未配置时客服接口统一返回 503, 不影响主站功能
- **语音通话**: `routes/voice.py` WebSocket 网关编排 火山流式 ASR(`volcano_asr.py`) → **复用 chat_stream** → 火山双向流式 TTS(`volcano_tts.py`); 二进制协议编解码在 `volcano_protocol.py`(事件号对照官方 demo); 并发模型三协程——主循环(音频透传) + asr_reader(definite 增量分句入队, 按「已消费分句数」去重防重复触发) + round_runner(顺序执行轮次, **每轮独立 TTS 会话**, FinishSession 后须重新 StartSession); 打断=静音不取消: 前端本地能量检测(依赖 AEC)发 `barge_in`, 网关停发音频但轮次后台跑完(工具调用/落库不丢), 新话语排队顺延; 语速由 `VOLCANO_TTS_SPEECH_RATE` 控制; 由 `VOLCANO_API_KEY` 启停, 麦克风需 HTTPS 环境
- SSE 流式接口需注意 Nginx 反代时关闭缓冲(`X-Accel-Buffering: no` 响应头已内置)

## 6. 本地开发环境搭建

### 6.1 后端

```bash
# 1. 创建并激活虚拟环境(建议 Python 3.12)
python -m venv .venv
.venv\Scripts\activate          # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 准备配置
# 复制 .env.example 为 .env, 并填写数据库连接信息与 SECRET_KEY
copy .env.example .env

# 4. 启动服务(默认 8000 端口, 启动时自动 create_all 建表)
uvicorn app.main:app --reload
```

接口文档(Swagger UI)启动后访问 `http://localhost:8000/docs`

### 6.2 前端

```bash
cd frontend
npm install
npm run dev          # 默认 http://localhost:3000
```

开发模式下 Vite 已配置代理, 将 `/api` 与 `/static` 转发到 `http://localhost:8000`

### 6.3 初始化管理员

```bash
.venv\Scripts\python.exe scripts\init_db.py
# 默认账号 admin / admin123, 首次登录后请尽快修改密码
```

## 7. 常用命令

| 用途 | 命令 |
| --- | --- |
| 后端启动(开发) | `uvicorn app.main:app --reload` |
| 后端语法检查 | `.venv\Scripts\python.exe -m compileall -q app` |
| 前端开发 | `cd frontend && npm run dev` |
| 前端构建 | `cd frontend && npm run build` |
| 初始化管理员 | `.venv\Scripts\python.exe scripts\init_db.py` |

## 8. 代码规范提示

- 时间戳统一使用 naive `datetime.now`(单时区部署, 不引入时区对象)
- 金额(价格、余额、充值金额等)全链路使用 `Decimal`: 数据库列用 `DECIMA(14, 2)`, schema 字段(如 `price`、`balance`、`amount`)声明为 `Decimal` 而非 `float`, service 层运算保持 `Decimal` 不混入 float; 仅在 FastAPI 序列化响应时由框架转成 JSON 数字
- 密码通过 `hash_password` / `verify_password` 处理, 禁止明文存储
- 新增接口时同步在 `schemas` 定义请求/响应模型, 并遵循统一响应结构
- 前端所有请求统一走 `src/api/request.js` 封装的实例, 不要直接使用原生 `axios`(刷新令牌的场景除外)
