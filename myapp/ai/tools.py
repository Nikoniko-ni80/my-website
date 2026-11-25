# ============================================================
# ai/tools.py —— AI 助手能用的"工具"
# ============================================================
# 【什么是工具】
#   就是一个普通的 Python 函数。模型自己执行不了任何代码,
#   它只能"说出"要调哪个函数、传什么参数, 真正执行的是我们。
#
# 【为什么需要工具】
#   模型的知识停在训练那一天, 也不知道你站里有哪些文章。
#   工具把"外面的事实"递到它面前: 查数据库、算数、查天气。
#
# 【返回值为什么是字符串】
#   工具的结果最后要被拼进 prompt 给模型看, 所以返回"人能读的一段话",
#   不要返回 JSON 或对象 —— 模型读一段自然语言比读 JSON 准得多。
# ============================================================
import logging

from database import SessionLocal
from models import Article

logger = logging.getLogger("ai.tools")

MAX_SNIPPET = 160      # 每条结果给模型看的内容长度 (太长浪费 token)


def search_articles(keyword: str, limit: int = 5) -> str:
    """按关键词搜站内公开文章, 返回标题 + 链接用 id + 一小段摘要。

    模型调它时传的 keyword 是它自己从用户问题里提炼的,
    可能带引号、可能是整句话, 这里做一次清洗。
    """
    kw = (keyword or "").strip().strip('"').strip("'")
    if not kw:
        return "错误: 关键词为空, 请给一个具体的词再搜。"

    try:
        limit = max(1, min(int(limit), 10))     # 模型可能瞎传, 钳在 1~10
    except (TypeError, ValueError):
        limit = 5

    db = SessionLocal()                        # 工具自己开一个短会话, 用完就关
    try:
        like = f"%{kw}%"
        rows = (
            db.query(Article)
            .filter(Article.is_public == True)          # noqa: E712
            .filter(Article.title.like(like) | Article.content.like(like))
            .order_by(Article.id.desc())
            .limit(limit)
            .all()
        )
    except Exception:
        logger.exception("search_articles 查询失败 kw=%s", kw)
        return "错误: 搜索时数据库出问题了。"
    finally:
        db.close()

    if not rows:
        return f"没有搜到和「{kw}」有关的公开文章。"

    lines = [f"搜到 {len(rows)} 篇和「{kw}」有关的文章:"]
    for r in rows:
        # 正文是 markdown, 去掉换行和多余符号, 只留一段干净文字
        snippet = " ".join((r.content or "").split())[:MAX_SNIPPET]
        lines.append(f"- 《{r.title}》(id={r.id}, 分类:{r.category or '无'}) 摘要: {snippet}")
    return "\n".join(lines)


# ============================================================
# 工具注册表: 名字 → 真正的函数
# ============================================================
# 模型输出 Action: search_articles("Redis")
# 程序解析出名字 "search_articles", 到这张表里取出函数再调用。
#
# ⚠️ 这张表就是安全边界: 没登记进来的函数, 模型喊破嗓子也调不到。
TOOLS = {
    "search_articles": search_articles,
}

##下面是生成说明书，要拼到系统提示词里面去
def list_tool_help() -> str:
    """把可用工具写成一段说明, 拼进 prompt 让模型知道手里有什么。"""
    return (
        "- search_articles(keyword: str, limit: int = 5): "
        "搜索本站公开文章的标题和正文, 返回标题、id 和摘要。"
        "当用户问『站里有没有关于 XX 的文章』、或者需要引用站内内容时使用。"
    )


def search_knowledge(query: str, top_k: int = 4) -> str:
    """在站内文章的正文里找最相关的段落, 返回原文片段 + 出处。

    和 search_articles 的区别:
      search_articles  只给标题和摘要, 适合回答"有没有这篇文章"
      search_knowledge 给正文片段, 适合回答"文章里是怎么说的"
    """
    from ai.rag import search_chunks      # 放这里导入, 避免循环引用

    q = (query or "").strip()
    if not q:
        return "错误: 查询为空, 请给一个具体问题。"

    try:
        top_k = max(1, min(int(top_k), 6))
    except (TypeError, ValueError):
        top_k = 4

    hits = search_chunks(q, top_k=top_k)
    if not hits:
        return f"站内文章里没有找到和「{q}」相关的内容。"

    parts = [f"从站内文章里找到 {len(hits)} 段相关内容:"]
    for i, h in enumerate(hits, 1):
        snippet = " ".join(h["content"].split())[:500]
        parts.append(f"[{i}] 出自《{h['title']}》(id={h['article_id']})\n{snippet}")
    parts.append("回答时请注明内容出自哪一篇(id)。")
    return "\n\n".join(parts)


TOOLS["search_knowledge"] = search_knowledge


def list_tool_help_2() -> str:
    """把所有工具的说明拼成一段, 给系统的 prompt 用。"""
    return (
        "- search_articles(keyword: str, limit: int = 5): 搜索本站公开文章, 返回标题、id 和摘要。\n"
        "  当用户问『站里有没有关于 XX 的文章』时使用。\n"
        "- search_knowledge(query: str, top_k: int = 4): 在文章正文里检索相关段落, 返回原文和出处。\n"
        "  当用户问『文章里怎么说的 / 具体原理 / 怎么解决』这类需要具体内容的问题时使用。"
    )
