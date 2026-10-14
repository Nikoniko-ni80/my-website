# ============================================================
# main.py - 应用的"总装车间"
# 运行: python -m uvicorn main:app --reload
# 测试: http://127.0.0.1:8000/docs
# ============================================================
# 【这个文件现在只干三件事】
#   ① 造出那个大 app
#   ② 给 app 装上 CORS 中间件
#   ③ 把 routers/ 里那三个"小号 app"挂上来 (include_router)
#
# 【接口都去哪了】
#   以前 20 个接口全堆在这个文件里 (500 多行), 现在按功能分装了:
#       routers/users.py        用户: 注册 / 登录 / 我的信息
#       routers/articles.py     文章 + 评论
#       routers/collections.py  收藏夹 + 收藏
#
# 【include_router 在干嘛】
#   每个 routers/*.py 里都有一个 router = APIRouter(), 那是个"小号 app",
#   它自己也登记了一批地址 (写的是 @router.post("/register") 这种)。
#   下面那三行, 就是把三个小号各自登记的地址【并到】大 app 里来。
#
#   结果: 前端看到的地址一个都没变 —— 还是 POST /register、GET /my/collections。
#   这次重构纯粹是文件层面的搬家, 行为一模一样。
# ============================================================
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import users, articles, collections, feedback, history, follows
# ⚠️ 这行跟上面两行【不一样】: 上面是别人写的库(pip 装的), 这个是【我自己写的文件夹】
#   一个文件夹 + 里面有 __init__.py  =  包  =  可以被 import
#   所以 users 就是 routers/users.py 那个文件; 用它的东西要写 users.router
#   (能找得到是因为: 你从 myapp/ 目录启动, 所以 myapp/ 在 Python 的查找路径里)

app = FastAPI()

# 允许跨域 (CORS): 前端(5173端口) 跟后端(8000端口) 不同源, 浏览器默认禁止跨端口请求,
# 加了这段中间件, 后端就"允许"前端的请求了
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # 学习用: 允许所有来源 (生产环境要写具体的前端域名)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- 把三个"小号 app"挂上来 ----------
# 挂的顺序不影响功能 (地址各是各的, 不会撞车)。
# 这里按"用户 → 内容 → 收藏"排, 跟业务上从基础到复杂的顺序一致, 看着顺。
app.include_router(users.router)
app.include_router(articles.router)
app.include_router(collections.router)
app.include_router(feedback.router)
app.include_router(history.router)
app.include_router(follows.router)
