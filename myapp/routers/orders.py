# ============================================================
# routers/orders.py —— 付费文章: 下单 / 支付 / 我的订单
# ============================================================
# 【钱的流程】
#   创建订单 pending ──支付──▶ paid ──▶ 写 purchases (解锁)
#          │
#          └─ 30 分钟没付 ──MQ──▶ cancelled
#
# 【两条线, 一条同步一条异步】
#   同步 (用户马上要看到结果):
#       改订单状态 + 写购买记录 + 返回成功
#   异步 (晚一点没关系的):
#       作者收益入账、通知作者  ← 发到 payment.exchange, 由消费者去做
#
# ★ 为什么不把"解锁"也丢给 MQ?
#   因为用户付完钱会立刻刷新页面。如果解锁在队列里排队, 他会看到"已支付但你还没买"
#   —— 用户能立刻感知到的结果, 不能异步。
# ============================================================
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import Article, Order, Purchase, User
from schemas import OrderIn
from dependencies import get_current_user
from mq import ORDER_TTL_MS, publish_order_delay, publish_payment_success
from routers.balance import add_balance_log

router = APIRouter()

# 预览多少字 (没买的人只能看到这么多)
PREVIEW_LEN = 300


def has_purchased(db: Session, user_id: int | None, article_id: int) -> bool:
    """这个人有没有买过这篇文章。别的地方(文章详情)也调它。"""
    if user_id is None:
        return False
    return db.query(Purchase).filter(
        Purchase.user_id == user_id,
        Purchase.article_id == article_id,
    ).first() is not None


def make_preview(content: str) -> str:##content就是全文，我这里就是截出前300
    """付费文章给没买的人看的开头。"""
    content = content or ""
    if len(content) <= PREVIEW_LEN:
        return content
    return content[:PREVIEW_LEN] + "\n\n……（购买后可阅读全文）"


# ------------------------------------------------------------
# ① 创建订单 POST /orders  {article_id}
# ------------------------------------------------------------
@router.post("/orders")
def create_order(
    body: OrderIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    me = current_user["id"]

    article = db.query(Article).filter(
        Article.id == body.article_id,
        Article.is_public == True,
    ).first()
    if article is None:
        return {"error": "文章不存在或未公开"}
    if not article.is_paid or article.price <= 0:
        return {"error": "这篇文章是免费的"}
    if article.user_id == me:
        return {"error": "这是你自己的文章"}
    if has_purchased(db, me, article.id):
        return {"error": "你已经有这篇文章了"}

    # ★ 已经有一个待支付的订单 → 直接复用它, 别越点越多
    pending = db.query(Order).filter(
        Order.user_id == me,
        Order.article_id == article.id,
        Order.status == "pending",
    ).order_by(Order.id.desc()).first()
    if pending:
        return {
            "order_id": pending.id,
            "amount": pending.amount,
            "status": pending.status,
            "expire_at": str(pending.expire_at) if pending.expire_at else "",
            "reused": True,
        }

    now = datetime.now()
    order = Order(
        user_id=me,
        article_id=article.id,
        amount=article.price,          # ★ 金额快照: 以后作者改价, 这单不变
        status="pending",
        expire_at=now + timedelta(milliseconds=ORDER_TTL_MS),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    # ★ 提交之后再发 MQ: 万一发送失败, 订单已经存在, 只是少了"自动关单"
    #   (反过来的话: 消息发了, 事务回滚了 → 消费者去查一个不存在的订单)
    publish_order_delay(order.id)##开始调用mq

    return {
        "order_id": order.id,
        "amount": order.amount,
        "status": order.status,
        "expire_at": str(order.expire_at) if order.expire_at else "",
        "reused": False,
    }


# ------------------------------------------------------------
# ② 支付 POST /orders/{id}/pay   (模拟支付, 真实项目是第三方回调)
# ------------------------------------------------------------
@router.post("/orders/{order_id}/pay")
def pay_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    me = current_user["id"]

    # ★ with_for_update: 锁住这一行, 两个人同时点"支付"时排队处理
    order = db.query(Order).filter(
        Order.id == order_id,
        Order.user_id == me,           # ★ 只能付自己的订单
    ).with_for_update().first()
    if order is None:
        return {"error": "订单不存在"}

    # ★ 幂等: 重复点击"我付好了"、或者第三方重复回调, 都不能重复处理
    if order.status == "paid":
        return {"message": "已经支付过了", "article_id": order.article_id, "already": True}
    if order.status == "cancelled":
        return {"error": "订单已取消, 请重新下单"}

    # ★ 查余额: 也要锁行, 防止同一用户两笔订单同时扣款把余额扣穿
    user = db.query(User).filter(User.id == me).with_for_update().first()
    if user is None:
        return {"error": "用户不存在"}
    if user.balance < order.amount:
        return {"error": "余额不足, 请先充值"}

    order.status = "paid"
    order.paid_at = datetime.now()

    # ★ 扣款 + 记流水 (和订单状态、购买记录同一个事务)
    add_balance_log(db, user, -order.amount, "buy_article", order.id)

    # 写购买记录 = 解锁。已经买过就不重复插 (唯一约束是最后防线)
    if not has_purchased(db, me, order.article_id):
        db.add(Purchase(
            user_id=me,
            article_id=order.article_id,
            order_id=order.id,
        ))

    db.commit()

    # 异步: 作者收益 + 通知作者
    publish_payment_success(
        order_id=order.id,
        user_id=me,
        article_id=order.article_id,
        amount=order.amount,
    )

    return {"message": "支付成功", "article_id": order.article_id, "already": False}


# ------------------------------------------------------------
# ③ 我的订单 GET /my/orders
# ------------------------------------------------------------
@router.get("/my/orders")
def my_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Order, Article.title)
        .join(Article, Article.id == Order.article_id)
        .filter(Order.user_id == current_user["id"])
        .order_by(Order.id.desc())
        .limit(100)
        .all()
    )
    return {
        "items": [
            {
                "id": o.id,
                "article_id": o.article_id,
                "title": title,
                "amount": o.amount,
                "status": o.status,
                "created_at": str(o.created_at) if o.created_at else "",
                "paid_at": str(o.paid_at) if o.paid_at else "",
            }
            for o, title in rows
        ]
    }


# ------------------------------------------------------------
# ④ 我买过的文章 GET /my/purchases
# ------------------------------------------------------------
@router.get("/my/purchases")
def my_purchases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(Purchase, Article)
        .join(Article, Article.id == Purchase.article_id)
        .filter(Purchase.user_id == current_user["id"])
        .order_by(Purchase.id.desc())
        .all()
    )
    return {
        "items": [
            {
                "article_id": a.id,
                "title": a.title,
                "author": a.user_id,
                "created_at": str(p.created_at) if p.created_at else "",
            }
            for p, a in rows
        ]
    }
