# ============================================================
# routers/feedback.py —— 建议反馈
# ============================================================
# 这是"加新功能 = 加新文件"的一次示范:
#   新功能不用往 users.py / articles.py 里塞, 自己开一个文件,
#   然后在 main.py 里 include_router 挂上去就行。
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User, Feedback
from schemas import FeedbackIn
from dependencies import get_current_user

router = APIRouter()


# ---------- 提交建议反馈 POST /feedback (需登录) ----------
@router.post("/feedback")
def create_feedback(
    fb: FeedbackIn,
    current_user: User = Depends(get_current_user),   # 需登录: 记下是谁提的
    db: Session = Depends(get_db),
):
    # ★ 后端再校验一次"不能为空"
    #   前端也会校验（空的不让提交），但那只是"用户体验"。
    #   别人可以用 curl 绕过前端直接发请求, 所以后端必须自己查一遍。
    #   —— 这条规矩永远成立: 【前端校验是体验, 后端校验才是安全】
    if not fb.content.strip():
        return {"error": "反馈内容不能为空"}

    new = Feedback(
        content=fb.content.strip(),          # strip 去掉首尾空格/换行
        contact=fb.contact.strip(),          # 联系方式选填, 不填就是空字符串
        user_id=current_user["id"],          # ★ 谁提的自动填当前登录用户, 不从前端来
    )
    db.add(new)
    db.commit()
    db.refresh(new)

    return {"message": "感谢反馈！", "id": new.id}
