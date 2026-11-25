# 博客社区网站

一个从零实现的前后端分离博客社区，包含文章、评论、社交、付费和 AI 助手等模块，已部署上线。

**线上地址：<https://like6657.cn>**

## 功能

- **用户**：注册 / 登录（JWT）、个人主页、资料与头像修改
- **文章**：Markdown 写作、封面上传、分类与标签、评论（两级楼中楼）、点赞
- **收藏与历史**：多收藏夹、浏览历史
- **社交**：关注 / 粉丝、关注动态流（Feed）、私信（WebSocket）、站内通知（SSE 实时推送）
- **内容发现**：首页推荐、分类页、标签页、热度排行榜
- **付费**：付费文章、余额与充值、VIP 折扣（模拟支付流程，未接入真实支付渠道）
- **AI 助手**：接入 DeepSeek，流式对话，多轮会话保存，按用户按日限额
- **其他**：图片上传、意见反馈

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI、SQLAlchemy 2、Pydantic |
| 数据库 | MySQL 8 |
| 缓存 | Redis（对象缓存、ZSET 热榜、按日限额） |
| 消息队列 | RabbitMQ（延迟消息关单、支付事件异步处理） |
| 实时通信 | SSE（通知）、WebSocket（私信） |
| 前端 | Vue 3、Vite、vue-router；marked + DOMPurify + highlight.js |
| 部署 | Docker Compose（MySQL / Redis / RabbitMQ / 后端 / 前端）、Nginx 反向代理 |

## 目录结构

```
.
├── myapp/                 # FastAPI 后端
│   ├── routers/           # 按业务拆分的接口
│   ├── ai/                # 模型调用与 AI 工具
│   ├── models.py          # 数据表定义
│   ├── cache.py           # Redis 缓存与热榜
│   ├── mq.py              # RabbitMQ 连接与消费者框架
│   ├── consumers.py       # 关单 / 收益 / 通知消费者
│   └── sse.py / ws.py     # 通知推送 / 私信连接管理
├── myapp-frontend/        # Vue 3 前端
├── deploy/mysql-init/     # 首次启动导入的 SQL
├── docker-compose.yml     # 五个容器的编排
└── 项目设计.md             # 表结构、流程与设计取舍
```

## 本地运行

### 方式一：Docker Compose

1. 在项目根目录创建 `.env`：

   ```
   SECRET_KEY=<随机长串>
   AI_BASE_URL=https://api.deepseek.com
   AI_MODEL=deepseek-chat
   AI_API_KEY=<你的 Key>
   ```

2. 启动：

   ```bash
   docker compose up -d --build
   ```

3. 浏览器打开 <http://localhost>

### 方式二：分别启动

后端（需要本地已启动 MySQL / Redis / RabbitMQ）：

```bash
cd myapp
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

接口文档：<http://127.0.0.1:8000/docs>

前端：

```bash
cd myapp-frontend
npm install
npm run dev
```

接口地址默认 `http://127.0.0.1:8000`，可通过环境变量 `VITE_API_BASE` 覆盖。

## 几个设计取舍

- **计数不存列**：点赞、收藏、关注都用明细表 + 唯一约束，数量查询时现算，天然防重复、防并发丢失。
- **删除靠外键级联**：挂在文章下的数据随文章删除；订单和通知不级联，保留交易记录与历史快照。
- **热榜用 Redis ZSET**：浏览时只写 Redis，后台任务定时把阅读量回写 MySQL，避免每次浏览都写库。
- **推送只推信号**：SSE 只告诉前端"有变化了"，内容仍从数据库拉取，推送丢了数据也不会丢。
- **支付不信任前端**：价格从数据库读，支付结果由服务端判定；订单状态机 + 30 分钟延迟消息自动关单；余额扣款加行锁；MQ 消费者依靠状态判断和唯一约束保证幂等。
- **缓存一致性**：凡是被缓存的数据，修改时"改库 + 清缓存"两件事一起做。

完整设计文档见 [项目设计.md](项目设计.md)。

## 说明

- 支付为模拟流程（余额扣减），未接入真实支付渠道。
- AI 助手目前为流式对话；站内文章检索的工具调用仍在开发中。
