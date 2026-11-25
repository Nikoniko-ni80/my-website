# ============================================================
# routers/ai.py —— AI 助手的接口层
# ============================================================
# 【它负责哪一段】
#   浏览器 ──①──► 这个文件 ──②──► ai/client.py ──► DeepSeek
#
#   ① 收请求、验登录、限额、拼 system prompt
#   ② 调用 chat_stream, 再把模型吐的字包成 SSE 发回浏览器
# ============================================================
import json
import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from ai.agent import run_agent
from ai.client import AIError, chat_stream
from ai.tools import list_tool_help_2
from cache import redis_client
from database import get_db
from dependencies import get_current_user
from models import AiConversation, AiMessage
from schemas import AiChatIn, AiConvIn, AiMsgIn

router = APIRouter()
logger = logging.getLogger("ai")    ##引入了一个python自带的日志方法，ai是日志名字

# 每个用户每天最多问多少次 (防止有人刷你的 Key)
DAILY_LIMIT = int(os.getenv("AI_DAILY_LIMIT", "100"))#从父进程搞一个信息过来

# 系统提示词: 定义助手是谁、能干什么、有什么边界。
# 永远由后端提供, 不接受前端传来的 system —— 否则用户能改写它的规矩。
#
# 【为什么工具说明也写在这里】
#   system prompt 是模型看到的第一段内容, 位置最靠前、最不容易被忽略。
#   工具说明丢在几百字的历史消息后面, 模型经常当没看见。
#
# 【为什么会有一段"输出格式"】
#   模型不按固定格式说话, 程序就没法把它"想调哪个工具"从人话里抠出来。
#   这一步叫"结构化输出", 是 Agent 能被代码驱动的前提。
BASE_PROMPT = """你是本站（技术笔记）的 AI 助手。用简洁、准确的中文回答技术问题。
不确定的事情直接说不知道，不要编造。

# 你可以使用的工具
{tool_help}

# 输出格式（必须严格遵守）
需要查资料时，只输出两行：
Thought: 你打算做什么
Action: search_articles("关键词")

需要具体内容（原文怎么写的、原理、怎么解决）时：
Thought: 需要查文章正文
Action: search_knowledge("用户的问题")

信息已经够了、可以回答时，只输出两行：
Thought: 信息够了
Action: Finish[最终答案]

# 规则
- 每次只输出一组 Thought/Action，不要多写
- Action 必须写在一行内，参数用英文双引号
- 没搜到就说没搜到，不要编造站内文章
- 用 search_knowledge 找到内容后，回答末尾要注明出自哪篇（写标题或 id）"""

# 工具说明由 tools.py 统一提供, 加新工具时这里不用改
SYSTEM_PROMPT = BASE_PROMPT.format(tool_help=list_tool_help_2())


def _consume_quota(user_id: int) -> bool:
    """消耗一次当日额度, 返回 True 表示还能用。

    Redis key 形如 ai:quota:1:20261110, 计数 +1, 第一次设置 24 小时过期。
    Redis 挂了就放行 (宁可让 AI 用不了, 也不要因为缓存故障把功能全封死)。
    """
    key = f"ai:quota:{user_id}:{datetime.now():%Y%m%d}"##拼写正确的key
    try:
        used = redis_client.incr(key)##Redis命令INCR:把某个key值加一然后返回加完的值
        if used == 1:
            redis_client.expire(key, 86400)##1说明是第一次建立，设置24小时过期
        return used <= DAILY_LIMIT
    except Exception:
        logger.exception("AI 额度检查失败, 本次放行")
        return True


# ============================================================
# 【已停用】老的流式聊天接口 POST /ai/chat
# ============================================================
# 这个是前端自己存数据然后一起发出去, 所以一刷新就没了。
# 现在改用 /chat: 历史由后端查数据库, 并且会落库(用户的话 + AI 的回答)。
# 前端已经不再调它, 先注释掉留档, 确认不要了再删。
# @router.post("/ai/chat")
# async def ai_chat(payload: AiChatIn, current_user: dict = Depends(get_current_user)):
#     """收到对话 → 调模型 → 以 SSE 流返回。"""
#     if not _consume_quota(current_user["id"]):
#         return JSONResponse(
#             status_code=429,
#             content={"error": f"今天的 AI 额度（{DAILY_LIMIT} 次）用完了，明天再来"},
#         )
#
#     # 只保留最近 10 条, 且只接受 user/assistant。
#     # 前端传来的 system 一律丢弃 —— system 只能由后端定。
#     messages = [{"role": "system", "content": SYSTEM_PROMPT}]
#     ##模型拿到的第一条永远是后端定的人设，前端传什么都影响不了它。
#     for msg in payload.messages[-10:]:##数第 10 个取到最后
#         if msg.role not in ("user", "assistant"):##只允许这两种
#             continue
#         text = msg.content.strip()##去空白
#         if not text:##如果是空消息就不发了
#             continue
#         messages.append({"role": msg.role, "content": text[:2000]})
#
#     if len(messages) == 1:##说明只有system一条，不用发
#         return JSONResponse(status_code=400, content={"error": "消息不能为空"})
#
#     # 限制单次输出, 防止一次生成几千字把费用拉高
#     max_tokens = max(1, min(payload.max_tokens, 1000))##最多1000最少1
#
#     async def event_stream():
#         try:
#             async for piece in chat_stream(messages, max_tokens=max_tokens):##开始调用写好的ai.py
#                       ##piece就是后面的chat_stream一点一点yield出来的数据
#                 event = json.dumps(     ##返回的中文包成json
#                     {"type": "delta", "content": piece},
#                     ensure_ascii=False,    ##用中文形式，不用编码
#                 )
#                 yield f"data: {event}\n\n"    ##按照sse格式写
#
#             yield "data: [DONE]\n\n"    ##yield借书事件，前端看到DONE就停止接收
#
#         except AIError as exc:
#             # 技术细节进日志, 前端只看到人话
#             logger.error("AI 调用失败 user=%s: %s", current_user.get("id"), exc)
#             ##进日志，logger是PYthon自带日志工具
#             event = json.dumps(
#                 {"type": "error", "message": "AI 暂时不可用，请稍后再试"},
#                 ensure_ascii=False,
#             )
#             yield f"data: {event}\n\n"
#
#     return StreamingResponse(
#         event_stream(),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache",
#             "X-Accel-Buffering": "no",   # 告诉 nginx 别缓冲
#         },
#     )
#
#
# ============================================================
# 多轮会话 —— 存库 (Day 2)
# ============================================================
# 【接口】
#   POST   /ai/conversations                  新建会话
#   GET    /ai/conversations                  我的会话列表
#   PUT    /ai/conversations/{cid}            改名
#   DELETE /ai/conversations/{cid}            删除
#   GET    /ai/conversations/{cid}/messages   拉历史
#   POST   /ai/conversations/{cid}/messages   发一条消息
#
# 【权限: 六个接口全都要过同一关】
#   先按 id 查会话, 再比 user_id。不是自己的, 一律 404 —— 不用 403。
#   403 等于告诉对方"这条确实存在, 只是你不能看", 存不存在就泄露了。
# ============================================================
MAX_CONV = 50        # 列表最多返回多少个会话
MAX_HISTORY = 50     # 一次最多拉多少条历史
MAX_TITLE = 100      # 标题最长多少个字
MAX_MSG = 4000       # 一条消息最长多少个字


def _own_conversation(db: Session, conversation_id: int, user_id: int) -> AiConversation:
    """按 id 找会话, 顺便验明是不是本人的。找不到 / 不是本人的, 都返回 404。"""
    conv = db.query(AiConversation).filter(AiConversation.id == conversation_id).first()
    if conv is None or conv.user_id != user_id:
        raise HTTPException(status_code=404, detail="对话不存在")
    return conv ##返回这个对话对象


@router.post("/ai/conversations")
def create_conversation(
    payload: AiConvIn,      ##新建会话的json结构体
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """开一个新会话。刚建的时候还没有消息, 标题先叫"新对话"。"""
    title = payload.title.strip()[:MAX_TITLE] or "新对话"
    conv = AiConversation(user_id=current_user["id"], title=title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return {"id": conv.id, "title": conv.title, "updated_at": conv.updated_at}


@router.get("/ai/conversations")
def list_conversations(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """我的会话列表, 最近聊过的排最上面。"""
    rows = (
        db.query(AiConversation)
        .filter(AiConversation.user_id == current_user["id"])
        .order_by(AiConversation.updated_at.desc())
        .limit(MAX_CONV)
        .all()
    )
    return [
        {"id": c.id, "title": c.title, "updated_at": c.updated_at}
        for c in rows
    ]


@router.put("/ai/conversations/{conversation_id}")
def rename_conversation(
    conversation_id: int,
    payload: AiConvIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """给会话改名。空标题直接拒绝, 不然列表里会出现一行空白。"""
    conv = _own_conversation(db, conversation_id, current_user["id"])
    title = payload.title.strip()[:MAX_TITLE]
    if not title:
        raise HTTPException(status_code=400, detail="标题不能为空")
    conv.title = title
    db.commit()
    return {"ok": True, "title": conv.title}


@router.delete("/ai/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """删会话。先删消息再删会话 —— 外键没开级联, 反过来删会报错。"""
    conv = _own_conversation(db, conversation_id, current_user["id"])
    db.query(AiMessage).filter(AiMessage.conversation_id == conv.id).delete()
    db.delete(conv)
    db.commit()
    return {"ok": True}


@router.get("/ai/conversations/{conversation_id}/messages")
def list_messages(
    conversation_id: int,
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """拉历史。按 id 倒序取最近 N 条, 再翻回正序返回。"""
    conv = _own_conversation(db, conversation_id, current_user["id"])
    limit = max(1, min(limit, MAX_HISTORY))
    rows = (
        db.query(AiMessage)
        .filter(AiMessage.conversation_id == conv.id)
        .order_by(AiMessage.id.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [
        {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at}
        for m in rows
    ]




# ============================================================
# 在会话里聊天: 存用户消息 → 调模型 → 存 AI 回答 (Day 3)
# ============================================================
HISTORY_FOR_MODEL = 10     # 拼给模型的历史条数 (不是全部历史, 控制 token)


@router.post("/ai/conversations/{conversation_id}/chat")
async def chat_in_conversation(
    conversation_id: int,
    payload: AiMsgIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """在这个会话里继续聊。流式返回, 并把两边的话都存下来。"""
    from database import SessionLocal   # 放这里导入, 避免和上面的循环依赖

    conv = _own_conversation(db, conversation_id, current_user["id"])

    text = payload.content.strip()
    if not text:
        raise HTTPException(status_code=400, detail="消息不能为空")
    text = text[:MAX_MSG]

    if not _consume_quota(current_user["id"]):
        return JSONResponse(
            status_code=429,##403没权限 404没文件  429来的太勤了
            content={"error": f"今天的 AI 额度（{DAILY_LIMIT} 次）用完了，明天再来"},
        )

    # ---------- ① 先存用户的话 ----------
    is_first = db.query(AiMessage).filter(AiMessage.conversation_id == conv.id).count() == 0
    if is_first:
        conv.title = text[:20]##如果是第一句就用发的语句第一句选20字符当对话名字
    conv.updated_at = datetime.now()

    user_msg = AiMessage(conversation_id=conv.id, role="user", content=text)
    db.add(user_msg)
    db.commit()

    # ---------- ② 取最近几条历史, 拼成要发给模型的消息 ----------
    rows = (
        db.query(AiMessage)
        .filter(AiMessage.conversation_id == conv.id)
        .order_by(AiMessage.id.desc())
        .limit(HISTORY_FOR_MODEL)
        .all()
    )
    rows.reverse()

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for m in rows:
        messages.append({"role": m.role, "content": m.content})

    # ---------- ③ 跑 agent 循环 + 存 AI 的回答 ----------
    # 跟以前不一样: 以前只调一次模型, 现在交给 run_agent,
    # 它会自己判断"要不要查工具、查到之后要不要再想一轮"。
    async def event_stream():
        reply_parts = []
        try:
            async for ev in run_agent(messages):
                etype = ev.get("type")

                if etype == "delta":
                    # 最终答案的碎片: 攒起来准备存库, 同时推给前端
                    reply_parts.append(ev["content"])
                    yield f"data: {json.dumps({'type': 'delta', 'content': ev['content']}, ensure_ascii=False)}\n\n"

                elif etype == "tool":
                    # 让前端能显示"正在查资料…"
                    yield f"data: {json.dumps({'type': 'tool', 'content': ev.get('content', '')}, ensure_ascii=False)}\n\n"

                elif etype == "error":
                    yield f"data: {json.dumps({'type': 'error', 'message': ev.get('message', 'AI 暂时不可用')}, ensure_ascii=False)}\n\n"

                # thinking 事件暂时不发: 前端还没做"思考中"面板
        finally:
            reply = "".join(reply_parts).strip()
            if reply:
                s = SessionLocal()
                try:
                    s.add(AiMessage(conversation_id=conversation_id, role="assistant", content=reply))
                    row = s.query(AiConversation).filter(AiConversation.id == conversation_id).first()
                    if row:
                        row.updated_at = datetime.now()
                    s.commit()
                except Exception:
                    logger.exception("AI 回答存库失败 conv=%s", conversation_id)
                finally:
                    s.close()

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
