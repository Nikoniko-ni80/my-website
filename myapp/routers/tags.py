# ============================================================
# routers/tags.py —— 标签
# ============================================================
# 【这个文件干两件事】
#   ① 给别的路由提供工具函数: normalize_tag / get_or_create_tags / set_article_tags
#   ② 提供两个查询接口: 标签联想、某个标签下的文章
#
# 【核心思想：标签是"共享实体"】
#   文章 A 贴的 MySQL 和文章 B 贴的 MySQL 是【同一个】Tag 行。
#   所以打标签时要: 先按名字查, 查到就复用, 查不到才新建。
# ============================================================
import re
import unicodedata
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import Tag, ArticleTag, Article, ArticleLike, User
from routers.orders import make_preview

router = APIRouter()

MAX_TAGS_PER_ARTICLE = 5     # 一篇文章最多几个标签
MAX_TAG_LEN = 30             # 跟 tags.name 的 String(30) 对齐


# ------------------------------------------------------------
# ① 规范化
# ------------------------------------------------------------
def normalize_tag(raw: str) -> str:
    """把用户输入的标签弄成统一写法。

    只解决"写法差异", 不解决"语义相同":
        " Redis "        → "Redis"        (去首尾空格)
        "Redis    缓存"   → "Redis 缓存"   (连续空格合并)
        "Ｒｅｄｉｓ"       → "Redis"        (全角转半角)

    ★ 这里【不转小写】:
        显示要保留用户第一次输入的写法 (FastAPI 不能变成 fastapi)。
        大小写的判断交给数据库 —— 你的库是 utf8mb4_0900_ai_ci,
        'Redis' = 'redis' 在 SQL 里就是相等。
    """
    s = unicodedata.normalize("NFKC", raw or "")##转半角
    s = s.strip() ##去空格
    s = re.sub(r"\s+", " ", s)##合并空格
    return s


# ------------------------------------------------------------
# ② 有就复用，没有就新建
# ------------------------------------------------------------
def get_or_create_tags(db: Session, names: list[str]) -> list[Tag]:
    """把一串标签名 → 真正的 Tag 行。

    返回去重后的 Tag 列表（同一次提交里 "Redis" 和 "redis" 会合并成一个）。
    """
    result = []
    seen = set()

    for raw in (names or []):
        # ★ 先看"已经收够 5 个了没", 再处理下一个。
        #   不能写成 names[:5] —— 那样遇到 ["", "", "", "", "", "Redis"]
        #   会先把前 5 个空串切出来, Redis 反而被丢掉。
        if len(result) >= MAX_TAGS_PER_ARTICLE:
            break

        name = normalize_tag(raw)
        if not name or len(name) > MAX_TAG_LEN:
            continue                     # 空的 / 太长的直接丢掉, 不报错

        tag = db.query(Tag).filter(Tag.name == name).first()
        #     ↑ 库里是 ci 排序规则, 所以 'redis' 能查到已有的 'Redis'

        if tag is None:                  # 以前没人用过这个标签
            tag = Tag(name=name)
            db.add(tag)
            db.flush()                   # 拿到自增 id, 但先不提交

        if tag.id not in seen:           # 同一次提交里的重复 (Redis / redis)
            seen.add(tag.id)
            result.append(tag)

    return result


# ------------------------------------------------------------
# ③ 给一篇文章重新设置标签（编辑文章时也用它）
# ------------------------------------------------------------
def set_article_tags(db: Session, article_id: int, names: list[str]):
    """先删掉旧的关联，再按新的标签名重建。"""
    db.query(ArticleTag).filter(ArticleTag.article_id == article_id).delete()

    for tag in get_or_create_tags(db, names):
        db.add(ArticleTag(article_id=article_id, tag_id=tag.id))


# ------------------------------------------------------------
# ④ 批量查标签（列表页用，避免 N+1）
# ------------------------------------------------------------
def tags_of_articles(db: Session, article_ids: list[int]) -> dict:
    """{文章id: [{"id":..,"name":..}, ...]}

    一条 IN 查完一批文章的标签，再在内存里分组 ——
    跟点赞数、评论数那里是同一个套路。
    """
    out = defaultdict(list)
    if not article_ids:
        return out

    rows = (
        db.query(ArticleTag.article_id, Tag.id, Tag.name)
        .join(Tag, Tag.id == ArticleTag.tag_id)
        .filter(ArticleTag.article_id.in_(article_ids))
        .all()
    )
    for aid, tid, name in rows:
        out[aid].append({"id": tid, "name": name})
    return out


# ------------------------------------------------------------
# ⑤ 标签联想 GET /tags?keyword=re
# ------------------------------------------------------------
@router.get("/tags")
def search_tags(
    keyword: str = "",
    limit: int = 10,
    db: Session = Depends(get_db),
):
    """发文页的"推荐标签": 名字包含关键词的标签, 按使用次数从多到少。"""
    limit = max(1, min(limit, 30))

    q = (
        db.query(Tag.id, Tag.name, func.count(ArticleTag.id).label("count"))
        .outerjoin(ArticleTag, ArticleTag.tag_id == Tag.id)
        .group_by(Tag.id, Tag.name)
        .order_by(func.count(ArticleTag.id).desc(), Tag.name)
    )
    if keyword.strip():
        q = q.filter(Tag.name.contains(keyword.strip()))

    rows = q.limit(limit).all()
    return {"items": [{"id": i, "name": n, "count": c} for i, n, c in rows]}


# ------------------------------------------------------------
# ⑥ 某个标签下的文章 GET /tags/{name}/articles
# ------------------------------------------------------------
@router.get("/tags/{name}/articles")
def articles_by_tag(
    name: str,
    page: int = 1,
    size: int = 10,
    db: Session = Depends(get_db),
):
    """标签页: 返回形状跟 GET /articles 一样, 前端直接复用卡片。"""
    tag = db.query(Tag).filter(Tag.name == name).first()
    if tag is None:
        return {"items": [], "total": 0, "page": page, "size": size,
                "pages": 0, "tag": None}

    q = (
        db.query(Article, User.username)
        .join(ArticleTag, ArticleTag.article_id == Article.id)
        .join(User, Article.user_id == User.id)
        .filter(ArticleTag.tag_id == tag.id, Article.is_public == True)
    )
    total = q.count()##这里开始分页
    rows = (q.order_by(Article.id.desc())
             .offset((page - 1) * size).limit(size).all())

    ids = [a.id for a, _ in rows]  #就是这一页的文章id
    likes = {}
    if ids:
        likes = {
            aid: n for aid, n in
            db.query(ArticleLike.article_id, func.count())
            .filter(ArticleLike.article_id.in_(ids))
            .group_by(ArticleLike.article_id).all()
        }

    return {
        "items": [
            {"id": a.id, "title": a.title,
             "content": make_preview(a.content) if a.is_paid else a.content,
             "user_id": a.user_id, "author": username,
             "category": a.category,
             "is_paid": a.is_paid, "price": a.price, "cover": a.cover,
             "like_count": likes.get(a.id, 0)}
            for a, username in rows
        ],
        "total": total, "page": page, "size": size,
        "pages": (total + size - 1) // size,
        "tag": {"id": tag.id, "name": tag.name},
    }
