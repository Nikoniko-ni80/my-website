# ============================================================
# routers/history.py —— 浏览历史
# ============================================================
# 记住"谁看过哪篇文章"。
#   同一个人 + 同一篇文章, 只留【一条】记录 (看第二遍就更新时间, 不新增)
#   这个操作有个名字叫 upsert = update + insert = "有就更新, 没有就插入"
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User, Article, History
from dependencies import get_current_user

router = APIRouter()


# ---------- 记录一次浏览 POST /history/{article_id} (需登录) ----------
# 前端每次打开文章详情页就调一次。
# 注意: 前端是【静默调用】的 —— 这个请求失败不能影响文章打开,
#       毕竟"记不上浏览历史"是小事, "文章打不开"是大事。
@router.post("/history/{article_id}")
def add_history(
    article_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 文章存在吗?
    art = db.query(Article).filter(Article.id == article_id).first()
    if art is None:
        return {"error": "文章不存在"}

    # ★ upsert: 先找找看这个人看过这篇没有
    row = db.query(History).filter(
        History.user_id == current_user["id"],
        History.article_id == article_id,
    ).first()

    if row:
        # 看过 → 只把时间改成现在 (不新增一条)
        row.viewed_at = datetime.now()
    else:
        # 没看过 → 插一条新的
        db.add(History(user_id=current_user["id"], article_id=article_id))

    db.commit()
    return {"message": "ok"}


# ---------- 我的浏览历史 GET /my/history (需登录) ----------
@router.get("/my/history")
def list_history(
    limit: int = 50,                  # 最多给几条 (历史可能很多, 先卡个上限)
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = (
        # 查三样: 文章对象 + 作者名 + 看的时间
        #   ★ 注意 History.viewed_at 是【某一列】, 所以循环里 f 直接就是 datetime, 不用再 .viewed_at
        db.query(Article, User.username, History.viewed_at)
        .join(History, History.article_id == Article.id)
        .join(User, Article.user_id == User.id)
        .filter(History.user_id == current_user["id"])
        .order_by(History.viewed_at.desc())      # 最近看的在最前面
        .limit(limit)
        .all()
    )
    return [
        {"id": a.id, "title": a.title, "content": a.content,
         # ★ user_id 是给前端做"点作者名跳个人主页"用的
         "user_id": a.user_id, "author": u, "viewed_at": str(f)}
        for a, u, f in rows
    ]


# ---------- 清空浏览历史 DELETE /my/history (需登录) ----------
@router.delete("/my/history")
def clear_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.query(History).filter(
        History.user_id == current_user["id"]
    ).delete()
    db.commit()
    return {"message": f"已清空 {n} 条浏览记录"}
##这里n是删除的返回值(返回几条),后面就是
