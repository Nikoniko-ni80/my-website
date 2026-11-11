# ============================================================
# ws.py —— WebSocket: 服务器主动把新消息推给浏览器
# ============================================================
# 【它解决什么】
#   以前前端每 4 秒问一次"有新消息吗"。现在反过来了:
#   后端一落库, 就通过这条常驻连接直接推过去。
#
# 【一张表: 谁在线】
#   connections = { user_id: {连接1, 连接2, ...} }
#   一个人可能开好几个页面, 所以一个 id 对应多个连接。
#
# 【两个必须注意的事】
#   ① 浏览器发 WebSocket 不能带 Authorization 头
#      → token 只能放网址参数: /ws/chat?token=xxx
#   ② 连接断开必须从表里删掉, 否则越积越多 (内存泄漏)
#
# ★ 只在【单进程】有效: 表在内存里, 多开一个 uvicorn 就找不到对方。
#   多实例要上 Redis 发布订阅广播 (以后再说)。
# ============================================================
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from auth import decode_token
from database import SessionLocal
from models import User

router = APIRouter()

##13: {  下面是13和服务器的连接
##        <WebSocket 对象 A>,   # 13 号的标签页 1
##        <WebSocket 对象 B>,   # 13 号的标签页 2  ！！正常情况
##   },
##16: {
##        <,,,>
##         ...
##    }
##
##


class ConnectionManager:##这个connectionmanager对象是我要在内存后端进程里面创办的一个对象
    """在线连接表。"""

    def __init__(self):##创建对象时自动跑一次，把 connections 设成空字典；
        self.connections: dict[int, set[WebSocket]] = {}

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()       # 同意浏览器的请求升级成 WebSocket
        self.connections.setdefault(user_id, set()).add(ws)
    ##同意这次 WebSocket 握手，并把这个连接登记到在线表里。

    def disconnect(self, user_id: int, ws: WebSocket):
        conns = self.connections.get(user_id)
        if not conns:
            return
        conns.discard(ws)
        if not conns:                           # 这个人的最后一个连接也没了
            self.connections.pop(user_id, None)

    async def send_to(self, user_id: int, data: dict):
        #给对面那个人发，如果他有两个标签页就都要发
        for ws in list(self.connections.get(user_id, ())):
            try:
                await ws.send_json(data)
            except Exception:
                # 这条连接已经废了, 顺手清掉
                self.disconnect(user_id, ws)


manager = ConnectionManager()

##下面这个检测是我向服务器建立websoket连接的时候检测一次
def user_from_token(token: str):
    """WebSocket 版的鉴权: 跟 get_current_user 做同一件事, 只是 token 从网址来。"""
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = payload["user_id"]
    except Exception:
        return None

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.id == user_id).first()
        return {"id": u.id, "username": u.username} if u else None
    finally:
        db.close()

##下面是一条连接的生命周期——验人 → 登记 → 挂着等 → 断开清理。就是组装之前的方法
@router.websocket("/ws/chat")
async def chat_ws(ws: WebSocket, token: str = ""):
    """聊天推送通道。

    ★ 这里【不负责发消息】: 发送还是走 POST /conversations/{user_id}/messages,
      因为那边有完整的校验、落库、幂等。这条连接只负责"收推送"。
    """
    user = user_from_token(token)
    if user is None:
        await ws.close(code=1008)          # 未授权, 拒绝握手
        return

    await manager.connect(user["id"], ws)##建立连接
    ##！！！注意，异步是说我的这个执行过程中可以执行chat_ws以外的东西，不是说可以执行下面的try
    try:
        while True:
            # 我们不需要客户端发内容, 但必须一直读:
            #   ① 感知"对方断开了" (断开时这里会抛 WebSocketDisconnect)
            #   ② 顺手支持心跳: 客户端发 ping, 回 pong
            msg = await ws.receive_text()##等客户端发文本；收到就返回
            if msg == "ping":
                await ws.send_text("pong")
                ##心跳pingpong是我的服务器为了确保连接一直在要不断发的空请求交互
    except WebSocketDisconnect:##except = "如果 try 里出错，跳到这里处理"。
        pass
    finally:##finally就是不论如何都会进行，无论是走到上面的exept还是函数出错了
            ##服务器出错也要死之前执行

        manager.disconnect(user["id"], ws)
