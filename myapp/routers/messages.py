# ============================================================
# routers/messages.py —— 私信
# ============================================================
# 【两层结构】
#   conversations  一个聊天窗口（谁和谁）
#   messages       窗口里的每一条消息
#
# 【核心规则：user_a 永远存小的 id】
#   张三(3) 找 李四(7)  → (3,7)
#   李四(7) 找 张三(3)  → 也排序成 (3,7)
#   → 同一对人永远命中同一行, 不会出现两个窗口
#
# 【接口】
#   GET  /conversations                     我的会话列表
#   GET  /conversations/{id}/messages       聊天记录
#   POST /conversations/{user_id}/messages  给某人发消息
#   PUT  /conversations/{id}/read           标记已读
# ============================================================
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import get_db
from models import Conversation, Message, User
from schemas import MessageIn
from dependencies import get_current_user
from ws import manager

router = APIRouter()

MAX_MSG_LEN = 500       # 一条消息最多多少字
PAGE_MSG = 30           # 一次拉多少条聊天记录


# ------------------------------------------------------------
# 工具: 找到（或新建）两个人之间的会话
# ------------------------------------------------------------
# 【会话是怎么诞生的 · 我的理解】
#   发第一句话的时候, 后端才建立这个 conversation。
#   建完把 id 返回给前端 —— 两个人眼里的"这个对话"从此有了同一个 id。
#   之后任何一个人打开对话框, 用的都是这个 id:
#       GET /conversations/{id}/messages
#   所以只要前端手里有这个对话, 就一定知道它的 id,
#   也就能拉记录、标已读（发消息用的则是对方的 user_id）。
#
#   ★ 对方是怎么拿到这个 id 的?
#       他打开"我的消息" → GET /conversations → 列表里每一项都带着 id
#   ★ 前端永远不会自己编 id, 只会从接口返回值或列表里拿。
def get_or_create_conversation(db: Session, me: int, other_id: int) -> Conversation:
    a, b = sorted([me, other_id])          # ★ 永远小的在前

    conv = db.query(Conversation).filter(
        Conversation.user_a == a,
        Conversation.user_b == b,
    ).first()

    if conv is None:
        conv = Conversation(user_a=a, user_b=b)
        db.add(conv)
        db.flush()                          # 拿到自增 id, 先不提交
    return conv


def get_my_conversation(db: Session, conv_id: int, me: int):
    """取会话, 并检查"我是不是这两个人之一"。"""
    c = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if c is None:
        return None
    if me not in (c.user_a, c.user_b):
        return None                          # 别人的会话, 当不存在
    return c


# ------------------------------------------------------------
# ① 会话列表 GET /conversations
# ------------------------------------------------------------
@router.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """左边那一列: 每个聊天对象 + 最后一句话 + 未读数, 按最近活跃排序。"""
    me = current_user["id"]

    convs = (
        db.query(Conversation)
        .filter(or_(Conversation.user_a == me, Conversation.user_b == me))
        .order_by(Conversation.last_message_at.desc())
        .all()
    )
    if not convs:
        return {"items": []}

    conv_ids = [c.id for c in convs]

    # 每个会话的"对方 id"
    other_of = {c.id: (c.user_b if c.user_a == me else c.user_a) for c in convs}
    other_ids = list(set(other_of.values()))

    # ① 对方的用户信息 (一次 IN 查完)
    users = {
        u.id: u for u in db.query(User).filter(User.id.in_(other_ids)).all()
    }

    # ② 每个会话的未读数 (一条 GROUP BY)
    unread_map = dict(
        db.query(Message.conversation_id, func.count())
        .filter(
            Message.conversation_id.in_(conv_ids),
            Message.from_user != me,          # 只数"对方发给我"的
            Message.is_read == False,
        )
        .group_by(Message.conversation_id)
        .all()
    )

    # ③ 每个会话的最后一条消息
    #    先取每个会话最大的 message id (id 自增 = 最新), 再一次性查回来
    last_ids = [
        x[0] for x in
        db.query(func.max(Message.id))
        .filter(Message.conversation_id.in_(conv_ids))
        .group_by(Message.conversation_id)
        .all()
    ]
    last_msgs = {}
    if last_ids:
        last_msgs = {
            m.conversation_id: m
            for m in db.query(Message).filter(Message.id.in_(last_ids)).all()
        }

    return {"items": [
        {
            "id": c.id,
            "user_id": other_of[c.id],
            "username": users[other_of[c.id]].username if other_of[c.id] in users else "已注销用户",
            "avatar": users[other_of[c.id]].avatar if other_of[c.id] in users else "",
            "last_message": last_msgs[c.id].content if c.id in last_msgs else "",
            "last_message_at": str(c.last_message_at) if c.last_message_at else "",
            "unread": unread_map.get(c.id, 0),
        }
        for c in convs
    ]}


# ------------------------------------------------------------
# ①b 查"我和某人"有没有会话 GET /conversations/with/{user_id}
# ------------------------------------------------------------
# 个人主页点「私信」时先问这里:
#   有会话 → 直接进聊天页, 能看到历史
#   没会话 → 弹一个输入框, 发第一句(由 send_message 创建)
# ★ 这个接口【只查不建】, 避免产生空会话。
@router.get("/conversations/with/{user_id}")
def get_conversation_with(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    me = current_user["id"]
    if user_id == me:
        return {"conversation_id": None}

    a, b = sorted([me, user_id])
    c = db.query(Conversation).filter(
        Conversation.user_a == a,
        Conversation.user_b == b,
    ).first()

    return {"conversation_id": c.id if c else None}


# ------------------------------------------------------------
# ② 聊天记录 GET /conversations/{id}/messages?before=xx
# ------------------------------------------------------------
@router.get("/conversations/{conversation_id}/messages")
def list_messages(
    conversation_id: int,
    before: int | None = None,
    ##before是当前最早的一条，如果往上拉就要往before上面取30条，然后更新before
    after: int | None = None,
    ##after是当前最新的一条 —— 轮询时只取比它新的 (前端每几秒问一次"有新消息吗")
    limit: int = PAGE_MSG,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    me = current_user["id"]

    conv = get_my_conversation(db, conversation_id, me)
    if conv is None:
        return {"error": "会话不存在"}

    limit = max(1, min(limit, 50))

    q = db.query(Message).filter(Message.conversation_id == conversation_id)

    if after is not None:
        # ★ 轮询分支: 只取"比 after 更新"的消息, 按时间正序返回
        #   用 `is not None` 而不是 `if after` —— 因为第一次轮询可能传 after=0
        #   前端拿到后直接追加到列表末尾, 不用重排
        rows = (
            q.filter(Message.id > after)
            .order_by(Message.id.asc())
            .limit(limit)
            .all()
        )
        has_more = False          # 轮询用不到"往上翻"
    else:
        if before:
            q = q.filter(Message.id < before)

        # 先按 id 倒序拿最新的一批, 返回前再反过来 (聊天窗口里老的在上)
        rows = q.order_by(Message.id.desc()).limit(limit + 1).all()
        # 取最新 limit+1 条, 多拿一条用于判断还有没有更早的, 之后扔掉

        has_more = len(rows) > limit   # 有没有多的那一条
        rows = rows[:limit]            # 有就扔掉
        rows.reverse()                 # 老的在前

    other_id = conv.user_b if conv.user_a == me else conv.user_a
    other = db.query(User).filter(User.id == other_id).first()

    # 打开会话 → 把"对方发的、我没读的"标成已读
    marked = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.from_user != me,
        Message.is_read == False,
    ).update({"is_read": True})
    db.commit()

    return {
        "conversation_id": conv.id,
        "user": {"id": other_id,
                 "username": other.username if other else "已注销用户",
                 "avatar": other.avatar if other else ""},
        "messages": [
            {"id": m.id, "from_user": m.from_user,
             "content": m.content, "is_read": m.is_read,
             "created_at": str(m.created_at) if m.created_at else ""}
            for m in rows
        ],
        "has_more": has_more,
        "marked_read": marked,
    }


# 【list_messages 的流程 · 速查】
#   ① 先确认这个会话是我的            get_my_conversation
#        不是我的 → 返回 "会话不存在"
#
#   ② 取最新的一批: ORDER BY id DESC LIMIT (limit + 1)
#        └─ 多拿 1 条, 只用来判断 has_more, 不显示
#
#   ③ rows = rows[:limit]
#        └─ 把多拿的那条扔掉
#
#   ④ rows.reverse()
#        └─ 数据库给的是"新的在前"; 聊天窗要"老的在上, 新的在下"
#
#   ⑤ 把"对方发的、我没读的"标成已读
#
#   ⑥ 返回: 对方信息 + 消息列表 + has_more
#
#   前端拿到后:
#       - 从上往下渲染
#       - 自动滚到最底部 (显示最新一条)
#       - 想往上翻历史 → 带 ?before=最早那条的id 再要一批
#         (第一版可以不做)


# ------------------------------------------------------------
# ③ 发消息 POST /conversations/{user_id}/messages
#这个发消息只是发消息是吧，没有把消息获取到发送人这里的功能，
#就是说我要发一条消息就要用一次发消息api再搞一次上面的获取消息
# ------------------------------------------------------------
@router.post("/conversations/{user_id}/messages")
async def send_message(
    user_id: int,
    body: MessageIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    me = current_user["id"]

    # ① 不能发给自己
    if user_id == me:
        return {"error": "不能给自己发私信"}

    # ② 内容检查
    content = body.content.strip()
    if not content:
        return {"error": "消息不能为空"}
    if len(content) > MAX_MSG_LEN:
        return {"error": f"一条消息最多 {MAX_MSG_LEN} 字"}

    # ③ 对方得存在
    other = db.query(User).filter(User.id == user_id).first()
    if other is None:
        return {"error": "用户不存在"}

    # ④ 找/建会话
    conv = get_or_create_conversation(db, me, user_id)

    # ⑤ 插消息
    msg = Message(conversation_id=conv.id, from_user=me, content=content)
    db.add(msg)

    # ⑥ 更新会话的最后活跃时间 (会话列表按它排序)
    conv.last_message_at = datetime.now()

    db.commit()
    db.refresh(msg)

    # ★ 顺便把"刚创建的那条消息"完整返回。
    #   前端拿到后可以直接追加到聊天窗，不用再调一次 GET 拉列表。
    #   (created_at 是数据库生成的, 必须 refresh 后才有值)
    item = {
        "id": msg.id,
        "from_user": msg.from_user,
        "content": msg.content,
        "is_read": msg.is_read,
        "created_at": str(msg.created_at) if msg.created_at else "",
    }

    # ★ WebSocket 推送: 对方在线就立刻收到, 不在线就算了(下次打开拉历史)
    #   注意放在 commit 之后 —— 先落库, 再通知, 顺序跟 MQ 那条铁律一样
    await manager.send_to(user_id, {
        "type": "message",
        "conversation_id": conv.id,
        "item": item,
    })

    return {
        "message": "已发送",
        "conversation_id": conv.id,      # 第一次聊天时, 前端靠它跳进聊天页
        "item": item,
    }


# 【面试可以这么讲 · 发消息的返回设计】
#
#   ❌ 旧写法:
#        POST 只返回 { "message": "已发送", "id": 3 }
#        前端拿不到 content / created_at, 画不出气泡
#        → 只能再发一次 GET /conversations/{id}/messages 重新拉列表
#        → 发一条消息 = 2 次请求
#
#   ✅ 现在:
#        POST 直接返回刚创建的那条消息 item
#        → 前端 push 进列表, 立即上屏, 不用再拉
#        → 发一条消息 = 1 次请求
#
#   ★ 第一次聊天时, 这个返回还承担第二个职责:
#        会话是【发第一条消息时】才创建的, 前端在此之前没有会话 id。
#        所以返回里同时带 conversation_id ——
#        前端拿到后把 "野窗口" (/messages/new/{对方id})
#        替换成正式窗口 (/messages/{会话id})。
#
#   ★ 为什么用服务端返回的 created_at, 而不是前端本地 new Date():
#        两边时钟可能有偏差, 后续拉历史时消息顺序会对不上。
#        时间以数据库为准。


# ------------------------------------------------------------
# ④ 标记已读 PUT /conversations/{id}/read
# ------------------------------------------------------------
@router.put("/conversations/{conversation_id}/read")
def mark_conversation_read(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    me = current_user["id"]

    conv = get_my_conversation(db, conversation_id, me)
    if conv is None:
        return {"error": "会话不存在"}

    n = db.query(Message).filter(
        Message.conversation_id == conversation_id,
        Message.from_user != me,          # 只标对方发的
        Message.is_read == False,
    ).update({"is_read": True})
    db.commit()
    return {"message": "已读", "count": n}
