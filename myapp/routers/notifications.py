# ============================================================
# routers/notifications.py —— 通知
# ============================================================
# 【这个文件的三层】
#   ① 常量 + notify(): 给别的路由用的"发通知"工具
#   ② 查询接口: 我的通知 / 未读数 / 标记已读 / 清空
#   ③ 设置接口: 通知开关 / 关注自动回复
#
# 【核心概念：收件人 vs 寄件人】
#   user_id   = 收件人（内容被互动的人）
#   from_user = 寄件人（做出动作的人；系统通知为 NULL）
#
#   例: 张三赞了李四的文章
#         → user_id = 李四, from_user = 张三
# ============================================================
from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import get_db
from models import Conversation, Message, Notification, NotificationSetting, User
from schemas import NotifySettingIn, GreetingIn
from dependencies import get_current_user
import sse

router = APIRouter()

# ★ 合法的通知类型 —— 放应用层，加新类型只改这一行，不用 ALTER TABLE
#   (数据库里 type 就是 String(20))
NOTIFY_TYPES = {"like", "comment", "reply", "follow", "payment", "system"}

# 【六种类型速查】
#   type       什么时候产生                 收件人(user_id)     文案例子
#   ---------  ---------------------------  ------------------  --------------------------
#   like       有人赞你的文章               文章作者            "张三 赞了你的文章《…》"
#   comment    有人评论你的文章             文章作者            "张三 评论了你的文章《…》"
#   reply      有人回复你的评论             被回复的人          "张三 回复了你的评论"
#   follow     有人关注你                   被关注的人          "张三 关注了你"
#   payment    有人买了你的付费文章         文章作者            "张三 购买了你的文章《…》"
#   system     管理员/平台操作              目标用户            "你的文章因违规被删除"
#
# ★ 规则: 收件人 = "内容被互动的一方"
#     张三赞/评论李四的文章 → 通知发给【李四】
#
# ★ system 的 from_user:
#     平台公告 → NULL
#     管理员删文章 → 管理员 id (可追溯是谁干的)
#     前端是按 type 显示系统图标的, 不是按 from_user 是否为空
#
# ★ 原来的 greeting (关注欢迎语) 已经【搬家】了:
#     它现在是一条真正的私信, 由 routers/follows.py 直接往 messages 表插,
#     不再走通知这条路 —— 因为通知只能看、不能回。
#
# 【每种由哪里触发】
#   like / comment / reply  → routers/articles.py
#   follow                  → routers/follows.py
#   system                  → 管理端 (第 8 步, 还没做)

# 【左侧分类 → 实际 type 的映射】
#   页面左边那一列不是一对一, "评论与回复"其实包含两种 type
CATEGORY_TYPES = {
    "reply":  ("comment", "reply"),    # 评论与回复
    "like":   ("like",),               # 收到的赞
    "follow": ("follow",),             # 新增关注 (greeting 已改走私信, 不在通知里了)
    "order":  ("payment",),            # 交易 (付费文章卖出去了)
    "system": ("system",),             # 系统通知
    # 空字符串 / 不传 → 全部
}


# ------------------------------------------------------------
# ① 发通知（核心工具，别的地方都调它）
# ------------------------------------------------------------
def notify(
    db: Session,
    to_user: int,             # 收件人
    type: str,                # 类型
    content: str,             # 一句话文案（快照）
    link: str = "",           # 点开跳哪
    from_user: int | None = None,   # 谁触发的；系统通知传 None
) -> bool:
    """给某人发一条通知。返回 True = 真发了, False = 跳过。

    会自动处理三件事:
      ① 类型合法吗
      ② 是不是发给自己（是 → 跳过）
      ③ 收件人关掉这类通知了吗（关了 → 跳过）
    """
    # ① 类型必须在白名单里
    if type not in NOTIFY_TYPES:
        print(f"[通知] 未知类型: {type}")
        return False

    # ② 不给自己发通知（自己赞自己、自己评论自己）
    if from_user is not None and to_user == from_user:
        return False

    # ③ 查收件人的开关: 没有记录 = 默认开启
    setting = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == to_user,
        NotificationSetting.type == type,
    ).first()
    if setting is not None and not setting.enabled:
        return False

    db.add(Notification(
        user_id=to_user,
        from_user=from_user,
        type=type,
        content=content[:300],      # 别超过列宽
        link=link[:200],
    ))

    # ★ SSE: 只推一个"你有一条新通知"的信号, 不推内容。
    #   前端收到后自己去拉 unread-count / 列表 —— 数据以数据库为准。
    #   就算是事务最后回滚了, 前端刷新一次也看不到这条, 不会显示错数据。
    sse.push_notification(to_user)
    return True


def notify_like(db: Session, article, liker: dict) -> bool:
    """点赞通知: 同一个人对同一篇只发一次。

    为什么单独包一层:
      用户可以"点赞 → 取消 → 再点赞", 每轮都会调到这里。
      不去重的话, 一个人就能刷出几十条通知。
    """
    link = f"/article/{article.id}"
    exists = db.query(Notification).filter(
        Notification.user_id == article.user_id,
        Notification.from_user == liker["id"],
        Notification.type == "like",
        Notification.link == link,
    ).first()
    if exists:
        return False

    return notify(
        db,
        to_user=article.user_id,
        type="like",
        content=f"{liker['username']} 赞了你的文章《{article.title}》",
        link=link,
        from_user=liker["id"],
    )


# ------------------------------------------------------------
# ①b 未读统计（导航栏红点 + 左侧分类数字，两边共用一个函数）
# ------------------------------------------------------------
# 【为什么单独抽出来】
#   红点要数的东西现在有【两个来源】:
#       notifications 表  → 通知未读
#       messages    表  → 私信未读
#   以前只数第一个, 所以"有人给你发私信"这件事, 导航栏完全不知道。
#
#   这个函数一次算清四样, 两个接口都调它, 免得两边算得不一样。
def unread_stats(db: Session, me: int) -> dict:
    me_id = me if isinstance(me, int) else me["id"]

    # ① 通知未读: 按 type 分组数一次, 顺便就能拼出分类数字
    rows = (
        db.query(Notification.type, func.count(Notification.id))
        .filter(Notification.user_id == me_id, Notification.is_read == False)
        .group_by(Notification.type)
        .all()
    )
    by_type = {t: c for t, c in rows}
    unread = sum(by_type.values())

    # ② 分类数字: "评论与回复"其实是 comment + reply 两种, 加一起
    by_category = {
        key: sum(by_type.get(t, 0) for t in types)
        for key, types in CATEGORY_TYPES.items()
    }

    # ③ 私信未读: 我参与的会话里, 别人发的、我没读的
    message_unread = (
        db.query(func.count(Message.id))
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            or_(Conversation.user_a == me_id, Conversation.user_b == me_id),
            Message.from_user != me_id,
            Message.is_read == False,
        )
        .scalar()
    ) or 0

    return {
        "unread": unread,                 # 通知未读 (老字段, 保持兼容)
        "message_unread": message_unread, # 私信未读
        "total": unread + message_unread, # 导航栏红点用这个
        "by_category": by_category,       # 左侧每个分类各显示各的
    }


# ============================================================
# ② 查询接口
# ============================================================
@router.get("/notifications")
def list_notifications(
    page: int = 1,
    size: int = 20,
    category: str = "",        # ★ 左侧分类: reply / like / follow / system, 空 = 全部
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """我的通知, 按时间倒序。"""
    me = current_user["id"]
    size = max(1, min(size, 50))

    # 分类 → type 列表 (不在映射里的值 = 不过滤, 当"全部")
    types = CATEGORY_TYPES.get(category)

    conds = [Notification.user_id == me]
    if types:
        conds.append(Notification.type.in_(types))

    q = db.query(Notification).filter(*conds)
    total = q.count()

    rows = (
        # 顺便把寄件人的名字查出来 (系统通知没有寄件人 → 用 outerjoin)
        db.query(Notification, User.username)
        .outerjoin(User, User.id == Notification.from_user)##联表是为了显示发件人name
        .filter(*conds)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * size).limit(size).all()
    )

    # 未读数是【全部】的, 不跟分类走 (导航栏红点显示总数)
    # ★ 现在连私信也一起算了, 见 unread_stats
    stats = unread_stats(db, me)

    return {
        "items": [
            {"id": n.id, "type": n.type, "content": n.content, "link": n.link,
             "is_read": n.is_read,
             "from_user": n.from_user,
             "from_username": username or "",        # 系统消息为空
             "created_at": str(n.created_at) if n.created_at else ""}
            for n, username in rows
        ],
        "total": total, "unread": stats["unread"],
        "stats": stats,          # ★ 左侧分类数字 + 私信未读都在这
        "page": page, "size": size,
        "pages": (total + size - 1) // size,
    }


@router.get("/notifications/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导航栏那个红点用的。

    ★ 现在返回四样:
        unread          通知未读
        message_unread  私信未读
        total           两者相加 —— 导航栏显示这个
        by_category     左侧分类数字
    """
    return unread_stats(db, current_user["id"])


@router.put("/notifications/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """一键全部已读。"""
    n = db.query(Notification).filter(
        Notification.user_id == current_user["id"],
        Notification.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"message": "已全部标为已读", "count": n}


@router.put("/notifications/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ★ 必须带 user_id 过滤 —— 不然能改别人的通知
    row = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user["id"],
    ).first()
    if row is None:
        return {"error": "通知不存在"}
    row.is_read = True
    db.commit()
    return {"message": "已读"}


@router.delete("/notifications")
def clear_notifications(
    category: str = "",        # ★ 空 = 清空全部; 传分类 = 只清这一类
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清空消息。

    category 不传 → 清空全部
    category=like / reply / follow / system → 只清这一类
    (跟 GET /notifications 用的是同一套分类映射)
    """
    types = CATEGORY_TYPES.get(category)

    q = db.query(Notification).filter(
        Notification.user_id == current_user["id"]
    )
    if types:
        q = q.filter(Notification.type.in_(types))

    n = q.delete()          # ★ 硬删
    db.commit()
    return {"message": "已清空", "count": n, "category": category or "all"}


# ============================================================
# ③ 设置接口
# ============================================================
@router.get("/notification-settings")
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回【全部类型】的开关状态（没记录的按开启补上）。"""
    me = current_user["id"]
    rows = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == me
    ).all()
    saved = {r.type: r.enabled for r in rows}

    u = db.query(User).filter(User.id == me).first()

    return {
        # sorted 让顺序稳定, 前端不用自己排
        "items": [
            {"type": t, "enabled": saved.get(t, True)}     # ★ 没有记录 = 默认开启
            for t in sorted(NOTIFY_TYPES)
        ],
        "follow_greeting": u.follow_greeting if u else "",
    }


@router.put("/notification-settings/greeting")
def update_greeting(
    body: GreetingIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """设置"关注自动回复"。传空字符串 = 关闭。"""
    u = db.query(User).filter(User.id == current_user["id"]).first()
    if u is None:
        return {"error": "用户不存在"}
    u.follow_greeting = body.greeting.strip()[:200]
    db.commit()
    return {"message": "已保存", "follow_greeting": u.follow_greeting}


@router.put("/notification-settings")
def update_setting(
    body: NotifySettingIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """改一个开关（有记录就改, 没有就插一条）。"""
    if body.type not in NOTIFY_TYPES:
        return {"error": "未知的通知类型"}

    me = current_user["id"]
    row = db.query(NotificationSetting).filter(
        NotificationSetting.user_id == me,
        NotificationSetting.type == body.type,
    ).first()

    if row is None:
        db.add(NotificationSetting(user_id=me, type=body.type, enabled=body.enabled))
    else:
        row.enabled = body.enabled

    db.commit()
    return {"message": "已保存", "type": body.type, "enabled": body.enabled}
