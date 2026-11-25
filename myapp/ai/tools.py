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
