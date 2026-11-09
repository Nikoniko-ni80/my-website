# ============================================================
# routers/articles.py —— 文章 + 评论接口
# ============================================================
# 从 main.py 搬过来的, 代码本身一个字没改, 只把 @app 换成了 @router
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from cache import (count_view, add_hot,
                   redis_client, HOT_KEY,
                   W_VIEW, W_LIKE, W_COMMENT,
                   remember_article_title, forget_article_title, suggest_articles)
from database import get_db
from models import User, Article, Comment, CommentLike, ArticleLike
from schemas import ArticleIn, CommentIn, CATEGORIES
from dependencies import get_current_user, get_current_user_optional
from routers.tags import set_article_tags, tags_of_articles
from routers.notifications import notify, notify_like
from routers.orders import has_purchased, make_preview

router = APIRouter()


# ============================================================
# 文章功能 (业务资源)
#   - 增/改/删/我的文章 → 要登录
#   - 看公开文章 → 不用登录
# ============================================================

# ---------- 发布文章 POST /articles (需登录) ----------
@router.post("/articles")
def create_article(
    article: ArticleIn,
    current_user: User = Depends(get_current_user),   # 需登录: 验 token 拿到当前用户
    db: Session = Depends(get_db),
):
    # ★ 分类要校验: 前端传的东西不可信 (万一传了个 "abc" 进去, 它哪个 tab 都不属于)
    if article.category and article.category not in CATEGORIES:
        return {"error": "分类不合法"}

    # ★ 付费: 设了付费但价格 <= 0, 按免费处理 (不然会变成"标着付费但不要钱")
    is_paid = bool(article.is_paid and article.price > 0)
    price = article.price if is_paid else 0

    new_article = Article(
        title=article.title,
        content=article.content,
        user_id=current_user["id"],    # ★关键①: 作者自动填"当前登录用户", 不从前端来!
        is_public=article.is_public,   # 公开/私有
        category=article.category,     # 分类 (可能是 "")
        is_paid=is_paid,
        price=price,
        cover=article.cover[:200],
    )
    db.add(new_article)
    db.commit()
    db.refresh(new_article)            # 从数据库刷新, 拿到自动生成的 id

    # ★ 处理标签: 查已有的复用 / 没有的自动创建 / 在中间表建关联
    #   (放在文章入库之后 —— 因为中间表需要 article_id)
    set_article_tags(db, new_article.id, article.tags)
    db.commit()

    # 标题索引进 Redis（搜索建议用，不查库）
    # ★ 只有公开文章才进；私有文章不该被别人搜到
    if new_article.is_public:
        remember_article_title(new_article.id, new_article.title, current_user["username"])

    return {"message": "发布成功", "id": new_article.id, "title": new_article.title}


# ---------- 我的文章 GET /my/articles (需登录) ----------
@router.get("/my/articles")
def list_my_articles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # ★关键②: 加 user_id 过滤 → 只返回"我自己的"(含私有)
    rows = db.query(Article).filter(Article.user_id == current_user["id"]).all()

    # ★ 一次算出这批文章各自的点赞量 (IN + GROUP BY) —— 跟首页那段一样
    art_ids = [a.id for a in rows]
    like_map = {}
    if art_ids:
        like_map = {
            aid: n for aid, n in
            db.query(ArticleLike.article_id, func.count())
            .filter(ArticleLike.article_id.in_(art_ids))
            .group_by(ArticleLike.article_id)
            .all()
        }

    return [
        {"id": a.id, "title": a.title, "content": a.content,
         "user_id": a.user_id, "is_public": a.is_public,
         "category": a.category, "cover": a.cover,
         "like_count": like_map.get(a.id, 0)}
        for a in rows
    ]


# ---------- 看自己的某篇文章 GET /my/articles/{id} (需登录, 含私有) ----------
@router.get("/my/articles/{article_id}")
def get_my_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 只能看"自己的" (加 user_id 过滤)
    row = db.query(Article).filter(
        Article.id == article_id, Article.user_id == current_user["id"]
    ).first()
    if row is None:
        return {"error": "文章不存在或不是你的"}

    # 右侧作者卡片要头像/简介 —— current_user 是缓存过的精简版(只有id+username),
    # 所以这里自己再查一次完整的 User
    u = db.query(User).filter(User.id == current_user["id"]).first()
    return {"id": row.id, "title": row.title, "content": row.content,
            "user_id": row.user_id, "is_public": row.is_public,
            "category": row.category,
            "cover": row.cover,
            # ★ 付费设置: 编辑时要回填到表单里
            "is_paid": row.is_paid, "price": row.price,
            "author": current_user["username"],
            "author_avatar": u.avatar if u else "",
            "author_bio":    u.bio if u else "",
            "created_at":    str(row.created_at) if row.created_at else "",
            # ★ 点赞量 + 我赞过没 (跟 get_article 保持一致)
            "like_count": db.query(ArticleLike).filter(
                ArticleLike.article_id == article_id
            ).count(),
            "liked_by_me": _has_liked(current_user, article_id, db),
            # ★ 标签: [{"id": 1, "name": "Redis"}, ...]
            "tags": tags_of_articles(db, [article_id]).get(article_id, [])}


# ---------- 改自己的文章 PUT /articles/{id} (需登录) ----------
@router.put("/articles/{article_id}")
def update_article(
    article_id: int,
    article: ArticleIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # ★关键②: 查的时候加 user_id 过滤 → 只能改自己的
    row = db.query(Article).filter(
        Article.id == article_id, Article.user_id == current_user["id"]
    ).first()
    if row is None:
        return {"error": "文章不存在或不是你的"}

    # 分类要校验 (跟 create_article 一样: 前端传的东西不可信)
    if article.category and article.category not in CATEGORIES:
        return {"error": "分类不合法"}

    row.title = article.title
    row.content = article.content
    row.is_public = article.is_public
    row.category = article.category
    # ★ 付费设置同理: 标了付费但价格 <= 0 → 按免费
    row.is_paid = bool(article.is_paid and article.price > 0)
    row.price = article.price if row.is_paid else 0
    row.cover = article.cover[:200]
    db.commit()

    # ★ 标签也整体替换掉 (先删旧关联, 再按新的一批重建)
    set_article_tags(db, article_id, article.tags)
    db.commit()

    # 标题/公开状态可能改了 → 同步 Redis 索引
    if row.is_public:
        remember_article_title(article_id, row.title, current_user["username"])
    else:
        forget_article_title(article_id)   # 改成私有 → 从建议里移除

    return {"message": "修改成功"}


# ---------- 删自己的文章 DELETE /articles/{id} (需登录) ----------
@router.delete("/articles/{article_id}")
def delete_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(Article).filter(
        Article.id == article_id, Article.user_id == current_user["id"]
    ).first()
    if row is None:
        return {"error": "文章不存在或不是你的"}

    # ★ 第 0 步之后这里变干净了: 只删文章, 什么都不用手动清
    #   因为 comments / favorites / histories 的外键都改成了 ON DELETE CASCADE
    #   —— 数据库自己会把挂在它下面的评论/收藏/浏览记录一起删掉
    #
    #   改之前是这样(三行手动删, 而且每加一张挂文章的表就要回来再加一行):
    #     db.query(Comment).filter(Comment.article_id == article_id).delete()
    #     db.query(Favorite).filter(Favorite.article_id == article_id).delete()
    #     db.query(History).filter(History.article_id == article_id).delete()
    db.delete(row)
    db.commit()

    # 从标题索引里删掉
    forget_article_title(article_id)

    return {"message": "删除成功"}


# ---------- 搜索建议 GET /suggest (不用登录, 只读 Redis) ----------
# 输入框边输边调用；不查 MySQL，真正搜索才走 /articles
@router.get("/suggest")
def suggest(keyword: str = "", limit: int = 6):
    return {"items": suggest_articles(keyword, max(1, min(limit, 10)))}


# ---------- 公开文章列表 GET /articles (不用登录, 带分页 + 搜索) ----------
# 【查询参数】比路径参数多一种来源 —— 从网址【问号后面】来:
#     GET /articles?page=2&size=9&keyword=Python
#                   ↑ 这几个就是查询参数
#   写在函数参数里就行, FastAPI 会自动去问号后面找。
#   (路径参数是在路径里占位的, 比如 /articles/{article_id}; 查询参数是可选筛选)
@router.get("/articles")#/articles?page=2&size=8&keyword=Python
def list_articles(
    page: int = 1,              # 第几页 (从 1 开始)
    size: int = 9,              # 每页几篇
    keyword: str = "",          # 搜索词 (空的 = 不筛)
    category: str = "",         # ★ 分类 (空的 = 全部, 对应首页那个"全部"tab)
    db: Session = Depends(get_db),
):
    # ① 先把"要查什么"攒成一个查询 (还没真的去数据库)
    #    JOIN users 表, 顺便拿到作者名字 (Article.user_id == User.id)
    q = (
        db.query(Article, User.username)
        .join(User, Article.user_id == User.id)
        .filter(Article.is_public == True)#只要公开的
    )

    # ② 有搜索词才加这个条件 (没有就查全部)
    #    contains = SQL 的 LIKE '%关键词%'
    if keyword.strip(): #strip是去空格方法
        q = q.filter(Article.title.contains(keyword.strip()))

    # ②b ★ 有分类才筛分类 (没传 = 全部, 对应首页那个"全部"tab)
    if category.strip():
        q = q.filter(Article.category == category.strip())

    # ③ 先数【一共】几条
    #    ★ 必须在 offset/limit 之前数! 不然数出来的是"这一页有几条"
    total = q.count()

    # ④ 再只取【这一页】
    #    offset(9) = 跳过前 9 条    limit(9) = 最多拿 9 条
    #    page=1 → 跳过 0 条      page=2 → 跳过 9 条
    rows = (
        q.order_by(Article.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
        )#前端需要哪个page我就返回哪个

    # ⑤ ★ 一次算出【这一页这 9 篇】各自的点赞量 (IN + GROUP BY)
    #   跟评论列表那套一模一样: 攒名单 → 一条 SQL → 转字典
    #   ⚠️ 别写成"循环 9 次, 每篇查一次" —— 那就是 N+1
    art_ids = [a.id for a, _ in rows]
    like_map = {}
    if art_ids:
        like_map = {
            aid: n for aid, n in
            db.query(ArticleLike.article_id, func.count())
            .filter(ArticleLike.article_id.in_(art_ids))     # ← 一条 IN
            .group_by(ArticleLike.article_id)
            .all()
        }
        # ⚠️ 一篇赞都没有的文章不会出现在结果里 → 下面用 .get(id, 0) 补 0

    # ⑤ ★ 同一页文章的标签, 也是一条 IN 查完再分组 (别 N+1)
    tag_map = tags_of_articles(db, art_ids)

    return {
        "items": [
            {"id": a.id, "title": a.title,
             # ★ 付费文章在列表里只给开头 —— 这一层没有登录信息, 也不该给全文
             #   (真要看全文, 去详情页, 那里才判断"买没买")
             "content": make_preview(a.content) if a.is_paid else a.content,
             "user_id": a.user_id, "author": username,
             "category": a.category,                  # ★ 分类 (空字符串 = 未分类)
             "is_paid": a.is_paid,                    # ★ 是不是付费
             "price": a.price,                        # ★ 价格 (分)
             "cover": a.cover,                        # ★ 封面 (空 = 渐变)
             "like_count": like_map.get(a.id, 0),     # ★ 现算的, 补 0
             "tags": tag_map.get(a.id, [])}           # ★ 标签
            for a, username in rows
        ],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size,   # 一共几页
        #   ↑ 向上取整的小技巧: 12 篇 / 每页 9 → (12+8)//9 = 2 页
        #     直接写 12//9 会得到 1 (整数除法向下取整), 所以先加 size-1
    }


# ============================================================
# 热榜 GET /articles/hot
# ============================================================
# ⚠️⚠️ 这个接口【必须】写在 /articles/{article_id} 的【前面】!
#
#   FastAPI 是按【声明顺序】匹配路由的。如果写在后面,
#   请求 /articles/hot 会先撞上 /articles/{article_id} 那条,
#   它把 "hot" 当成 article_id 去转 int → 直接 422。
#   这个 bug 特别隐蔽: 代码看着全对, 就是报 422。
#
# 【为什么不能直接 ZREVRANGE 取前 10】
#   ZSET 里存的是【原始分】, 没算时间衰减 —— 老文章会永远霸榜。
#   所以流程是: 取一批候选 → 现算衰减 → 重排 → 取前 limit。
# ============================================================
@router.get("/articles/hot")
def hot_articles(
    limit: int = 10,
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 50))        # 防着前端传 99999

    # ---------- ① 从 Redis 拿【原始分】前 50 ----------
    raw = redis_client.zrevrange(HOT_KEY, 0, 49, withscores=True)
    #     z->zset类型  rev->反序  range->取一段  
    #     → [ ("11", 50.0), ("20", 34.0), ... ]
    raw_map = {int(aid): float(score) for aid, score in raw}
    #           ↑ 成员是字符串, 转成 int
    #把 Redis 返回的列表，转成方便按 id 查分数的字典。

    # ---------- ② 补上"最近 24 小时发布的新文章" ----------
    # 为什么? 新文章原始分低, 排不进前 50 → 永远没机会上榜。
    #        这跟"时间衰减要给新文章机会"的初衷矛盾, 所以单独留座位。
    since = datetime.now() - timedelta(hours=24)
    recent_ids = [
        rid for (rid,) in db.query(Article.id).filter(
            Article.is_public == True,
            Article.created_at >= since,
        ).all()
    ]

    # ★ 这些新文章如果不在前 50 里, raw_map 里是没有它们的分数的。
    #   必须回 Redis 单独补查 —— 不能默认 0,
    #   否则"有点热度但没进前 50"的文章会被当成 0 分, 补了等于没补。
    if recent_ids:
        pipe = redis_client.pipeline()
        for aid in recent_ids:
            pipe.zscore(HOT_KEY, aid) 
            ##zscore->查单个    把查询多篇文章的命令合在一起
        for aid, s in zip(recent_ids, pipe.execute()):
        ##拿着这批新文章的 id，去 HOT_KEY 这个 ZSET 里挨个查分数
            if s is not None:
                raw_map[aid] = float(s)

    ids = list(raw_map.keys())
    if not ids:
        return {"items": []}              # 冷启动, 榜还没建

    # ---------- ③ 一次把候选的详情查出来 ----------
    rows = (
        db.query(Article, User.username)
        .join(User, Article.user_id == User.id)
        .filter(Article.id.in_(ids), Article.is_public == True)
        .all()
    )

    # 点赞量: 还是 IN + GROUP BY 那一套, 别写成 N+1
    likes = {
        aid: n for aid, n in #aid就是文章名
        db.query(ArticleLike.article_id, func.count())
        .filter(ArticleLike.article_id.in_(ids))
        .group_by(ArticleLike.article_id).all()
    }

    # ---------- ④ 现算衰减分 ----------
    #     展示分 = 原始分 / (发布后几小时 + 2) ^ 1.5
    #     "+2" 防止刚发布的文章除以 0
    #     "1.5" 来自 Reddit / Hacker News 的公开公式
    now = datetime.now()
    ranked = []
    for a, name in rows:##rows是319的文章表+作者名
        created = a.created_at or now
        hours = max((now - created).total_seconds() / 3600, 0)
        shown = raw_map.get(a.id, 0) / ((hours + 2) ** 1.5)
        ranked.append((shown, a, name))

    # ---------- ⑤ 重排, 取前 limit ----------
    ranked.sort(key=lambda x: -x[0])      # 降序 (Python 没有直接倒序的 sort)

    return {"items": [
        {"id": a.id, "title": a.title,
         "content": make_preview(a.content) if a.is_paid else a.content,
         "user_id": a.user_id, "author": name,
         "category": a.category,
         "is_paid": a.is_paid, "price": a.price, "cover": a.cover,
         "like_count": likes.get(a.id, 0),
         # ① 显示用: 原始热度分 (用户看得懂 —— "这篇被互动了 50 次")
         "heat": int(raw_map.get(a.id, 0)),
         # ② 排序用: 衰减后的分。很小是正常的 ——
         #    你的文章都发了三四周, 50 / 15000 ≈ 0.003。
         #    它只负责"谁排前面", 不适合直接显示。
         "rank_score": round(shown, 4)}
        for shown, a, name in ranked[:limit]
    ]}


# ---------- 小工具: 判断"我赞过这篇文章没" ----------
# 抽成函数是因为有两个接口要用 (看公开文章 / 看自己的文章)。
# 名字前面加下划线 _ 是约定: "这是本文件内部用的小工具, 外面别调"。
def _has_liked(current_user, article_id: int, db) -> bool:
    if current_user is None:
        return False                      # 没登录 → 当然没赞过
    return db.query(ArticleLike).filter(
        ArticleLike.user_id == current_user["id"],
        ArticleLike.article_id == article_id,
    ).first() is not None


# ---------- 看某篇公开文章 GET /articles/{id} (不用登录) ----------
@router.get("/articles/{article_id}")
def get_article(
    article_id: int,
    request: Request,      # ★ 多要一个 request, 是为了拿【访客 IP】(没登录时用它去重)
    # ★ 可选登录: 没登录也能看文章, 登录了才知道"我赞过没"
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    # 只找"公开的"; 作者看自己的(含私有)走 /my/articles
    # ★ 查整个 User 对象(不是只查 User.username) —— 右侧作者卡片要头像和简介
    row = (
        db.query(Article, User)
        .join(User, Article.user_id == User.id)
        .filter(Article.id == article_id, Article.is_public == True)
        .first()
    )
    if row is None:
        return {"error": "文章不存在或未公开"}
    a, u = row

    # ------------------------------------------------------------
    # ★ 记一次阅读 (第 9 步: 阅读量 + 热度榜)
    # ------------------------------------------------------------
    # 【为什么放在这个位置】
    #   上面那句 if row is None 已经 return 走了。能执行到这儿, 说明
    #   "这篇文章真的存在、真的是公开的" —— 不会给不存在的 id 刷量。
    #
    # 【为什么写在 GET 里】GET 按道理是"只读"的, 这里偷偷写了数据, 确实别扭。
    #   但另一个候选位置 POST /history/{id} 要登录才调得到, 未登录的阅读
    #   就全丢了(演示时你自己多半是没登录的状态)。两害相权取这个。
    #   ★ 真实项目里也确实这么干, 叫"埋点写在读接口里"。
    #
    # 【viewer 是干嘛的】只是个去重标记, 不落库:
    #     登录了 → "u3"    (同一个账号一小时内只算一次)
    #     没登录 → "ip127.0.0.1"
    viewer = f"u{current_user['id']}" if current_user else f"ip{request.client.host}"
    ##如果前端没有返回对象就用ip
    count_view(article_id, viewer)

    # ↑ 阅读量 +1 (记账用)
    # ↓ 同时给热度 +1 (排名用) —— 这是【两件不同的事】:
    #     阅读量回答"这篇被看了几次", 热度回答"这篇热不热"
    #   阅读是最廉价的互动, 所以权重最低 (W_VIEW = 1)
    add_hot(article_id, W_VIEW)

    # ------------------------------------------------------------
    # ★ 付费文章: 没买只能看开头
    # ------------------------------------------------------------
    # 【为什么截断必须在这里做】
    #   如果把全文发给前端、再用 CSS 盖一层遮罩 —— 右键"查看网页源代码"
    #   就能拿到全文。付费内容一个字都不能发给没买的人。
    me = current_user["id"] if current_user else None
    is_author = me is not None and a.user_id == me
    purchased = has_purchased(db, me, a.id)
    locked = bool(a.is_paid and a.price > 0 and not is_author and not purchased)

    return {"id": a.id, "title": a.title,
            "content": make_preview(a.content) if locked else a.content,
            "user_id": a.user_id, "author": u.username,
            "category": a.category,
            # ★ 付费相关
            "is_paid": a.is_paid,
            "price": a.price,
            "cover": a.cover,
            "locked": locked,            # 前端看到 True → 显示"购买解锁"
            "purchased": purchased,      # 我买过没
            "is_author": is_author,      # 是不是我自己的文章
            # ★ 右侧作者卡片用 (只给这几样, 不给 password_hash/is_admin)
            "author_avatar": u.avatar,
            "author_bio":    u.bio,
            "created_at":    str(a.created_at) if a.created_at else "",
            # ★ 点赞量: 现算, 不存列
            "like_count": db.query(ArticleLike).filter(
                ArticleLike.article_id == article_id
            ).count(),
            # ★ 我赞过没 (没登录就是 False)
            "liked_by_me": _has_liked(current_user, article_id, db),
            # ★ 标签
            "tags": tags_of_articles(db, [article_id]).get(article_id, [])}


# ============================================================
# 评论功能
#   - 看评论 → 不用登录
#   - 发评论 → 要登录
# ============================================================

# ---------- 发评论 POST /articles/{id}/comments (需登录) ----------
# 【这 4 个参数我都不填, 但来源分两种】
#
#   一种是"拿来就有"的:
#       article_id  ←  网址 /articles/7/comments 里那段, 摘下来就是 7
#       comment     ←  请求体里那坨 JSON, 拿来就是
#     这俩 FastAPI 看一眼类型注解就知道去哪儿摘, 不用费劲。
#
#   另一种是"得跑一趟才有的":
#       current_user  ←  得先验 token、解出 user_id、查缓存查库, 才知道我是谁
#       db            ←  得先开会话、连上 MySQL, 才有这东西
#     既然要跑一趟, 就得告诉框架"跑哪段代码" → 所以写 Depends(那段代码的名字)
#
# ★【为啥非得"报上去"让框架跑, 我自己调不行吗?】
#   get_db 不是普通函数, 他有自己的生态结构:
#       造一个会话 → yield 交出来 → 我拿去用 → 用完他关掉
#   我自己调的话, 三处都卡住:
#     ① 我连会话都拿不到 —— get_db() 给我的是个"停在中间的生成器", 不是会话
#     ② 就算我手动 next() 把他推完, "关闭"这步得发生在【我用完之后】,
#        可我一个函数 return 出去就"死"了, 没有"之后"了 —— 我关不了
#     ③ 我这函数还有三条出口 (文章不存在 / 未公开 / 评论成功),
#        每条出口前都得记得关一次, 漏一个就漏一个连接 —— 迟早会忘
#   (get_db 里的 finally 就是治这个的: 不管从哪条路出去, 他都会关)
#   所以: "用"归我, "造"和"关"归 get_db, 框架负责在合适的时候按下开始和结束。
#
# ★【唯一要记住的细节】Depends(get_db) 里的 get_db 没加括号 = 我没调他,
#   只是把名字报上去。写成 get_db() 就变成"立刻跑完, 结果给你",
#   那框架就没法管开头和收尾了。
@router.post("/articles/{article_id}/comments")
def create_comment(
    article_id: int,                                  # 拿来就有 (网址里摘的)
    comment: CommentIn,                               # 拿来就有 (请求体里拿的)
    current_user: User = Depends(get_current_user),   # 报名字 → 框架跑一趟给我
    db: Session = Depends(get_db),                    # 报名字 → 框架跑一趟给我
):
    # 先确认这篇文章存在
    art = db.query(Article).filter(Article.id == article_id).first()
    if art is None:
        return {"error": "文章不存在"}
    # 私有的文章: 只有作者能评论 (别人的私有文章评论不了)
    if not art.is_public and art.user_id != current_user["id"]:
        return {"error": "文章未公开, 无法评论"}

    # ★ 楼中楼的三个字段, 默认都是空 (= 这是一条顶层评论)
    root_id = None
    parent_id = None
    reply_to_user_id = None

    # ---------- 如果这是在【回复某条评论】, 后端把拍平规则算好 ----------
    # ⚠️ 前端只传"我要回复哪一条"(reply_to_comment_id), 剩下的全由后端推。
    #    因为"拍平"是【后端的内部设计】, 不该漏给前端去理解。
    if comment.reply_to_comment_id is not None:
        target = db.query(Comment).filter(
            Comment.id == comment.reply_to_comment_id,
            Comment.article_id == article_id,  # ★ 必须属于【同一篇文章】!
        ).first()
        # ↑ 为什么必须限定文章? 不然有人可以拿 A 文章的评论 id,
        #   发到 B 文章的接口上, 造出一条"跨文章的回复" —— 数据就乱了。
        if target is None:
            return {"error": "要回复的评论不存在"}

        parent_id = target.id                  # 我直接回复的那条
        # ★★★ 拍平的核心就这一行:
        #     被回复的【是根】   → root_id 就是它自己
        #     被回复的【是回复】 → 沿用它的 root_id (还是那个根)
        #   所以不管回复谁, root_id 永远指向【顶层】, 谁也不指向上一条回复。
        root_id = target.root_id or target.id
        reply_to_user_id = target.user_id      # 被回复的人

    new_comment = Comment(
        content=comment.content,
        user_id=current_user["id"],   # ★ 评论人自动填"当前登录用户" (不是前端传的)
        article_id=article_id,        # 评的哪篇
        root_id=root_id,              # 顶层为 None; 回复则指向根
        parent_id=parent_id,
        reply_to_user_id=reply_to_user_id,
    )
    db.add(new_comment)

    # ---------- 通知 ----------
    # 回复 → 通知"被回复的人"; 顶层评论 → 通知"文章作者"
    if comment.reply_to_comment_id is not None and reply_to_user_id:
        notify(
            db,
            to_user=reply_to_user_id,
            type="reply",
            content=f"{current_user['username']} 回复了你的评论",
            link=f"/article/{article_id}",
            from_user=current_user["id"],
        )
    else:
        notify(
            db,
            to_user=art.user_id,
            type="comment",
            content=f"{current_user['username']} 评论了你的文章《{art.title}》",
            link=f"/article/{article_id}",
            from_user=current_user["id"],
        )

    # 评论 + 通知, 一次提交
    db.commit()
    db.refresh(new_comment)

    # ★ 评论 +5 热度。放在 commit【之后】—— 确认真的存进库了才算数。
    #   放前面的话, 万一 commit 失败, 热度就白涨了。
    add_hot(article_id, W_COMMENT)

    return {"message": "评论成功", "id": new_comment.id, "root_id": new_comment.root_id}


# ---------- 看某篇的评论 GET /articles/{id}/comments (不用登录) ----------
#注意，评论是单独于文章的信息
#就相当于用户每次点击一个文章块，前端就发出两个网络请求，一个文章，一个评论
# 然后两个请求的返回内容分别显示在正文和评论区
@router.get("/articles/{article_id}/comments")
def list_comments(
    article_id: int,
    sort: str = "time",        # time = 按时间(默认) / hot = 按点赞量
    # ★ 注意这个依赖: 是"可选登录"版 —— 没登录返回 None, 【不报 401】
    #   因为看评论是公开的, 但不能登录的话就不知道"我能不能删"
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    me = current_user["id"] if current_user else None

    # 文章作者是谁 —— 算 can_delete 要用 (文章作者能删任何评论)
    art = db.query(Article).filter(Article.id == article_id).first()
    if art is None:
        return {"error": "文章不存在"}
    article_author = art.user_id

    # ========== ① 顶层评论 ==========
    q = db.query(Comment).filter(
        Comment.article_id == article_id,
        Comment.root_id == None,        # 空的 = 它自己就是根
    )

    if sort == "hot":
        # 按点赞量排。
        # ⚠️ 必须 outerjoin 【左连接】, 不能用 join!
        #    用 join 的话, 一条赞都没被点过的评论会【整个消失】。
        #    (跟 /my/following 那个"没发过文章的人会被丢掉"是同一个坑)
        q = (
            q.outerjoin(CommentLike, CommentLike.comment_id == Comment.id)
            .group_by(Comment.id)
            .order_by(func.count(CommentLike.id).desc(),   # 赞多的在前
                      Comment.created_at.desc())           # 赞数一样时, 新的在前
        )
    else:
        q = q.order_by(Comment.created_at.desc())          # 新的在前

    tops = q.limit(50).all()        # 顶层评论先卡个上限 (还没做分页)
    top_ids = [c.id for c in tops] ##现在先把这50个顶层评论id抽出来

    # ========== ② 【一次】捞出所有回复 (IN, 不是循环) ==========
    reps = []
    if top_ids:
        reps = (
            db.query(Comment)
            .filter(Comment.root_id.in_(top_ids))     # ★ 一条 SQL 搞定全部
            # ★ 回复按时间【正序】—— 对话要顺着读, 倒着读不通
            #   (跟顶层评论的倒序【方向相反】, 是有意的)
            .order_by(Comment.created_at.asc())
            .all()
        )

    # ========== ③ 【一次】算出所有评论的点赞量 (IN + GROUP BY) ==========
    # 根和回复都算自己的, 没有"汇聚到根"这回事
    all_ids = top_ids + [r.id for r in reps] #这里的+不是加而是列表拼接，
    #会得到一个超级大的列表，前50个是根id，后面全是回复id
    like_map = {}
    if all_ids:
        rows = (
            db.query(CommentLike.comment_id, func.count())
            .filter(CommentLike.comment_id.in_(all_ids))
            .group_by(CommentLike.comment_id)
            .all()
        )
        like_map = {cid: n for cid, n in rows}
    # ⚠️ 没被赞过的评论不会出现在 like_map 里 —— 所以下面要用 .get(id, 0) 补 0

    # ========== ③b 【一次】查出"我赞过哪些" (决定按钮显示"赞"还是"已赞") ==========
    liked_by_me = set()
    if me is not None and all_ids:
        liked_by_me = {
            cid for (cid,) in db.query(CommentLike.comment_id).filter(
                CommentLike.comment_id.in_(all_ids),
                CommentLike.user_id == me,
            ).all()
        }

    # ========== ④ 【一次】查出所有相关用户的名字 ==========
    # 要查两种人: ① 评论作者  ② 被回复的人
    uids = {c.user_id for c in tops} | {r.user_id for r in reps}
    uids |= {r.reply_to_user_id for r in reps if r.reply_to_user_id}
    #加一句避免有些被回复评论已经被删了
    names = {}
    if uids:
        names = {u.id: u.username
                 for u in db.query(User).filter(User.id.in_(uids)).all()}

    # ========== ⑤ 拼装 ==========
    def can_delete(c):
        """我能不能删这条评论。
        ★ 规则【只在后端这一处】—— 前端只读 can_delete, 不自己算。
          两个条件取【或】: 我是这条评论的作者, 或者我是这篇文章的作者。
          ⚠️ 写成 `cmt.user_id != me and article_author != me` 才对 ——
             那是"两个都不是我"才拒绝。写成 or 就变成"两个都得是我"了。
        """
        if me is None:
            return False                   # 没登录, 一律不能删
        return c.user_id == me or article_author == me

    def pack(c):
        """把一个 Comment 对象变成前端要的 dict"""
        return {
            "id":         c.id,
            "content":    c.content,
            "user_id":    c.user_id,
            "author":     names.get(c.user_id, "?"),##后面的值是娶不到是给啥
            "created_at": str(c.created_at) if c.created_at else "",
            "like_count": like_map.get(c.id, 0),      # ★ 现算的, 补 0
            "liked_by_me": c.id in liked_by_me,       # ★ 我赞过没 (给按钮显状态)
            "can_delete": can_delete(c),              # ★ 后端算好的
        }

    # 把回复按 root_id 分组
    grouped = defaultdict(list)#特殊字典
    for r in reps:
        grouped[r.root_id].append(r) #这句话的意思是从grouped当中取出r.root_id对象并将r加入
        ##就相当于现在变成{9010:[],  9011:[],  9012:[]

    # 拼成嵌套: 回复装在它那条顶层评论的 replies 里
    return [
        {
            **pack(t),
            # ⚠️ .get(t.id, []) 那个默认值 [] 不能省 ——
            #    没有回复的顶层评论, 得给它一个【空数组】,
            #    不然前端 c.replies.length 会报错
            "replies": [
                {
                    **pack(r),
                    "reply_to_user_id": r.reply_to_user_id,
                    "reply_to_name": names.get(r.reply_to_user_id, "") if r.reply_to_user_id else "",
                }
                for r in grouped.get(t.id, [])
            ],
        }
        for t in tops
    ]


# ---------- 删评论 DELETE /comments/{id} (需登录) ----------
# ★ 注意路径是 /comments/{id}, 不是 /articles/xxx —— 删评论不需要知道文章
@router.delete("/comments/{comment_id}")
def delete_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cmt = db.query(Comment).filter(Comment.id == comment_id).first()
    if cmt is None:
        return {"error": "评论不存在"}

    art = db.query(Article).filter(Article.id == cmt.article_id).first()
    if art is None:
        return {"error": "文章不存在"}

    me = current_user["id"]

    # ★★ 权限: 两个条件取【或】
    #     ① 我是这条评论的作者
    #     ② 我是这篇文章的作者
    #   ⚠️ 写成 `cmt.user_id != me and art.user_id != me` ——
    #      意思是"两个都不是我", 那才拒绝。别写成 or (会变成"两个都得是我")
    #
    #   ★ 这道检查【必须】有, 哪怕前端已经藏了删除按钮。
    #     因为攻击者不打开你的网页, 直接 curl 打这个接口。
    if cmt.user_id != me and art.user_id != me:
        return {"error": "没有权限删这条评论"}

    # ★ 就这一行。剩下两件事数据库全包了:
    #   ① 删的是【顶层评论】 → root_id 的 CASCADE 会把整棵树带走
    #      (为什么一条 CASCADE 就够, 不用递归? 因为拍平 ——
    #       所有回复的 root_id 都直接指向顶层, 谁也不指向上一条回复)
    #   ② 删的是【一条回复】 → 别人 parent_id 指向它的, 由 SET NULL 置空;
    #      而别人的内容、别人的 root_id 一根毫毛都不动
    # ★ 删之前先数一下要消失几条评论:
    #   删【根评论】会级联带走它下面所有回复, 那些也是评论, 分也得扣。
    #   只扣 5 分的话, 有人发一堆评论再一删, 分数就永久虚高了。
    n_deleted = 1 + db.query(Comment).filter(Comment.root_id == cmt.id).count()

    db.delete(cmt)
    db.commit()

    # ★ 扣掉这些评论的热度。不管是谁删的 —— 作者删别人的评论, 一样要扣,
    #   因为那些评论确实从站上消失了。
    add_hot(art.id, -W_COMMENT * n_deleted)

    return {"message": "删除成功"}


# ============================================================
# 评论点赞
# ============================================================
# ★ 跟文章点赞结构一模一样 (article_likes / comment_likes 两张表)
# ★ 点赞量【不存列】, 永远 COUNT(*) 现算 —— 列表接口里那句 IN + GROUP BY

# ---------- 点赞 POST /comments/{id}/like (需登录) ----------
@router.post("/comments/{comment_id}/like")
def like_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    cmt = db.query(Comment).filter(Comment.id == comment_id).first()
    if cmt is None:
        return {"error": "评论不存在"}

    me = current_user["id"]

    # ★ 已经赞过了吗? (防手抖双击 / 多标签页)
    #   不查的话, 第二条 INSERT 会撞唯一约束 (user_id, comment_id) → 报难看的 500
    exists = db.query(CommentLike).filter(
        CommentLike.user_id == me,
        CommentLike.comment_id == comment_id,
    ).first()
    if exists:
        return {"message": "已经赞过了"}      # 当成功, 不报错

    db.add(CommentLike(user_id=me, comment_id=comment_id))
    db.commit()
    return {"message": "点赞成功"}


# ---------- 取消点赞 DELETE /comments/{id}/like (需登录) ----------
@router.delete("/comments/{comment_id}/like")
def unlike_comment(
    comment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # ★ 跟取消关注一样: 不用检查评论存不存在 —— 删 0 行无害
    n = db.query(CommentLike).filter(
        CommentLike.user_id == current_user["id"],
        CommentLike.comment_id == comment_id,
    ).delete()
    db.commit()
    return {"message": "已取消点赞" if n else "本来就没赞"}


# ============================================================
# 文章点赞
# ============================================================
# ★ 跟评论点赞【完全一个模子】, 只是换成了 article_likes / article_id
#   ——这就是"两张表分开"带来的好处: 逻辑能复用, 而不是写一套 if 判断类型

# ---------- 给文章点赞 POST /articles/{id}/like (需登录) ----------
@router.post("/articles/{article_id}/like")
def like_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    art = db.query(Article).filter(Article.id == article_id).first()
    if art is None:
        return {"error": "文章不存在"}
    # 别人的私密文章, 点不了赞 (跟"评论不了"一样的规矩)
    if not art.is_public and art.user_id != current_user["id"]:
        return {"error": "文章未公开, 无法点赞"}

    me = current_user["id"]

    # ★ 已经赞过了吗? 防手抖双击 / 多标签页 / curl
    exists = db.query(ArticleLike).filter(
        ArticleLike.user_id == me,
        ArticleLike.article_id == article_id,
    ).first()
    if exists:
        return {"message": "已经赞过了"}      # 当成功, 不报错

    db.add(ArticleLike(user_id=me, article_id=article_id))

    # ★ 通知作者（自己赞自己不通知；同一个人同一篇只发一次，防止反复赞刷通知）
    notify_like(db, art, current_user)

    db.commit()

    # ★ 点赞 +3 热度。注意放在了"已经赞过"那个 return 的【后面】——
    #   重复点赞走不到这里, 所以不会重复加分。
    add_hot(article_id, W_LIKE)

    return {"message": "点赞成功"}


# ---------- 取消文章点赞 DELETE /articles/{id}/like (需登录) ----------
@router.delete("/articles/{article_id}/like")
def unlike_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # ★ 还是那句: 取消不用检查文章存不存在 —— 删 0 行无害
    n = db.query(ArticleLike).filter(
        ArticleLike.user_id == current_user["id"],
        ArticleLike.article_id == article_id,
    ).delete()
    db.commit()

    # ★ 只有【真的删掉了一条赞】才扣分。
    #   不加 if n 的话,"取消一个本来就没赞的"会被白扣 3 分 ——
    #   有人狂调这个接口就能把别人文章的热度刷成负数。
    if n:
        add_hot(article_id, -W_LIKE)

    return {"message": "已取消点赞" if n else "本来就没赞"}
