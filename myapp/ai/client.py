# ============================================================
# ai/client.py —— 跟大模型 API 打交道的唯一入口
## 本文件只负责和模型说话，就是只负责后端到deepseek
# ============================================================
# 【为什么单独放一个文件】
#   以后换模型(DeepSeek → 智谱/豆包), 只改这里和 .env,
#   接口层、前端一行都不用动。
# ============================================================
import json
import os ##os 是个工具箱，里面有很多函数。
          ##它主要读"当前进程自己"的环境变量(父进程当时创建这个进程继承过来的)
from pathlib import Path

import httpx
from dotenv import load_dotenv
##从 dotenv 这个包里，只拿 load_dotenv 这一个函数出来用。
##dotenv 是第三方包（pip 装的，包名 python-dotenv，import 名是 dotenv），专门用来读 .env 文件

# ---------- 读 .env ----------
# 本地开发时, Key 写在 myapp/.env 里, 不在代码里, 也不进 git。
# Docker 里没有这个文件, load_dotenv 什么都不做, 环境变量由 compose 注入。
# __file__ = .../myapp/ai/client.py
# parent = ai/, parent.parent = myapp/, 所以 .env 在 myapp/.env
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
#算出 myapp/.env 的绝对路径，然后交给 load_dotenv 去读。

# ---------- 配置 ----------
# 三个都从环境变量读, 换模型只改 .env
AI_BASE_URL = os.getenv("AI_BASE_URL", "https://api.deepseek.com").rstrip("/")
AI_MODEL = os.getenv("AI_MODEL", "deepseek-chat")
AI_API_KEY = os.getenv("AI_API_KEY", "")##后面是默认值，env没有就设空值


class AIError(Exception):##造一个错误类叫做AIError
    """调用模型失败时抛这个, 上层统一转成友好提示。

    为什么要自定义异常?
      上层不想去区分 httpx.TimeoutException / HTTPStatusError / JSON 错误,
      统一 catch AIError 就够了, 也让错误信息能直接给用户看。
    """

##注意，下面这个发送消息给模型的流发送函数是异步的，就是说
##上层调用gen = chat_stream(messages)，什么都不会发生，不会发送，只有一个生成器对象
##开始执行async for piece in gen:
##         ...
##的时候才开始执行
async def chat_stream(messages: list[dict], max_tokens: int = 800, temperature: float = 0.7):
    """把对话发给模型, 流式返回文字片段。

    参数:
      messages    [{"role": "system"/"user"/"assistant", "content": "..."}]
      max_tokens  这次回答最多生成多少 token (限制费用)
      temperature 0~2, 越低越稳, 越高越发散

    用法:
      async for piece in chat_stream(messages):
          ...  # piece 是一小段文字
    """
    if not AI_API_KEY:
        raise AIError("AI_API_KEY 未配置")

    url = f"{AI_BASE_URL}/chat/completions" ##openai的固定格式，大厂商通用
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": AI_MODEL,
        "messages": messages,##注意，message是之前所有的对话记录，全发过去
        "stream": True,          # ★ 关键: 让模型一段段返回, 不是等全部生成完
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    try:
        # 连接超时 10 秒; 整个请求最长 120 秒 (模型偶尔会想很久)
        timeout = httpx.Timeout(120.0, connect=10.0)
        #整个请求从开始到结束，最多 120 秒。建立连接最多 10 秒
        async with httpx.AsyncClient(timeout=timeout) as client:
            ##注意 with ,async with是保证用完自动关闭连接
            # stream("POST", ...) 不会把响应体一次性读进内存
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                #普通是client.post(..),stream是请求发出后响应体读取大模型的回复不一次性下载而是一段一段读
                if resp.status_code != 200:##看状态码有没有出错,有问题就返回响应体
                    body = await resp.aread()
                    # body 可能很长, 只留前 200 字节, 免得日志爆炸
                    raise AIError(f"模型接口返回 {resp.status_code}: {body[:200]!r}")
                    #注意这里为啥要返回整个相应体，不单纯给一个报错是因为我好根据响应体信息查问题
                # 模型返回的是 SSE 格式, 一行一行读
                async for line in resp.aiter_lines():
                    line = line.strip()
                    # 空行 / 心跳行(以 : 开头) 直接跳过
                    if not line or not line.startswith("data:"):
                        continue

                    data = line[len("data:"):].strip()

                    # 流结束的标志
                    if data == "[DONE]":
                        break

                    try:
                        obj = json.loads(data)##data现在是字符串，把它搞成python字典
                    except json.JSONDecodeError:
                        #不是每一行都是合法 JSON，有的厂商会夹带调试行。
                        #解析失败就 continue 看下一行，不能因为一行脏数据让整个回答崩掉。
                        continue

                    choices = obj.get("choices") or []##如果是 None，用[]兜底
                    if not choices:
                        continue

                    delta = choices[0].get("delta") or {}
                    ##choices 是模型返回的 "候选回答"列表——因为接口允许一次要多个版本的答案。
                    piece = delta.get("content")##得到真正的回答文字
                    if piece:                 # 空字符串不要 yield, 前端会多出空消息
                        yield piece##相当于可循环的return

    except httpx.TimeoutException as exc:
        raise AIError("模型响应超时, 请稍后再试") from exc
    except httpx.HTTPError as exc:
        raise AIError(f"连接模型失败: {exc}") from exc
