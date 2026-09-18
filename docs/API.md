# API 文档

## 1. 基础约定

- **Base URL**: `http://<host>:8000/api/v1`
- **数据格式**: 请求体与响应体均为 `application/json`(登录接口使用 `application/x-www-form-urlencoded`)
- **鉴权方式**: Bearer Token需要登录的接口在请求头携带: 

```http
Authorization: Bearer <access_token>
```

- 交互式文档: `http://<host>:8000/docs`(Swagger UI)

### 1.1 统一响应结构

所有业务接口统一返回如下结构: 

```json
{
  "code": 200,
  "message": "success",
  "data": { }
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| code | int | 状态码, 成功为 `200`; 失败与 HTTP 状态码一致 |
| message | string | 提示信息, 成功默认 `success`, 失败为具体错误描述 |
| data | any | 业务数据, 无数据时为 `null` |

### 1.2 错误码

| HTTP 状态码 | 含义 |
| --- | --- |
| 400 | 业务校验失败 / 参数有误 |
| 401 | 未认证或凭证失效 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 422 | 请求参数校验失败 |
| 500 | 服务器内部错误 |

错误响应示例: 

```json
{
  "code": 400,
  "message": "用户名已存在",
  "data": null
}
```

## 2. 认证模块 `/auth`

### 2.1 用户注册

`POST /auth/register`

请求体: 

```json
{
  "username": "zhangsan",
  "email": "zhangsan@example.com",
  "phone": "13800138000",
  "password": "Abc12345",
  "password_confirm": "Abc12345"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| username | string | 是 | 字母开头, 3-50 位字母/数字/下划线 |
| email | string | 是 | 合法邮箱 |
| phone | string | 否 | 11 位手机号 |
| password | string | 是 | 8-20 位, 含大小写字母与数字 |
| password_confirm | string | 是 | 需与 password 一致 |

成功响应 `data`(用户信息): 

```json
{
  "user_id": 1,
  "username": "zhangsan",
  "email": "zhangsan@example.com",
  "phone": "13800138000",
  "balance": 1000.0,
  "role": "user",
  "created_at": "2026-01-01T00:00:00"
}
```

### 2.2 用户登录

`POST /auth/login`

请求体(form-urlencoded): 

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| username | string | 是 | 用户名 |
| password | string | 是 | 密码 |

成功响应 `data`: 

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### 2.3 刷新访问令牌

`POST /auth/refresh`

请求体: 

```json
{ "refresh_token": "eyJ..." }
```

成功响应 `data`: 

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### 2.4 获取当前用户信息

`GET /auth/me`(需登录)

成功响应 `data`: 同「用户注册」中的用户信息结构

## 3. 用户模块 `/users`

> 以下接口均需登录(Bearer Token)

### 3.1 更新当前用户信息

`PUT /users/me`

请求体(字段均为可选; 修改 email/phone 时 `current_password` 必填):  

```json
{
  "username": "newname",
  "email": "new@example.com",
  "phone": "13900139000",
  "current_password": "Abc12345"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| username | string | 否 | 新用户名, 无需密码验证 |
| email | string | 否 | 新邮箱, 需 `current_password` 验证 |
| phone | string | 否 | 新手机号, 需 `current_password` 验证 |
| current_password | string | 条件 | 修改 email/phone 时必填 |

- 修改项与原值相同则跳过; 用户名/邮箱/手机号与他人重复时返回 400
- 成功响应 `data`: 更新后的用户信息

### 3.2 修改密码

`PUT /users/me/password`

请求体: 

```json
{ "old_password": "Abc12345", "new_password": "Xyz98765" }
```

成功响应: `data` 为 `null`, `message` 为 `密码修改成功`

### 3.3 查询余额

`GET /users/me/balance`

成功响应 `data`: 

```json
{ "balance": 1000.0, "currency": "CNY" }
```

### 3.4 账户充值

`POST /users/me/recharge`

请求体: 

```json
{ "amount": 500 }
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| amount | number | 是 | 充值金额, 必须大于 0 |

成功响应 `data`: 

```json
{ "balance": 1500.0, "currency": "CNY" }
```

## 4. 商品模块 `/products`

### 4.1 商品列表(分页)

`GET /products`

查询参数: 

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| page | int | 1 | 页码, >=1 |
| page_size | int | 10 | 每页数量, 1-100 |

成功响应 `data`: 

```json
{
  "items": [ { "product_id": 1, "name": "iPhone 17 Pro", "price": 9999.0, "stock": 100, "image_url": "/static/upload/xxx.jpg", "is_active": true, "description": "..." } ],
  "total": 100,
  "page": 1,
  "page_size": 10
}
```

### 4.2 商品搜索

`GET /products/search`

查询参数: `keyword`(必填)、`page`、`page_size`响应 `data` 结构同「商品列表」

### 4.3 商品详情

`GET /products/{product_id}`

成功响应 `data`: 单个商品对象(结构见 4.1 中 `items` 元素)

### 4.4 创建商品(管理员)

`POST /products`(需管理员)

请求体: 

```json
{
  "name": "MacBook Air",
  "description": "M4 芯片",
  "price": 9499.0,
  "stock": 50,
  "image_url": "/static/upload/macbook_air_display.jpg"
}
```

成功响应 `data`: 新建的商品对象

### 4.5 更新商品(管理员)

`PUT /products/{product_id}`(需管理员)

请求体字段均可选(`name` / `description` / `price` / `stock` / `image_url` / `is_active`), 仅更新传入字段成功响应 `data`: 更新后的商品对象

### 4.6 删除商品(管理员)

`DELETE /products/{product_id}`(需管理员)

软删除(将 `is_active` 置为 `false`)成功响应: `data` 为 `null`, `message` 为 `删除成功`

## 5. 购物车模块 `/cart`

> 以下接口均需登录(Bearer Token)

### 5.1 查看购物车

`GET /cart`

成功响应 `data`: 

```json
{
  "items": [
    {
      "cart_item_id": 1,
      "product_id": 1,
      "product_name": "iPhone 17 Pro",
      "product_price": 9999.0,
      "quantity": 2,
      "subtotal": 19998.0,
      "created_at": "2026-01-01T00:00:00",
      "image_url": "/static/upload/xxx.jpg"
    }
  ],
  "total_amount": 19998.0,
  "total_quantity": 2
}
```

### 5.2 添加商品到购物车

`POST /cart/items`

请求体: 

```json
{ "product_id": 1, "quantity": 2 }
```

成功响应 `data`: 更新后的购物车结构(同 5.1)

### 5.3 更新购物车商品数量

`PUT /cart/items/{product_id}`

请求体: 

```json
{ "quantity": 3 }
```

成功响应 `data`: 更新后的购物车结构

### 5.4 删除购物车商品

`DELETE /cart/items/{product_id}`

成功响应 `data`: 更新后的购物车结构

### 5.5 清空购物车

`DELETE /cart/clear`

成功响应 `data`: 清空后的购物车结构(`items` 为空)

> 结算已改为订单模式: 在购物车页勾选商品后调用「6.2 创建订单」, 不再有 `/cart/checkout` 接口

## 6. 订单模块 `/orders`

> 以下接口均需登录订单状态: `1`=待支付, `2`=已支付, `3`=已取消待支付订单 20 分钟内有效, 超时未支付由系统惰性取消(查询/支付时判定)并自动回补库存

### 6.1 订单列表(分页)

`GET /orders?page=1&page_size=10&status=1`

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| page | int | 否 | 页码, 默认 1 |
| page_size | int | 否 | 每页数量, 默认 10, 1-100 |
| status | int | 否 | 按状态过滤: 1/2/3 |

成功响应 `data`: 

```json
{
  "items": [ { "order_id": 1, "order_no": "20260910120000AB12CD34", "total_amount": 19998.0, "status": 1, "expire_at": "2026-09-10T12:20:00", "paid_at": null, "created_at": "2026-09-10T12:00:00", "items": [ { "product_id": 1, "product_name": "iPhone 17 Pro", "product_price": 9999.0, "image_url": "/static/upload/xxx.jpg", "quantity": 2, "subtotal": 19998.0 } ] } ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

### 6.2 创建订单

`POST /orders`(购物车选中商品结算)

请求体: 

```json
{ "product_ids": [1, 2, 3] }
```

行为: 锁定商品行扣减库存(防超卖)、生成待支付订单(20 分钟有效)、删除对应购物车项

常见失败: 未选择商品(400)、购物车中不存在该商品(400)、商品已下架(400)、库存不足(400)

### 6.3 订单详情

`GET /orders/{order_id}`

成功响应 `data`: 同 6.1 中单个订单结构

### 6.4 支付订单

`POST /orders/{order_id}/pay`

使用账户余额支付, 扣款成功后订单变为「已支付」

常见失败: 余额不足(400)、订单已取消(400)、重复支付(400)

### 6.5 取消订单

`POST /orders/{order_id}/cancel`

仅待支付订单可取消, 取消后自动回补库存, 订单状态变为「已取消」

### 6.6 删除订单

`DELETE /orders/{order_id}`

仅已取消的订单可删除, 成功响应 `data` 为 `null`

## 7. 智能客服模块 `/chat`

> 以下接口均需登录依赖 `DEEPSEEK_API_KEY` 配置, 未配置时返回 503消息以 SSE 流式返回(仅流式接口), 其余接口为统一 JSON 响应

### 7.1 新建会话

`POST /chat/sessions`

成功响应 `data`: 

```json
{ "session_id": 1, "title": "新会话", "created_at": "...", "updated_at": "..." }
```

### 7.2 会话列表

`GET /chat/sessions`

成功响应 `data`: 会话数组, 按更新时间倒序

### 7.3 会话消息历史

`GET /chat/sessions/{session_id}/messages`

成功响应 `data`: 

```json
{
  "session": { "session_id": 1, "title": "..." },
  "messages": [ { "message_id": 1, "role": "user", "content": "...", "context": null, "created_at": "..." } ]
}
```

`context` 不为 `null` 时为卡片快照: `{ "type": "product|order", "id": 1, "text": "注入客服的描述文本" }`

### 7.4 删除会话

`DELETE /chat/sessions/{session_id}`(级联删除消息)

### 7.5 推荐卡片

`GET /chat/recommendations`

返回最近订单、在售商品与购物车项, 供前端渲染卡片后随消息回发: 

```json
{
  "orders": [ { "type": "order", "id": 1, "order_no": "...", "status": 1, "total_amount": 99.0 } ],
  "products": [ { "type": "product", "id": 3, "name": "...", "price": 59.0, "image_url": "..." } ],
  "carts": [ { "type": "cart", "product_id": 3, "name": "...", "quantity": 2 } ]
}
```

> 订单/商品卡片发送时作为 `context` 传给 7.6; 购物车卡片点击后直接填充提问文本即可, 无需 `context`

### 7.6 发送消息(SSE 流式)

`POST /chat/sessions/{session_id}/messages/stream`

请求体: 

```json
{ "content": "帮我看看这个商品还有货吗", "context": { "type": "product", "id": 3 } }
```

`context` 可选, 对应前端发送的商品/订单卡片

响应为 `text/event-stream`, 每个事件一行 `data: {JSON}`: 

| 事件 type | 字段 | 说明 |
| --- | --- | --- |
| meta | session_id, user_message_id | 流开始, 用户消息已落库 |
| delta | content | 回复文本增量, 按序拼接即为完整回复 |
| tool | name, display | 客服正在调用工具(如「正在查询订单」) |
| done | message_id | 回复完成, 助手消息已落库 |
| error | message | 出错提示 |

### 7.7 语音通话(WebSocket)

`WS /voice/call?token=<access_token>&session=<chat_session_id>`

实时语音通话网关: 浏览器麦克风音频 → 火山流式 ASR 识别 → **复用 `chat_stream` 对话管线**(工具调用/会话记忆与文字客服完全一致) → 火山双向流式 TTS 合成音频回传。`VOLCANO_API_KEY` 未配置时连接即返回 `error` 事件并关闭; 麦克风权限要求 HTTPS(或 localhost)环境。

上行消息:

| 类型 | 格式 | 说明 |
| --- | --- | --- |
| 音频帧 | 二进制 | PCM 16k 16bit mono, 约 200ms/帧, 网关直接透传 ASR |
| stop | 文本 JSON | 挂断, 结束通话 |
| audio_played | 文本 JSON | 本句音频已播放完毕, 网关回到聆听状态 |
| barge_in | 文本 JSON | 前端本地能量检测到用户开口(依赖浏览器回声消除), 网关立即静音当前播报 |

下行消息:

| 类型 type | 字段 | 说明 |
| --- | --- | --- |
| status | phase | 状态机: `listening`(聆听) / `thinking`(思考) / `speaking`(播报) |
| subtitle | text | ASR 实时字幕(累计文本) |
| final | text | 一句说完的确定分句, 触发一轮对话 |
| assistant_delta | text | 回复文本增量 |
| assistant_text | text | 本轮完整回复 |
| tool | display | 正在调用工具(如「正在添加购物车」) |
| audio | pcm | TTS 音频块(base64 PCM 24k, 语速由 `VOLCANO_TTS_SPEECH_RATE` 控制) |
| audio_done | - | 本轮音频下发完毕 |
| interrupted | - | 用户已打断, 播报停止 |
| error | message | 出错提示 |

打断语义: 播报期间用户开口只触发**静音**——立即停止下发音频与字幕, 但当前轮次的工具调用与消息落库在后台照常完成(说到做到); 打断时说的新话语进入队列, 本轮结束后立即处理。

## 8. 数据模型速查

### UserResponse

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| user_id | int | 用户 ID |
| username | string | 用户名 |
| email | string | 邮箱 |
| phone | string\|null | 手机号 |
| balance | number | 账户余额 |
| role | string | `user` / `admin` |
| created_at | string | 注册时间 |

### ProductResponse

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| product_id | int | 商品 ID |
| name | string | 商品名称 |
| description | string\|null | 商品描述 |
| price | number | 价格 |
| stock | int | 库存 |
| image_url | string\|null | 图片 URL |
| is_active | bool | 是否上架 |
| created_at / updated_at | string | 时间戳 |
