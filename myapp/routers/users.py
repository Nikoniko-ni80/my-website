# ============================================================
# routers/users.py —— 用户相关接口 (注册 / 登录 / 我的信息)
# ============================================================
# 从 main.py 搬过来的, 代码本身一个字没改, 只把 @app 换成了 @router
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User, Article, Follow
from schemas import UserRegister, UserLogin, ProfileIn
from cache import redis_client          # ★ 改用户名后要清这个缓存
from auth import hash_password, verify_password, create_token
from dependencies import get_current_user

# 小号 app: 只登记这个文件里的 3 个地址
router = APIRouter()


# ---------- 注册接口 POST /register ----------
@router.post("/register")
def register(user: UserRegister, db: Session = Depends(get_db)):
    # 参数说明:
    #   user: UserRegister  → FastAPI 读"类型注解", 从请求体收数据 + 校验
    #   db: Depends(get_db) → FastAPI 去调 get_db 拿会话, 用完自动关。
    #        (前端从不传 db; 不是"有就用没有就调", 而是【永远】去调 get_db)
    #        背后: FastAPI 后台做 gen=get_db() → next(gen) 拿到会话 → 用完 → close() 触发 finally 关。
    #        分工: "怎么开会话/关会话"写在 get_db 里, "啥时候调/关"由 FastAPI 管。
    #   总结: user 靠"类型注解"从请求来, db 靠"Depends"让框架造。

    # ① 先检查用户名有没有被注册过
    exists = db.query(User).filter(User.username == user.username).first()
    # query意思是“查询”后面括号里面就是哪张表
    if exists:
        return {"error": "用户名已存在"}

    # ② 把密码加密 (存哈希, 不存明文)
    hashed = hash_password(user.password)

    # ③ 用 User 类造一个用户对象
    new_user = User(username=user.username, password_hash=hashed)

    # ④ 存进数据库
    db.add(new_user)      # 加进会话
    db.commit()           # 提交(真正写库)

    # ⑤ 返回成功 (注意: 不返回密码)
    return {"message": "注册成功", "username": new_user.username}


@router.post("/login")
def login(user: UserLogin , db: Session=Depends(get_db)):
    exists= db.query(User).filter(User.username==user.username).first()
    if not exists:
        return{"error":"用户不存在,请注册"}
    bool=verify_password(user.password,exists.password_hash)
    if not bool:
        return{"error":"密码错误"}
    token=create_token(exists.id)
    return{"message":"登陆成功","token":f"{token}"}


# ---------- 受保护接口 GET /me (我的信息, 必须带 Token) ----------
@router.get("/me")
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # current_user = get_current_user 验完 token 后返回的 dict (只有 id + username)
    #
    # ⚠️ 但它是个【缓存过的精简版】—— get_current_user 里只往 Redis 存了 id 和 username。
    #    要拿头像/简介这些, 得自己再查一次数据库。
    u = db.query(User).filter(User.id == current_user["id"]).first()
    if u is None:
        return {"error": "用户不存在"}

    return {
        "id":         u.id,
        "username":   u.username,
        "avatar":     u.avatar,
        "bio":        u.bio,
        "created_at": str(u.created_at) if u.created_at else "",
        # ★ 下面两个是"只给自己看"的, 别人的主页不给 (见 get_user)
        "is_admin":   u.is_admin,
        # ★ "是不是 VIP" 永远【现算】, 不存布尔 —— 时间是会自己走的, 不需要定时任务
        "is_vip":     bool(u.vip_expire_at and u.vip_expire_at > datetime.now()),
        "vip_expire_at": str(u.vip_expire_at) if u.vip_expire_at else None,
    }


# ---------- 看别人的主页 GET /users/{id} (不用登录) ----------
# 【公开接口】—— 分享主页链接给没登录的人, 也该能看
@router.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.id == user_id).first()
    if u is None:
        return {"error": "用户不存在"}

    # 他的【公开】文章 (私密的别人看不到)
    arts = (
        db.query(Article)
        .filter(Article.user_id == user_id, Article.is_public == True)
        .order_by(Article.id.desc())
        .all()
    )

    return {
        "id":         u.id,
        "username":   u.username,
        "avatar":     u.avatar,
        "bio":        u.bio,
        "created_at": str(u.created_at) if u.created_at else "",
        "articles": [
            {"id": a.id, "title": a.title, "content": a.content,
             "created_at": str(a.created_at)}
            for a in arts
        ],
        "article_count": len(arts),
        # ★ 关注数 / 粉丝数: 都是【现算】的, 不存列
        #   "他关注了谁"  → 查 follows 里 user_id == 他
        #   "谁关注了他"  → 查 follows 里 target_user_id == 他
        #   这两个用了 follows 的【唯一索引 (user_id, target_user_id)】
        #   也能用它的【最左前缀 user_id】, 都是走索引的, 很快
        "following_count": db.query(Follow).filter(Follow.user_id == user_id).count(),
        "follower_count":  db.query(Follow).filter(Follow.target_user_id == user_id).count(),
    }
    # ⚠️ 故意【不返回】这三样:
    #     password_hash  —— 密码永远不出口
    #     is_admin       —— 别人的管理权限不该公开
    #     vip_expire_at  —— 别人的充了多久跟你无关 (以后要显示"他是VIP"就单独加个 is_vip)


# ---------- 改自己的资料 PUT /me (需登录) ----------
@router.put("/me")
def update_me(
    profile: ProfileIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    u = db.query(User).filter(User.id == current_user["id"]).first()
    if u is None:
        return {"error": "用户不存在"}

    # ★ 只改【自己的】资料, 所以不用传 user_id —— 从 token 里拿 current_user["id"]。
    #   如果让前端传 user_id, 别人就能改你的资料了。
    u.avatar = profile.avatar.strip()
    u.bio    = profile.bio.strip()

    # ---------- 用户名: 只有【明确传了】才动它 ----------
    # profile.username 默认是 None, 表示"这次请求没提改名的事"
    # (avatar/bio 用的是 "", 所以每次都会被覆盖 —— 那两个允许被清空)
    renamed = False
    if profile.username is not None:
        new_name = profile.username.strip()

        if not new_name:
            return {"error": "用户名不能填空白"}

        if new_name != u.username:
            # ★ 查重: username 在数据库里有【唯一约束】。
            #   不查的话, 撞名会直接被数据库拒绝, 报一个很难看的 500。
            #   自己先查一遍, 就能返回一句人话。
            taken = db.query(User).filter(
                User.username == new_name, User.id != u.id
            ).first()
            if taken:
                return {"error": "这个用户名已经有人用了"}

            u.username = new_name
            renamed = True

    db.commit()

    # ★★★ 关键的一步: 改了用户名, 必须清掉 Redis 里的用户缓存
    #   get_current_user 会把 {"id", "username"} 缓存 5 分钟 (dependencies.py)
    #   不清的话, 这 5 分钟里所有用 current_user["username"] 的接口
    #   返回的还是【旧名字】—— 数据库改了, 接口没改, 出了名的难查
    #
    #   ⚠️ 为什么 avatar/bio 不用清? 因为它们【没被缓存】。
    #      原则: 被缓存过的数据, 改的时候都是"改库 + 清缓存"两件事。
    if renamed:
        redis_client.delete(f"user:{u.id}")

    return {"message": "已保存", "avatar": u.avatar, "bio": u.bio,
            "username": u.username}
