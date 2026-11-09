# ============================================================
# routers/balance.py —— 站内余额
# ============================================================
# 【两条接口】
#   GET  /my/balance          看余额 + 最近流水
#   POST /my/balance/recharge 模拟充值 (真实项目接支付渠道, 这里直接加钱)
#
# 【钱的三条铁律】
#   ① 余额用整数(分)存, 不用浮点
#   ② 改余额必须同时写流水 —— 只改数不留账, 出问题对不出来
#   ③ 改余额要锁行 (with_for_update), 否则两个人同时扣会扣穿
# ============================================================
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import BalanceLog, User
from schemas import RechargeIn
from dependencies import get_current_user

router = APIRouter()

# 单次模拟充值上限: 1000 元 = 100000 分 (防止手滑充一个亿)
MAX_RECHARGE = 100_000


def add_balance_log(db: Session, user: User, amount: int, reason: str, order_id: int | None = None):
    """改余额 + 记一条流水 (调用方负责 commit)。

    ★ 余额和流水必须在同一个事务里, 不能只改一个。
    """
    user.balance += amount
    db.add(BalanceLog(
        user_id=user.id,
        amount=amount,
        reason=reason,
        order_id=order_id,
        balance_after=user.balance,
    ))


@router.get("/my/balance")
def my_balance(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    me = current_user["id"]
    u = db.query(User).filter(User.id == me).first()
    if u is None:
        return {"error": "用户不存在"}

    logs = (
        db.query(BalanceLog)
        .filter(BalanceLog.user_id == me)
        .order_by(BalanceLog.id.desc())
        .limit(20)
        .all()
    )

    return {
        "balance": u.balance,
        "items": [
            {
                "id": l.id,
                "amount": l.amount,              # 正数进账, 负数出账
                "reason": l.reason,
                "order_id": l.order_id,
                "balance_after": l.balance_after,
                "created_at": str(l.created_at) if l.created_at else "",
            }
            for l in logs
        ],
    }


@router.post("/my/balance/recharge")
def recharge(
    body: RechargeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    me = current_user["id"]

    if body.amount <= 0:
        return {"error": "充值金额必须大于 0"}
    if body.amount > MAX_RECHARGE:
        return {"error": f"单次最多充值 {MAX_RECHARGE // 100} 元"}

    # ★ 锁住这一行: 两个人同时充值/扣款时, 排队执行, 不会算错
    u = db.query(User).filter(User.id == me).with_for_update().first()
    if u is None:
        return {"error": "用户不存在"}

    add_balance_log(db, u, body.amount, "recharge")
    db.commit()

    return {"message": "充值成功", "balance": u.balance}
