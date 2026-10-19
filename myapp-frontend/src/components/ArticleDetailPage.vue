<template>
  <div class="page detail">
    <!-- 返回 -->
    <button class="back" @click="$router.push('/home')">‹ 返回首页</button>

    <p v-if="loading">加载中...</p>

    <template v-else-if="article">
     <!-- ★ 左右两栏: 左边正文+评论, 右边作者卡片 -->
     <div class="layout">
      <div class="main">

      <!-- 文章正文 -->
      <div class="art card">
        <h1 class="title">{{ article.title }}</h1>
        <div class="meta">
          <span class="avatar"><IconUser /></span>
          <!-- ★ 作者名可点 → 跳个人主页 -->
          <span class="author clickable" @click="goAuthor">{{ article.author }}</span>
          <span class="time">{{ fmtDate(article.created_at) }}</span>
          <!-- 点赞按钮: margin-left:auto 把这一组推到最右边 -->
          <button class="like-btn" :class="{ on: liked }" @click="toggleLikeArticle">
            👍<span v-if="likeCount"> {{ likeCount }}</span>
          </button>
          <!-- 收藏按钮: 已收藏时变实心青绿 -->
          <button class="fav-btn" :class="{ on: favCount > 0 }" @click="openPicker">
            ⭐ {{ favCount > 0 ? `已收藏 (${favCount})` : '收藏' }}
          </button>
        </div>
        <!-- ⚠️ 这里必须用 favMsg, 不能用上面那个 error!
             error 只渲染在最后那个 v-else 分支里, 文章加载成功时根本不会显示 -->
        <p v-if="favMsg" class="fav-msg">{{ favMsg }}</p>
        <hr />
        <!-- 正文: 用 v-html 插入【渲染好的 HTML】
             ⚠️ 内容已经在 renderMarkdown 里被 DOMPurify 洗过了, 见 utils/markdown.js -->
        <div v-if="article.content" class="md-body" v-html="renderedContent"></div>
        <div v-else class="empty-content">（无内容）</div>

        <!-- ★ 标签: 点一下 → 跳到该标签的列表页 (不是搜索框) -->
        <div v-if="article.tags && article.tags.length" class="tag-list">
          <span class="tag-list-label">标签</span>
          <span
            v-for="t in article.tags" :key="t.id"
            class="tag-chip"
            @click="$router.push(`/tag/${encodeURIComponent(t.name)}`)"
          ># {{ t.name }}</span>
        </div>
      </div>

      <!-- 评论区 -->
      <div class="comments card">
        <div class="c-head">
          <h3 class="c-title">评论（{{ totalCount }}）</h3>
          <!-- 排序切换: 点一下重新请求, 后端换 ORDER BY -->
          <div class="sort-tabs">
            <button :class="{ on: sort === 'time' }" @click="switchSort('time')">最新</button>
            <button :class="{ on: sort === 'hot' }" @click="switchSort('hot')">最热</button>
          </div>
        </div>

        <!-- 发评论 / 回复 -->
        <div class="c-input">
          <!-- 回复模式: 顶上多一条"回复 @某某"，带个叉取消 -->
          <div v-if="replyTo" class="reply-hint">
            回复 <b>@{{ replyTo.author }}</b>
            <button class="cancel-reply" @click="cancelReply">✕</button>
          </div>
          <div class="input-row">
            <input
              v-model="newComment"
              :placeholder="inputPlaceholder"
              @keyup.enter="handleComment"
            />
            <button class="send" :disabled="cBusy" @click="handleComment">发送</button>
          </div>
        </div>

        <!-- 提示条: 成功用柔和青绿, 失败才用红色 -->
        <p v-if="cMsg" class="c-msg" :class="{ err: !cMsgOk }">{{ cMsg }}</p>

        <!-- 评论列表 -->
        <div class="c-list">
          <div v-for="c in comments" :key="c.id" class="c-block">
            <!-- ===== 顶层评论 ===== -->
            <div class="c-item">
              <span class="c-avatar"><IconUser /></span>
              <div class="c-body">
                <p class="c-author">
                  <span class="clickable" @click="goUser(c.user_id)">{{ c.author }}</span>
                  <span class="c-time">{{ fmtTime(c.created_at) }}</span>
                </p>
                <p class="c-content">{{ c.content }}</p>

                <div class="c-ops">
                  <button class="op" :class="{ on: c.liked_by_me }" @click="toggleLike(c)">
                    👍<span v-if="c.like_count"> {{ c.like_count }}</span>
                  </button>
                  <button class="op" @click="startReply(c)">回复</button>
                  <!-- ⚠️ 后端说能删才显示 —— 但【后端自己还会再查一遍】 -->
                  <button v-if="c.can_delete" class="op danger" @click="askDelete(c)">
                    删除
                  </button>
                </div>
              </div>
            </div>

            <!-- ===== 回复区 (缩进一层) ===== -->
            <div v-if="c.replies && c.replies.length" class="c-replies">
              <div v-for="r in visibleReplies(c)" :key="r.id" class="c-item">
                <span class="c-avatar small"><IconUser /></span>
                <div class="c-body">
                  <p class="c-author">
                    <span class="clickable" @click="goUser(r.user_id)">{{ r.author }}</span>
                    <template v-if="r.reply_to_name">
                      回复
                      <span class="clickable" @click="goUser(r.reply_to_user_id)">
                        {{ r.reply_to_name }}
                      </span>
                    </template>
                    <span class="c-time">{{ fmtTime(r.created_at) }}</span>
                  </p>
                  <p class="c-content">{{ r.content }}</p>

                  <div class="c-ops">
                    <button class="op" :class="{ on: r.liked_by_me }" @click="toggleLike(r)">
                      👍<span v-if="r.like_count"> {{ r.like_count }}</span>
                    </button>
                    <button class="op" @click="startReply(r, c)">回复</button>
                    <button v-if="r.can_delete" class="op danger" @click="askDelete(r)">
                      删除
                    </button>
                  </div>
                </div>
              </div>

              <!-- 只显示前 3 条, 其余折叠 -->
              <button
                v-if="c.replies.length > 3 && !expanded.has(c.id)"
                class="more"
                @click="expand(c.id)"
              >
                展开另外 {{ c.replies.length - 3 }} 条回复 ⌄
              </button>
              <button
                v-else-if="c.replies.length > 3"
                class="more"
                @click="collapse(c.id)"
              >
                收起 ⌃
              </button>
            </div>
          </div>

          <p v-if="comments.length === 0" class="c-empty">还没有评论，来说两句～</p>
        </div>
      </div>

      <!-- ===== 相关阅读 (看完正文还有地方去, 也让页面往下延伸) ===== -->
      <div v-if="related.length" class="related card">
        <h3 class="rel-title">📚 相关阅读</h3>
        <div class="rel-grid">
          <div
            v-for="r in related" :key="r.id"
            class="rel-item"
            @click="goArticle(r.id)"
          >
            <p class="rel-name">{{ r.title }}</p>
            <div class="rel-meta">
              <span class="rel-author">{{ r.author }}</span>
              <span>👍 {{ r.like_count || 0 }}</span>
            </div>
          </div>
        </div>
      </div>

      </div>  <!-- /.main -->

      <!-- ========== 右侧作者卡片 ========== -->
      <aside class="side">
        <div class="ac card">
          <div class="ac-avatar" @click="goAuthor">
            <img v-if="article.author_avatar" :src="article.author_avatar" alt="" />
            <span v-else><IconUser /></span>
          </div>
          <p class="ac-name" @click="goAuthor">{{ article.author }}</p>
          <p class="ac-bio">{{ article.author_bio || '这个人很懒，什么都没写～' }}</p>

          <!-- 关注按钮: 点一下切换。自己的文章不显示 (关注自己没意义) -->
          <button
            v-if="!isMe"
            class="ac-follow"
            :class="{ on: following }"
            :disabled="followBusy"
            @click="toggleFollow"
          >
            {{ following ? '✓ 已关注' : '+ 关注' }}
          </button>
          <button v-else class="ac-follow mine" @click="goAuthor">
            这是我自己的文章
          </button>
          <button class="ac-home" @click="goAuthor">查看主页 ›</button>
        </div>

        <!-- ===== 作者的其他文章 (填满右侧栏) ===== -->
        <div v-if="authorArticles.length" class="ac card">
          <p class="ac-side-title">📄 他的其他文章</p>
          <div
            v-for="a in authorArticles" :key="a.id"
            class="side-art"
            :title="a.title"
            @click="goArticle(a.id)"
          >{{ a.title }}</div>
          <button class="ac-home" @click="goAuthor">查看全部 ›</button>
        </div>

        <!-- 📚 系列: 第 6 步才做, 先占个位置 -->
        <div class="ac card placeholder">
          <p class="ph-title">📚 他的系列</p>
          <p class="ph-tip">系列功能还没做（第 6 步）</p>
        </div>
      </aside>
     </div>  <!-- /.layout -->

      <!-- 收藏面板: 放在这个 template 里面, 因为文章加载出来了才可能收藏它 -->
      <Modal v-model="showPicker" title="收藏到收藏夹">
        <CollectionPicker :article-id="articleId" @changed="onFavChanged" />
      </Modal>

      <!-- 删评论的二次确认 -->
      <Modal v-model="showDel" title="删除评论">
        <p class="del-text">
          确定删掉这条评论吗？
          <!-- ★ 顶层评论会带走下面的回复, 这个提示必须说清楚 -->
          <template v-if="delIsTree">
            <br />它下面的<b>所有回复</b>也会一起消失。
          </template>
        </p>
        <p v-if="delTarget" class="del-quote">"{{ delTarget.content }}"</p>
        <p class="del-tip">删了就找不回来了。</p>

        <div class="m-btns">
          <button class="cancel" @click="showDel = false">再想想</button>
          <button class="danger" @click="doDelete">确定删除</button>
        </div>
      </Modal>
    </template>

    <p v-else class="err">{{ error || '文章不存在或未公开' }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getArticle, getMyArticle, getComments, addComment, getCollectionsOfArticle, addHistory,
  getMe, followUser, unfollowUser, getFollowStatus,
  deleteComment, likeComment, unlikeComment,
  likeArticle, unlikeArticle,
  getPublicArticles, getUserProfile
} from '../services/authApi.js'
import { renderMarkdown } from '../utils/markdown.js'
import Modal from './Modal.vue'
import CollectionPicker from './CollectionPicker.vue'
import { goLogin } from '../utils/auth.js'

const route = useRoute()
const router = useRouter()

// ★ 路由参数永远是"字符串", 得转成数字 (不转的话拿它去跟 id 比较会永远不相等)
const articleId = Number(route.params.id)

const article = ref(null)

// 正文渲染成 HTML (文章一变就重算)
const renderedContent = computed(() => renderMarkdown(article.value?.content || ''))

const comments = ref([])
const newComment = ref('')
const loading = ref(false)
const error = ref('')
const isLogin = ref(!!localStorage.getItem('token'))

// ---- 页面下半部分: 让看完正文的人还有地方去 ----
const related = ref([])          // 同分类的其他文章
const authorArticles = ref([])   // 作者的其他公开文章

// ---- 评论区状态 ----
const sort = ref('time')             // 'time' 最新 / 'hot' 最热
const replyTo = ref(null)            // 正在回复谁: { id, author }; null = 发顶层评论
const replyRoot = ref(null)          // 回复完之后要展开哪棵树
const expanded = ref(new Set())      // 哪些顶层评论展开了全部回复
const cMsg = ref('')                 // 评论区的提示 (错误/成功)
const cMsgOk = ref(true)             // true = 成功提示, false = 错误提示
const cBusy = ref(false)             // 请求锁
const showDel = ref(false)           // 删除确认弹窗
const delTarget = ref(null)          // 要删的那条
const delIsTree = ref(false)         // ★ 它是不是顶层(删了会带走整棵树)

// 评论总数 = 顶层 + 所有回复
const totalCount = computed(
  () => comments.value.reduce((n, c) => n + 1 + (c.replies ? c.replies.length : 0), 0)
)

const inputPlaceholder = computed(() => {
  if (!isLogin.value) return '登录后可评论'
  return replyTo.value ? `回复 @${replyTo.value.author}…` : '说点什么…'
})

// ---- 收藏相关 ----
const showPicker = ref(false)      // 收藏面板开不开
const favCount = ref(0)            // 这篇被收进了几个收藏夹 (0 = 没收藏)
const favMsg = ref('')             // 收藏自己的错误提示 (不能复用上面的 error!)

// ---------- 拉评论列表 ----------
// ⚠️ token 是【可选】的: 带上后端才知道 can_delete / liked_by_me
const loadComments = async () => {
  const token = localStorage.getItem('token')      // 可能是 null
  try {
    const res = await getComments(articleId, sort.value, token)
    if (res.data.error) { showErr(res.data.error); return }
    comments.value = res.data
  } catch (e) {
    console.error('获取评论失败', e)
  }
}

// 切换排序 → 重新拉一次 (后端换 ORDER BY)
const switchSort = async (s) => {
  if (sort.value === s) return
  sort.value = s
  expanded.value = new Set()        // 换排序后收起所有展开
  await loadComments()
}

// 只显示前 3 条回复, 除非点了"展开"
const visibleReplies = (c) => (expanded.value.has(c.id) ? c.replies : c.replies.slice(0, 3))
const expand = (id) => { expanded.value = new Set([...expanded.value, id]) }
const collapse = (id) => {
  const s = new Set(expanded.value)
  s.delete(id)
  expanded.value = s
}

const goUser = (id) => { if (id) router.push(`/user/${id}`) }
const goArticle = (id) => { if (id) router.push(`/article/${id}`) }

// 页面下半部分的内容: 相关阅读 + 作者的其他文章
// ★ 这是"装饰性内容" —— 加载失败【不能】影响正文, 所以整段包 try
const loadMoreSections = async () => {
  if (!article.value) return
  try {
    // ① 作者的其他文章 (顺手拿个人主页的数据)
    const pr = await getUserProfile(article.value.user_id)
    authorArticles.value = (pr.data.articles || [])
      .filter(a => a.id !== articleId)
      .slice(0, 5)

    // ② 相关阅读: 优先同分类; 没分类就取最新的一批
    const cat = article.value.category || ''
    const rr = await getPublicArticles(1, 7, '', cat)
    related.value = (rr.data.items || [])
      .filter(a => a.id !== articleId)
      .slice(0, 6)
  } catch (e) {
    // 只影响"底部推荐", 不影响正文和评论
    console.error('相关阅读加载失败:', e)
  }
}

// 时间 → 人话
const fmtTime = (s) => {
  if (!s) return ''
  const d = new Date(s.replace(' ', 'T'))
  if (isNaN(d)) return ''
  const min = Math.floor((Date.now() - d.getTime()) / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day} 天前`
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

// 提示条: 默认是"成功"样式 (柔和青绿)
const toast = (m, ok = true) => {
  cMsg.value = m
  cMsgOk.value = ok
  setTimeout(() => { if (cMsg.value === m) cMsg.value = '' }, 2000)
}

// 错误提示: 红色
const showErr = (m) => {
  cMsg.value = m
  cMsgOk.value = false
}

onMounted(async () => {
  loading.value = true
  const id = route.params.id
  try {
    // ① 先按"公开文章"拿 (任何人都能看)
    //    带上 token: 后端才能告诉我们 liked_by_me
    const res = await getArticle(id, localStorage.getItem('token'))
    if (!res.data.error) {
      article.value = res.data
    } else {
      // ② 不是公开的 → 如果登录了, 再试"我自己的"(含私有)
      const token = localStorage.getItem('token')
      if (token) {
        const res2 = await getMyArticle(token, id)
        if (!res2.data.error) {
          article.value = res2.data          // 作者看自己的私有文章 ✓
        } else {
          error.value = res2.data.error
        }
      } else {
        error.value = res.data.error
      }
    }
    // 拿到文章了 → 拉评论
    if (article.value) await loadComments()
    // ★ 点赞的状态直接从文章详情里拿 (后端已经算好放在返回里了, 不用再发请求)
    if (article.value) {
      likeCount.value = article.value.like_count || 0
      liked.value = article.value.liked_by_me || false
    }
    // 再问一次"这篇被收进了几个夹子", 让收藏按钮一开始就显示正确状态
    await loadFavCount()
    // 问一次"我关注作者了吗", 让关注按钮显示对的状态
    await loadFollowStatus()
    // 问一次"我是谁" —— 用来判断"这是不是我自己的文章"(自己的文章不显示关注按钮)
    await loadMyId()
    // ★ 底部推荐【不 await】—— 让它自己慢慢加载, 不拖慢正文显示
    loadMoreSections()
    // 顺便记一笔浏览历史
    await recordHistory()
  } catch (e) {
    error.value = '加载失败：' + e.message
  }
  loading.value = false
})

// ---------- 发评论 / 回复 ----------
const handleComment = async () => {
  const text = newComment.value.trim()
  if (!text) return
  const token = localStorage.getItem('token')
  if (!token) { goLogin(router); return }
  if (cBusy.value) return

  cBusy.value = true
  try {
    // replyTo 有值 → 回复那条; 没有 → 发顶层评论
    const res = await addComment(token, articleId, text, replyTo.value ? replyTo.value.id : null)
    if (res.data.error) { showErr(res.data.error); return }

    newComment.value = ''
    if (replyRoot.value) expand(replyRoot.value)   // 展开那棵树, 好看见自己刚发的
    replyTo.value = null
    replyRoot.value = null
    await loadComments()
    toast('发布成功')
  } catch (e) {
    showErr('评论失败：' + e.message)
  }
  cBusy.value = false
}

// ---------- 点某条评论的「回复」 ----------
// root 参数: 回复的是【一条回复】时, 把它的顶层评论传进来 (用来展开那棵树)
const startReply = (c, root = null) => {
  if (!isLogin.value) { goLogin(router); return }
  replyTo.value = { id: c.id, author: c.author }
  replyRoot.value = root ? root.id : c.id
  document.querySelector('.c-input input')?.focus()
}
const cancelReply = () => { replyTo.value = null; replyRoot.value = null }

// ---------- 点赞 / 取消 ----------
// ⚠️ 本地先改 (点一下立刻有反馈), 失败了再回滚
const toggleLike = async (c) => {
  if (!isLogin.value) { goLogin(router); return }
  const token = localStorage.getItem('token')

  const wasLiked = c.liked_by_me
  c.liked_by_me = !wasLiked
  c.like_count += wasLiked ? -1 : 1

  try {
    // 重复点赞/重复取消, 后端都返回 message(当成功), 不报错
    await (wasLiked ? unlikeComment(token, c.id) : likeComment(token, c.id))
  } catch (e) {
    c.liked_by_me = wasLiked          // 回滚
    c.like_count += wasLiked ? 1 : -1
    toast('操作失败', false)
  }
}

// ---------- 删除 ----------
// c.replies !== undefined → 它是顶层评论 (删了带走整棵树)
const askDelete = (c) => {
  delTarget.value = c
  delIsTree.value = c.replies !== undefined
  showDel.value = true
}

const doDelete = async () => {
  const token = localStorage.getItem('token')
  if (!token) { goLogin(router); return }
  try {
    const res = await deleteComment(token, delTarget.value.id)
    if (res.data.error) { showErr(res.data.error); showDel.value = false; return }
    showDel.value = false
    delTarget.value = null
    await loadComments()
    toast('已删除')
  } catch (e) {
    showErr('删除失败：' + e.message)
    showDel.value = false
  }
}

// ---------- 点"收藏"按钮: 打开收藏面板 ----------
const openPicker = () => {
  if (!isLogin.value) {          // 没登录 → 去登录 (跟上面发评论的处理一样)
    goLogin(router)
    return
  }
  favMsg.value = ''
  showPicker.value = true
}

// 面板里每改一次, 它就把新的数量报给我, 我不用再发一次请求
const onFavChanged = (n) => { favCount.value = n }

// ---------- 跳作者的个人主页 ----------
const goAuthor = () => {
  if (article.value?.user_id) router.push(`/user/${article.value.user_id}`)
}

// ---------- 文章点赞 ----------
const likeCount = ref(0)
const liked = ref(false)
const likeBusy = ref(false)

// 点赞/取消 —— 跟评论点赞一样: 本地先改(点一下立刻有反馈), 失败再回滚
const toggleLikeArticle = async () => {
  if (!isLogin.value) { goLogin(router); return }
  const token = localStorage.getItem('token')
  if (likeBusy.value) return
  likeBusy.value = true

  const was = liked.value
  liked.value = !was
  likeCount.value += was ? -1 : 1

  try {
    // 重复点赞/重复取消, 后端都返回 message(当成功), 不会报错
    const res = await (was
      ? unlikeArticle(token, articleId)
      : likeArticle(token, articleId))
    if (res.data.error) {                 // 后端业务错误 → 回滚
      liked.value = was
      likeCount.value += was ? 1 : -1
      favMsg.value = res.data.error
    }
  } catch (e) {
    liked.value = was
    likeCount.value += was ? 1 : -1
    favMsg.value = '操作失败：' + e.message
  }
  likeBusy.value = false
}

// ---------- 关注 ----------
const following = ref(false)        // 我关没关注这篇文章的作者
const followBusy = ref(false)       // 请求锁: 防止连点两次
const myId = ref(null)              // 我是谁 (用来判断"这是我自己的文章")
const isMe = computed(() => myId.value !== null && article.value?.user_id === myId.value)

// 点一下 → 关注/取关切换
const toggleFollow = async () => {
  const token = localStorage.getItem('token')
  if (!token) { goLogin(router); return }
  if (followBusy.value) return            // 正在请求中, 直接忽略这次点击

  followBusy.value = true
  try {
    const uid = article.value.user_id
    const res = following.value
      ? await unfollowUser(token, uid)    // 已关注 → 取关
      : await followUser(token, uid)      // 没关注 → 关注

    // ⚠️ 后端业务错误是 200 + {error}, 要自己查
    if (res.data.error) { favMsg.value = res.data.error; return }

    // ⚠️ 注意: 重复关注时后端返回 {message: "已经关注过了"} —— 那是【成功】,
    //    不是错误。所以这里不判断 message 内容, 直接把状态切成"已关注"就行。
    //    (跟收藏功能那边"把重复收藏当成功"是同一个思路)
    following.value = !following.value
  } catch (e) {
    console.error('关注操作失败', e)
    favMsg.value = '操作失败：' + e.message
  }
  followBusy.value = false
}

// 进页面时问一次"我关注他了吗"
// 【静默失败】: 这只是决定按钮显示什么字, 失败了不该影响看文章
const loadFollowStatus = async () => {
  if (!isLogin.value || !article.value) return
  const token = localStorage.getItem('token')
  try {
    const res = await getFollowStatus(token, article.value.user_id)
    if (!res.data.error) following.value = res.data.following
  } catch (e) {
    console.error('获取关注状态失败', e)
  }
}

// 问一次"我是谁" (同样静默失败 —— 只影响按钮显不显示, 不影响看文章)
const loadMyId = async () => {
  if (!isLogin.value) return
  const token = localStorage.getItem('token')
  try {
    const res = await getMe(token)
    if (!res.data.error) myId.value = res.data.id
  } catch (e) {
    console.error('获取我的信息失败', e)
  }
}

// 没有头像时用 emoji 占位 (跟其他页面一个套路: 名字的字符和决定用哪只动物)

// 发布时间: "2026-09-23 11:42:47" → "2026年9月23日"
const fmtDate = (s) => {
  if (!s) return ''
  const d = new Date(s.replace(' ', 'T'))
  if (isNaN(d)) return ''
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

// ---------- 进页面时先问一次"这篇在哪些收藏夹里" ----------
// 这里【故意静默失败】(只 console.error): 这只是个装饰性的数字,
// 不能因为它的请求失败就让整篇文章打不开
const loadFavCount = async () => {
  if (!isLogin.value) return              // 没登录就别发了, 必然 401
  const token = localStorage.getItem('token')
  try {
    const res = await getCollectionsOfArticle(token, articleId)
    if (res.data.error) return            // 后端业务错误 (200 + error)
    favCount.value = res.data.filter((c) => c.favorited).length
  } catch (e) {
    console.error('获取收藏状态失败', e)
  }
}

// ---------- 顺便记一笔浏览历史 ----------
// 【静默调用】: 这只是"顺手记一下"的小事, 失败了绝不能影响文章打开
//   —— 记不上浏览历史是小事, 文章打不开是大事
// 没登录就不记 (后端也要求登录才能记)
const recordHistory = async () => {
  if (!isLogin.value) return
  const token = localStorage.getItem('token')
  try {
    await addHistory(token, articleId)
  } catch (e) {
    console.error('记录浏览历史失败', e)
  }
}
</script>

<style scoped>
/* ★ 改成左右两栏: 左边正文, 右边作者卡片。所以整体要放宽 */
.detail { max-width: 1200px; padding-top: 24px; }

/* 两栏布局: 左边自动占满, 右边固定 260px */
.layout { display: flex; gap: 20px; align-items: flex-start; }
.main { flex: 1; min-width: 0; }        /* min-width:0 防止长代码块把布局撑破 */
.side { width: 260px; flex-shrink: 0; }

/* 窄屏幕(手机/小窗)时改成上下堆叠, 作者卡片跑到下面去 */
@media (max-width: 900px) {
  .layout { flex-direction: column; }
  .side { width: 100%; }
}

/* ---------- 右侧作者卡片 ---------- */
.ac { padding: 22px 20px; margin-bottom: 14px; text-align: center; }

.ac-avatar {
  width: 64px; height: 64px; border-radius: 50%; margin: 0 auto 12px;
  background: linear-gradient(135deg, #ccfbf1 0%, #a5b4fc 100%);
  display: flex; align-items: center; justify-content: center;
  font-size: 28px; cursor: pointer; overflow: hidden;
}
.ac-avatar img { width: 100%; height: 100%; object-fit: cover; }

.ac-name {
  font-size: 15px; font-weight: 600; color: #1f2937;
  cursor: pointer; margin-bottom: 10px;
}
.ac-name:hover { color: #14b8a6; }

.ac-bio {
  font-size: 12px; color: #6b7280; line-height: 1.7;
  margin-bottom: 16px; word-break: break-word;
}

/* 关注按钮: 没关注 = 实心青绿; 已关注 = 白底描边 */
.ac-follow {
  width: 100%; padding: 9px 0; border: none; border-radius: 10px;
  background: #14b8a6; color: #fff; font-size: 13px; font-weight: 600;
  cursor: pointer; margin-bottom: 8px; transition: all 0.15s;
}
.ac-follow:hover { background: #0d9488; }
.ac-follow:disabled { opacity: 0.6; cursor: not-allowed; }
/* ← 已关注的样子 */
.ac-follow.on {
  background: #fff; color: #14b8a6; border: 1px solid #14b8a6;
}
.ac-follow.on:hover { background: #f0fdfa; }
/* 自己的文章: 不是按钮, 是个说明 */
.ac-follow.mine {
  background: #f1f5f9; color: #94a3b8; font-weight: 400; cursor: default;
}
.ac-follow.mine:hover { background: #e2e8f0; }
.ac-home {
  width: 100%; padding: 8px 0; border: 1px solid #e6ebf2; border-radius: 10px;
  background: #fff; color: #64748b; font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.ac-home:hover { border-color: #14b8a6; color: #14b8a6; }

/* ---- 右侧栏: 作者的其他文章 ---- */
.ac-side-title {
  font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 10px;
}
.side-art {
  font-size: 12px; line-height: 1.5; color: #4b5563;
  padding: 8px 0; border-bottom: 1px dashed #eef1f6;
  cursor: pointer; overflow-wrap: anywhere;
  transition: color 0.15s;
}
.side-art:last-of-type { border-bottom: none; }
.side-art:hover { color: #0f766e; }

/* ---- 底部: 相关阅读 ---- */
.related { padding: 22px 26px; }
.rel-title {
  font-size: 16px; font-weight: 700; color: #1f2937; margin-bottom: 14px;
}
.rel-grid {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px;
}
.rel-item {
  padding: 12px 14px; border-radius: 12px;
  background: #f8fafc; border: 1px solid transparent;
  cursor: pointer; transition: all 0.16s;
}
.rel-item:hover {
  background: #f0fdfa; border-color: #ccfbf1;
  transform: translateY(-2px);
}
.rel-name {
  font-size: 13px; font-weight: 600; color: #1f2937;
  line-height: 1.5; margin-bottom: 6px; overflow-wrap: anywhere;
}
.rel-meta {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 11px; color: #9aa5b1;
}
.rel-author { color: #14b8a6; }

/* 系列那块: 先占位, 第 6 步再填真内容 */
.placeholder { background: #fafcfc; border: 1px dashed #e6ebf2; }
.ph-title { font-size: 13px; color: #64748b; font-weight: 600; margin-bottom: 6px; }
.ph-tip { font-size: 12px; color: #b6c0cc; }

.back {
  border: none; background: transparent; cursor: pointer;
  font-size: 14px; color: #4b5563; padding: 6px 12px; border-radius: 8px;
  margin-bottom: 16px;
}
.back:hover { background: #f0fdfa; color: #14b8a6; }

/* 文章 */
.art { padding: 34px 40px; margin-bottom: 18px; }
.title { font-size: 28px; color: #1f2937; margin-bottom: 16px; line-height: 1.4; }
.meta { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.avatar {
  width: 28px; height: 28px; border-radius: 50%;
  background: linear-gradient(135deg, #ccfbf1 0%, #a5b4fc 100%);
  display: flex; align-items: center; justify-content: center; font-size: 14px;
}
.author { font-size: 14px; color: #4b5563; }
.clickable { cursor: pointer; }
.clickable:hover { color: #14b8a6; text-decoration: underline; }
.time { font-size: 12px; color: #9aa5b1; }

/* 点赞按钮: margin-left:auto 把这【一组按钮】推到这一行最右边
   (注意 auto 只写在点赞上 —— 收藏跟在它后面就行) */
.like-btn {
  margin-left: auto;
  padding: 7px 16px; border: 1px solid #e6ebf2; border-radius: 20px;
  background: #fff; color: #4b5563; font-size: 13px; cursor: pointer;
  transition: all 0.18s;
}
.like-btn:hover { border-color: #14b8a6; color: #14b8a6; }
/* 已点赞 → 实心青绿 */
.like-btn.on { background: #14b8a6; border-color: #14b8a6; color: #fff; font-weight: 600; }
.like-btn.on:hover { background: #0d9488; }

.fav-btn {
  padding: 7px 16px; border: 1px solid #e6ebf2; border-radius: 20px;
  background: #fff; color: #4b5563; font-size: 13px; cursor: pointer;
  transition: all 0.18s;
}
.fav-btn:hover { border-color: #14b8a6; color: #14b8a6; }
/* 已收藏 → 实心青绿 */
.fav-btn.on { background: #14b8a6; border-color: #14b8a6; color: #fff; font-weight: 600; }
.fav-btn.on:hover { background: #0d9488; }

.fav-msg { color: #e74c3c; font-size: 13px; margin-top: -8px; margin-bottom: 10px; }

hr { border: none; border-top: 1px solid #eef1f6; margin: 18px 0; }
/* ⚠️ 这里【不能】写 white-space: pre-wrap —— 那是给纯文本用的,
   会把你换行、空格原样保留, 跟 Markdown 渲染出来的 HTML 冲突。
   Markdown 正文的样式统一在全局 style.css 的 .md-body 里。 */
.empty-content { color: #a8b2c1; }

/* ---- 正文底部的标签 ---- */
.tag-list {
  display: flex; align-items: center; flex-wrap: wrap; gap: 8px;
  margin-top: 26px; padding-top: 16px;
  border-top: 1px dashed #eef1f6;
}
.tag-list-label {
  font-size: 12px; color: #9aa5b1; margin-right: 2px;
}
.tag-chip {
  display: inline-block;
  padding: 4px 10px; border-radius: 8px;
  background: #f0fdfa; color: #0f766e;
  font-size: 12px; line-height: 1.5;
  cursor: pointer; transition: all 0.15s;
}
.tag-chip:hover { background: #ccfbf1; transform: translateY(-1px); }

/* 评论区 */
.comments { padding: 24px 28px; }

.c-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.c-title { font-size: 17px; }

/* 排序切换 (最新 / 最热) */
.sort-tabs { display: flex; gap: 6px; }
.sort-tabs button {
  padding: 5px 14px; border: none; border-radius: 14px;
  background: #f1f5f9; color: #64748b; font-size: 12px; cursor: pointer;
  transition: all 0.15s;
}
.sort-tabs button.on { background: #14b8a6; color: #fff; font-weight: 600; }

/* ---- 发评论 / 回复 ---- */
.c-input { margin-bottom: 18px; }

.reply-hint {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: #0f766e; background: #f0fdfa;
  padding: 7px 14px; border-radius: 10px; margin-bottom: 8px;
}
.reply-hint b { font-weight: 600; }
.cancel-reply {
  margin-left: auto; border: none; background: transparent;
  color: #94a3b8; font-size: 14px; cursor: pointer; padding: 0 4px;
}
.cancel-reply:hover { color: #e74c3c; }

.input-row { display: flex; gap: 10px; }
.input-row input {
  flex: 1; min-width: 0; padding: 11px 16px; border: 1px solid #e6ebf2;
  border-radius: 20px; font-size: 14px; outline: none; background: #f9fcfb;
}
.input-row input:focus { border-color: #14b8a6; background: #fff; }
.input-row .send {
  padding: 0 22px; border: none; border-radius: 20px; cursor: pointer;
  background: #14b8a6; color: #fff; font-size: 14px; font-weight: 600;
}
.input-row .send:hover { background: #0d9488; }
.input-row .send:disabled { opacity: 0.6; cursor: not-allowed; }

/* 提示条: 成功 = 柔和青绿; 失败才用红色 (.err) */
.c-msg {
  color: #0f766e;
  background: #f0fdfa;
  border: 1px solid #ccfbf1;
  font-size: 12.5px;
  font-weight: 500;
  letter-spacing: 0.2px;
  line-height: 1.6;
  margin-bottom: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  text-align: center;
}
.c-msg.err {
  color: #c0392b;
  background: #fef2f2;
  border-color: #fee2e2;
}

/* ---- 评论条目 ---- */
.c-block { border-top: 1px solid #f4f7f6; }
.c-block:first-child { border-top: none; }

.c-item {
  display: flex; gap: 10px; padding: 12px 0;
  align-items: flex-start;        /* 头像跟第一行对齐, 不要垂直居中 */
}
/* ★★ min-width: 0 不能省 —— 长评论撑破屏幕就靠它
   flex 子项默认 min-width: auto = "我最少要跟我内容一样宽"
   长评论很宽 → 它不肯被压缩 → 顶破容器
   写 0 才是告诉它"你可以比我内容还窄, 该换行就换行" */
.c-body { flex: 1; min-width: 0; }

.c-avatar {
  width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0;
  background: linear-gradient(135deg, #ccfbf1 0%, #a5b4fc 100%);
  display: flex; align-items: center; justify-content: center; font-size: 14px;
}
.c-avatar.small { width: 24px; height: 24px; font-size: 11px; }

.c-author { font-size: 13px; color: #0f766e; font-weight: 600; }
.c-author .clickable { cursor: pointer; }
.c-author .clickable:hover { text-decoration: underline; }
.c-time { color: #b6c0cc; font-weight: 400; font-size: 12px; margin-left: 8px; }

.c-content {
  font-size: 14px; color: #374151; margin-top: 4px; line-height: 1.6;
  overflow-wrap: anywhere;      /* 长串(URL/长英文)能断 */
  word-break: break-word;
}

/* ---- 操作行 (赞 / 回复 / 删除) ---- */
.c-ops { display: flex; gap: 14px; margin-top: 6px; }
.c-ops .op {
  border: none; background: transparent; cursor: pointer;
  font-size: 12px; color: #94a3b8; padding: 2px 0;
  transition: color 0.15s;
}
.c-ops .op:hover { color: #14b8a6; }
.c-ops .op.on { color: #14b8a6; font-weight: 600; }
.c-ops .op.danger:hover { color: #e74c3c; }

/* ---- 回复区 (缩进一层) ---- */
.c-replies {
  margin-left: 40px;                       /* 缩进 = "我在回复上面那条" */
  padding-left: 14px;
  border-left: 2px solid #f1f5f9;          /* 左边一条竖线, 像 B站 */
}

.more {
  border: none; background: transparent; cursor: pointer;
  font-size: 12px; color: #0f766e; padding: 6px 0;
}
.more:hover { text-decoration: underline; }

.c-empty { text-align: center; color: #a8b2c1; padding: 24px 0; font-size: 13px; }

/* ---- 删除确认弹窗 ---- */
.del-text { font-size: 14px; color: #4b5563; line-height: 1.8; }
.del-text b { color: #e74c3c; }
.del-quote {
  font-size: 13px; color: #6b7280; background: #f8fafc;
  padding: 10px 14px; border-radius: 8px; margin: 12px 0;
  overflow-wrap: anywhere; word-break: break-word;
  max-height: 80px; overflow-y: auto;
}
.del-tip { font-size: 12px; color: #a8b2c1; }
.m-btns { display: flex; gap: 10px; justify-content: flex-end; margin-top: 18px; }
.m-btns button {
  padding: 9px 20px; border: none; border-radius: 10px;
  font-size: 14px; cursor: pointer;
}
.m-btns .cancel { background: #f1f5f9; color: #64748b; }
.m-btns .cancel:hover { background: #e2e8f0; }
.m-btns .danger { background: #e74c3c; color: #fff; font-weight: 600; }
.m-btns .danger:hover { background: #c0392b; }

.err { text-align: center; color: #a8b2c1; padding: 60px 0; }
</style>
