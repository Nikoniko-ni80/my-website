# ============================================================
# models.py - ORM 模型 (一个类 = 一张表)
# ============================================================
from sqlalchemy import (Column, Integer, String, Text, ForeignKey,
                        DateTime, Boolean, UniqueConstraint, Index)
from sqlalchemy.dialects.mysql import MEDIUMTEXT
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

    # ★ 关注自动回复 (第 7 步)
    #   别人关注你时, 自动发给对方的一句欢迎语。空字符串 = 不设置、不发。
    #   为什么不放 notification_settings? 那边存的是"开关"(布尔), 这里是一段文本,
    #   而且每个用户只有一个 → 直接放 users 更自然。
    follow_greeting = Column(String(200), default="", nullable=False)

    # ★ 站内余额 (第 10 步): 单位【分】。
    #   真正扣钱/加钱在 balance_logs 里留流水, 这里只是"当前余额"这个结果。
    #   余额 = 流水加出来的结果; 对不上时以流水为准, 把余额重算一遍。
    balance       = Column(Integer, default=0, nullable=False)

# ⚠️ 注意: User 里存的是 password_hash, 不是 password! (永远不存明文密码)
# 【外键】ForeignKey("users.id") = "这一列的值, 必须是 users 表里存在的 id" —— 表之间的关联靠它
#   例: 一条笔记 user_id=4 → 说明"这是 4 号用户(xiaoli)写的"

class Article(Base):
    __tablename__ = "articles"       # 对应 articles 表

    id         = Column(Integer, primary_key=True)                        # 主键
    title      = Column(String(100), nullable=False)                      # 标题
    # ★ 内容用 MEDIUMTEXT 不是 TEXT:
    #   TEXT 上限 64KB (约 2 万汉字), 长章节/长文直接存不进去;
    #   MEDIUMTEXT 上限 16MB, 够用了。写 with_variant 是为了别的数据库不受影响。
    content    = Column(Text().with_variant(MEDIUMTEXT(), "mysql"))        # 内容
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
    view_count = Column(Integer, default=0, nullable=False)
    # 封面图: 存相对路径 /uploads/xxx.png; 空 = 用渐变色占位
    cover      = Column(String(200), default="", nullable=False)       # 阅读量(总访问次数, 不去重)

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


# ============================================================
# 标签 (第 5B 步)
# ============================================================
class Tag(Base):
    """标签本身 —— 一个可以被多篇文章【共享】的实体。

    为什么不直接在 articles 存一列 "MySQL,Redis"?
      ① 查不准: LIKE '%Redis%' 会把 "RedisCluster" 也扫进来
      ② 改不动: 把 "Redis" 改名成 "Redis 7", 要改 N 篇文章
      ③ 数不了: "这个标签下有几篇" 得把字符串读出来在代码里数
      ④ 加不了属性: 标签想加个描述/颜色, 没地方放

    所以标签先是一张表 —— 有 id, 才能被引用、被统计、被改名。
    """
    __tablename__ = "tags"

    id   = Column(Integer, primary_key=True)
    name = Column(String(30), unique=True, nullable=False)
    # ★ unique 顺便建了索引 → "按名字找标签" 走它
    # ★ MySQL 默认排序规则(_ci)不区分大小写 →
    #     "Redis" 和 "redis" 会撞唯一约束, 自动当成同一个标签

    created_at = Column(DateTime, server_default=func.now())


class ArticleTag(Base):
    """文章 ↔ 标签 的中间表（多对多）。

    一行 = 一个"配对": 某篇文章贴了某个标签。

    为什么必须单独一张表?
      一列只能装一个值 —— 文章有多个标签, 一列装不下。
      而标签又要被多篇文章共享 → 关系升级成多对多 → 必须中间表。

    ★ 两个索引, 正好对应"从左到右 / 从右到左":
        ① (article_id, tag_id)  来自唯一约束
           → 查"这篇文章有哪些标签"
        ② (tag_id)              来自外键(MySQL 自动建)
           → 查"这个标签下有哪些文章"
    """
    __tablename__ = "article_tags"
    __table_args__ = (
        # ★ UniqueConstraint 参数 = ("列1", "列2", ..., name="约束名")
        #   列直接放前面, 名字用 name= 关键字 (跟 Index 的顺序相反)
        #   它会被 MySQL 建成【唯一索引】: 既挡重复, 又加速"按这两列查"
        UniqueConstraint("article_id", "tag_id", name="uq_article_tag"),   # ★ 同一篇不能重复贴同一个标签
    )

    id         = Column(Integer, primary_key=True)
    # 删文章 → 它的标签关联自动消失; 标签本身还在
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    # 删标签 → 关联消失; 文章本身不动
    tag_id     = Column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)


# ============================================================
# 通知 (第 7 步)
# ============================================================
class Notification(Base):
    """一条通知 = 一条"你被谁做了什么"的记录。

    ★ 6 种通知都装在这一张表里, 因为它们的【结构完全一样】:
         给谁 / 因为谁 / 什么类型 / 一句话 / 点哪 / 读没读
      不一样的是 type 的取值, 不是字段。

    ★ user_id 和 from_user 别搞反:
         user_id   = 收件人 (内容被互动的人)
         from_user = 寄件人 (做出动作的人; 系统通知 / 平台公告为 NULL)

    ★ content 存的是【快照字符串】, 不是 article_id:
         文章删了 / 用户改名了, 通知里那句话还得显示得出来。
    """
    __tablename__ = "notifications"
    __table_args__ = (
        # ★ Index 的参数顺序: Index("索引名", "列1", "列2", ...)
        #   ┌ 第一个是【自己起的名字】, 不是列!
        #   └ 列从第二个参数开始。
        #
        #   ⚠️ 跟 UniqueConstraint 正好相反:
        #        Index("名字", "列1", "列2")
        #        UniqueConstraint("列1", "列2", name="名字")   ← 列在前, 名字用 name=
        #
        # "我的消息"页的核心查询: WHERE user_id = 我 ORDER BY created_at DESC
        Index("idx_notify_user_time", "user_id", "created_at"),
    )

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)   # 收件人
    from_user  = Column(Integer, ForeignKey("users.id"), nullable=True)    # 寄件人 (系统消息为 NULL)
    type       = Column(String(20), nullable=False)                        # like/comment/reply/follow/greeting/system
    content    = Column(String(300), default="", nullable=False)           # 一句话文案 (快照)
    link       = Column(String(200), default="", nullable=False)           # 点开跳哪, 如 /article/7
    is_read    = Column(Boolean, default=False, nullable=False)            # 读没读 (红点/未读数)
    created_at = Column(DateTime, server_default=func.now())


class NotificationSetting(Base):
    """通知开关: 用户想不想收到某一类通知。

    ★ 关键规则: 没有记录 = 默认开启。
      好处:
        ① 新用户不用预插 6 行
        ② 以后加新类型, 老用户也不用补数据
    """
    __tablename__ = "notification_settings"
    __table_args__ = (
        UniqueConstraint("user_id", "type", name="uq_user_notify_type"),
    )

    id      = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type    = Column(String(20), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)


# ============================================================
# 私信（第 13 步的一部分，提前做）
# ============================================================
class Conversation(Base):
    """两个人之间的一个聊天窗口。

    ★ user_a 永远存【小的】id, user_b 存【大的】id。
      为什么? 不规定顺序的话:
          张三(id=3) 找 李四(id=7) → (3,7)
          李四(id=7) 找 张三(id=3) → (7,3)
        → 同一个聊天出现两个会话, 记录被劈成两半。
      规定了顺序, 两个人永远落在同一行上。

    ★ last_message_at: 会话列表按它倒序 (最近聊过的排最前)
    """
    __tablename__ = "conversations"
    __table_args__ = (
        # ★ 这两行的参数顺序【不一样】, 注意看:
        #
        #   UniqueConstraint("列1", "列2", name="名字")    ← 列在前, 名字用 name=
        #   Index("名字", "列1", "列2")                    ← 名字在前, 列在后
        #
        #   为什么? 因为 UniqueConstraint 的"列"可以有任意多个,
        #   名字只能用 name= 这种关键字参数区分;
        #   而 Index 的 [名字] 是一个固定位置, 列跟在后面。

        # ■ UniqueConstraint 是什么:
        #   "这几列的组合, 整张表不能出现第二次" —— 一条【规则】。
        #   MySQL 用一个【唯一索引】来实现它: 既挡重复, 又顺便能加速查询。
        #   ⚠️ (3,7) 和 (7,3) 是两个不同的组合, 都能插进去 →
        #      所以代码里必须先 sorted(), 两个人才能落在同一行。
        UniqueConstraint("user_a", "user_b", name="uq_conv_users"),   # ★ 同一对人只有一个会话

        # ■ Index 只是一棵"排好序的目录", 不限制数据
        Index("idx_conv_b", "user_b"),   # 反方向查"我参与的会话" (user_a 方向由唯一索引覆盖)
    )

    id              = Column(Integer, primary_key=True)
    user_a          = Column(Integer, ForeignKey("users.id"), nullable=False)   # 小的 id
    user_b          = Column(Integer, ForeignKey("users.id"), nullable=False)   # 大的 id
    last_message_at = Column(DateTime, server_default=func.now())               # 会话列表排序
    created_at      = Column(DateTime, server_default=func.now())


class Message(Base):
    """一条私信。

    is_read 的意思是"对方读没读":
        我发的消息 → is_read=False, 对方打开会话后改成 True
    """
    __tablename__ = "messages"
    __table_args__ = (
        # ★ Index 参数 = ("索引名", "列1", "列2", ...)
        #   第一个参数是【名字】不是列!
        #   ↑ 这行建出来的目录: 先按 conversation_id 排, 同一会话再按 id 排
        #
        # 拉聊天记录: WHERE conversation_id=? ORDER BY id DESC LIMIT 30
        Index("idx_msg_conv_id", "conversation_id", "id"),

        # 再建一个"按会话 + 是否已读"的目录, 专门给下面的统计用
        # 数未读: WHERE conversation_id=? AND is_read=0
        Index("idx_msg_conv_unread", "conversation_id", "is_read"),
    )
    ##只有Column(..)才是键结构,上面这两个是表设置
    ##这个args是装索引约束的东西，比如这里面装了两个索引(index)

    id              = Column(Integer, primary_key=True)
    # 删会话 → 里面的消息一起删
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    from_user       = Column(Integer, ForeignKey("users.id"), nullable=False)   # 谁发的
    content         = Column(Text, nullable=False)
    is_read         = Column(Boolean, default=False, nullable=False)
    created_at      = Column(DateTime, server_default=func.now())


# ============================================================
# 付费文章 (第 10 步)
# ============================================================
# 【三张表, 各管一件事】
#   orders      交易过程 (待支付 / 已支付 / 已取消)
#   purchases   拥有的权利 (能不能看全文, 只查这张)
#   earnings    作者的账 (每一笔都要能查到是哪笔订单来的)
#
# ★ 为什么不直接用"已支付的订单"判断能不能看?
#   因为订单是过程, 可能退款、作废; 权利是结果。
#   以后加退款: 订单改 refunded, 删掉 purchases —— 判断逻辑不用动。

class Order(Base):
    """一笔购买订单。创建时金额就【冻住】, 之后作者改价不影响已有订单。"""
    __tablename__ = "orders"
    __table_args__ = (
        # 我的订单列表: WHERE user_id=? ORDER BY created_at DESC
        Index("idx_order_user_time", "user_id", "created_at"),
        # 后台按状态扫 (待支付 / 已支付)
        Index("idx_order_status", "status"),
    )

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    amount     = Column(Integer, nullable=False)     # 单位: 分。下单那一刻的价格快照
    # pending 待支付 / paid 已支付 / cancelled 已取消(超时或用户放弃)
    status     = Column(String(20), default="pending", nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    paid_at    = Column(DateTime, nullable=True)
    expire_at  = Column(DateTime, nullable=True)     # 什么时候该关单 (信息用, 真正执行靠 MQ)


class Purchase(Base):
    """购买记录 = "这个人拥有这篇文章"。

    判断能不能看全文, 只查这张表。
    """
    __tablename__ = "purchases"
    __table_args__ = (
        # ★ 一个人对一篇文章只能有一条记录 —— 重复支付也插不进来
        UniqueConstraint("user_id", "article_id", name="uq_purchase_user_article"),
    )

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    order_id   = Column(Integer, ForeignKey("orders.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Earning(Base):
    """作者收益流水。一笔订单只记一次 (order_id 唯一)。"""
    __tablename__ = "earnings"
    __table_args__ = (
        # ★ MQ 是"至少一次", 同一条消息可能来两遍。
        #   靠这个唯一约束, 第二遍插入会被数据库直接拒绝 —— 这就是幂等的最后防线。
        UniqueConstraint("order_id", name="uq_earning_order"),
        Index("idx_earning_user", "user_id"),
    )

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)   # 作者
    order_id   = Column(Integer, ForeignKey("orders.id"), nullable=False)
    article_id = Column(Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    amount     = Column(Integer, nullable=False)     # 作者实得 (分), 平台抽成后的
    created_at = Column(DateTime, server_default=func.now())


class BalanceLog(Base):
    """资金流水。只追加, 永不修改。

    ★ 为什么单独一张表, 不塞进 orders?
      一笔订单会产生【多条】资金变动: 买家 -500, 作者 +400, 平台 +100。
      而且很多资金变动根本没有订单: 充值、提现、发奖励、退款。
      所以账本必须能记"跟订单无关的钱"。

    ★ 余额 = SUM(amount)。对不上时以流水为准, 把 users.balance 重算一遍。
    """
    __tablename__ = "balance_logs"
    __table_args__ = (
        # 查"我的流水": WHERE user_id=? ORDER BY created_at DESC
        Index("idx_balance_user_time", "user_id", "created_at"),
    )

    id      = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # 正数 = 进账, 负数 = 出账 (单位: 分)
    amount  = Column(Integer, nullable=False)
    # recharge 充值 / buy_article 买文章 / article_income 文章收入 / refund 退款
    reason  = Column(String(30), nullable=False)
    # 关联订单, 充值为 NULL (所以必须允许为空)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True)
    # 变动之后的余额: 对账时能一眼看出从哪一步开始不对
    balance_after = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


# ============================================================
# AI 助手: 会话 + 消息 (一对多)
# ============================================================
# 【为什么两张表】
#   一次会话 = 一个壳, 里面挂着一串消息。
#   全塞一张表的话, 每条消息都要重复存"这是谁的、会话叫什么标题",
#   改个标题得改几千行, 查"我有几个会话"得扫全表。
#
# 【为什么消息表里没有 user_id】
#   消息只认会话, 用户是谁通过会话查出来。
#   要是消息里也存一份 user_id, 两份数据就可能对不上。
#
# ⚠️ 安全: 查消息前必须先查会话, 确认这会话的 user_id 是当前登录的人,
#    不能直接 WHERE conversation_id = 前端传来的数字 —— 否则改个数字就能看别人的记录。


class AiConversation(Base):
    """一次对话 (左边列表里的那一行)"""
    __tablename__ = "ai_conversations"
    __table_args__ = (
        # 查"我的会话列表": WHERE user_id=? ORDER BY updated_at DESC
        Index("idx_ai_conv_user_time", "user_id", "updated_at"),##(索引名，第一列，第二列)
    )##有些东西不属于某一列，属于整张表——索引、唯一约束、字符集这些。这些就统一放进 __table_args__。

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    # 列表里显示的那句话, 一般取第一条消息的前 20 个字
    title      = Column(String(100), default="新对话", nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    # 最后一条消息的时间, 用来排序 (最近聊的排最上面)
    # onupdate: 每次改这一行, 数据库自动刷新这个时间
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AiMessage(Base):
    """会话里的一条消息"""
    __tablename__ = "ai_messages"
    __table_args__ = (
        # 查"这个会话的消息": WHERE conversation_id=? ORDER BY id
        Index("idx_ai_msg_conv", "conversation_id", "id"),
    )

    id              = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id"), nullable=False)
    # 只允许两个值: user (我发的) / assistant (AI 回的)
    role            = Column(String(20), nullable=False)
    # 用 Text 不用 String: 一条回答可能好几千字
    content         = Column(Text, nullable=False)
    created_at      = Column(DateTime, server_default=func.now())
