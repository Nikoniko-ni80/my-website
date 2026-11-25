# ============================================================
# ai/agent.py —— 智能体的循环 (ReAct)
# ============================================================
# 【它在整个链路的哪一段】
#   浏览器 → routers/ai.py → 【这里】 → ai/client.py → DeepSeek
#                          ↘ ai/tools.py (真正干活的函数)
#
# 【它干的活】
# 1. 把你这句话（+ 系统提示词）发给模型
# 2. 模型回：Thought… Action: search_articles("Redis")
# 3. 代码把 "search_articles" 和 "Redis" 拆出来     ← 拆
# 4. 去 TOOLS 字典里找到真函数，执行它               ← 做
# 5. 拿到"搜到 3 篇…"，写成 Observation 塞回对话
# 6. 再发一次给模型
# 7. 模型这回不调工具了，说 Finish[有，《Redis 为什么快》…]
# 8. 把括号里的答案给前端




# 【为什么要单独一个文件】
#   接口层管 HTTP, 模型层管说话, 这里管"想一步、做一步"。
#   以后换接口(网页/微信/命令行), 这个循环一行都不用改。
# ============================================================
import json
import logging
import re

from ai.client import AIError, chat_stream
from ai.tools import TOOLS

logger = logging.getLogger("ai.agent")

MAX_ROUNDS = 5        # 最多几轮 "思考 → 行动", 超过就强制收工


# ------------------------------------------------------------
# 解析工具: 从模型输出里抠出"它想调哪个函数"
# ------------------------------------------------------------
# 【模型只会说两种话】
#
#   (一) 想调工具
#        Thought: 需要查一下站内文章
#        Action: search_articles("Redis")
#
#   (二) 说完了
#        Thought: 信息够了
#        Action: Finish[站内有 3 篇讲 Redis 的文章]
#
# ------------------------------------------------------------
# 【下面是所有可能出现的格式, 以及每段落在哪个 group】
# ------------------------------------------------------------
#
# 一、ACTION_RE  (抓工具名和参数)
#
#   Action: search_articles("Redis")
#           └──── group(1) ───┘└group(2)┘
#   → group(1) = 'search_articles'
#   → group(2) = '"Redis"'                    (带引号)
#
#   Action: search_articles(keyword="Redis", limit=3)
#           └──── group(1) ───┘└──── group(2) ────┘
#   → group(1) = 'search_articles'
#   → group(2) = 'keyword="Redis", limit=3'    (整段交给 _parse_args 再拆)
#
#   Action: search_articles()
#           └──── group(1) ───┘└group(2)┘
#   → group(2) = ''                            (空字符串, 没有参数)
#
#   Action:search_articles("Redis")
#   → 少一个空格也能匹配 (\s* 允许没有空白)
#
# ------------------------------------------------------------
#
# 二、FINISH_RE  (抓最终答案)
#
#   Action: Finish[站内有 3 篇讲 Redis 的文章]
#                  └──────── group(1) ────────┘
#   → group(1) = '站内有 3 篇讲 Redis 的文章'
#
#   注意: 也兼容直接写 Finish[答案], 不带 Action: 前缀
#
# ------------------------------------------------------------
#
# 三、KWARG_RE  (把 "名字=值" 拆开, 用在 _parse_args 里)
#
#   keyword="Redis"
#   └group(1)┘└group(2)┘
#            └group(3)┘
#   → group(1) = 'keyword'     参数名
#   → group(2) = '"Redis"'     值(原样, 带引号)
#   → group(3) = 'Redis'       值(去掉了双引号) ← 用这个
#   → group(4) = None          这是双引号写法, 单引号那组没命中
#
#   keyword='Redis'
#   → group(3) = None
#   → group(4) = 'Redis'       ← 单引号写法, 用这个
#
#   limit=3
#   → group(2) = '3'           ← 裸值, 3 和 4 都是 None, 用这个
#   → group(3) = None
#   → group(4) = None
#
# ------------------------------------------------------------
# 【一句话总结】
#   ACTION_RE 负责"拆出工具名和参数"
#   FINISH_RE 负责"拆出最终答案"
#   KWARG_RE  负责"把 keyword=值 这种参数再拆成名字和值"
# ------------------------------------------------------------

ACTION_RE = re.compile(r"Action:\s*([A-Za-z_]\w*)\s*\((.*?)\)", re.S)
##这个正则匹配是吧模型回答的那一串字符串正则解析出我需要的字符串给我
##比如Action: search_articles("Redis")   我就要用这个ACRION_RE把东西分开成search_articles 和 "Redis"
#re是工具箱 compile是里面的一个函数，“写一个规则给我，做一个模板卡片”
#re.compile(规则)        → 做一张卡片, 放在 ACTION_RE 里
#ACTION_RE.search(文字)  → 拿卡片去筛这段文字


#括号里面的r：请不要把字符串中的\n理解为换行，就是一个字符串
#比如arr = 'a\nb'       3 个字符: a、换行、b
#    arr = r'a\nb'      4 个字符: a、\、n、b
##现在正式进入后面的规则本身"Action:\s*([A-Za-z_]\w*)\s*\((.*?)\)"
#      首先是Action:这一段强匹配，后面你不知道ai的回复会不会：后面空一格或者几格
#      所以就加个\s*就说明如果有几个 就自己跳过去直到识别到(
#      后面的([A-Za-z_]\w*)识别函数名，就是比如search_articles("Redis")
#                 [A-Za-z_]先识别出一个字母(这里是s)，然后后面的earch_articles全部由\w*识别(相当于要求一个字母开头的函数名)
#      识别完了search_articles就有可能出现   就要\s*
#      然后就是("Redis")这一段了，现在就是先比对括号字符要用\( \)这两个表示真的括号字符
        #      这是因为()本身在正则里面已经被用作“分组”了！！！
        #      比如最后我使用了模板m = 规则.search('Action: search_articles("Redis")')
        #      这个时候我的m是记得里面的内容的，依靠括号，比如m.group(1)就是第一个括号圈住的search_articles  m.group(2)就是第2个括号圈住的: "Redis"
#

FINISH_RE = re.compile(r"Finish\s*\[(.*)\]", re.S)
#匹配。。。
KWARG_RE = re.compile(r"([A-Za-z_]\w*)\s*=\s*(\"([^\"]*)\"|'([^']*)'|[^,)]+)")
#拆，把redis拆出来

def _parse_args(raw: str):
# 输入："Redis"                    输出：(["Redis"], {})
# 输入：keyword="Redis", limit=3    输出：([], {"keyword": "Redis", "limit": "3"})
    raw = (raw or "").strip()
    if not raw:
        return [], {}#判断空

    # 先看是不是第二种 keyword=value 的写法
    if "=" in raw:
        kwargs = {}
        for m in KWARG_RE.finditer(raw):
        ##finditer 就是：“拿卡片在 raw 这段文字里找，找到一个就交给你一个
        #每交来一个，就执行一次循环体
            key = m.group(1)
            val = m.group(3) if m.group(3) is not None else (
                m.group(4) if m.group(4) is not None else m.group(2).strip()
            )
            kwargs[key] = val.strip().strip('"').strip("'")##去空格，单双引号
        if kwargs:
            return [], kwargs##[], {"keyword": "Redis", "limit": "3"}

    # 否则按逗号切成位置参数
    parts = [p.strip().strip('"').strip("'") for p in raw.split(",") if p.strip()]
    return parts, {}##["Redis"], {}


def parse_action(output: str):
    """看模型这一段输出, 判断下一步干什么。

    返回三种可能:
      ("finish", "最终答案", None)      —— 它说干完了
      ("tool",   "工具名",   (args, kwargs)) —— 它想调工具
      ("none",   None, None)            —— 既没说结束也没说调工具(格式跑偏)
    """
    text = output or ""

    # 先看 Finish —— 注意要优先判断,
    # 因为有的模型会把 Finish 写在 Action 里: Action: Finish[...]
    m = FINISH_RE.search(text)
    if m:
        return "finish", m.group(1).strip(), None

    m = ACTION_RE.search(text)
    if m:
        name = m.group(1)
        if name.lower() == "finish":          # Action: Finish[...] 也归到这里
            return "finish", "", None
        args, kwargs = _parse_args(m.group(2))
        return "tool", name, (args, kwargs)

    return "none", None, None


def run_tool(name: str, args, kwargs) -> str:
    """按名字找到函数并执行。找不到 / 执行出错, 都返回一句人话给模型看。"""
    func = TOOLS.get(name)
    if func is None:
        return f"错误: 没有叫 {name} 的工具, 可用的是: {', '.join(TOOLS)}"

    try:
        return func(*args, **kwargs)
    except TypeError as exc:
        # 参数个数或名字对不上, 通常是模型自己写错了
        logger.warning("工具参数不匹配 name=%s args=%s kwargs=%s: %s", name, args, kwargs, exc)
        return f"错误: 调用 {name} 的参数不对({exc}), 请检查参数名再试。"
    except Exception as exc:
        logger.exception("工具执行失败 name=%s", name)
        return f"错误: {name} 执行失败({exc})。"


# ------------------------------------------------------------
# 主循环
# ------------------------------------------------------------
async def run_agent(messages: list[dict]):
    """一轮一轮地"想 → 做", 事件以 dict 的形式 yield 出去。

    事件类型:
      {"type": "thinking", "content": 一小段字}   模型正在想/正在写
      {"type": "tool",     "name": 工具名, "content": 给前端看的一句话}
      {"type": "delta",    "content": 最终答案的碎片}
      {"type": "error",    "message": 人话}
    """
    for round_no in range(1, MAX_ROUNDS + 1):
        logger.info("agent round %s", round_no)

        output_parts = []
        try:
            async for piece in chat_stream(messages, max_tokens=800):
                output_parts.append(piece)
                # 思考过程也流出去, 前端以后可以做"思考中"面板
                yield {"type": "thinking", "content": piece}
        except AIError as exc:
            logger.error("agent 调模型失败: %s", exc)
            yield {"type": "error", "message": "AI 暂时不可用，请稍后再试"}
            return

        output = "".join(output_parts).strip()

        kind, name_or_answer, params = parse_action(output)

        # ① 它说结束了
        if kind == "finish":
            answer = name_or_answer or ""
            if not answer:
                # Action: Finish[] 这种抠不出内容的情况, 退一步用整段输出
                answer = output
            yield {"type": "delta", "content": answer}
            return

        # ② 它要调工具
        if kind == "tool":
            args, kwargs = params
            logger.info("agent 调用工具 %s args=%s kwargs=%s", name_or_answer, args, kwargs)
            yield {"type": "tool", "name": name_or_answer,
                   "content": f"正在使用工具：{name_or_answer}"}

            result = run_tool(name_or_answer, args, kwargs)

            # 把模型这一轮说的话 + 工具结果 都塞回历史, 再来一轮
            messages.append({"role": "assistant", "content": output})
            messages.append({"role": "user", "content": f"Observation: {result}"})
            continue

        # ③ 格式跑偏: 没说 Finish 也没说 Action
        logger.warning("agent 输出不符合格式: %s", output[:200])
        yield {"type": "delta", "content": output}
        return

    # 转满 MAX_ROUNDS 还没收工
    logger.warning("agent 达到最大轮数 %s 仍未结束", MAX_ROUNDS)
    yield {"type": "delta", "content": "这个问题我查了几轮还没搞定，换个问法试试？"}
