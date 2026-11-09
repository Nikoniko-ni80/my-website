import axios from 'axios'

// 后端地址。
// ★ 默认走本地；打包/上线时用环境变量 VITE_API_BASE 覆盖：
//   开发:  不设 → http://127.0.0.1:8000
//   上线:  设成 /api → 请求打到当前域名的 /api/xxx，由 nginx 转给后端
//          (这样前后端同域, 不用管跨域, SSE/WebSocket 也走同一个口)
// ⚠️ 这里必须用"是否定义"来判断, 不能用 || ——
//    || 会把空字符串也当成没写, 那样同域部署就失效了。
const ENV_BASE = import.meta.env.VITE_API_BASE
export const API_BASE = ENV_BASE === undefined ? 'http://127.0.0.1:8000' : ENV_BASE

const api = axios.create({
  baseURL: API_BASE,
  timeout: 5000
})

// 注册: 发 POST /register {username, password}
export const register = (username, password) => {
  return api.post('/register', { username, password })
}

// 登录: 发 POST /login → 后端返回 {message, token}
export const login = (username, password) => {
  return api.post('/login', { username, password })
}

// 我的信息: 发 GET /me, 并且要把 token 放在请求头里!
export const getMe = (token) => {
  return api.get('/me', {
    headers: { Authorization: `Bearer ${token}` }   // ← token 放这
  })
}


// ================= 文章相关 =================

// 看【公开文章】(不用登录): GET /articles
// 看【公开文章】(不用登录): GET /articles?page=1&size=9&keyword=xx
// 用 axios 的 params 选项传查询参数, 它会自动拼成网址问号后面那串
// (还会自动把它转义好, 中文/空格都不用管)
// ★ category: 分类 (空字符串 = 全部)。后端看到空就不加过滤条件
export const getPublicArticles = (page = 1, size = 9, keyword = '', category = '') => {
  return api.get('/articles', {
    params: { page, size, keyword, category }
  })
}

// 热榜 (不用登录): GET /articles/hot?limit=10
// 后端已经按"热度 ÷ 时间衰减"排好序了, 前端直接渲染就行
export const getHotArticles = (limit = 10) => {
  return api.get('/articles/hot', { params: { limit } })
}

// 看【某一篇公开文章】(不用登录): GET /articles/{id}
// → {..., like_count, liked_by_me}
// ⚠️ 带上 token 的话, 后端才知道 liked_by_me (没带就一律 false)
export const getArticle = (id, token = null) => {
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  return api.get(`/articles/${id}`, { headers })
}

// 给文章点赞: POST /articles/{id}/like (带 token)
// 重复点赞返回 {message: "已经赞过了"} —— 是成功不是错误
export const likeArticle = (token, articleId) => {
  return api.post(`/articles/${articleId}/like`, {}, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 取消文章点赞: DELETE /articles/{id}/like (带 token)
export const unlikeArticle = (token, articleId) => {
  return api.delete(`/articles/${articleId}/like`, {
    headers: { Authorization: `Bearer ${token}` }
  })
}


// ================= 评论相关 =================

// 看某篇文章的评论: GET /articles/{id}/comments?sort=time|hot
// → [{ id, content, author, user_id, created_at, like_count, liked_by_me, can_delete,
//      replies: [{ ..., reply_to_user_id, reply_to_name }] }]
//
// ⚠️ token 是【可选】的! 带了的话后端就知道:
//      can_delete  → 这条我能不能删
//      liked_by_me → 这条我赞过没
//    不带也能看评论, 只是上面两个都是 false
export const getComments = (articleId, sort = 'time', token = null) => {
  const headers = token ? { Authorization: `Bearer ${token}` } : {}
  return api.get(`/articles/${articleId}/comments`, { params: { sort }, headers })
}

// 发评论 / 回复: POST /articles/{id}/comments (带 token)
// replyToCommentId 不传 = 发一条顶层评论
// 传 9102          = 回复 9102 那条 (不管它是根还是回复, 后端自动算拍平)
export const addComment = (token, articleId, content, replyToCommentId = null) => {
  return api.post(`/articles/${articleId}/comments`,
    { content, reply_to_comment_id: replyToCommentId },
    { headers: { Authorization: `Bearer ${token}` } })
}

// 删评论: DELETE /comments/{id} (带 token)
// ⚠️ 后端会再查一遍权限 —— 前端藏按钮只是体验, 拦住攻击者的是后端
export const deleteComment = (token, commentId) => {
  return api.delete(`/comments/${commentId}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 给评论点赞: POST /comments/{id}/like (带 token)
// 重复点赞返回 {message: "已经赞过了"} —— 是【成功】不是错误
export const likeComment = (token, commentId) => {
  return api.post(`/comments/${commentId}/like`, {}, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 取消点赞: DELETE /comments/{id}/like (带 token)
export const unlikeComment = (token, commentId) => {
  return api.delete(`/comments/${commentId}/like`, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 看【我的文章】(含私有, 带 token): GET /my/articles
export const getMyArticles = (token) => {
  return api.get('/my/articles', {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 看【我的某一篇】(含私有): GET /my/articles/{id}
export const getMyArticle = (token, id) => {
  return api.get(`/my/articles/${id}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 发布文章: POST /articles (带 token, 传 title + content + is_public + category + tags)
// tags 是一串标签名, 例如 ["Redis", "缓存"]
// price 单位是【分】: 5 元 = 500
export const addArticle = (token, title, content, isPublic, category = '', tags = [], isPaid = false, price = 0, cover = '') => {
  return api.post('/articles',
    { title, content, is_public: isPublic, category, tags, is_paid: isPaid, price, cover },
    { headers: { Authorization: `Bearer ${token}` } })
}

// 删文章: DELETE /articles/{id} (带 token)
export const deleteArticle = (token, id) => {
  return api.delete(`/articles/${id}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 改文章: PUT /articles/{id} (带 token, 传新 title + content + is_public + category + tags)
export const updateArticle = (token, id, title, content, isPublic, category = '', tags = [], isPaid = false, price = 0, cover = '') => {
  return api.put(`/articles/${id}`,
    { title, content, is_public: isPublic, category, tags, is_paid: isPaid, price, cover },
    { headers: { Authorization: `Bearer ${token}` } })
}


// ================= 标签相关 =================

// 标签联想: GET /tags?keyword=re  (不用登录)
// 返回 [{id, name, count}, ...]
export const getTags = (keyword = '', limit = 10) => {
  return api.get('/tags', { params: { keyword, limit } })
}

// 标签页: GET /tags/{name}/articles  (不用登录)
// 返回形状跟 getPublicArticles 一样: {items, total, page, size, pages, tag}
export const getArticlesByTag = (name, page = 1, size = 10) => {
  return api.get(`/tags/${encodeURIComponent(name)}/articles`, {
    params: { page, size }
  })
}


// ================= 通知相关 (都要登录) =================
const auth = (token) => ({ headers: { Authorization: `Bearer ${token}` } })

// 我的通知 (分页 + 分类)
// category: '' 全部 / 'reply' 评论与回复 / 'like' 收到的赞 /
//           'follow' 新增关注 / 'system' 系统通知
export const getNotifications = (token, page = 1, size = 20, category = '') => {
  return api.get('/notifications', { params: { page, size, category }, ...auth(token) })
}

// 未读数 (导航栏红点)
export const getUnreadCount = (token) => {
  return api.get('/notifications/unread-count', auth(token))
}

// 一条标为已读
export const markNotificationRead = (token, id) => {
  return api.put(`/notifications/${id}/read`, {}, auth(token))
}

// 全部已读
export const markAllNotificationsRead = (token) => {
  return api.put('/notifications/read-all', {}, auth(token))
}

// 清空 (category 不传 = 全部; 传分类 = 只清这一类)
export const clearNotifications = (token, category = '') => {
  return api.delete('/notifications', { params: { category }, ...auth(token) })
}

// 通知设置 (开关 + 自动回复)
export const getNotificationSettings = (token) => {
  return api.get('/notification-settings', auth(token))
}
export const updateNotificationSetting = (token, type, enabled) => {
  return api.put('/notification-settings', { type, enabled }, auth(token))
}
export const updateFollowGreeting = (token, greeting) => {
  return api.put('/notification-settings/greeting', { greeting }, auth(token))
}


// ================= 私信相关 (都要登录) =================

// 我的会话列表: [{id, user_id, username, last_message, last_message_at, unread}]
export const getConversations = (token) => {
  return api.get('/conversations', auth(token))
}

// 我和某人有没有会话? → {conversation_id: 5} / {conversation_id: null}
// (只查不建)
export const getConversationWith = (token, userId) => {
  return api.get(`/conversations/with/${userId}`, auth(token))
}

// 聊天记录 (before 可选: 传最早那条的 id, 取更早的)
export const getMessages = (token, conversationId, before = null, limit = 30) => {
  return api.get(`/conversations/${conversationId}/messages`, {
    params: { limit, ...(before ? { before } : {}) },
    ...auth(token),
  })
}

// 轮询新消息: 只取比 afterId 更新的 (聊天页每几秒问一次)
export const getMessagesAfter = (token, conversationId, afterId, limit = 50) => {
  return api.get(`/conversations/${conversationId}/messages`, {
    params: { after: afterId, limit },
    ...auth(token),
  })
}

// 发消息 ★ 这里传的是【对方的 user_id】, 不是会话 id
// 返回 {message, conversation_id, item}
export const sendMessage = (token, userId, content) => {
  return api.post(`/conversations/${userId}/messages`, { content }, auth(token))
}

// 标记已读
export const markConversationRead = (token, conversationId) => {
  return api.put(`/conversations/${conversationId}/read`, {}, auth(token))
}


// ================= 收藏相关 =================
// ⚠️ 注意一个容易搞混的地方: "加收藏"和"取消收藏"的参数顺序不一样!
//   加:   body 里是 {article_id, collection_id}          (文章在前)
//   取消: 路径是 /my/collections/{collection_id}/articles/{article_id}  (夹子在前)
//   为了不搞混, 下面这两个函数我都规定成 (token, collectionId, articleId) 的顺序。

// 我的收藏夹列表: GET /my/collections → [{id, name, count}]
// (后端发现一个夹子都没有时, 会自动帮你建一个"默认收藏夹")
export const getCollections = (token) => {
  return api.get('/my/collections', {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 新建收藏夹: POST /my/collections {name} → {message, id, name}
export const createCollection = (token, name) => {
  return api.post('/my/collections', { name }, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 收藏夹改名: PUT /my/collections/{id} {name} → {message}
export const renameCollection = (token, id, name) => {
  return api.put(`/my/collections/${id}`, { name }, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 删收藏夹: DELETE /my/collections/{id} → {message}
// (里面的收藏记录会被后端一起删掉!)
export const deleteCollection = (token, id) => {
  return api.delete(`/my/collections/${id}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 看某个夹子里的文章: GET /my/collections/{id}/articles → [{id, title, content, author}]
// ⚠️ 注意: 返回里【没有 is_public】, 所以列表页不要显示"公开/私有"标签
export const getCollectionArticles = (token, id) => {
  return api.get(`/my/collections/${id}/articles`, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 看"这一篇被收进了哪些收藏夹": GET /my/articles/{id}/collections
// → [{id, name, count, favorited}]   (favorited = 这一篇在不在这个夹子里)
export const getCollectionsOfArticle = (token, articleId) => {
  return api.get(`/my/articles/${articleId}/collections`, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 收藏: POST /favorites {article_id, collection_id} → {message, id}
// 重复收藏时后端返回 {error: "这个收藏夹里已经有这篇文章了"}
export const addFavorite = (token, collectionId, articleId) => {
  return api.post('/favorites',
    { article_id: articleId, collection_id: collectionId },
    { headers: { Authorization: `Bearer ${token}` } }
  )
}

// 取消收藏: DELETE /my/collections/{cid}/articles/{aid} → {message}
export const removeFavorite = (token, collectionId, articleId) => {
  return api.delete(`/my/collections/${collectionId}/articles/${articleId}`, {
    headers: { Authorization: `Bearer ${token}` }
  })
}


// ================= 建议反馈 =================

// 提交反馈: POST /feedback (带 token) → {message} 或 {error}
// 需要登录 —— 后端要记下是谁提的
export const sendFeedback = (token, content, contact = '') => {
  return api.post('/feedback', { content, contact }, {
    headers: { Authorization: `Bearer ${token}` }
  })
}


// ================= 浏览历史 =================

// 记录一次浏览: POST /history/{articleId} (带 token)
// 同一个人看同一篇多次, 后端只留一条 (更新时间, 不新增)
export const addHistory = (token, articleId) => {
  return api.post(`/history/${articleId}`, {}, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 我的浏览历史: GET /my/history → [{id, title, content, author, viewed_at}]
export const getHistory = (token) => {
  return api.get('/my/history', {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 清空浏览历史: DELETE /my/history → {message}
export const clearHistory = (token) => {
  return api.delete('/my/history', {
    headers: { Authorization: `Bearer ${token}` }
  })
}


// ================= 个人主页 =================

// 看【别人的主页】(不用登录): GET /users/{id}
// → {id, username, avatar, bio, created_at, articles: [...], article_count}
// ⚠️ 后端【不返回】password_hash / is_admin / vip_expire_at —— 别人的这些跟你无关
export const getUserProfile = (userId) => {
  return api.get(`/users/${userId}`)
}

// 改自己的资料: PUT /me {avatar, bio, username} (带 token)
// → {message, avatar, bio, username} 或 {error}
// ⚠️ 传不了 user_id —— 后端从 token 里认人, 所以只能改自己的
// ⚠️ username 不传 = 不改用户名 (后端那边默认是 None)
export const updateMe = (token, avatar, bio, username) => {
  return api.put('/me', { avatar, bio, username }, {
    headers: { Authorization: `Bearer ${token}` }
  })
}


// ================= 关注 + Feed 流 =================

// 关注某人: POST /users/{id}/follow (带 token) → {message} 或 {error}
// ⚠️ 重复关注返回的是 {message: "已经关注过了"} —— 是【成功】不是错误!
//    所以前端要【把这种情况当成成功】, 不能弹红字
export const followUser = (token, userId) => {
  return api.post(`/users/${userId}/follow`, {}, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 取关: DELETE /users/{id}/follow (带 token)
// ⚠️ 取关一个本来就没关注的, 会返回 {message: "本来就没关注"} —— 也是成功
export const unfollowUser = (token, userId) => {
  return api.delete(`/users/${userId}/follow`, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 查"我关没关注他": GET /users/{id}/follow-status (带 token) → {following: true/false}
// ⚠️ 这是【需要登录】的接口, 没登录就别调 (必然 401), 直接按"没关注"显示
export const getFollowStatus = (token, userId) => {
  return api.get(`/users/${userId}/follow-status`, {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 粉丝列表 (不用登录): GET /users/{id}/followers → [{id, username, avatar, bio}]
export const getFollowers = (userId) => {
  return api.get(`/users/${userId}/followers`)
}

// 关注列表 (不用登录): GET /users/{id}/following → [{id, username, avatar, bio}]
export const getFollowing = (userId) => {
  return api.get(`/users/${userId}/following`)
}

// 我的关注流: GET /my/feed?page=1&size=10 (带 token)
// → {items: [...], total, page, size, pages}
// ⚠️ 只包含【我关注的人】发的【公开】文章 —— 不含我自己发的, 也不含别人的私密文章
export const getMyFeed = (token, page = 1, size = 10) => {
  return api.get('/my/feed', {
    params: { page, size },
    headers: { Authorization: `Bearer ${token}` }
  })
}

// 我关注的人 (带"最近更新时间"): GET /my/following (带 token)
// → [{id, username, avatar, bio, last_update}]
// ⚠️ 按 last_update 倒序 —— "谁刚发了新文章, 谁排最前面"
// ⚠️ last_update 可能是 null (那人一篇文章都没发过), 会被排到最后
export const getMyFollowing = (token) => {
  return api.get('/my/following', {
    headers: { Authorization: `Bearer ${token}` }
  })
}


// ================= 付费文章 / 余额（都要登录） =================

// 下单: POST /orders {article_id} → {order_id, amount, status, expire_at}
export const createOrder = (token, articleId) => {
  return api.post('/orders', { article_id: articleId }, auth(token))
}

// 支付(模拟): POST /orders/{id}/pay → {message, article_id} 或 {error}
export const payOrder = (token, orderId) => {
  return api.post(`/orders/${orderId}/pay`, {}, auth(token))
}

// 我的订单
export const getMyOrders = (token) => api.get('/my/orders', auth(token))

// 我买过的文章
export const getMyPurchases = (token) => api.get('/my/purchases', auth(token))

// 余额 + 最近流水 → {balance, items:[{amount, reason, balance_after, created_at}]}
export const getBalance = (token) => api.get('/my/balance', auth(token))

// 模拟充值, amount 单位是【分】: 100 元 = 10000
export const recharge = (token, amount) => {
  return api.post('/my/balance/recharge', { amount }, auth(token))
}


// ================= SSE / WebSocket 地址 =================
// EventSource / WebSocket 都不能带自定义请求头, 所以 token 放网址参数
export const eventStreamUrl = (token) => {
  return `${API_BASE}/events?token=${encodeURIComponent(token)}`
}

// 把 http://... 换成 ws://...，拼出 WebSocket 地址
// ★ API_BASE 可能是相对路径 (/api, 上线同域部署的情况),
//   这时要自己用当前页面的协议和域名拼成绝对地址 ——
//   WebSocket 构造函数要的是 ws:// 或 wss:// 开头的完整地址。
export const wsUrl = (path, token) => {
  const q = `?token=${encodeURIComponent(token || '')}`

  if (API_BASE.startsWith('http')) {
    return `${API_BASE.replace(/^http/, 'ws')}${path}${q}`
  }

  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${location.host}${API_BASE}${path}${q}`
}


// ================= 搜索建议 =================
// 只读 Redis，不查数据库；真正搜索还是走 getPublicArticles
export const getSuggestions = (keyword, limit = 6) => {
  return api.get('/suggest', { params: { keyword, limit } })
}


// ================= 文件上传 =================
// 传一个 File 对象（<input type="file"> 里拿到的），返回 {url: "/uploads/xxx.png"}
// 注意：不要手动设置 Content-Type，让浏览器自己带 multipart 边界
export const uploadFile = (token, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/upload', fd, auth(token))
}
