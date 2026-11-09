# ============================================================
# consumers.py —— MQ 的消费者
# ============================================================
# 三个消费者, 各干各的:
#   ① order.expire.queue   30 分钟后: 还是待支付 → 取消
#   ② earning.queue        支付成功: 给作者记一笔收益
#   ③ notify.queue         支付成功: 给作者发一条通知
#
# 【重要: 每个消费者都必须是幂等的】
#   RabbitMQ 承诺的是"至少一次", 同一条消息可能来两遍 (网络抖动、重连、重投)。
#   处理两遍和处理一遍结果一样, 才叫幂等。
#     ② 靠 earnings.order_id 的唯一约束
#     ③ 靠"查有没有发过"去重
#     ① 天然幂等: status 从 pending 改成 cancelled, 改两次结果一样
# ============================================================
from database import SessionLocal
from models import Article, Earning, Notification, Order, User
from mq import (EARNING_QUEUE, EXPIRE_QUEUE, NOTIFY_QUEUE,
                start_consumer)
from routers.notifications import notify
from routers.balance import add_balance_log


##注意，整体是由broker来推
# 作者分成 80% (剩下的算平台服务费)
AUTHOR_RATE = 0.8


def handle_order_expire(payload: dict):
    ##payload就是mq.py 的 on_message 里
    ##payload = json.loads(body)  这个具体内容的json封装
    """30 分钟到了: 订单还是待支付就取消。"""
    order_id = payload.get("order_id")##搞到json里面的order_id值
    if not order_id:
        return

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order is None:
            print(f"[关单] 订单 {order_id} 不存在, 跳过")
            return
        if order.status != "pending":
            # 已经付了 / 已经取消 → 什么都不做 (这就是幂等)
            print(f"[关单] 订单 {order_id} 状态是 {order.status}, 跳过")
            return
        ##！！！幂等！！！！
        #幂等 = 同一个操作做一次和做很多次，结果一样。
        #查余额：查 1 次、查 10 次，余额不变   → 幂等
       # 100 元：扣 1 次、扣 10 次，钱少 1000 → 不幂等
       # 但是mq里面会有多次反复发送的机制，所以我要应用层不断验证诸如“这一单是不是有？”等等检验 
        order.status = "cancelled"
        db.commit()
        print(f"[关单] 订单 {order_id} 超时未支付, 已取消")
    finally:
        db.close()


def handle_payment_earning(payload: dict):
    """支付成功: 给作者记一笔收益。"""
    order_id = payload.get("order_id")
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order is None or order.status != "paid":
            print(f"[收益] 订单 {order_id} 状态不对, 跳过")
            return

        # 幂等第一道: 先查有没有记过
        if db.query(Earning).filter(Earning.order_id == order_id).first():
            print(f"[收益] 订单 {order_id} 已经记过, 跳过")
            return

        article = db.query(Article).filter(Article.id == order.article_id).first()
        if article is None:
            return

        amount = int(order.amount * AUTHOR_RATE)
        db.add(Earning(
            user_id=article.user_id,
            order_id=order.id,
            article_id=article.id,
            amount=amount,
        ))

        # ★ 作者余额入账 + 记流水, 和 Earning 在同一个事务里。
        #   如果 Earning 撞上 order_id 唯一约束, 整个事务回滚,
        #   余额也不会被重复加 —— 幂等靠这一层兜底。
        author = db.query(User).filter(User.id == article.user_id).with_for_update().first()
        if author is not None:
            add_balance_log(db, author, amount, "article_income", order.id)

        db.commit()
        print(f"[收益] 订单 {order_id}: 作者 {article.user_id} +{amount} 分")
    except Exception:
        db.rollback()
        raise          # 抛出去, 让 mq.py 决定重试


def handle_payment_notify(payload: dict):
    """支付成功: 告诉作者"有人买了你的文章"。"""
    order_id = payload.get("order_id")
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if order is None or order.status != "paid":
            return

        article = db.query(Article).filter(Article.id == order.article_id).first()
        buyer = db.query(User).filter(User.id == order.user_id).first()
        if article is None:
            return

        link = f"/article/{article.id}"

        # 幂等: 同一个人对同一篇文章只会买一次, 所以按这三样去重就够
        exists = db.query(Notification).filter(
            Notification.user_id == article.user_id,
            Notification.from_user == order.user_id,
            Notification.type == "payment",
            Notification.link == link,
        ).first()
        if exists:
            print(f"[通知] 订单 {order_id} 已经通知过, 跳过")
            return

        notify(
            db,
            to_user=article.user_id,
            type="payment",
            content=f"{buyer.username if buyer else '有人'} 购买了你的文章《{article.title}》",
            link=link,
            from_user=order.user_id,
        )
        db.commit()
    finally:
        db.close()


def start_consumers():
    """在 main.py 的 lifespan 里调一次, 把三个消费者线程点着。"""
    start_consumer(EXPIRE_QUEUE, handle_order_expire, "order-expire")
    start_consumer(EARNING_QUEUE, handle_payment_earning, "payment-earning")
    start_consumer(NOTIFY_QUEUE, handle_payment_notify, "payment-notify")
