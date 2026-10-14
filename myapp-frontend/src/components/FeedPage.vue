<template>
  <div class="page feed-page">
    <!-- ★ 左右两栏: 左边「我关注的人」, 右边「动态流」
         (跟「我的收藏」页一个结构) -->
    <div class="layout">
      <!-- ========== 左: 我关注的人 ========== -->
      <aside class="side card">
        <div class="side-head">
          <span>我的关注</span>
          <span class="cnt">{{ following.length }}</span>
        </div>

        <div v-if="followingLoading" class="side-tip">加载中...</div>

        <template v-else-if="following.length">
          <div
            v-for="u in following"
            :key="u.id"
            class="f-item"
            @click="$router.push(`/user/${u.id}`)"
          >
            <div class="f-avatar">
              <img v-if="u.avatar" :src="u.avatar" alt="" />
              <span v-else>{{ emojiOf(u.username) }}</span>
            </div>
            <div class="f-text">
              <p class="f-name">{{ u.username }}</p>
              <p class="f-time">{{ u.last_update ? fmtTime(u.last_update) + '更新' : '还没发过文章' }}</p>
            </div>
          </div>
        </template>

        <p v-else class="side-tip">还没关注任何人</p>
      </aside>

      <!-- ========== 右: 动态流 ========== -->
      <div class="main">
        <div class="head">
          <h2>动态</h2>
          <p class="sub">我关注的人发的新文章</p>
        </div>

        <p v-if="loading" class="tip">加载中...</p>
        <p v-else-if="error" class="tip">{{ error }}</p>

        <template v-else>
          <div v-if="items.length" class="list">
            <div
              v-for="(a, i) in items"
              :key="a.id"
              class="item card hoverable"
              @click="goDetail(a.id)"
            >
              <div class="cover" :class="coverOf(i)">{{ emojiOf(a.author) }}</div>
              <div class="art-text">
                <p class="t"><strong>{{ a.title }}</strong></p>
                <p class="c">{{ stripMarkdown(a.content) || '（无内容）' }}</p>
                <p class="meta">
                  <span class="author-link" @click.stop="goUser(a.user_id)">{{ a.author }}</span>
                  · {{ fmtTime(a.created_at) }}
                </p>
              </div>
            </div>
          </div>

          <!-- 空状态 -->
          <div v-else class="empty card">
            <p class="em-ico">👀</p>
            <p v-if="following.length">你关注的人还没发新文章～</p>
            <p v-else>你还没有关注任何人</p>
            <p class="em-sub">去首页逛逛，看到喜欢的作者点进他的主页 → 点「+ 关注」</p>
            <button class="em-btn" @click="$router.push('/home')">去首页看看</button>
          </div>

          <!-- 分页 -->
          <div v-if="pages > 1" class="pager">
            <button :disabled="page <= 1" @click="go(page - 1)">‹ 上一页</button>
            <span>{{ page }} / {{ pages }}</span>
            <button :disabled="page >= pages" @click="go(page + 1)">下一页 ›</button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getMyFeed, getMyFollowing } from '../services/authApi.js'
import { stripMarkdown } from '../utils/markdown.js'

const router = useRouter()

const items = ref([])
const page = ref(1)
const pages = ref(1)
const loading = ref(false)
const error = ref('')

const following = ref([])          // 左侧栏: 我关注的人
const followingLoading = ref(false)

const goDetail = (id) => router.push(`/article/${id}`)
const goUser = (id) => { if (id) router.push(`/user/${id}`) }

// ---- 封面装饰 (跟其他列表页一个套路, 纯样式) ----
const covers = ['cover-1', 'cover-2', 'cover-3', 'cover-4', 'cover-5', 'cover-6']
const coverOf = (i) => covers[i % covers.length]
const emojiOf = (name) => {
  const pool = ['🐦', '🐕', '🐳', '🐱', '🦊', '🐼']
  let n = 0
  for (const ch of (name || '?')) n += ch.charCodeAt(0)
  return pool[n % pool.length]
}

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

// ---- 统一处理 401 ----
const handleErr = (err) => {
  if (err.response && err.response.status === 401) {
    localStorage.removeItem('token')
    router.push('/login')
  } else {
    error.value = '加载失败：' + err.message
  }
}

// 左侧栏: 我关注的人 (静默失败 —— 挂了不影响看动态)
const loadFollowing = async () => {
  const token = localStorage.getItem('token')
  if (!token) return
  followingLoading.value = true
  try {
    const res = await getMyFollowing(token)
    if (!res.data.error) following.value = res.data
  } catch (e) {
    console.error('获取关注列表失败', e)
  }
  followingLoading.value = false
}

// 右侧: 动态流
const load = async () => {
  const token = localStorage.getItem('token')
  if (!token) { router.push('/login'); return }   // 这个页必须登录

  loading.value = true
  error.value = ''
  try {
    const res = await getMyFeed(token, page.value)
    if (res.data.error) {
      error.value = res.data.error
    } else {
      items.value = res.data.items
      pages.value = res.data.pages
    }
  } catch (err) {
    handleErr(err)
  }
  loading.value = false
}

const go = (p) => {
  page.value = p
  load()
  document.querySelector('.main')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

onMounted(() => {
  loadFollowing()
  load()
})
</script>

<style scoped>
/* ★ 两栏布局 (跟「我的收藏」页一个结构) */
.feed-page { max-width: 1080px; padding-top: 24px; }
.layout { display: flex; gap: 20px; align-items: flex-start; }
.side { width: 230px; flex-shrink: 0; }
.main { flex: 1; min-width: 0; }

/* 窄屏改成上下堆叠 */
@media (max-width: 900px) {
  .layout { flex-direction: column; }
  .side { width: 100%; }
  /* 手机上看, 关注列表太长会把动态挤到很下面, 先隐藏 */
  .side { display: none; }
}

/* ---------- 左: 关注列表 ---------- */
.side { padding: 16px 8px; }
.side-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 10px 12px; font-size: 14px; font-weight: 600; color: #374151;
  border-bottom: 1px solid #f1f5f9; margin-bottom: 8px;
}
.cnt { font-size: 12px; color: #9aa5b1; font-weight: 400; }

.f-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; border-radius: 10px; cursor: pointer;
  transition: background 0.15s;
}
.f-item:hover { background: #f0fdfa; }

.f-avatar {
  width: 34px; height: 34px; border-radius: 50%; flex-shrink: 0; overflow: hidden;
  background: linear-gradient(135deg, #ccfbf1 0%, #a5b4fc 100%);
  display: flex; align-items: center; justify-content: center; font-size: 16px;
}
.f-avatar img { width: 100%; height: 100%; object-fit: cover; }

.f-text { flex: 1; min-width: 0; }
.f-name {
  font-size: 13px; color: #374151; font-weight: 500;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.f-time { font-size: 11px; color: #b6c0cc; margin-top: 2px; }

.side-tip { font-size: 12px; color: #b6c0cc; text-align: center; padding: 20px 0; }

/* ---------- 右: 动态流 ---------- */
.head { margin-bottom: 18px; }
.head h2 { font-size: 20px; }
.sub { font-size: 13px; color: #9aa5b1; margin-top: 6px; }

.item {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 18px; margin-bottom: 10px; cursor: pointer;
}
.cover {
  width: 54px; height: 54px; border-radius: 12px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 24px;
}
.art-text { flex: 1; min-width: 0; }
.t { font-size: 15px; }
.c {
  color: #6b7280; margin-top: 5px; font-size: 13px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.meta { color: #9aa5b1; font-size: 12px; margin-top: 6px; }
.author-link { cursor: pointer; color: #0f766e; }
.author-link:hover { color: #14b8a6; text-decoration: underline; }

.tip { text-align: center; color: #a8b2c1; padding: 60px 0; }

/* 空状态 */
.empty { text-align: center; padding: 56px 20px; }
.em-ico { font-size: 42px; margin-bottom: 14px; }
.empty p { font-size: 14px; color: #8b95a3; }
.em-sub { font-size: 12px; color: #a8b2c1; margin-top: 8px; }
.em-btn {
  margin-top: 20px; padding: 9px 24px; border: none; border-radius: 20px;
  background: #14b8a6; color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;
}
.em-btn:hover { background: #0d9488; }

/* 分页 */
.pager {
  display: flex; align-items: center; justify-content: center; gap: 16px;
  margin-top: 24px; font-size: 13px; color: #8b95a3;
}
.pager button {
  padding: 7px 16px; border: 1px solid #e6ebf2; border-radius: 8px;
  background: #fff; color: #64748b; font-size: 13px; cursor: pointer;
}
.pager button:hover:not(:disabled) { border-color: #14b8a6; color: #14b8a6; }
.pager button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
