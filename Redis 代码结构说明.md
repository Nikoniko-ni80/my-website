# Redis 代码结构说明 · 阅读指北

> 整理于 2026-10-19
>
> **用途**：做"阅读量 + 热度榜"时，代码里冒出一堆 `count_view` / `add_hot` / `redis_client.zincrby` / `HOT_KEY` / `"hot:raw"`，
> 看着都是名字，但**完全不是一个物种**。这份文档把它们分清楚。
>
> **配套**：[项目设计.md](项目设计.md) 第四节「Redis 用在哪」 · 第八节（附录）「Redis 命令速查」在 `myapp/cache.py` 文件末尾

---

## 零、一句话概括

> **`count_view` / `add_hot` 是【我写的普通 Python 函数】，Redis 根本不认识它们。**
> **它们只是"信封"，信封里面装的才是 Redis 命令。**

---

## 一、这里有四个层级

```
第 4 层  你项目里写的函数        count_view / add_hot / sync_views_to_db
           ↑ 用 Python 写的普通函数, 跟 Redis 无关
           │
第 3 层  别人写的 Python 库        redis / redis_client / redis_client.zincrby
           ↑ pip 装的, 用来"发命令"
           │
第 2 层  Redis 自己的命令          SET / HINCRBY / ZINCRBY / HGETALL
           ↑ Redis 服务器认识的词汇
           │
第 1 层  Redis 服务器里的箱子      "hot:raw" / "article:views" / "viewed:7:u3"
           ↑ 真正存数据的地方, 但【不在你的代码里】
```

**最常见的错误：把这四层当成同一层。**

---

## 二、所有名字对号入座

| 名字 | 到底是啥 | 谁写的 | 在哪定义 |
|---|---|---|---|
| `redis` | **Python 库** | 别人（pip 装）| — |
| `redis_client` | **Python 变量**，里面装着一个"连接对象" | 你 | `myapp/cache.py:7` |
| `redis_client.zincrby` | **方法**（redis 库提供的，作用是"发送 ZINCRBY 命令"）| 别人（redis 库）| — |
| `ZINCRBY` | **Redis 命令**（Redis 服务器的词汇）| Redis | — |
| `HOT_KEY` | **Python 变量**，值是字符串 | 你 | `myapp/cache.py:88` |
| `"hot:raw"` | **字符串**，在 Redis 里是**箱子的名字** | — | — |
| `VIEWS_KEY` | **Python 变量**，值是字符串 | 你 | `myapp/cache.py:36` |
| `"article:views"` | **字符串**，箱子的名字 | — | — |
| **`count_view`** | **你项目里的 Python 函数** | 你 | `myapp/cache.py:39` |
| **`add_hot`** | **你项目里的 Python 函数** | 你 | `myapp/cache.py:99` |
| `sync_views_to_db` | 你项目里的 Python 函数 | 你 | `myapp/tasks.py` |
| `_sync_loop` | 你项目里的 Python 函数 | 你 | `myapp/tasks.py` |
| `start_background_tasks` | 你项目里的 Python 函数 | 你 | `myapp/tasks.py` |
| `get_article` / `like_article` | 你的接口函数 | 你 | `myapp/routers/articles.py` |

---

## 三、看名字猜类型（不用再问）

| 名字长这样 | 就是什么 | 例子 |
|---|---|---|
| **全大写 + 下划线** | Python **常量**（字符串或数字）| `HOT_KEY` `VIEWS_KEY` `W_LIKE` `SYNC_INTERVAL` |
| **全小写 + 下划线** | Python **变量或函数** | `count_view` `add_hot` `redis_client` `sync_views_to_db` |
| **带点** | **在调方法** | `redis_client.zincrby(...)` = "对 redis_client 做 zincrby" |
| **带冒号的字符串** | **Redis 里箱子的名字** | `"hot:raw"` `"article:views"` `"viewed:7:u3"` |
| **全大写单词** | **Redis 命令**（只在文档/命令行出现）| `SET` `HINCRBY` `ZINCRBY` |

### ⚠️ 三层抽象，一个比一个虚

```
箱子的真身:   Redis 内存里的那个 ZSet        ← 真正装数据的东西
名字:         "hot:raw"                      ← 字符串, 用来找到箱子
变量:         HOT_KEY                        ← Python 常量, 存着这个字符串
```

**`HOT_KEY` 不是箱子，`"hot:raw"` 也不是箱子。它们只是"地址条"。**

---

## 四、调用关系图

### 【用户点开文章】

```
浏览器
  │  GET /articles/23
  ↓
get_article()                          ← routers/articles.py   (你的接口)
  ├─ db.query(Article)...              ← MySQL: 查文章内容
  │
  ├─ count_view(23, "ip127.0.0.1")     ← cache.py              (你写的函数)
  │     ├─ redis_client.set(...)       → Redis 命令 SET        (去重标记)
  │     └─ redis_client.hincrby(...)   → Redis 命令 HINCRBY    (零头 +1)
  │
  └─ add_hot(23, 1)                    ← cache.py              (你写的函数)
        └─ redis_client.zincrby(...)   → Redis 命令 ZINCRBY    (热度 +1)
  │
  ↓
返回 JSON
```

### 【后台线程，每 5 分钟自己跑】

```
_sync_loop()                           ← tasks.py               (你写的函数)
  └─ sync_views_to_db()                ← tasks.py               (你写的函数)
        ├─ redis_client.pipeline()
        │     ├─ hgetall(...)          → Redis 命令 HGETALL     (拿走零头)
        │     └─ delete(...)           → Redis 命令 DEL         (清空)
        └─ db.query(Article).update(...)   ← MySQL: view_count 累加
```

### 【启动时】

```
uvicorn 启动
  └─ lifespan()                        ← main.py
        └─ start_background_tasks()    ← tasks.py
              └─ threading.Thread(...).start()   ← 后台线程起来了
```

---

## 五、一次点击，四条命令

```
GET /articles/23
  │
  ├─ SET     viewed:23:ip127.0.0.1  1  NX EX 3600     ← 去重
  ├─ HINCRBY article:views  23  1                     ← 阅读量零头 +1
  ├─ ZINCRBY hot:raw  1  23                           ← 热度 +1
  └─ SELECT ... FROM articles WHERE id = 23           ← MySQL 拿正文
```

**前三句是写 Redis，第四句是读 MySQL。用户在等这四件事做完。**

---

## 六、为什么 `count_view` / `add_hot` 要包一层？

**直接写不行吗？当然行：**

```python
redis_client.zincrby("hot:raw", 3, article_id)
```

**但包成函数有三个好处：**

| 原因 | 说明 |
|---|---|
| **① 有 5 个地方要调** | `zincrby` 写 5 遍，哪天 key 名改了要改 5 处 |
| **② 防止打错 key 名** | key 名只写一次（`HOT_KEY`），不会有人手滑写成 `"hot:rows"` |
| **③ 统一加保护** | `add_hot` 里有 `try/except`，Redis 挂了不会让点赞接口 500。直接调的话每个地方都得包一遍 |

**这是"封装"的意义：把"怎么做"藏起来，外面只需要知道"做什么"。**

```python
# 从 articles.py 的角度看, 只需要理解这一句:
add_hot(article_id, W_LIKE)      # "给这篇文章加 3 分热度"
```

---

## 七、文件职责

| 文件 | 干什么 | 你需要看懂多少 |
|---|---|---|
| `cache.py` | 对 Redis 的**薄封装**。定义 key 名、权重、三个小函数 | **全部**（只有 12 行真实代码）|
| `tasks.py` | 后台定时任务：倒库 + 重建 | 主要看 `sync_views_to_db()` |
| `main.py` | 启动钩子，点着后台线程 | 只看 `lifespan` 那 4 行 |
| `routers/articles.py` | 业务接口，调用 `count_view` / `add_hot` | 看 5 个调用点的**位置** |

### 建议阅读顺序

```
1. cache.py 最开头（redis_client 怎么连的）
2. cache.py 的 count_view（最短的完整例子）
3. routers/articles.py 的 get_article（看它被怎么调用）
4. tasks.py 的 sync_views_to_db（数据怎么回去的）
5. cache.py 的 add_hot（跟 count_view 几乎一样）
```

---

## 八、Redis 里的箱子（当前状态）

```
Redis 内存
{
   "user:11"                    →  String  用户缓存, 5 分钟过期
   "article:views"              →  Hash    { "23": "1", "20": "1" }   零头, 倒完清空
   "hot:raw"                    →  ZSet    { "23": 2.0, "20": 1.0 }   热度分, 一直留着
   "viewed:23:ip127.0.0.1"      →  String  "1"                        去重标记, 1 小时过期
}
```

| 箱子 | 形状 | 装什么 | 活多久 |
|---|---|---|---|
| `user:{id}` | String | 一段 JSON | 5 分钟 |
| `article:views` | **Hash** | 文章id → 阅读零头 | 倒完库清空 |
| `hot:raw` | **ZSet** | 文章id → 热度分 | 一直留着（能从 MySQL 重建）|
| `viewed:{文章}:{人}` | String | `"1"`（值不重要，存在即信息）| 1 小时 |

**⚠️ Redis 的规则：空箱子等于不存在。** 里面的东西删光了，箱子本身也没了。

---

## 九、常见困惑 Q&A

**Q：`"hot:raw"` 是字符串，那怎么对字符串做数字操作？**
A：**没有对字符串做数字操作。** `"hot:raw"` 只是**箱子的名字**，数字在箱子里面：
```
"hot:raw"  →  ZSet 箱子  →  { "23": 2.0, "20": 1.0 }
   ↑名字                        ↑这里才是数字
```

**Q：这些箱子什么时候"定义"的？**
A：**没有定义这一步。** 你第一次写它的时候，Redis 现场造一个。形状由命令首字母决定：
`HINCRBY` 造 Hash，`ZINCRBY` 造 ZSet，`SET` 造 String。

**Q：`count_view` 是 Redis 的方法吗？**
A：**不是。** 是我在 `cache.py` 里写的普通 Python 函数。里面的 `redis_client.set(...)` 才是 Redis 库的方法。

**Q：那 `redis_client.zincrby` 又是谁？**
A：是 **redis 库（pip 装的）提供的方法**。它替你向 Redis 服务器发送 `ZINCRBY` 命令。

**Q：`ZINCRBY` 又是什么？**
A：**Redis 服务器自己的命令词汇。** 在你的代码里从没出现过（因为都是小写的方法调用），只在文档和 `redis-cli` 里出现。

**Q：为什么名字里有冒号？**
A：**冒号是人为约定的分隔符**，Redis 只当普通字符。它是"文件夹"的意思，用来分类：`user:` / `article:` / `viewed:` / `hot:`。**名字起乱了，以后就找不到、也清不掉。**

---

## 十、速记卡

```
count_view / add_hot      →  我写的函数, 负责"发命令"
redis_client.xxx()        →  redis 库的方法, 负责"怎么发"
ZINCRBY / SET / HINCRBY   →  Redis 服务器听得懂的词汇
"hot:raw"                 →  Redis 里某个箱子的名字
HOT_KEY                   →  存着 "hot:raw" 这个字符串的 Python 常量
```

**从 `articles.py` 往上看，你只需要认识 `add_hot`。**
**从 `cache.py` 往下看，你才需要认识 `zincrby`。**
**两层之间隔着封装 —— 不需要同时理解两边。**
