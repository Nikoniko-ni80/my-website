# ============================================================
# ai/rag.py —— 知识库检索 (RAG 的"R")
# ============================================================
# 【我自己的理解（原话）】
#   "实际上不是用户的问题附带了这个东西，不是我这边后端收到用户的问题
#    然后搞出用户的问题相关的卡片一起发过去。更类似于 tools：
#    ai 可以回答某些话时调用函数和相关参数，比如"雪崩"，
#    我的后端收到以后就去调用工具，然后去找数据库搞东西，找到四条发过去。"
#
#   —— 这段说得对。补两点：
#   ① 库不是"向量数据库服务", 就是 MySQL 里的一张表 ai_chunks + 关键词打分,
#      跑在我们自己后端里, 没有额外服务。
#   ② 不是每次都检索: 是模型自己决定要不要查、用什么词查。
#
# 【这一版做了什么】
#   把文章切成 400 字左右的小块, 提问时按关键词把这些块排个序,
#   取最像的几块交给模型, 让它照着答、并且能说出出处。
#
# 【为什么暂时不用向量】
#   DeepSeek 不提供 embedding 接口, 接第三方还要再申请一个 key。
#   站里只有几十篇文章, 全量扫一遍也只要几毫秒 ——
#   先用"关键词 + 打分"把链路跑通, 以后换成向量只需要换 search_chunks 内部。
#
# 【面试可以这么讲】
#   "我先做了 BM25 思路的关键词检索, 接口层已经和向量检索一样(输入问题, 输出片段+出处),
#    换成 embedding 只需要替换打分函数, 上层不用动。"
# ============================================================
import logging
import math
import re

import jieba

from database import SessionLocal
from models import AiChunk, Article

logger = logging.getLogger("ai.rag")

STOPWORDS = {
    "怎么", "什么", "为什么", "如何", "可以", "一个", "这个", "那个", "我们", "他们",
    "就是", "还是", "以及", "因为", "所以", "但是", "如果", "已经", "需要", "问题",
    "文章", "站里", "内容", "一下", "告诉", "请问", "帮我", "哪些", "多少",
}


MAX_CHUNK = 400        # 每块大概多少字
OVERLAP = 60           # 相邻块重叠多少字 (避免一句话被切断)
TOP_K = 4              # 一次返回几块


def split_article(text: str) -> list[str]:
    """把一篇文章切成若干块。

    策略: 先按空行切成段, 段太长了再按句号切, 直到每块不超过 MAX_CHUNK。
    相邻块留一点重叠, 防止关键句正好被切在边界上。
    """
    text = (text or "").strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces: list[str] = []
    for p in paragraphs:
        if len(p) <= MAX_CHUNK:
            pieces.append(p)
            continue
        # 段落太长: 按句子再切
        sentences = re.split(r"(?<=[。！？.!?])", p)
        buf = ""
        for s in sentences:
            if len(buf) + len(s) <= MAX_CHUNK:
                buf += s
            else:
                if buf:
                    pieces.append(buf)
                buf = s[-MAX_CHUNK:]
        if buf:
            pieces.append(buf)

    # 合并太碎的块 + 加重叠
    chunks, buf = [], ""
    for p in pieces:
        if len(buf) + len(p) <= MAX_CHUNK:
            buf = (buf + "\n" + p).strip()
        else:
            if buf:
                chunks.append(buf)
            buf = p
    if buf:
        chunks.append(buf)

    overlapped = []
    for i, c in enumerate(chunks):
        if i > 0 and OVERLAP > 0:
            c = chunks[i - 1][-OVERLAP:] + c
        overlapped.append(c)
    return overlapped


def rebuild_all() -> tuple[int, int]:
    """把库里所有公开文章重新切一遍, 返回 (文章数, 块数)。"""
    db = SessionLocal()
    try:
        db.query(AiChunk).delete()
        articles = db.query(Article).filter(Article.is_public == True).all()  # noqa: E712
        count = 0
        for a in articles:
            for i, piece in enumerate(split_article(a.content or "")):
                db.add(AiChunk(article_id=a.id, idx=i, title=a.title[:120], content=piece))
                count += 1
        db.commit()
        return len(articles), count
    finally:
        db.close()


def _grams(text: str) -> dict[str, float]:
    """把一句话切词, 返回 {词: 权重}。

    中文用 jieba 分词 —— 自己按 2/3 字切会把"怎么解决"这种跨词片段也当关键词,
    反而干扰排序。英文/数字直接按词切。
    词越长越具体, 权重给得越高。
    """
    text = (text or "").strip()
    if not text:
        return {}

    words: dict[str, float] = {}
    for w in jieba.lcut(text):
        w = w.strip().lower()
        if not w or w in STOPWORDS or len(w) < 2:
            continue
        words[w] = 3.0 if len(w) >= 3 else 1.5
    return words


def search_chunks(query: str, top_k: int = TOP_K) -> list[dict]:
    """按关键词给所有块打分, 返回最相关的几块。"""
    q_grams = _grams(query)
    if not q_grams:
        return []

    db = SessionLocal()
    try:
        rows = db.query(AiChunk).all()
    finally:
        db.close()

    # 先算每个关键词的"稀有度": 在越多块里出现, 说明它越没区分度
    # ("为什么"到处都是, "雪崩"只在几块里有)
    df = {g: 0 for g in q_grams}
    bodies = []
    for c in rows:
        body = c.content.lower()
        bodies.append(body)
        for g in q_grams:
            if g in body:
                df[g] += 1

    total = max(len(rows), 1)
    idf = {g: math.log((total + 1) / (n + 1)) for g, n in df.items()}
    common_cut = total * 0.35          # 超过 35% 的块都有 → 视为无区分度, 不计分

    scored = []
    for c, body in zip(rows, bodies):
        hit = 0.0
        strong = 0
        best = 0.0                     # 命中的最稀有那个词有多稀有
        for g, weight in q_grams.items():
            if df[g] > common_cut or df[g] == 0:
                continue
            if g in body:
                hit += body.count(g) * weight * idf[g]
                strong += 1
                best = max(best, idf[g])
        if strong < 2:
            continue
        score = (hit + best * 4) / (len(body) ** 0.5)

        # 标题里命中关键词的, 直接加权 —— 标题最能代表整篇在讲什么
        title = (c.title or "").lower()
        if any(g in title for g, w in q_grams.items() if df.get(g, 0) and df[g] <= common_cut):
            score *= 2.5

        scored.append((score, c))

    scored.sort(key=lambda x: -x[0])

    results, seen = [], set()
    for score, c in scored:
        if c.article_id in seen:      # 同一篇文章只取最相关的一块, 覆盖面更广
            continue
        seen.add(c.article_id)
        results.append({
            "article_id": c.article_id,
            "title": c.title,
            "content": c.content,
            "score": round(score, 3),
        })
        if len(results) >= top_k:
            break
    return results
