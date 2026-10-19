# ============================================================
# cache.py - Redis 缓存连接 (跟 database.py 连 MySQL 一个套路)
# ============================================================
# 【这个项目里, Redis 一共存 4 种东西】
#   ① user:{id}            用户信息的副本            String  5 分钟过期
#   ② article:views        阅读量零头(还没倒库的)     Hash    倒完库就清空
#   ③ viewed:{文章}:{人}    去重标记, 防重复计数       String  1 小时过期
#   ④ hot:raw              文章的热度原始分          ZSet    永久(能从 MySQL 重建)
# ============================================================
import redis

# 连接 Redis (数据在内存里, 比 MySQL 快得多)
redis_client = redis.Redis(  #这个redif.Redis相当于sql的engine,在后面{}设置地址和端口
    host="localhost",
    port=6379,
    decode_responses=True,   # 让取出来的是字符串, 不是字节
    #加密部分的两种编码  "abc".encode()   字符串编码为字节
    #                   b"abc".decode()   字节解码为字符串
)


# ============================================================
# 阅读量
# ============================================================
# 【为什么阅读量要过 Redis, 不直接 UPDATE MySQL?】
#   看一篇文章就写一次磁盘, 人一多就顶不住。Redis 全在内存, 每秒扛几万次。
#   所以: 先在 Redis 里【攒着】, 每隔几分钟整体倒一次回 MySQL。
#   → 这就是"缓冲/缓存"在真实场景里的标准用法。
#
# 【存成什么结构】
#   article:views 是一个 Hash(哈希), 长这样:
#       {
#         "7":  "12",     ← 文章 7 攒了 12 次还没倒回去的阅读
#         "15": "3",      ← 文章 15 攒了 3 次
#       }
#
#   为什么不一篇一个 key (article:views:7) ?
#     因为倒库是"整体倒"。Hash 一条命令就能拿走全部 + 清空全部;
#     散着存就得先问 Redis"我有哪些 key"(KEYS 命令),
#     而 KEYS 会把整个 Redis 卡住扫一遍, 生产环境是禁用命令。
#     → 能聚成一个 key 就聚一个。
VIEWS_KEY = "article:views"


def count_view(article_id: int, viewer: str) -> bool:
    """记一次阅读。

    viewer = "看的人是谁"的标记 (登录了是 u{id}, 没登录是 ip{IP})。
             它【只用来去重】, 不会被存进 MySQL。

    返回 True  = 这次真的 +1 了
         False = 这人一小时内已经看过 / Redis 出问题了
    """
    try:
        # ① 去重: 同一人一小时内只算一次
        #    nx=True = "这个 key 不存在才设置", 返回 True 说明是头一回
        #    ex=3600 = 一小时后这个 key 自己消失, 不占地方
        #    → 这就是那条规律: 临时要的"谁"用会过期的缓存, 永久要的"谁"才建表
        if not redis_client.set(f"viewed:{article_id}:{viewer}", 1, ex=3600, nx=True):
            return False

        # ② 计数: 攒进 Hash, 等定时任务倒回 MySQL (见 main.py 的后台线程)
        redis_client.hincrby(VIEWS_KEY, article_id, 1)
        return True

    except Exception as e:
        # ★ Redis 挂了也【不能】让文章打不开 —— 阅读量是小事, 看文章是大事
        print("记录阅读量失败:", e)
        return False


# ============================================================
# 热度榜
# ============================================================
# 【和阅读量的区别】
#   阅读量那个 Hash (article:views) 是"还没倒回 MySQL 的零头", 倒完就清空。
#   这个 ZSET (hot:raw) 是【文章的热度分】, 一直留着, 不会清空。
#
# 【为什么用 ZSET (有序集合)】
#   因为它每个成员都带一个"分数", Redis 内部一直按分数帮你排好。
#   要"前 10 名" → 一条命令就行, 不用自己排序。
#
# 【存的是什么】
#   hot:raw = { "7": 38, "15": 12, ... }
#                 ↑ id   ↑ 热度分
#
#   注意: 【只存文章 id, 不存文章内容】。
#   内容在 MySQL 里, 取到 id 再回去查 —— 就像图书馆的索引卡。
#
# 【为什么 key 叫 hot:raw 而不是 hot:articles】
#   raw = 原始分。它【没有算时间衰减】。
#   排行榜上真正展示的分数是"读的时候现算"的, 见 routers/articles.py 的热榜接口。

HOT_KEY = "hot:raw"

# 权重: 按"用户花的力气"排
#   看一眼  → 零成本
#   点个赞  → 一次点击
#   写评论  → 要想、要打字
W_VIEW    = 1
W_LIKE    = 3
W_COMMENT = 5


def add_hot(article_id: int, weight: int):
    """给某篇文章加热度分。

    weight 可以是负数 —— 取消点赞 / 删评论的时候用。
    (Redis 支持负分, 不会出错)
    """
    try:
        redis_client.zincrby(HOT_KEY, weight, article_id)
    except Exception as e:
        # 跟阅读量一样: 加热度失败也不能影响用户操作
        print("加热度失败:", e)


# ============================================================
# 附: Redis 命令速查 (看不懂上面的方法名就回来瞄一眼)
# ============================================================
# 【规律一】命令 = 前缀字母 + 动词
#   前缀字母 = 操作哪种形状:
#       没前缀 → String       H → Hash
#       Z     → ZSet         L → List      S → Set
#   动词:
#       SET/ADD  设置/添加        GET/RANGE  取
#       INCRBY   自增指定数       DEL/REM    删
#       EXISTS   存不存在         TTL        还剩几秒
#
#   所以 zincrby = Z(Set) + INCRBY = "在 ZSet 里加分"
#        hincrby = H(ash)  + INCRBY = "在 Hash 里加数"
#
# 【规律二】Python 写法 = 命令名全小写, 参数顺序照抄
#   Redis  :  ZINCRBY hot:raw 3 7
#   Python :  redis_client.zincrby("hot:raw", 3, 7)
#   选项在网上是关键字参数:
#   Redis  :  SET k v NX EX 3600
#   Python :  redis_client.set("k", v, nx=True, ex=3600)
#
# 【本项目用到的命令】
#   SET k v NX EX 3600      设值, 只在不存在时设, 3600 秒后自己消失
#   HINCRBY key 字段 数      Hash 里某个字段 +数 (没有就当 0)
#   HGETALL key              把整个 Hash 取出来 (返回 dict)
#   DEL key                  删掉整个 key
#   ZINCRBY key 数 成员      ZSet 里某个成员的分 +数 (传负数就是扣)
#   ZREVRANGE key 0 9        ZSet 按分【从高到低】取第 0~9 个
#           ... WITHSCORES   顺便把分数也带出来
#   ZREM key 成员            从 ZSet 里删掉某个成员
#   EXISTS key               这个 key 存不存在 (1/0)
#
# 【注意参数顺序不同】
#   HINCRBY key 字段 数      ← 字段在前
#   ZINCRBY key 数  成员      ← 分数在前
#   这是 Redis 的规定, 只能记。
#
# 【忘了怎么查】
#   ① https://redis.io/commands ，每个命令第一行就是语法
#   ② redis-cli 里敲  HELP ZINCRBY
#   ③ Python 里敲     help(redis_client.zincrby)
#
# 【5 分钟上手练习】终端敲 redis-cli，逐条粘:
#   HSET  demo:views 7 0
#   HINCRBY demo:views 7 1
#   HGETALL demo:views
#   ZADD  demo:hot 0 7
#   ZINCRBY demo:hot 3 7
#   ZINCRBY demo:hot 5 8
#   ZREVRANGE demo:hot 0 -1 WITHSCORES    ← 顺序本来就是排好的
#   DEL demo:views demo:hot               ← 收拾干净
# ============================================================


# ============================================================
# 附: 功能调用图 (谁调谁, 一眼看明白)
# ============================================================
# 【第一层: 用户点开一篇文章】
#
#   浏览器
#     │  GET /articles/23
#     ↓
#   get_article()                       ← routers/articles.py  (接口)
#     ├─ db.query(Article).first()      → MySQL: 查正文
#     │
#     ├─ count_view(23, "ip127.0.0.1")  ← cache.py  (本文件, 上面那个函数)
#     │     ├─ redis_client.set(...)      → Redis 命令 SET      去重标记
#     │     └─ redis_client.hincrby(...)  → Redis 命令 HINCRBY  零头 +1
#     │
#     └─ add_hot(23, 1)                 ← cache.py  (本文件, 下面那个函数)
#           └─ redis_client.zincrby(...)  → Redis 命令 ZINCRBY  热度 +1
#     ↓
#   返回 JSON
#
#
# 【第二层: 后台线程, 每 5 分钟自己跑一次 (完全不在请求里)】
#
#   _sync_loop()                        ← tasks.py
#     └─ sync_views_to_db()             ← tasks.py
#           ├─ redis_client.pipeline()
#           │     ├─ hgetall(...)       → Redis 命令 HGETALL  拿走零头
#           │     └─ delete(...)        → Redis 命令 DEL      清空
#           └─ db.query(Article).update → MySQL: view_count 累加
#
#
# 【第三层: 服务启动时, 只跑一次】
#
#   uvicorn 启动
#     └─ lifespan()                     ← main.py
#           └─ start_background_tasks() ← tasks.py
#                 └─ Thread(...).start()  后台线程点着了, 开始睡觉
#
#
# 【⚠️ 四层名字别混】
#   本文件里的 count_view / add_hot   = 我写的 Python 函数 (Redis 不认识它们)
#   redis_client.xxx(...)             = redis 库的方法 (负责把命令发出去)
#   SET / HINCRBY / ZINCRBY           = Redis 服务器认识的命令
#   "hot:raw" / "article:views"       = Redis 里箱子的名字 (只是字符串)
#
#   完整说明见项目根目录: 《Redis 代码结构说明.md》
# ============================================================
