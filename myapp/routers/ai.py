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

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from ai.client import AIError, chat_stream
from cache import redis_client
from dependencies import get_current_user
from schemas import AiChatIn

router = APIRouter()
logger = logging.getLogger("ai")

# 每个用户每天最多问多少次 (防止有人刷你的 Key)
DAILY_LIMIT = int(os.getenv("AI_DAILY_LIMIT", "100"))

# 系统提示词: 定义助手是谁、能干什么、有什么边界。
# 永远由后端提供, 不接受前端传来的 system —— 否则用户能改写它的规矩。
SYSTEM_PROMPT = """你是本站（小明的文章站）的 AI 助手。
用简洁、准确的中文回答技术问题。
不确定的事情直接说不知道，不要编造。
不要声称站内有某篇文章，除非用户消息里提供了相关上下文。"""


def _consume_quota(user_id: int) -> bool:
    """消耗一次当日额度, 返回 True 表示还能用。

    Redis key 形如 ai:quota:1:20261110, 计数 +1, 第一次设置 24 小时过期。
    Redis 挂了就放行 (宁可让 AI 用不了, 也不要因为缓存故障把功能全封死)。
    """
    key = f"ai:quota:{user_id}:{datetime.now():%Y%m%d}"
    try:
        used = redis_client.incr(key)
        if used == 1:
            redis_client.expire(key, 86400)
        return used <= DAILY_LIMIT
    except Exception:
        logger.exception("AI 额度检查失败, 本次放行")
        return True


@router.post("/ai/chat")
async def ai_chat(payload: AiChatIn, current_user: dict = Depends(get_current_user)):
    """收到对话 → 调模型 → 以 SSE 流返回。"""
    if not _consume_quota(current_user["id"]):
        return JSONResponse(
            status_code=429,
            content={"error": f"今天的 AI 额度（{DAILY_LIMIT} 次）用完了，明天再来"},
        )

    # 只保留最近 10 条, 且只接受 user/assistant。
    # 前端传来的 system 一律丢弃 —— system 只能由后端定。
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in payload.messages[-10:]:
        if msg.role not in ("user", "assistant"):
            continue
        text = msg.content.strip()
        if not text:
            continue
        messages.append({"role": msg.role, "content": text[:2000]})

    if len(messages) == 1:
        return JSONResponse(status_code=400, content={"error": "消息不能为空"})

    # 限制单次输出, 防止一次生成几千字把费用拉高
    max_tokens = max(1, min(payload.max_tokens, 1000))

    async def event_stream():
        try:
            async for piece in chat_stream(messages, max_tokens=max_tokens):
                event = json.dumps(
                    {"type": "delta", "content": piece},
                    ensure_ascii=False,
                )
                yield f"data: {event}\n\n"

            yield "data: [DONE]\n\n"

        except AIError as exc:
            # 技术细节进日志, 前端只看到人话
            logger.error("AI 调用失败 user=%s: %s", current_user.get("id"), exc)
            event = json.dumps(
                {"type": "error", "message": "AI 暂时不可用，请稍后再试"},
                ensure_ascii=False,
            )
            yield f"data: {event}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # 告诉 nginx 别缓冲
        },
    )
