# ============================================================
# routers 包 —— 按"功能"把接口分装到几个文件里
# ============================================================
# 【它是啥】
#   一个文件夹里放了几个"小号 app"。
#   以前 20 个接口全挤在 main.py 里 (@app.xxx), 现在按功能分成三份:
#       users.py        用户: 注册 / 登录 / 我的信息
#       articles.py     文章 + 评论
#       collections.py  收藏夹 + 收藏
#
# 【怎么工作的】
#   每个文件里造一个小号 app:  router = APIRouter()
#   然后那边写成 @router.post("/register")  (从 @app 改成 @router, 别的没变)
#   最后 main.py 里挂上去:     app.include_router(users.router)
#
#   include_router = "把那个小号 app 里登记的地址, 全都并到我这来"
#
# 【前端有感觉吗】没有。地址一个都没变, 还是 POST /register、GET /my/collections。
#   改动纯粹在文件层面 —— 把 20 行 @app.xxx 分装到 3 个盒子里。
#
# 【这个 __init__.py 是干嘛的】
#   一个空文件, 作用是告诉 Python "routers 是个包" (包 = 能被 import 的文件夹)。
#   有了它, main.py 里才能写 from routers import users。
