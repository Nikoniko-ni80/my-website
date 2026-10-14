# ============================================================
# routers/follows.py —— 关注 + Feed 流
# ============================================================
# 又是"加新功能 = 加新文件"的一次示范。
# 挂上去只要在 main.py 加一行 include_router。
from fastapi import APIRouter, Depends
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from database import get_db
from models import User, Article, Follow
from dependencies import get_current_user

router = APIRouter()


# ---------- 关注 POST /users/{id}/follow (需登录) ----------
@router.post("/users/{user_id}/follow")
def follow_user(
    user_id: int,                                       # 拿来就有 (网址里摘的)
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    me = current_user["id"]

    # ① 不能关注自己
    if user_id == me:
        return {"error": "不能关注自己"}

    # ② 对方得存在
    #   ⚠️ 不查的话, 数据库的【外键】会拒绝这条 INSERT
    #      → 报一个难看的 500, 而不是一句人话
    #   (这跟"改用户名要先查重"是同一个套路: 约束是最后防线, 能提前查就提前查)
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        return {"error": "用户不存在"}

    # ③ 已经关注过了吗?
    #   ⚠️ 必须查! 不然重复点击会插第二条 → 撞上唯一约束 (user_id, target_user_id) → 500
    #   什么情况会重复?
    #     手抖快速双击 (前端按钮还没来得及变色, 第二个请求已经发出去了)
    #     开了两个标签页, 各点了一次
    #     有人直接 curl
    #   ★ 这种"其实已经达成了目标"的情况, 当成成功返回, 不报红字
    #     (跟收藏功能遇到"重复收藏"是同一个处理思路)
    exists = db.query(Follow).filter(
        Follow.user_id == me,
        Follow.target_user_id == user_id,
    ).first()
    if exists:
        return {"message": "已经关注过了"}

    # ④ ★ 重点: "我"从【token】里拿, "关注谁"从【网址】里拿
    #   如果 user_id 也从请求体里拿, 那前端说关注谁就关注谁 —— 但这里本来就允许
    #   指定关注对象, 所以唯一不能信的是"我是谁", 而那个永远从 token 来
    db.add(Follow(user_id=me, target_user_id=user_id))
    db.commit()

    return {"message": "关注成功"}


# ---------- 取关 DELETE /users/{id}/follow (需登录) ----------
@router.delete("/users/{user_id}/follow")
def unfollow_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # ★ 取关【不用】检查"对方存不存在" —— 这是关注/取关的不对称之处:
    #     关注 = INSERT → 不查会被外键拒绝 → 500
    #     取关 = DELETE → 删 0 行, 无事发生 → 完全无害
    #   "取消一个本来就没关注的", 结果本来也就是"无事发生", 所以直接执行就行
    n = db.query(Follow).filter(
        Follow.user_id == current_user["id"],
        Follow.target_user_id == user_id,
    ).delete()
    db.commit()

    return {"message": "已取关" if n else "本来就没关注"}


# ---------- 查"我关没关注他" GET /users/{id}/follow-status (需登录) ----------
# 【为什么单独一个接口, 而不是塞进 GET /users/{id}】
#   因为 GET /users/{id} 是【不用登录】的公开接口 (分享主页链接给没登录的人也能看)。
#   要让它返回"我关没关注", 就得知道"我是谁" —— 但没登录时压根没有"我"。
#   所以单独开一个: 需要登录 → 前端登录了才调, 没登录就跳过(按"没关注"显示)
#   (这跟文章页那个"这篇在几个收藏夹里"是同一个模式)
@router.get("/users/{user_id}/follow-status")
def follow_status(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hit = db.query(Follow).filter(
        Follow.user_id == current_user["id"],
        Follow.target_user_id == user_id,
    ).first()
    return {"following": hit is not None}


# ---------- 粉丝列表 GET /users/{id}/followers (不用登录) ----------
# "谁关注了他" → 用 target_user_id 反着查
@router.get("/users/{user_id}/followers")
def list_followers(user_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(User)
        # 表里哪一行的 target 是他, 那一行的 user 就是他的粉丝
        .join(Follow, Follow.user_id == User.id)
        .filter(Follow.target_user_id == user_id)
        .order_by(Follow.id.desc())          # 最近关注的在前
        .all()
    )
    return [
        {"id": u.id, "username": u.username, "avatar": u.avatar, "bio": u.bio}
        for u in rows
    ]


# ---------- 关注列表 GET /users/{id}/following (不用登录) ----------
# "他关注了谁" → 用 user_id 查
@router.get("/users/{user_id}/following")
def list_following(user_id: int, db: Session = Depends(get_db)):
    rows = (
        db.query(User)
        # 表里哪一行的 user 是他, 那一行的 target 就是他关注的人
        .join(Follow, Follow.target_user_id == User.id)
        .filter(Follow.user_id == user_id)
        .order_by(Follow.id.desc())
        .all()
    )
    return [
        {"id": u.id, "username": u.username, "avatar": u.avatar, "bio": u.bio}
        for u in rows
    ]


# ---------- 我的关注列表 GET /my/following (需登录) ----------
# 给「关注」页左边那一栏用: 列出我关注的人 + 每人最近更新时间, 按更新时间倒序
# ★ "有人更新就排前面" —— 就是按 last_update 倒序
@router.get("/my/following")
def my_following(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(User, func.max(Article.created_at).label("last_update"))
        .join(Follow, Follow.target_user_id == User.id)      # 我关注的人
        # ★★ 这里是 outerjoin (左连接), 不是 join!
        #   为什么? 因为有人可能【一篇文章都没发过】, 那种人也该出现在列表里,
        #   只是 last_update 是空的、排到最后。用 inner join 他们会被直接丢掉。
        #   条件里的 and_ 是"两个都要满足":
        #     文章是他的  AND  文章是公开的 (别人私密的文章不该影响排序)
        .outerjoin(Article, and_(
            Article.user_id == User.id,
            Article.is_public == True,
        ))
        .filter(Follow.user_id == current_user["id"])
        .group_by(User.id)                                   # 每个人一行 (他可能有多篇文章)
        .order_by(func.max(Article.created_at).desc())       # ★ 最近更新的排最前
        .all()
    )

    return [
        {
            "id": u.id, "username": u.username,
            "avatar": u.avatar, "bio": u.bio,
            # str() 转一下才能 JSON 化; 从没发过文章的就是 None
            "last_update": str(t) if t else None,
        }
        for u, t in rows
    ]
    # ★ 这个聚合查询里的 func.max + group_by, 跟"每个夹子里有几篇"是同一类东西 ——
    #   都是"分组后算一个数"。区别只在于这里算的是"最大时间"而不是"个数"。


# ---------- Feed 流 GET /my/feed (需登录) ----------
# 「关注」页: 我关注的人发的公开文章
# ★ 用的是【拉模式】(读的时候现算), 不是推模式 —— 不建新表
#   推模式要额外建一张 feeds 收件箱表, 而且有大 V 问题(1000万粉丝=插1000万行)
#   详见 项目设计.md 第三节「Feed 流」
@router.get("/my/feed")
def my_feed(
    page: int = 1,
    size: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Article, User.username)
        .join(User,   Article.user_id == User.id)                 # 拿作者名
        .join(Follow, Follow.target_user_id == Article.user_id)   # ★ 文章作者是我关注的人
        .filter(
            Follow.user_id == current_user["id"],                 # ★ 而且是我关注的
            Article.is_public == True,                            # ★ 别人私密的文章当然看不到
        )
    )

    total = q.count()
    rows = (
        q.order_by(Article.created_at.desc())                     # 最新的在前
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    return {
        "items": [
            {"id": a.id, "title": a.title, "content": a.content,
             "user_id": a.user_id, "author": username,
             "created_at": str(a.created_at) if a.created_at else ""}
            for a, username in rows
        ],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size,
    }
