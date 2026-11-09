# ============================================================
# sse.py —— SSE: 通知的"服务器主动推"
# ============================================================
# 【和 ws.py 的区别】
#   私信要双向 → WebSocket
#   通知只要服务器说、浏览器听 → SSE (更简单, 浏览器自带断线重连)
#
# 【"永不结束"是什么意思 —— 不封口】
#   请求(GET /events) 就是普通的一封信, 发一次就完了。
#   不结束的是【响应】:
#     服务器回了 200 + 响应头, 然后正文一直写、一直不"封口"。
#   HTTP/1.1 用 chunked 分块发送, 正常最后会发一个 0 长度块表示"正文结束";
#   SSE 永远不发这个结束块 → 这条响应一直开着 → 服务器随时能再写一段。
#   比喻: 点了一杯"无限续杯"—— 点单(请求)只说一次, 杯子(响应)一直不撤。
#   结束条件: 服务器关连接 / 浏览器关页面 / 断网 / 后端重启。
#
# 【一次连接长什么样】
#   浏览器: GET /events?token=xxx   (EventSource, 不能带自定义请求头, 所以 token 在网址里)
#   服务器: 不结束响应, 一直往里写
#             data: {"type":"notification"}
#             data: {"type":"notification"}
#
# 【推的是什么】
#   只推一个"信号", 不推通知内容。
#   前端收到信号 → 重新拉 unread-count / 列表。
#   好处: 就算事务回滚多推了一次, 前端刷新后看到的是数据库的真相, 不会显示错误数据。
#
# ★ 只在单进程有效 (队列在内存里); 多实例要 Redis pub/sub。
# ============================================================
import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ws import user_from_token

router = APIRouter()

# 事件循环: 在 main.py 启动时存下来
_loop: asyncio.AbstractEventLoop | None = None
#模块加载时是空的。类型标注 asyncio.AbstractEventLoop | None 只是说明"以后会放一个循环进来"

# 每个在线用户一组队列 (一个用户可能开好几个标签页, 一个页面一个队列)
#
# ★★ 重点: 队列里装的是【信号】, 不是通知内容。
#     只放 {"type": "notification"}。
#     前端收到后, 自己去调 GET /notifications 查表, 拿到真正的通知。
#
#   为什么这么设计?
#     ① 写完表才推信号; 就算事务最后回滚, 前端刷新一次也看不到, 不会显示错数据
#     ② 推送可能丢 (断网/断开), 数据不会丢 —— 下次拉表照样有
#     ③ 内容和数据库永远一致, 不用在推送里维护一份副本
_queues: dict[int, set[asyncio.Queue]] = {}


def set_loop(loop):
    global _loop#global全局变量，这样子main.py调用就是一个main.py的变量了
    _loop = loop
    ##把服务器启动时的那个"一直在转的循环"，存到一个全局变量里。


def _put(user_id: int, data: dict):
    """只能跑在事件循环线程里。"""
    for q in list(_queues.get(user_id, ())):
        try:
            q.put_nowait(data)##放进去，不等待
        except Exception:
            pass



#下面这个就是我的notify里面要调用的函数，这一步就是api调用notify建立了这一条信息以后
##notify还要用一下这个，这个pushnotification就是先看长连接还有没有跑，然后有的话就用
##这个长连接加东西到queue
def push_notification(user_id: int, data: dict | None = None):
    #call_soon_threadsafe
    #call 调用       soon 尽快     thread_safe	线程安全地
    #合起来 :从任何线程，安全地预约一次调用，尽快执行
    if _loop is None or _loop.is_closed():
        return #看后端跑没跑起来，loop都没有直接跑路
    _loop.call_soon_threadsafe(_put, user_id, data or {"type": "notification"})
    #"帮我把 _put 排进循环的待办清单，等循环转回来就执行。"

#下面这个函数就负责用户一旦进入网站就给他搞一个queue，
#然后里面有一个gen函数就是负责queue一旦有东西就直接发给前端用户
@router.get("/events")
async def events(request: Request, token: str = ""):
##async  必须是一直挂着等        request格式/event？   token是网址问号后面的？，不需要复杂方法查找
                            ##之前的一般接口地址格式更复杂要用专门的方法取请求头解开token
                            ##但是我的sse没有什么
    """SSE 长连接。浏览器用 EventSource 连这里。"""
    user = user_from_token(token)
    if user is None:
        return JSONResponse({"error": "未授权"}, status_code=401)

    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _queues.setdefault(user["id"], set()).add(q)

    async def gen():
        try:
            yield ": connected\n\n"        # 先发一句, 让浏览器知道连上了
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(q.get(), timeout=20)
                    # data 只是 {"type":"notification"} 这种信号;
                    # 浏览器收到后自己去拉列表, 不在这里传通知内容
                    yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                    ##yield = 把这段数据交出去，然后停在这里；
                    #浏览器收完，FastAPI 再来要，就继续往下跑。
                except asyncio.TimeoutError:
                    # 20 秒没消息就发个心跳, 防止中间代理把空闲连接掐掉
                    yield ": ping\n\n"
        finally:
            # 浏览器关页面 / 断网 → 把队列删掉, 否则内存泄漏
            s = _queues.get(user["id"])
            if s:
                s.discard(q)
                if not s:
                    _queues.pop(user["id"], None)

    return StreamingResponse( ##StreamingResponse	边生成边发送（SSE 就用它）
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",     # 让 nginx 不要缓冲 (以后上线用)
        },
    )
