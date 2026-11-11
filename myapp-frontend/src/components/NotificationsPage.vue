<template>
  <div class="page notif-page">
    <div class="layout">
      <!-- ================= 左栏: 来源分类 ================= -->
      <aside class="side card">
        <div class="side-title">🔔 消息中心</div>

        <div
          v-for="c in categories" :key="c.key"
          class="nav-item"
          :class="{ on: view === 'list' && category === c.key }"
          @click="switchCategory(c.key)"
        >
          <span class="nav-label">{{ c.label }}</span>
          <span v-if="countOf(c.key) > 0" class="nav-badge">
            {{ countOf(c.key) > 99 ? '99+' : countOf(c.key) }}
          </span>
        </div>

        <div class="side-line"></div>

        <div class="nav-item" @click="$router.push('/messages')">
          <span class="nav-label">✉️ 私信</span>
          <span v-if="stats.message_unread > 0" class="nav-badge">
            {{ stats.message_unread > 99 ? '99+' : stats.message_unread }}
          </span>
        </div>

        <div
          class="nav-item"
          :class="{ on: view === 'settings' }"
          @click="openSettings"
        >
          <span class="nav-label">⚙️ 消息设置</span>
        </div>
      </aside>

      <!-- ================= 右栏: 内容 ================= -->
      <section class="main card">
        <!-- 私信入口: 放在最上面, 一眼能看到 -->
        <div class="pm-entry" @click="$router.push('/messages')">
          <div class="pm-left">
            <span class="pm-ico">✉️</span>
            <div>
              <p class="pm-title">私信</p>
              <p class="pm-sub">和站内用户一对一聊天</p>
            </div>
          </div>
          <span class="pm-right">
            <span v-if="stats.message_unread > 0" class="pm-badge">
              {{ stats.message_unread > 99 ? '99+' : stats.message_unread }} 条未读
            </span>
            <span v-else>去聊天 →</span>
          </span>
        </div>

        <!-- ---------- 列表 ---------- -->
        <template v-if="view === 'list'">
          <div class="main-head">
            <h2>{{ currentLabel }}</h2>
            <div class="head-actions">
              <button class="btn" :disabled="unread === 0" @click="markAll">全部已读</button>
              <button class="btn danger" :disabled="items.length === 0" @click="showClear = true">
                {{ category ? '清空本类' : '清空' }}
              </button>
            </div>
          </div>

          <p v-if="loading" class="tip">加载中...</p>
          <p v-else-if="items.length === 0" class="tip">
            这里还没有消息～
            <br />
            <span class="tip-sub">别人赞你、评论你、关注你的时候，会出现在这里</span>
          </p>

          <div v-else class="notif-list">
            <div
              v-for="n in items" :key="n.id"
              class="notif-row"
              :class="{ unread: !n.is_read, clickable: !!n.link }"
              @click="open(n)"
            >
              <div class="n-avatar">
                <IconUser />
                <span class="n-type">{{ TYPE_ICON[n.type] || '🔔' }}</span>
              </div>

              <div class="n-body">
                <p class="n-text">{{ n.content }}</p>
                <p class="n-meta">
                  <span v-if="n.from_username" class="n-from">{{ n.from_username }}</span>
                  <span>{{ fmtTime(n.created_at) }}</span>
                </p>
              </div>

              <span v-if="!n.is_read" class="dot" title="未读"></span>
            </div>
          </div>

          <!-- 分页 -->
          <div v-if="pages > 1" class="pager">
            <button class="pg-btn" :disabled="page === 1" @click="goPage(page - 1)">‹ 上一页</button>
            <button
              v-for="p in pageList" :key="p"
              class="pg-num" :class="{ on: p === page }"
              @click="goPage(p)"
            >{{ p }}</button>
            <button class="pg-btn" :disabled="page === pages" @click="goPage(page + 1)">下一页 ›</button>
          </div>
        </template>

        <!-- ---------- 设置 ---------- -->
        <template v-else>
          <div class="main-head">
            <h2>消息设置</h2>
          </div>

          <h3 class="s-title">通知开关</h3>
          <p class="s-tip">关掉之后，这类通知不再产生。没有设置过的默认开启。</p>
          <div class="switch-list">
            <label v-for="s in settings" :key="s.type" class="switch-row">
              <span class="s-label">{{ TYPE_LABEL[s.type] || s.type }}</span>
              <input type="checkbox" :checked="s.enabled" @change="toggle(s)" />
            </label>
          </div>

          <h3 class="s-title greet-title">关注自动回复</h3>
          <p class="s-tip">
            别人关注你时，自动给对方发一条<b>私信</b>（不是通知，对方可以直接回复）。
            留空 = 不发送。
          </p>
          <textarea
            v-model="greeting"
            class="greet-input"
            maxlength="200"
            placeholder="比如：谢谢关注！有问题随时问我～"
          ></textarea>
          <div class="greet-actions">
            <span class="greet-msg">{{ greetMsg }}</span>
            <button class="btn" @click="saveGreeting">保存</button>
          </div>
        </template>
      </section>
    </div>

    <!-- 清空确认 -->
    <Modal v-model="showClear" title="清空消息">
      <p class="clear-text">
        确定清空{{ category ? `「${currentLabel}」下的` : '所有' }}消息吗？清空了就找不回来了。
      </p>
      <div class="m-btns">
        <button class="cancel" @click="showClear = false">再想想</button>
        <button class="danger" @click="doClear">确定清空</button>
      </div>
    </Modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  getNotifications, getUnreadCount, markNotificationRead, markAllNotificationsRead, clearNotifications,
  getNotificationSettings, updateNotificationSetting, updateFollowGreeting,
} from '../services/authApi.js'
import { goLogin } from '../utils/auth.js'
import Modal from './Modal.vue'

const router = useRouter()

// 左侧分类: key 会原样发给后端 (空字符串 = 全部)
const categories = [
  { key: '',       label: '全部消息' },
  { key: 'reply',  label: '评论与回复' },
  { key: 'like',   label: '收到的赞' },
  { key: 'follow', label: '新增关注' },
  { key: 'system', label: '系统通知' },
]

const TYPE_ICON = {
  like: '👍', comment: '💬', reply: '↩️',
  follow: '👤', system: '⚙️',
}
const TYPE_LABEL = {
  like: '有人赞我', comment: '有人评论我', reply: '有人回复我',
  follow: '有人关注我', system: '系统通知',
}

const view = ref('list')          // 'list' | 'settings'
const category = ref('')          // '' = 全部
const items = ref([])
const unread = ref(0)
// ★ 后端算好的未读统计: {unread, message_unread, total, by_category}
const stats = ref({ unread: 0, message_unread: 0, total: 0, by_category: {} })
const total = ref(0)
const pages = ref(0)
const page = ref(1)
const loading = ref(true)

const settings = ref([])
const greeting = ref('')
const greetMsg = ref('')

const showClear = ref(false)

const pageList = computed(() => Array.from({ length: pages.value }, (_, i) => i + 1))
const currentLabel = computed(
  () => categories.find(c => c.key === category.value)?.label || '全部消息'
)

const token = () => localStorage.getItem('token')

// 左边某一类显示几: 全部消息 = 通知未读总数, 其它 = by_category 里那一项
const countOf = (key) => {
  if (key === '') return stats.value.unread || 0
  return stats.value.by_category?.[key] || 0
}

// 改完数字(已读/清空)之后, 重新问一次后端, 再通知导航栏
const refreshStats = async () => {
  try {
    const r = await getUnreadCount(token())
    stats.value = r.data
    unread.value = r.data.unread || 0
  } catch (e) { /* 拿不到就先不更新 */ }
  window.dispatchEvent(new Event('unread-changed'))
}

// ---------- 时间显示 ----------
const fmtTime = (s) => {
  if (!s) return ''
  const d = new Date(s.replace(' ', 'T'))
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} 天前`
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

// ---------- 列表 ----------
const load = async () => {
  const t = token()
  if (!t) { goLogin(router); return }
  loading.value = true
  try {
    const res = await getNotifications(t, page.value, 20, category.value)
    items.value = res.data.items || []
    unread.value = res.data.unread || 0
    if (res.data.stats) stats.value = res.data.stats
    total.value = res.data.total || 0
    pages.value = res.data.pages || 0
  } catch (e) {
    console.error('加载通知失败:', e)
    items.value = []
  } finally {
    loading.value = false
  }
}

const switchCategory = (key) => {
  view.value = 'list'
  if (category.value === key) return
  category.value = key
  page.value = 1
  load()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const goPage = (p) => {
  if (p < 1 || p > pages.value) return
  page.value = p
  load()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

// 点一条: 先标已读, 再跳转
const open = async (n) => {
  if (!n.is_read) {
    try {
      await markNotificationRead(token(), n.id)
      n.is_read = true
      await refreshStats()       // 左边数字 + 导航栏红点一起更新
    } catch (e) { /* 标失败也不拦着跳转 */ }
  }
  if (n.link) router.push(n.link)
}

const markAll = async () => {
  try {
    await markAllNotificationsRead(token())
    items.value.forEach(n => { n.is_read = true })
    await refreshStats()
  } catch (e) {
    console.error(e)
  }
}

const doClear = async () => {
  try {
    // 传当前分类: 在"收到的赞"里点清空, 只清这一类的
    await clearNotifications(token(), category.value)
    showClear.value = false
    page.value = 1
    await load()          // ★ 重新拉一次: 列表和未读数都刷新
    window.dispatchEvent(new Event('unread-changed'))
  } catch (e) {
    console.error(e)
  }
}

// ---------- 设置 ----------
const openSettings = async () => {
  view.value = 'settings'
  if (settings.value.length === 0) await loadSettings()
}

const loadSettings = async () => {
  try {
    const res = await getNotificationSettings(token())
    settings.value = res.data.items || []
    greeting.value = res.data.follow_greeting || ''
  } catch (e) {
    console.error('加载设置失败:', e)
  }
}

const toggle = async (s) => {
  const next = !s.enabled
  try {
    await updateNotificationSetting(token(), s.type, next)
    s.enabled = next
  } catch (e) {
    console.error('保存设置失败:', e)
  }
}

const saveGreeting = async () => {
  try {
    const res = await updateFollowGreeting(token(), greeting.value)
    greeting.value = res.data.follow_greeting || ''
    greetMsg.value = '已保存'
    setTimeout(() => { greetMsg.value = '' }, 1500)
  } catch (e) {
    greetMsg.value = '保存失败'
  }
}

// ★ SSE 推来"有新通知"的信号 → 重新拉列表和未读数
//   (只推信号不推内容, 数据以数据库为准)
const onPush = () => {
  if (view.value === 'list') load()
}

onMounted(() => {
  load()
  window.addEventListener('notify-push', onPush)
})
onUnmounted(() => window.removeEventListener('notify-push', onPush))
</script>

<style scoped>
.notif-page { max-width: 1080px; }

/* 私信入口 */
.pm-entry {
  display: flex; align-items: center; justify-content: space-between; gap: 14px;
  margin: 16px 18px 6px;
  padding: 12px 16px;
  border-radius: 12px;
  background: linear-gradient(135deg, #f0fdfa 0%, #ffffff 70%);
  border: 1px solid #ccfbf1;
  cursor: pointer;
  transition: all 0.16s;
}
.pm-entry:hover { border-color: #14b8a6; transform: translateY(-1px); }
.pm-left { display: flex; align-items: center; gap: 12px; }
.pm-ico { font-size: 20px; }
.pm-title { font-size: 14px; font-weight: 700; color: #1f2937; }
.pm-sub { font-size: 11px; color: #9aa5b1; margin-top: 2px; }
.pm-right { font-size: 12px; color: #0f766e; flex-shrink: 0; }
.pm-badge {
  display: inline-block; padding: 3px 9px; border-radius: 12px;
  background: #e74c3c; color: #fff; font-size: 11px; font-weight: 600;
}

/* 左栏 + 右栏 */
.layout {
  display: grid;
  grid-template-columns: 200px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

/* ================= 左栏 ================= */
.side { padding: 16px 10px; }

.side-title {
  font-size: 15px; font-weight: 700; color: #1f2937;
  padding: 4px 10px 14px;
}

.nav-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; border-radius: 9px;
  font-size: 14px; color: #4b5563;
  cursor: pointer; transition: all 0.15s;
}
.nav-item:hover { background: #f7fffd; color: #0f766e; }
.nav-item.on { background: #f0fdfa; color: #0f766e; font-weight: 600; }

.nav-badge {
  min-width: 17px; height: 17px; padding: 0 5px;
  border-radius: 9px; background: #e74c3c; color: #fff;
  font-size: 10px; font-weight: 600; line-height: 17px; text-align: center;
}

.side-line {
  height: 1px; background: #eef1f6; margin: 10px 8px;
}

/* ================= 右栏 ================= */
.main {
  padding: 20px 24px;
  min-height: 560px;
}

.main-head {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; padding-bottom: 14px; margin-bottom: 12px;
  border-bottom: 1px solid #eef1f6; flex-wrap: wrap;
}
.main-head h2 { font-size: 17px; color: #1f2937; }
.head-actions { display: flex; gap: 8px; }

.btn {
  padding: 7px 13px; border: 1px solid #e6ebf2; border-radius: 9px;
  background: #fff; color: #64748b; font-size: 13px; font-family: inherit;
  cursor: pointer; transition: all 0.15s;
}
.btn:hover:not(:disabled) { border-color: #14b8a6; color: #0f766e; }
.btn:disabled { opacity: 0.45; cursor: default; }
.btn.danger:hover:not(:disabled) { border-color: #e74c3c; color: #c0392b; }

/* ---- 消息列表 ---- */
.tip {
  text-align: center; color: #9aa5b1; font-size: 13px;
  padding: 90px 0; line-height: 1.9;
}
.tip-sub { font-size: 12px; color: #b6c0cc; }

.notif-list { display: flex; flex-direction: column; }

.notif-row {
  display: flex; align-items: flex-start; gap: 12px;
  padding: 14px 10px;
  border-bottom: 1px solid #f4f7f6;
  border-left: 3px solid transparent;
  border-radius: 4px;
  transition: background 0.15s;
}
.notif-row:last-child { border-bottom: none; }
.notif-row.clickable { cursor: pointer; }
.notif-row.clickable:hover { background: #f8fffe; }
.notif-row.unread {
  border-left-color: #14b8a6;
  background: #f7fffd;
}

/* 头像 + 右上角的小类型图标 */
.n-avatar {
  position: relative;
  width: 38px; height: 38px; flex-shrink: 0;
  border-radius: 50%;
  background: #f0fdfa; color: rgba(15, 118, 110, 0.55);
  display: flex; align-items: center; justify-content: center;
}
.n-type {
  position: absolute; right: -3px; bottom: -3px;
  width: 18px; height: 18px; border-radius: 50%;
  background: #fff; border: 1px solid #eef1f6;
  font-size: 10px; line-height: 16px; text-align: center;
}

.n-body { flex: 1; min-width: 0; }
.n-text {
  font-size: 14px; color: #1f2937; line-height: 1.6;
  overflow-wrap: anywhere;
}
.notif-row.unread .n-text { font-weight: 600; }
.n-meta {
  display: flex; gap: 8px; margin-top: 5px;
  font-size: 11px; color: #9aa5b1;
}
.n-from { color: #14b8a6; }

.dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #14b8a6; flex-shrink: 0; margin-top: 8px;
}

/* 分页 */
.pager {
  display: flex; justify-content: center; align-items: center;
  gap: 6px; margin-top: 22px; flex-wrap: wrap;
}
.pg-btn, .pg-num {
  border: 1px solid #e6ebf2; background: #fff; color: #4b5563;
  border-radius: 9px; padding: 7px 12px; font-size: 13px; cursor: pointer;
}
.pg-btn:disabled { opacity: 0.45; cursor: default; }
.pg-num.on { background: #14b8a6; border-color: #14b8a6; color: #fff; }

/* ---- 设置 ---- */
.s-title { font-size: 14px; color: #374151; margin: 6px 0 6px; }
.greet-title { margin-top: 26px; }
.s-tip { font-size: 12px; color: #9aa5b1; margin-bottom: 12px; }

.switch-list {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 16px;
}
.switch-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; border-radius: 9px; background: #f8fafc;
  font-size: 13px; color: #4b5563; cursor: pointer;
}
.switch-row input { accent-color: #14b8a6; cursor: pointer; width: 16px; height: 16px; }

.greet-input {
  width: 100%; min-height: 70px; padding: 10px 12px;
  border: 1px solid #e6ebf2; border-radius: 10px; outline: none;
  font-family: inherit; font-size: 13px; line-height: 1.6; resize: vertical;
}
.greet-input:focus { border-color: #14b8a6; }
.greet-actions {
  display: flex; align-items: center; justify-content: flex-end;
  gap: 12px; margin-top: 10px;
}
.greet-msg { font-size: 12px; color: #14b8a6; }

/* 清空弹窗 */
.clear-text { font-size: 14px; color: #374151; line-height: 1.7; margin-bottom: 18px; }
.m-btns { display: flex; justify-content: flex-end; gap: 10px; }
.m-btns button {
  padding: 8px 18px; border-radius: 9px; border: none;
  font-size: 13px; font-family: inherit; cursor: pointer;
}
.m-btns .cancel { background: #f1f5f9; color: #64748b; }
.m-btns .danger { background: #e74c3c; color: #fff; }

/* ================= 手机 ================= */
@media (max-width: 760px) {
  .layout { grid-template-columns: 1fr; }
  .side {
    display: flex; align-items: center; gap: 6px;
    overflow-x: auto; padding: 10px;
  }
  .side-title { padding: 0 6px; white-space: nowrap; }
  .side-line { display: none; }
  .nav-item { white-space: nowrap; padding: 8px 12px; }
  .main { min-height: 420px; padding: 16px; }
  .switch-list { grid-template-columns: 1fr; }
}
</style>
