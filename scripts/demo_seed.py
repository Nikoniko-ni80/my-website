# ============================================================
# demo_seed.py —— 造演示数据 + 模拟阅读
# ============================================================
# 【干嘛的】
#   ① 注册 8 个 demo 用户 (demo1 ~ demo8, 密码都是 123456)
#   ② 每人发 2~4 篇文章
#   ③ 把一部分文章的发布时间改到过去 (让"时间衰减"看得出来)
#   ④ 模拟用户随机阅读 / 点赞 / 评论
#   ⑤ 最后把 Redis 里的阅读量零头倒回 MySQL
#
# 【怎么跑】
#   先启动后端 (launcher 或 uvicorn), 然后在项目根目录:
#       python scripts/demo_seed.py
#
#   不想最后倒库:
#       python scripts/demo_seed.py --no-sync
#
# 【为什么要"带 token 阅读"】
#   阅读去重的标记是 viewed:{文章}:{人}。
#   登录用户算 "u{id}", 未登录算 "ip{IP}"。
#   如果全用未登录去读, 全是同一个 IP → 每篇只算 1 次。
#   所以这里每个 demo 用户都登录, 各读各的, 才能模拟出"很多人看过"。
# ============================================================
import json
import os
import random
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import pymysql

BASE = "http://127.0.0.1:8000"
PASSWORD = "123456"

DB_CONF = dict(host="localhost", user="root", password="123456",
               database="myapp_db", charset="utf8mb4")

# demo 用户名前缀: 以后想清理, 找 demo1 ~ demo8 就行
DEMO_USERS = [f"demo{i}" for i in range(1, 9)]

CATEGORIES = ["前端", "后端", "AI", "其他", ""]

TITLES = [
    "从零搭一个 FastAPI 项目，我踩过的 5 个坑",
    "MySQL 索引到底该怎么建？一次真实对比",
    "Vue3 组合式 API 和选项式，到底选哪个",
    "Redis 缓存穿透、击穿、雪崩，一次说清",
    "一次线上慢查询的完整排查过程",
    "git 常用命令速查（附三个大坑）",
    "Docker 入门：镜像、容器、仓库",
    "Python 装饰器到底在装饰什么",
    "SQL 注入是怎么发生的，又该怎么防",
    "为什么你的接口这么慢：N+1 问题",
    "JWT 到底安全在哪，又危险在哪",
    "Nginx 反向代理配置笔记",
    "数据库范式：为什么不能所有字段塞一张表",
    "前端请求为什么总要加 loading 状态",
]

CONTENTS = [
    """## 背景

最近在做一个自己的小站，从零开始搭，记录一下踩过的坑。

### 坑一：路径问题

一开始用的绝对路径，换台电脑就跑不起来了。

```python
# ❌ 写死
path = "C:/Users/xxx/project"

# ✅ 跟着文件自己走
path = os.path.dirname(os.path.abspath(__file__))
```

### 坑二：忘了加 CORS

前端 5173，后端 8000，浏览器直接拦。

```python
app.add_middleware(CORSMiddleware, allow_origins=["*"])
```

### 小结

写代码的时候多想想"换台电脑还能不能跑"。
""",
    """## 先说结论

索引不是越多越好。**索引是为了查询，代价是写入变慢、占空间。**

### 什么列适合建索引

- 经常出现在 `WHERE` 里的
- 经常用来 `ORDER BY` 的
- **区分度高**的（比如 id、用户名）

### 什么列不适合

- 只有几个值的（比如性别、分类）
- 很少被查询的

我项目里 `category` 只有 4 个值，**故意不建索引** —— 建了反而拖慢写入。

### 怎么验证

```sql
EXPLAIN SELECT * FROM articles WHERE category = '后端';
```

看 `type`：`ALL` 是全表扫描，`ref` / `range` 才是走索引。
""",
    """## 两种写法

### 选项式（老写法）

```js
export default {
  data() { return { count: 0 } },
  methods: { add() { this.count++ } }
}
```

### 组合式（新写法）

```js
import { ref } from 'vue'
const count = ref(0)
const add = () => count.value++
```

### 我的感受

小页面两种都行。**逻辑一复杂，组合式明显更好拆** —— 可以把一段逻辑抽成一个 `useXxx()` 函数，到处复用。
""",
    """## 三个概念

| 问题 | 现象 | 解法 |
|---|---|---|
| 穿透 | 查一个根本不存在的 key | 布隆过滤器 / 缓存空值 |
| 击穿 | 热点 key 突然过期 | 互斥锁 / 逻辑过期 |
| 雪崩 | 大量 key 同时过期 | 过期时间加随机值 |

### 最容易忽略的

**防雪崩其实很简单**：给过期时间加个随机数。

```python
ex = 3600 + random.randint(0, 600)
```

就这一行，能把"同时过期"拆散开。
""",
    """## 起因

一个列表接口，平时 50ms，某天突然变成 3 秒。

## 排查

### ① 先看慢查询日志

```sql
SHOW VARIABLES LIKE 'slow_query_log';
```

### ② EXPLAIN 看执行计划

发现 `type=ALL`，全表扫描 200 万行。

### ③ 加索引

```sql
CREATE INDEX idx_user_created ON articles(user_id, created_at);
```

### ④ 还是慢

因为 `ORDER BY` 的列跟索引顺序不一致，用不上索引排序。

**改成 `(user_id, created_at DESC)` 之后，降到 20ms。**

## 教训

索引不是"加到 WHERE 的列上"就行，**还要看 ORDER BY**。
""",
    """## 日常三条

```bash
git status              # 看改了啥
git add .               # 装进待提交清单
git commit -m "说明"     # 存档
```

## 三个坑

### 坑 1：`.gitignore` 不能写行尾注释

```
node_modules/   # 注释     ← 整行失效！
```

**注释必须单独占一行。**

### 坑 2：`.gitignore` 管不了已提交的文件

```bash
git rm -r --cached .
git add .
```

### 坑 3：`add` 后面要有空格

```bash
git add.      # ❌ 报错
git add .     # ✅
```
""",
    """## 三个核心概念

```
镜像 (Image)  →  一个打包好的模板
容器 (Container) → 镜像跑起来的实例
仓库 (Registry) → 存放镜像的地方
```

## 最小示例

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```

```bash
docker build -t myapp .
docker run -p 8000:8000 myapp
```

## 为什么需要它

**"我这能跑啊"** —— 这句话以后可以不用说了。
""",
    """## 装饰器到底在干嘛

```python
def log(func):
    def wrapper(*args, **kwargs):
        print(f"调用 {func.__name__}")
        return func(*args, **kwargs)
    return wrapper

@log
def hello():
    print("hi")
```

**`@log` 等价于 `hello = log(hello)`。**

就这么简单：把一个函数传进去，换一个新的出来。

## 常见用途

- 打日志
- 计时
- 权限校验
""",
    """## 注入怎么发生的

```python
# ❌ 字符串拼接
sql = f"SELECT * FROM users WHERE name = '{name}'"
```

用户输入 `' OR '1'='1`，整条 SQL 就变形了。

## 怎么防

**用参数化查询，永远不要自己拼 SQL。**

```python
# ✅
cur.execute("SELECT * FROM users WHERE name = %s", (name,))
```

ORM 天然就是参数化的，所以用 SQLAlchemy 基本不用担心这个。
""",
    """## 现象

一个列表接口，10 条数据，发了 11 条 SQL。

## 原因

```python
for article in articles:
    article.author = db.query(User).get(article.user_id)   # 每条一次!
```

## 解法：一次查完

```python
user_ids = [a.user_id for a in articles]
users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids))}

for article in articles:
    article.author = users[article.user_id]     # 内存里查
```

**11 条 SQL → 2 条。**
""",
    """## 结构

```
header.payload.signature
```

- `header`：算法
- `payload`：用户 id、过期时间（**明文，谁都能解**）
- `signature`：用密钥签的，改一个字节就失效

## 所以

**JWT 里绝对不要放密码、手机号这种东西。**

## 常见误区

**JWT 没法"主动失效"。** 签发出去，到期前一直有效。
要"踢人下线"，得配合黑名单（通常放 Redis）。
""",
    """## 最简单的配置

```nginx
server {
    listen 80;
    server_name example.com;

    location / {
        proxy_pass http://127.0.0.1:5173;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
    }
}
```

## 注意

代理之后，后端的 `request.client.host` 会变成 Nginx 的 IP。
真实 IP 要从 `X-Forwarded-For` 头里取。
""",
]

COMMENTS = [
    "写得很清楚，学到了",
    "有个小问题想请教一下：如果是高并发场景呢？",
    "收藏了，回头细看",
    "这一步我卡了好久，谢谢",
    "补充一点：还可以用连接池",
    "讲得比书上明白多了",
    "刚好最近在做类似的东西",
    "这个坑我也踩过",
    "期待下一篇",
]


def call(method, path, body=None, token=None):
    """发一个 HTTP 请求, 返回解析后的 JSON"""
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def make_users():
    """注册/登录 demo 用户, 返回 [(username, token), ...]"""
    result = []
    for name in DEMO_USERS:
        try:
            call("POST", "/register", {"username": name, "password": PASSWORD})
            print(f"  + 注册 {name}")
        except urllib.error.HTTPError:
            pass                      # 已存在, 下面直接登录
        r = call("POST", "/login", {"username": name, "password": PASSWORD})
        if "token" not in r:
            print(f"  ! {name} 登录失败: {r}")
            continue
        result.append((name, r["token"]))
    return result


def make_articles(users):
    """每个用户发几篇文章, 返回 [(article_id, author_name), ...]"""
    created = []
    for name, token in users:
        n = random.randint(2, 4)
        for _ in range(n):
            title = random.choice(TITLES)
            # 标题后面加个序号, 避免完全重复看着奇怪
            title = f"{title} · {random.randint(1, 99)}"
            body = random.choice(CONTENTS)
            cat = random.choice(CATEGORIES)
            try:
                r = call("POST", "/articles", {
                    "title": title,
                    "content": body,
                    "is_public": True,
                    "category": cat,
                }, token=token)
                if "id" in r:
                    created.append((r["id"], name))
            except urllib.error.HTTPError as e:
                print(f"  ! 发文失败: {e}")
        print(f"  + {name} 发了 {n} 篇")
    return created


def backdate(article_ids):
    """把文章发布时间打散到过去 30 天, 让时间衰减看得出来"""
    conn = pymysql.connect(**DB_CONF)
    try:
        cur = conn.cursor()
        now = datetime.now()
        fresh = 0
        for aid in article_ids:
            r = random.random()
            if r < 0.30:
                delta = timedelta(hours=random.uniform(0.5, 6))      # 今天发的
                fresh += 1
            elif r < 0.70:
                delta = timedelta(days=random.uniform(1, 7))          # 一周内
            else:
                delta = timedelta(days=random.uniform(7, 30))         # 更早
            cur.execute("UPDATE articles SET created_at = %s WHERE id = %s",
                        (now - delta, aid))
        conn.commit()
        print(f"  + 打散发布时间完成 (其中 {fresh} 篇是 6 小时内发的)")
    finally:
        conn.close()


def simulate(users, articles, n_reads=12):
    """随机阅读 / 点赞 / 评论"""
    if not articles:
        print("  ! 没有文章, 跳过模拟")
        return
    reads = likes = comments = 0
    for name, token in users:
        picks = random.sample(articles, min(n_reads, len(articles)))
        for aid, _author in picks:
            try:
                call("GET", f"/articles/{aid}", token=token)
                reads += 1
            except urllib.error.HTTPError:
                continue

            if random.random() < 0.40:
                try:
                    call("POST", f"/articles/{aid}/like", token=token)
                    likes += 1
                except urllib.error.HTTPError:
                    pass

            if random.random() < 0.15:
                try:
                    call("POST", f"/articles/{aid}/comments",
                         {"content": random.choice(COMMENTS)}, token=token)
                    comments += 1
                except urllib.error.HTTPError:
                    pass
        print(f"  + {name} 读完了 {len(picks)} 篇")
    print(f"  合计: 阅读 {reads} 次 / 点赞 {likes} 次 / 评论 {comments} 条")


def sync_now():
    """把 Redis 里的阅读量零头立刻倒回 MySQL (不用等 5 分钟)"""
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "..", "myapp"))
    try:
        from tasks import sync_views_to_db
        n = sync_views_to_db()
        print(f"  + 立刻倒库完成, {n} 篇文章的阅读量已写回 MySQL")
    except Exception as e:
        print(f"  ! 倒库失败(不影响热榜): {e}")


def main():
    random.seed()
    print("=" * 56)
    print(" 演示数据生成器")
    print("=" * 56)

    # 先确认后端在跑
    try:
        call("GET", "/articles?page=1&size=1")
    except Exception as e:
        print(f"\n✗ 连不上后端 {BASE}")
        print(f"  {e}")
        print("  先把后端启动起来 (python launcher.py 或 uvicorn main:app)")
        return

    print("\n[1/5] 注册 / 登录 demo 用户")
    users = make_users()

    print("\n[2/5] 发文章")
    articles = make_articles(users)

    print("\n[3/5] 打散发布时间")
    backdate([aid for aid, _ in articles])

    print("\n[4/5] 模拟阅读 / 点赞 / 评论")
    simulate(users, articles)

    print("\n[5/5] 收尾")
    if "--no-sync" not in sys.argv:
        sync_now()
    else:
        print("  - 跳过倒库 (--no-sync), 5 分钟后后台线程会自己倒)")

    print()
    print("=" * 56)
    print(" 完成! 去浏览器看看:")
    print("   首页     http://localhost:5173/#/home")
    print("   热榜     http://localhost:5173/#/hot")
    print("=" * 56)


if __name__ == "__main__":
    main()
