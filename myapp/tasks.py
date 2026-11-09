# ============================================================
# tasks.py —— 后台定时任务
# ============================================================
# 【为什么需要这个文件】
#   你的后端平时是"被动"的: 没人请求, 就什么都不发生。
#   但"把 Redis 里攒的阅读量倒回 MySQL"这件事, 不能等请求 ——
#   没人看文章的时候, 那些零头也得回数据库。
#   所以需要一个"主动"的东西: 在旁边一直跑、到点就干活的线程。
#
# 【它怎么工作】
#   死循环: 睡 300 秒 → 倒一次 → 睡 300 秒 → 倒一次 ...
#   它跟主线程【同时】跑, 互不干扰:
#       主线程    在门口接待 HTTP 请求
#       这个线程  在旁边睡觉, 到点醒来干活
#
# 【为什么不能放在请求里】
#   放请求里的话, 那个请求就得等 5 分钟才返回 —— 页面早卡死了。
# ============================================================
import threading
import time

from sqlalchemy import func

from cache import (redis_client, VIEWS_KEY, HOT_KEY, TITLE_KEY,
                   W_VIEW, W_LIKE, W_COMMENT)
from database import SessionLocal
from models import Article, ArticleLike, Comment

SYNC_INTERVAL = 300      # 秒。测试时可以临时改成 10


def sync_views_to_db() -> int:
    """把 Redis 里攒的阅读量零头, 一次性加回 MySQL。

    返回: 这次同步了几篇文章 (0 = 这五分钟没人看)
    """
    # ---------- ① 拿走 + 清空 ----------
    # 为什么要把两条命令"捆成一次"发出去?
    #   分开发的话, "读"和"删"中间有几毫秒的缝。
    #   这期间新来的 +1 会被你顺手一起删掉 → 阅读量凭空消失。
    #   pipeline 默认带事务(MULTI/EXEC), Redis 保证这两条之间插不进别人的命令。
    pipe = redis_client.pipeline()
    pipe.hgetall(VIEWS_KEY)        # 读出全部零头
    pipe.delete(VIEWS_KEY)         # 然后清空
    raw = pipe.execute()[0]        # [0] = 第一条命令(读)的结果

    if not raw:
        return 0                   # 这五分钟没人看, 连数据库都不用开

    # ---------- ② 累加回 MySQL ----------
    # ★ 必须是 "原来的值 + 增量", 不能写成 "= 增量"
    #   因为 Redis 里存的是【零头】, 不是总数。写成等于会把历史阅读量抹掉。
    # ★ 线程里没有 get_db 帮忙收尾, 所以自己开会话、自己关。
    db = SessionLocal()
    try:
        for aid, delta in raw.items():
            db.query(Article).filter(Article.id == int(aid)).update(
                {"view_count": Article.view_count + int(delta)}
            )
        db.commit()
        return len(raw)
    finally:
        db.close()


def rebuild_hot():
    """Redis 里的热度榜没了 → 从 MySQL 重新算一遍。

    什么时候会需要它?
      - redis-server 重启 (没开持久化的话, 内存里的数据全没)
      - 你手动把 hot:raw 删了
      - 第一次部署, 之前根本没有热度数据

    为什么能重建?
      因为热度分是【派生数据】:
          热度 = 阅读数×1 + 点赞数×3 + 评论数×5
      这三样东西全都在 MySQL 里躺着, 随时能重新算出来。

      ★ 能重算的数据, 才敢只放在内存里。
        (阅读量零头就不行 —— 那是原始数据, 丢了就真丢了,
         所以才要每 5 分钟倒回 MySQL)
    """
    # 已经有一份了, 就不用重建。
    # 注意: 空气箱在 Redis 里等于不存在, 所以 exists 对空的 ZSet 返回 0。
    if redis_client.exists(HOT_KEY):
        return

    db = SessionLocal()
    try:
        # ① 每篇文章的阅读数
        views = dict(db.query(Article.id, Article.view_count).all())

        # ② 每篇文章的点赞数 (GROUP BY 现算, 不存列 —— 老铁律)
        likes = dict(
            db.query(ArticleLike.article_id, func.count())
            .group_by(ArticleLike.article_id).all()
        )

        # ③ 每篇文章的评论数
        comments = dict(
            db.query(Comment.article_id, func.count())
            .group_by(Comment.article_id).all()
        )

        # ④ 三组 id 并起来。
        #    注意不能只用 views —— 有的文章阅读数可能还是 0(还没倒过库),
        #    但它有赞有评论, 也得参与排名。
        ids = set(views) | set(likes) | set(comments)

        # ⑤ 用【跟实时加分同一套】权重算分
        scores = {
            aid: views.get(aid, 0) * W_VIEW
               + likes.get(aid, 0) * W_LIKE
               + comments.get(aid, 0) * W_COMMENT
            for aid in ids
        }

        if scores:
            redis_client.zadd(HOT_KEY, scores)      # 一次性写进去
            print(f"[重建] 热榜重建完成, {len(scores)} 篇文章")
    finally:
        db.close()


def _sync_loop():
    """一直跑: 睡一会儿 → 倒一次"""
    while True:
        time.sleep(SYNC_INTERVAL)
        try:
            n = sync_views_to_db()
            if n:
                print(f"[倒库] {n} 篇文章的阅读量已写回 MySQL")
        except Exception as e:
            # ★ 必须 catch!
            #   不 catch 的话, 线程一旦遇到异常就直接死了, 而且不会有任何提示 ——
            #   你只会发现"阅读量怎么不涨了", 然后查半天。
            print("[倒库] 失败:", e)


def rebuild_title_index():
    """启动时从 MySQL 全量重建"文章标题索引"(Redis Hash)。

    ★ 只在启动时查一次库；之后的新增/改名/删除由接口自己维护。
    """
    import json
    from models import User

    db = SessionLocal()
    try:
        rows = (
            db.query(Article.id, Article.title, User.username)
            .join(User, User.id == Article.user_id)
            .filter(Article.is_public == True)   # ★ 私有文章不进搜索建议
            .all()
        )
        redis_client.delete(TITLE_KEY)
        # 逐条写（这个 redis-py 版本对 hset(mapping=...) 支持有问题）
        for aid, title, author in rows:
            redis_client.hset(TITLE_KEY, str(aid), json.dumps(
                {"id": aid, "title": title, "author": author},
                ensure_ascii=False,
            ))
        print(f"[标题索引] 重建 {len(rows)} 条")
    finally:
        db.close()


def start_background_tasks():
    """在 FastAPI 启动时调用一次: 先补热度榜, 再把后台线程点着"""
    # ★ 先重建 (Redis 刚重启时 hot:raw 是空的, 不补的话热榜会空着)
    #   外面包 try: 重建失败也不能让服务起不来 —— 最多热榜空一阵子。
    try:
        rebuild_hot()
    except Exception as e:
        print("[重建] 失败:", e)

    # 重建搜索建议的标题索引（只查一次库）
    try:
        rebuild_title_index()
    except Exception as e:
        print("[标题索引] 重建失败:", e)

    threading.Thread(target=_sync_loop, daemon=True).start()
    # daemon=True 的意思是: 主程序退出时, 这个线程跟着一起死。
    # 不加的话, 你按 Ctrl+C 会卡住 —— 主程序要等这个死循环结束才肯退出,
    # 而它是死循环, 永远不结束。


# ============================================================
# 附: 线程速查 (上面的代码看着陌生就回来瞄一眼)
# ============================================================
# 【一句话】
#   线程 = 在同一个程序里多开一条执行线, 两条同时跑。
#   主线程接请求, 这个线程睡觉/干活, 互不干扰。
#
# 【造线程】
#   threading.Thread(target=函数名, daemon=True).start()
#                      └── 注意【不加括号】!
#                          加括号 = 立刻执行
#                          不加   = 把函数交出去, 让别人决定何时调
#                          (跟 Depends(get_db) 完全同一个道理)
#
# 【start() 干嘛】
#   开一条新线程去跑那个函数, 然后【立刻返回】。
#   不会等你跑完 —— 要真等了, app 永远启动不了 (我们这函数是死循环)。
#
# 【time.sleep(n)】
#   只让【当前这条线程】暂停 n 秒, 主线程照常接请求。
#   而且不烧 CPU: 是真睡着, 操作系统的闹钟到点叫醒。
#
# 【daemon=True】
#   主程序退出时, 这条线程被直接杀掉。
#   不加的话, 主程序要等它结束 —— 而死循环永远不结束 → Ctrl+C 卡住。
#
# 【while True + sleep 就是"定时任务"】
#   没魔法, 就是"睡一会儿干一次"。缺点是【不准】:
#   如果干活花了 3 分钟, 下一轮就变成 8 分钟后了。
#   阅读量无所谓; "订单 15 分钟关单"那种就得换消息队列。
#
# 【为什么必须有 try/except】
#   线程死了没人通知你 —— 主线程报错满屏红字, 线程报错一声不吭。
#   没有 try, 数据库某次抽风这条线程就永久死掉,
#   你只会发现"阅读量怎么不涨了", 然后查半天。
#
# 【为什么用线程, 不用 asyncio】
#   倒库用的 redis-py 和 SQLAlchemy 都是【同步阻塞】的。
#   塞进 async 函数里会把整个事件循环卡住, 反而更糟。
#   线程在另一条线上阻塞, 不影响主线程。
#
# 【Python 线程的局限: GIL】
#   同一时刻只有一个线程在执行 Python 代码 →
#   多线程不能"多核并行算数学"(CPU 密集型没用)。
#   但 sleep / 等网络 / 等数据库时会释放 GIL →
#   我们这个线程 99.9% 时间在睡觉, 几乎不占 CPU, 非常合适。
# ============================================================
