# ============================================================
# dependencies.py - 放"由框架来调用"的函数 (FastAPI 管它们叫"依赖")
# ============================================================
# 【怎么认出这个文件里的函数】看调用它的时候加不加括号
#     我自己调:  hashed = hash_password("123456")           ← 有括号, 我主动调, 立刻拿结果
#     交给框架:  current_user = Depends(get_current_user)   ← ★ 没括号!
#   "没括号"的意思是: 不是"我调它", 而是把函数本身递给 FastAPI, 说
#     "请求来的时候你帮我调它, 把它返回的东西塞进 current_user"
#   (这个模式叫"控制反转", 外号"好莱坞原则": 别打电话给我们, 我们会打给你)
#
# 【跟 auth.py 的区别 —— 分界线是"谁调谁", 不是"碰不碰网络/数据库"】
#     auth.py         = 我的工具. 我调它们, 它们不知道外面有 HTTP
#                       (打开 auth.py 看: 连 import fastapi 都没有)
#     dependencies.py = 框架的工具. 框架调它们,
#                       任务是"从请求里挖出路由需要的东西"
#
# 【因为是框架在调, 这类函数有几条特殊规矩】
#   ① 参数能从"请求"里挖:   authorization: str = Header(...)
#   ② 参数能再要别的依赖:   db: Session = Depends(get_db)   ← 依赖能套娃
#   ③ 报错就抛 HTTPException, 框架自动把它变成 HTTP 401 响应 (不用自己拼响应)
#   ④ 你很难自己调它 —— 得先把它的依赖一个个准备好 (自己开会话、自己从
#      headers 里取 Authorization、用完自己关会话), 这些框架全包了
#
# 【判断一个新函数该不该放这】三个问题, 有一个"是"就说明不该放:
#   1. 它 import fastapi 了吗?               没有 → 不是依赖
#   2. 我调用它的时候加括号吗?                加   → 不是依赖
#   3. 参数里全是 Depends/Header/Query 吗?    不是 → 不是依赖
#   三个都否 → 那是普通函数: 碰数据库的进 crud.py, 纯逻辑的进 auth.py 这类工具文件
# ============================================================
import json
# json(库) 跟 JSON(格式) 是两回事: JSON 是"一种文本格式", json 是 Python 自带的"处理它的工具库"
#   你 lesson3 学过: json.dumps = 字典→JSON字符串 ; json.loads = JSON字符串→字典
#   这里用它的原因: Redis 只能存字符串, dict 要先 json.dumps 成字符串才能存进 Redis
#   (取出来时用 json.loads 转回 dict —— 一存一取, 正好一对)
from fastapi import Header, HTTPException, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User
from auth import decode_token
from cache import redis_client


# ---------- 验 Token 的依赖 (受保护接口用它) ----------
# 本函数就是得到前端的信息后验证是不是有token并解码
# 然后查询（redis再sql)然后返回查询的userid name
def get_current_user(
    authorization: str = Header(...),     # 从请求头 Authorization 里拿值
    db: Session = Depends(get_db),        # 依赖里也能再依赖 get_db
):
    # ① 前端传的是 "Bearer xxxxx", 去掉前缀取出纯 token
    token = authorization.replace("Bearer ", "")

    # ② 验 token + 解出 user_id (无效/过期会抛异常 → 转成 401)
    try:
        payload = decode_token(token)
        user_id = payload["user_id"]
    except Exception:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    # ③ 先查 Redis 缓存 (key = "user:4")
    cache_key = f"user:{user_id}" #定义4号，用这个东西来redis_client查
    cached = redis_client.get(cache_key) #用get方法查找redis
    if cached:
        # 缓存命中! 直接返回 (不查 MySQL, 快!)
        return json.loads(cached)          # 返回的是 dict

    # ④ 缓存没命中 → 查 MySQL
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")

    # ⑤ 存进 Redis (5分钟后过期) → 下次请求就能命中缓存
    user_data = {"id": user.id, "username": user.username}
    redis_client.set(cache_key, json.dumps(user_data), ex=300)
    #(标号，内容(json.dumps转格式),存储时间)

    return user_data                        # 统一返回 dict (缓存和查库都返回这个)


# ---------- 【可选登录】的依赖 ----------
# 跟 get_current_user 的唯一区别: 那个"没登录就 401", 这个"没登录就返回 None"。
#
# 【用在哪】"登录了能多看一点, 不登录也能看"的接口。
#   最典型的就是【评论列表】:
#       不登录  →  能看评论 (B站/知乎都这样)
#       登录了  →  还能顺便知道"这条评论我能不能删" (返回 can_delete)
#
# 【⚠️ 为什么不能直接用 get_current_user】
#   评论列表是公开接口, 没登录的人也该能看。
#   如果用 get_current_user, 没登录的人一打开文章页就 401 了 —— 显然不行。
#
# 【⚠️ 注意 Header(None) 不是 Header(...)】
#   Header(...) 的意思是"这个请求头必须带" —— 请求头完全没带时,
#   FastAPI 在【进我们这个函数之前】就直接返回 422 了, 根本轮不到我们判断。
#   写 Header(None) 才是"可选的", 我们才能自己决定"没有就返回 None"。
#
# 【⚠️ 这里有一小段代码跟 get_current_user 重复了】
#   故意没抽出来共用的 —— 因为 get_current_user 是所有受保护接口的必经之路,
#   动它风险大。宁可重复这 10 行, 也不去碰那条热点路径。
#   (以后要重构再说)
def get_current_user_optional(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
):
    # 没带 token → 就是"游客", 返回 None (不报错)
    if not authorization:
        return None

    token = authorization.replace("Bearer ", "")

    try:
        payload = decode_token(token)
        user_id = payload["user_id"]
    except Exception:
        return None                      # ★ token 坏了也当游客, 不报 401

    cache_key = f"user:{user_id}"
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        return None

    user_data = {"id": user.id, "username": user.username}
    redis_client.set(cache_key, json.dumps(user_data), ex=300)
    return user_data


# 说明: 现在 get_current_user 返回的是 dict 而不是 User 对象,
#   因为"从缓存拿到的"是 JSON(转成 dict), "从数据库拿到的"也统一转成 dict —— 保持一致.
#   所以接口里用 current_user["id"] 而不是 current_user.id
