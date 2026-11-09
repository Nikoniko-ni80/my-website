# ============================================================
# routers/collections.py —— 收藏功能 (收藏夹 + 收藏)
# ============================================================
# 从 main.py 搬过来的, 代码本身一个字没改, 只把 @app 换成了 @router
#
# 顺便: get_or_create_default_collection 也搬到了这个文件。
#   它本来在 main.py 里是唯一一个"不是路由"的函数, 显得格格不入。
#   搬过来的理由很简单: 用它的人全在这个文件里 (下面那两个 GET)。
#   一个只服务本文件的工具, 就该跟用它的代码待在一起。
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import User, Article, Collection, Favorite, ArticleLike
from routers.orders import make_preview
from schemas import CollectionIn, FavoriteIn
from dependencies import get_current_user

router = APIRouter()

# ============================================================
# 收藏功能 (收藏夹 + 收藏)
#   每个用户至少有一个"默认收藏夹"
# ============================================================

DEFAULT_COLLECTION = "默认收藏夹"

# 【这个函数干嘛的】
#   保证"每个用户至少有一个收藏夹"。
#   有就拿给你, 没有就当场建一个 —— 所以叫 get_or_create (拿 / 建)。
#
# 【为啥需要它】
#   收藏一篇文章必须选一个夹子 (favorites.collection_id 不能空)。
#   新用户一个夹子都没有 → 点「收藏」面板里空空的, 想收都没地方收。
#   与其让他自己去「新建收藏夹」, 不如后端兜底: 第一次来就送他一个。
#
# 【它啥时候跑】
#   前端永远不直接触发它 —— 它不是一个接口, 没有 URL, 点不到。
#   它是被这两个接口在内部"顺手叫一声"的:
#       · GET /my/collections                 → list_collections
#       · GET /my/articles/{id}/collections   → list_collections_of_article
#   所以: 你只要"看一眼收藏夹", 它就会跑一次。
#
# ★【为啥是"用的时候建", 而不是"注册的时候就建"?】这是个正经取舍, 当初这么算的:
#
#   方案A (现在这个): 用的时候兜底
#     ✓ 老用户自动补上 (改这功能之前注册的那批人, 下次打开收藏页就有了)
#     ✓ 谁绕过前端把夹子删光了, 下次打开也自动补回来
#     ✓ 以后新增"建用户"的途径 (比如第三方登录), 不用记得回来加代码
#     ✗ 缺点: 这是个 GET 接口, 却在偷偷写库
#             (REST 讲究 GET 只读、刷一百遍结果都一样, 这里破了规矩)
#
#   方案B: 注册时就建
#     ✓ GET 接口变回纯读
#     ✗ 老用户全得写脚本补 (改之前已经有 4 个用户一个夹子都没有)
#     ✗ 谁绕过前端删光夹子, 就永久没夹子了
#     ✗ 以后每个建用户的地方都得记得加这一行
#
#   最后选了 A, 因为:
#     ① 性能不是理由 —— 实测这查询 0.8 毫秒, 一个 HTTP 请求要 64 毫秒, 占 1.3%
#     ② "绝对不会没夹子" 比 "GET 语义干净" 值钱
#     ③ 这模式有正经名字: lazy creation (懒创建), 真实系统对"默认设置/默认分类"常这么干
#   一句话: 0.8 毫秒买"永远不会没夹子", 划算。
#
# 【小坑提醒】名字里的 "default" 有点骗人 ——
#   它实际拿的是"id 最小的那个夹子", 不一定真叫「默认收藏夹」。
#   正常情况没差别 (新用户第一次来建的就是它, id 最小);
#   但要是用户把「默认收藏夹」删了、还剩别的夹子, 返回的就是剩下那个。
#   目前用它的地方只关心"有个夹子能用", 不关心叫啥, 所以无所谓。
def get_or_create_default_collection(db, user_id):
    """拿用户的默认收藏夹; 一个都没有就自动建一个"""
    col = db.query(Collection).filter(
        Collection.user_id == user_id
    ).order_by(Collection.id).first()
    if col is None:
        col = Collection(name=DEFAULT_COLLECTION, user_id=user_id)
        db.add(col)
        db.commit()
        db.refresh(col)
    return col


# ---------- 我的收藏夹列表 GET /my/collections (需登录) ----------
@router.get("/my/collections")
def list_collections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_or_create_default_collection(db, current_user["id"])   # 保证至少有一个
    cols = db.query(Collection).filter(
        Collection.user_id == current_user["id"]
    ).order_by(Collection.id).all()
    result = []
    for c in cols:
        count = db.query(Favorite).filter(Favorite.collection_id == c.id).count()
        result.append({"id": c.id, "name": c.name, "count": count})
    return result


# ---------- 新建收藏夹 POST /my/collections (需登录) ----------
@router.post("/my/collections")
def create_collection(
    col: CollectionIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    new = Collection(name=col.name, user_id=current_user["id"])
    db.add(new)
    db.commit()
    db.refresh(new)
    return {"message": "创建成功", "id": new.id, "name": new.name}


# ---------- 收藏夹改名 PUT /my/collections/{id} (需登录) ----------
@router.put("/my/collections/{collection_id}")
def rename_collection(
    collection_id: int,
    col: CollectionIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(Collection).filter(
        Collection.id == collection_id, Collection.user_id == current_user["id"]
    ).first()
    if row is None:
        return {"error": "收藏夹不存在或不是你的"}
    row.name = col.name
    db.commit()
    return {"message": "修改成功"}


# ---------- 删收藏夹 DELETE /my/collections/{id} (需登录) ----------
@router.delete("/my/collections/{collection_id}")
def delete_collection(
    collection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(Collection).filter(
        Collection.id == collection_id, Collection.user_id == current_user["id"]
    ).first()
    if row is None:
        return {"error": "收藏夹不存在或不是你的"}
    # ★ 第 0 步之后这里也变干净了: 只删夹子就行
    #   favorites 的外键改成了 ON DELETE CASCADE, 夹子里的收藏记录数据库会自己删
    #   改之前是: db.query(Favorite).filter(Favorite.collection_id == collection_id).delete()
    db.delete(row)
    db.commit()
    return {"message": "删除成功"}


# ---------- 看某收藏夹里的文章 GET /my/collections/{id}/articles (需登录) ----------
@router.get("/my/collections/{collection_id}/articles")
def list_collection_articles(
    collection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    col = db.query(Collection).filter(
        Collection.id == collection_id, Collection.user_id == current_user["id"]
    ).first()
    if col is None:
        return {"error": "收藏夹不存在或不是你的"}
    rows = (
        # 多查一个 Favorite.created_at —— 前端卡片上要显示"收藏于X月X日"
        # (这个时间在 favorites 表里, 不在 articles 表里: 记的是"啥时候收的", 不是"啥时候写的")
        #
        # ★ 注意 query 里给"实体"和给"列", 返回的东西不一样:
        #     db.query(Article, User.username, Favorite.created_at)
        #               ↑ 实体      ↑ 列            ↑ 列
        #     → 拿到的是 (Article对象, 字符串, datetime)
        #   给实体给你整个对象; 给某一列就直接给你那一列的值。
        #   所以下面循环里 f 已经是 datetime 了, 不用再 f.created_at (会报错)
        db.query(Article, User.username, Favorite.created_at)
        .join(Favorite, Favorite.article_id == Article.id)
        .join(User, Article.user_id == User.id)
        .filter(Favorite.collection_id == collection_id)
        .order_by(Favorite.id.desc())
        .all()
    )
    # ★ 一次算出这批文章各自的点赞量 (IN + GROUP BY) —— 跟首页那段一样
    art_ids = [a.id for a, _, _ in rows]
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
        {"id": a.id, "title": a.title,
         # ★ 付费文章只给开头 (收藏夹里也可能收着别人的付费文章)
         "content": make_preview(a.content) if a.is_paid else a.content,
         "is_paid": a.is_paid, "price": a.price, "cover": a.cover,
         "user_id": a.user_id,          # ★ 给前端"点作者名跳主页"用
         "author": u,
         "favorited_at": str(f),
         "like_count": like_map.get(a.id, 0)}
        for a, u, f in rows
    ]


# ---------- 看"这篇被收进了哪些收藏夹" GET /my/articles/{id}/collections (需登录) ----------
# 为什么要专门做一个接口:
#   文章详情页点"收藏"要弹出一个面板, 面板上每个夹子都得显示
#   "这篇已经在里面了 ✓ / 还没收"。
#   如果只用现有的 GET /my/collections (只有 count) 和
#   GET /my/collections/{id}/articles (返回夹子里全部文章的正文),
#   前端得把每个夹子都拉一遍才知道有没有这篇 —— 夹子有几个就发几次请求, 太浪费。
#   所以让后端一次算好, 前端一次拿到。
@router.get("/my/articles/{article_id}/collections")
def list_collections_of_article(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # ① 先确认这篇文章"我能看" (跟 add_favorite 里一样的检查, 保持一致的规矩)
    art = db.query(Article).filter(Article.id == article_id).first()
    if art is None:
        return {"error": "文章不存在"}
    if not art.is_public and art.user_id != current_user["id"]:
        return {"error": "文章未公开, 无法收藏"}

    # ② 保证至少有一个收藏夹 (复用现成的函数; 面板上一个夹子都没有体验不好)
    get_or_create_default_collection(db, current_user["id"])

    # ③ 我的所有收藏夹
    cols = db.query(Collection).filter(
        Collection.user_id == current_user["id"]
    ).order_by(Collection.id).all()

    # ④ 逐个夹子算两件事: 里面共几篇 + 有没有"这一篇"
    #    写法跟 list_collections 里算 count 一模一样, 只是多查了一次"有没有这篇"
    result = []
    for c in cols:
        count = db.query(Favorite).filter(Favorite.collection_id == c.id).count()
        hit = db.query(Favorite).filter(
            Favorite.collection_id == c.id,
            Favorite.article_id == article_id,      # ★ 多这一个条件
        ).first()
        result.append({
            "id": c.id,
            "name": c.name,
            "count": count,                          # 夹子里一共几篇
            "favorited": hit is not None,            # ★ 这一篇在不在这个夹子里
        })
    return result


# ---------- 收藏一篇文章 POST /favorites (需登录) ----------
@router.post("/favorites")
def add_favorite(
    fav: FavoriteIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 确认收藏夹是自己的
    col = db.query(Collection).filter(
        Collection.id == fav.collection_id, Collection.user_id == current_user["id"]
    ).first()
    if col is None:
        return {"error": "收藏夹不存在或不是你的"}
    # 确认文章"能看" (公开的 或 自己的)
    art = db.query(Article).filter(Article.id == fav.article_id).first()
    if art is None:
        return {"error": "文章不存在"}
    if not art.is_public and art.user_id != current_user["id"]:
        return {"error": "文章未公开, 无法收藏"}
    # 已经收藏过了吗?
    exists = db.query(Favorite).filter(
        Favorite.collection_id == fav.collection_id,
        Favorite.article_id == fav.article_id
    ).first()
    if exists:
        return {"error": "这个收藏夹里已经有这篇文章了"}

    new = Favorite(collection_id=fav.collection_id, article_id=fav.article_id)
    db.add(new)
    db.commit()
    db.refresh(new)
    return {"message": "收藏成功", "id": new.id}


# ---------- 取消收藏 DELETE /my/collections/{cid}/articles/{aid} (需登录) ----------
@router.delete("/my/collections/{collection_id}/articles/{article_id}")
def remove_favorite(
    collection_id: int,
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    col = db.query(Collection).filter(
        Collection.id == collection_id, Collection.user_id == current_user["id"]
    ).first()
    if col is None:
        return {"error": "收藏夹不存在或不是你的"}
    row = db.query(Favorite).filter(
        Favorite.collection_id == collection_id,
        Favorite.article_id == article_id
    ).first()
    if row is None:
        return {"error": "没有收藏过这篇"}
    db.delete(row)
    db.commit()
    return {"message": "已取消收藏"}
