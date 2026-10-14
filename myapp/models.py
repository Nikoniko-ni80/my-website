# ============================================================
# models.py - ORM 模型 (一个类 = 一张表)
# ============================================================
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, UniqueConstraint
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"          # 对应 users 表

    id            = Column(Integer, primary_key=True)                # 主键
    username      = Column(String(50), unique=True, nullable=False)  # 用户名: 唯一 + 不能空
    password_hash = Column(String(200), nullable=False)              # 密码的"哈希值"(加密后)

    # ↓↓↓↓↓ 第 0 步新增的 5 列 ↓↓↓↓↓
    # ⚠️ 每一列都必须有 default 或者允许为空!
    #    不然已有的 10 个老用户会因为"新列没值"而读不出来
    avatar        = Column(String(200), default="", nullable=False)   # 头像图片地址
    bio           = Column(String(200), default="", nullable=False)   # 个人简介
    created_at    = Column(DateTime, server_default=func.now())       # 注册时间
    is_admin      = Column(Boolean, default=False, nullable=False)    # 是不是管理员
    # ★ VIP 存的是"到期时间", 不是"是不是会员"
    #   存布尔的话, 到期了得有个定时任务去改成 False —— 定时任务挂了, 满网站都是假会员
    #   存到期时间, 时间是会自己走的, 压根不需要任何后台任务
    vip_expire_at = Column(DateTime, nullable=True)                   # VIP 到期时间, 空 = 从没充过

# ⚠️ 注意: User 里存的是 password_hash, 不是 password! (永远不存明文密码)
# 【外键】ForeignKey("users.id") = "这一列的值, 必须是 users 表里存在的 id" —— 表之间的关联靠它
#   例: 一条笔记 user_id=4 → 说明"这是 4 号用户(xiaoli)写的"

class Article(Base):
    __tablename__ = "articles"       # 对应 articles 表

    id         = Column(Integer, primary_key=True)                        # 主键
    title      = Column(String(100), nullable=False)                      # 标题
    content    = Column(Text)                                             # 内容
    # ⬇ 外键: 这个 user_id 指向 users 表的 id (说明"这条笔记是哪个用户写的")
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    # ⬇ 公开/私有开关: True = 公开(谁都能看), False = 私有(只有作者能看)
    is_public  = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())              # 创建时间(数据库自动填)

    # ↓↓↓↓↓ 第 0 步新增的 3 列 ↓↓↓↓↓
    is_paid    = Column(Boolean, default=False, nullable=False)   # 是不是付费文章
    price      = Column(Integer, default=0, nullable=False)       # 价格, 单位【分】(不是"元"!)
                                                                  # ★ 钱永远用整数存: 9.9 元 = 990 分
                                                                  #   浮点数会有 0.1+0.2≠0.3 那种精度问题
    view_count = Column(Integer, default=0, nullable=False)       # 阅读量(总访问次数, 不去重)

    # ↓↓↓↓↓ 后来加的: 分类 ↓↓↓↓↓
    # ★ 一篇文章只能归【一个】类 (前端 / 后端 / AI / 其他)
    #   跟"标签"的区别: 标签是"涉及了哪些点"(能挂好几个), 分类是"属于哪一块"(只有一个)
    #   空字符串 = 没分类 (加这列之前的老文章都是这个值, 所以必须有默认值)
    #
    # ⚠️ 这里【故意不加索引】—— 虽然首页每次都要 WHERE category = '后端'。
    #    为什么不加? 因为"选择性太低":
    #      整个表只有 4 个不同的值, 查一个分类会命中【1/4 的行】
    #      → 走索引要"先查索引再回表", 比直接全表扫还慢
    #      → MySQL 自己也会判断出不该用索引, 那这个索引就是【白占地方 + 拖慢写入】
    #    什么时候才该给 category 加索引? 分类多到几百个、每个分类只占很小比例时。
    #    (规律: 索引适合"筛出来的行很少"的列; 一筛就筛掉一大半的, 不适合)
    category   = Column(String(20), default="", nullable=False)


class Comment(Base):
    __tablename__ = "comments"       # 对应 comments 表

    id         = Column(Integer, primary_key=True)                       # 主键
    content    = Column(Text, nullable=False)                            # 评论内容
    # ⬇ 两个外键: 这张表同时"连着" users 和 articles
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)     # 谁评的
    # ★ ondelete="CASCADE" = 文章被删时, 这条评论【由数据库自动删掉】
    #   以前要写 db.query(Comment).filter(...).delete() 手动删, 现在不用了
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)  # 评的哪篇
    created_at = Column(DateTime, server_default=func.now())             # 评论时间

    # ↓↓↓↓↓ 楼中楼的三个字段 (第 0 步起, 第 3 步理顺) ↓↓↓↓↓
    # ⚠️ 三个都是 nullable=True —— 顶层评论这三个都为空
    #
    # 【为什么要三个? 它们是三件不同的事】
    #   root_id   我挂在哪棵树上  → 顶层评论自己为 NULL
    #   parent_id 我直接回复的是【哪一条】
    #   reply_to_user_id  我回复的是【谁】
    #
    # ⚠️ parent_id 和 reply_to_user_id 信息上是重合的
    #    (parent_id 查一下那条评论, 就知道作者是谁)
    #    但还是两个都留, 因为:
    #      ① reply_to_user_id 显示"回复 李四"时不用多 JOIN 一层
    #      ② ★ 抗删除: 被回复的那条评论被删了, parent_id 会变 NULL,
    #         但 reply_to_user_id 还在 → 还能显示"回复 李四"
    #    (B站 也是这样: 被删评论下面的回复, 照样写着"回复某某人")
    #    这是【故意的冗余】—— 代价是自己保证它跟 parent_id 一致。

    # 根评论: 空 = 我自己就是根。
    # ★ CASCADE: 删一条顶层评论 → 挂在它下面的回复(包括回复的回复)全自动删
    #   为什么一条 CASCADE 就够, 不用递归? 因为拍平设计 ——
    #   所有回复的 root_id 都【直接指向顶层】, 谁也不指向上一条回复。
    root_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)

    # 直接回复的那条评论。
    # ★ SET NULL 不是 CASCADE! 被回复的那条删了, 只把我的指针置空 ——
    #   我自己挂在 root_id 那棵树上, 不该跟着死。
    parent_id = Column(Integer, ForeignKey("comments.id", ondelete="SET NULL"), nullable=True)

    # 被回复的人 (用户 id, 不是评论 id)
    reply_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)


# 【一张表连两张表】Comment 有两个外键: user_id → users, article_id → articles
#   一条评论 = "谁(user_id) 在 哪篇(article_id) 下面 说了什么(content)"


# 【收藏夹】所有人共用这一张表, 靠 user_id 区分是谁的 —— 不是每个用户一张表
#   (不然几万个用户就是几万张表, 想加一列还得改几万次)
#   查某个用户的: WHERE user_id = 6   ← 写起来就是 .filter(Collection.user_id == 6)
#
class Collection(Base):
    __tablename__ = "collections"    # 收藏夹

    id         = Column(Integer, primary_key=True)
    name       = Column(String(50), nullable=False)                        # 收藏夹名字
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)   # 这是谁的收藏夹
    created_at = Column(DateTime, server_default=func.now())


class Favorite(Base):
    __tablename__ = "favorites"      # 收藏记录 ("哪篇 收进 哪个夹子")
    __table_args__ = (
        # 唯一约束: 同一个收藏夹里, 同一篇文章只能收一次
        UniqueConstraint("collection_id", "article_id", name="uq_collection_article"),
    )

    id            = Column(Integer, primary_key=True)
    collection_id = Column(Integer, ForeignKey("collections.id"), nullable=False)  # 在哪个夹子
    # ★ 文章删了, 收藏记录自动跟着删(见 comments 表那段注释)
    article_id    = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)  # 哪篇文章
    created_at    = Column(DateTime, server_default=func.now())


# 【建议反馈】用户在「我的」页面提的意见
#   跟其他表一样, 也是所有人共用这一张, 靠 user_id 区分是谁提的
class Feedback(Base):
    __tablename__ = "feedbacks"

    id         = Column(Integer, primary_key=True)
    content    = Column(Text, nullable=False)                              # 反馈内容 (必填)
    contact    = Column(String(100))                                      # 联系方式 (选填, 留空也能提)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)   # 谁提的
    created_at = Column(DateTime, server_default=func.now())

    # ↓↓↓↓↓ 第 0 步新增的 2 列 (给管理端用) ↓↓↓↓↓
    # ★ 没有记录 = 待处理, 所以老数据自动就是 "pending"
    status = Column(String(20), default="pending", nullable=False)        # pending 待处理 / done 已处理
    reply  = Column(Text, nullable=True)                                  # 管理员的回复


# 【浏览历史】记"谁看过哪篇文章"
#   ★ 关键设计: 同一人 + 同一篇, 只留【一条】记录。
#     看第二遍不是新增一条, 而是把时间改成最新 —— 所以文件里那段用的是 upsert (有就更新, 没有就插入)
#     靠下面这个唯一约束在数据库层面兜底
class History(Base):
    __tablename__ = "histories"
    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_user_article_history"),
    )

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)      # 谁看的
    # ★ 文章删了, 浏览记录自动跟着删(见 comments 表那段注释)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)   # 看的哪篇
    viewed_at  = Column(DateTime, server_default=func.now())                  # 最后一次看的时间


# 【关注】谁 关注了 谁
#   ★ 一行 = 一条关注关系, 不是"一行一个用户后面跟一串他关注的人"
#     王五关注了张三和李四 → 表里 2 行, 不是 1 行
#   ★ 这是唯一一张【两边都指向 users】的表 (自关联)
class Follow(Base):
    __tablename__ = "follows"
    __table_args__ = (
        # 一个人对同一个人只能关注一次
        UniqueConstraint("user_id", "target_user_id", name="uq_user_target"),
    )

    id             = Column(Integer, primary_key=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)   # 我 (谁点的关注)
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)   # 我关注的人
    created_at     = Column(DateTime, server_default=func.now())
    #   列名为什么不用 follower_id / following_id? 那俩差一个字母, 太容易搞混。
    #   user_id / target_user_id 一眼就知道谁是谁。


# 【文章点赞】谁 赞了 哪篇文章
# 【评论点赞】谁 赞了 哪条评论
#   ★ 这是两张【独立】的表, 不是合并成一张 likes。
#
#   为什么不合并成 likes(user_id, target_type, target_id)?
#     合并版: target_id 一会儿指文章、一会儿指评论
#             → 那一列【没法建外键】(外键只能指向一张确定的表)
#             → 数据库管不了脏数据; 删文章时也没法靠 CASCADE 自动清点赞
#   分开两张: 每张都能挂外键, 删除清理全交给数据库
#             (而且是【级联传递】的: 删文章 → 删评论 → 删评论的点赞)
#
#   ★ 这两张表【都没有】like_count 这样的列 —— 点赞量永远 COUNT(*) 现算。
#     实测过: 160 万行数据下, 一次算 20 条评论的点赞量 = 5 毫秒
#             (因为走索引: type=range, Extra=Using index)
#     而存列的代价是: 要维护(+1/-1)、并发会丢、可能不一致。
class ArticleLike(Base):
    __tablename__ = "article_likes"
    __table_args__ = (
        UniqueConstraint("user_id", "article_id", name="uq_user_article_like"),   # ★ 防重复点赞
    )

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)      # 谁点的
    # ★ 删文章 → 这些点赞自动跟着删
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class CommentLike(Base):
    """评论点赞。★ 根评论和回复【一视同仁】—— 每条评论都能被赞, 各有各的点赞量。

    注意 comment_id 上没有"是不是根"的区别:
        谁赞的是哪一条, 就存哪一条的 id。
        "这条根的点赞量"和"那条回复的点赞量"是 count 各自的行算出来的, 没有汇聚。
    """
    __tablename__ = "comment_likes"
    __table_args__ = (
        UniqueConstraint("user_id", "comment_id", name="uq_user_comment_like"),   # ★ 防重复点赞
    )

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)      # 谁点的
    # ★ 删评论 → 这些点赞自动跟着删
    #   而且级联会往下传: 删文章 → CASCADE 删评论 → CASCADE 删评论的点赞
    comment_id = Column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # 【这张表会自动有两个索引, 你一个都不用写】
    #   ① (user_id, comment_id)  ← 来自上面的唯一约束
    #        干什么: 防重复点赞 + 查"我赞过这条没"
    #   ② (comment_id)           ← MySQL 为外键【自动建】的
    #        干什么: ★ 数"这条评论有几个赞"用的就是它
    #   ② 为什么 MySQL 会建? InnoDB 要求外键列必须有索引 ——
    #      因为删一条评论时, 数据库要找"哪些点赞指向它", 没索引就得全表扫。
    #   而这个"为删除而建的索引", 正好就是"数点赞量"要用的 —— 一举两得。
    #   验证: SHOW INDEX FROM comment_likes;
