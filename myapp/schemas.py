# ============================================================
# schemas.py - Pydantic 模型 (定义"前端传什么、返回什么"的格式)
# 注意: 跟 models.py 不同!
#   models.py  = 数据库的表结构 (ORM)
#   schemas.py = 网络接口的数据格式 (前端↔后端传的数据)
# ============================================================
# 【我的理解】
#   这个文件不是单纯作为"注释"提醒后端人员前端发送的格式怎么样,
#   而是【必须在这里写这些东西, 建立好类】!
#   因为我的 fastapi  def login(user: UserLogin, ...) 这种地方,
#   才会自动用 UserLogin 的标准去识别前端传过来的请求内容,
#   然后我后面也好在代码里面用我规定的这些类 (user.username / user.password)。
#   用途分两类: 输入格式 (UserRegister/UserLogin) + 输出格式 (UserOut)
# ============================================================
# 【校验不过会怎样】实测过的几种情况 (往 POST /articles/1/comments 发, 它要 CommentIn{content: str})
#   {"content": "正常评论"}                → ✅ 通过
#   {"text": "字段名写错"}                  → ❌ 422  (少字段)
#   {"content": 12345}                     → ❌ 422  (类型错)
#   ["a", "b"]                             → ❌ 422  (根本不是对象)
#   {content: 没有引号}                     → ❌ 422  (不是合法 JSON)
#   {"content": "正常", "author": "张三"}   → ✅ 通过! (多传的字段被静默忽略)
#
# ★ 关键: 校验不过时, FastAPI 【在进你的函数之前】就返回 422 了, 你的函数一行都不执行。
#     不会出现"字段不对就强行拿第一个用"这种事 —— Pydantic 只判"合规/不合规", 不猜你的意思。
#     422 的响应体长这样: {"detail": [{loc: 哪个字段, msg: 怎么了}]}
#     ⚠️ 注意里面【没有 error 字段】, 所以前端那套 if (res.data.error) 对 422 无效,
#        它会被 axios 当异常抛出, 走 catch 分支。
#
# ⚠️ 规矩是"至少要给这些", 不是"只能给这些" —— 多传的字段会被忽略, 不报错。
#    想改成"多一个就拒绝": model_config = {"extra": "forbid"}
# ============================================================
from pydantic import BaseModel


# ---------- 注册时, 前端要传的格式 ----------
class UserRegister(BaseModel):
    username: str
    password: str

# ---------- 登录时, 前端要传的格式 ----------
class UserLogin(BaseModel):
    username: str
    password: str

# ---------- 返回给前端的用户信息 ----------
class UserOut(BaseModel):
    id: int
    username: str
    # ⚠️ 注意: 这里【没有 password_hash】!
    # 永远不要把密码(哪怕加密后的)返回给前端

    class Config:
        from_attributes = True   # 允许"从 ORM 对象(User)自动转成这个格式"


# ---------- 允许的文章分类 ----------
# ⚠️ 前端也有一份一样的一份 (要画下拉框)。改了记得两边同步!
# 想加分类就加到这里 —— 但因为"分类"是平台定的, 改动不频繁, 所以先不做成接口。
CATEGORIES = ["前端", "后端", "AI", "其他"]


# ---------- 发文章时, 前端要传的格式 ----------
class ArticleIn(BaseModel):
    title: str
    content: str = ""            # 内容可以不填(默认空字符串)
    is_public: bool = False      # 公开/私有, 默认私有
    # ★ 分类: 空字符串 = 没分类。
    #   允许空是为了兼容从前端还不传这个字段的老代码, 而且"没分类"是个合法状态。
    category: str = ""

# ---------- 返回给前端的文章 ----------
class ArticleOut(BaseModel):
    id: int
    title: str
    content: str
    user_id: int                 # 作者的用户 id
    is_public: bool              # 是否公开

    class Config:
        from_attributes = True


# ---------- 发评论时, 前端要传的格式 ----------
class CommentIn(BaseModel):
    content: str                 # 评论内容

    # ★ 只有这两个字段是"前端说"的; 其余全是后端自己算的
    #   (user_id 从 token 拿; root_id / parent_id / reply_to_user_id
    #    从"被回复的那条评论"推出来 —— 前端【不用管拍平规则】)
    reply_to_comment_id: int | None = None
    #   不传 / 传 null  →  发一条【顶层评论】
    #   传 9102         →  回复 9102 这条评论 (不管 9102 是根还是回复)

# ---------- 返回给前端的评论 ----------
class CommentOut(BaseModel):
    id: int
    content: str
    user_id: int
    article_id: int

    class Config:
        from_attributes = True


# ---------- 收藏夹 ----------
class CollectionIn(BaseModel):
    name: str                    # 收藏夹名字

class FavoriteIn(BaseModel):
    article_id: int              # 收藏哪篇
    collection_id: int           # 放进哪个夹子


# ---------- 建议反馈 ----------
class FeedbackIn(BaseModel):
    content: str                 # 反馈内容 (必填)
    contact: str = ""            # 联系方式 (选填, 不写就是空字符串)


# ---------- 改个人资料 (PUT /me) ----------
class ProfileIn(BaseModel):
    avatar: str = ""             # 头像地址 (先只支持填 URL, 以后再做上传)
    bio: str = ""                # 个人简介

    # ★ username 用 str | None = None, 不是 str = ""
    #   区别很大:
    #     avatar/bio 是 str = ""  → 不传 = 改成空字符串 (会被清掉)
    #     username 是 None        → 不传 = None    → 代码里判断"没传就不动它"
    #   为什么 username 要特殊? 因为它【不能为空】(NOT NULL + 唯一)
    #   如果用 "" 当默认值, 前端只想改简介的时候会把用户名清空 → 数据坏了
    username: str | None = None  # 不传 = 不改用户名
