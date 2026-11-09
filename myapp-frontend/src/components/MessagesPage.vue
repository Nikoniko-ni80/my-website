<template>
  <div class="page msg-page">
    <div class="layout">
      <!-- ================= 左: 会话列表 ================= -->
      <aside class="side card">
        <div class="side-title">✉️ 私信</div>

        <p v-if="loadingConvs" class="side-tip">加载中…</p>
        <p v-else-if="convs.length === 0" class="side-tip">还没有私信</p>

        <div
          v-for="c in convs" :key="c.id"
          class="conv-item" :class="{ on: c.id === currentId }"
          @click="openConversation(c.id)"
        >
          <div class="conv-avatar"><IconUser /></div>
          <div class="conv-body">
            <div class="conv-top">
              <span class="conv-name">{{ c.username }}</span>
              <span class="conv-time">{{ fmtTime(c.last_message_at) }}</span>
            </div>
            <div class="conv-bottom">
              <span class="conv-last">{{ c.last_message }}</span>
              <span v-if="c.unread" class="conv-badge">{{ c.unread > 99 ? '99+' : c.unread }}</span>
            </div>
          </div>
        </div>
      </aside>

      <!-- ================= 右: 聊天窗 ================= -->
      <section class="main card">
        <template v-if="(currentId || peerId) && otherUser">
          <div class="chat-head">
            <span class="chat-name" @click="goUser(otherUser.id)">{{ otherUser.username }}</span>
          </div>

          <div ref="chatBox" class="chat-body">
            <p v-if="messages.length === 0" class="chat-tip">
              还没有消息，发一句打个招呼吧
            </p>

            <div
              v-for="m in messages" :key="m.id"
              class="bubble-row" :class="{ mine: m.from_user !== otherUser.id }"
            >
              <div class="bubble">{{ m.content }}</div>
              <span class="bubble-time">{{ fmtTime(m.created_at) }}</span>
            </div>
          </div>

          <p v-if="sendErr" class="send-err">{{ sendErr }}</p>

          <div class="chat-input">
            <input
              v-model="input"
              :disabled="sending"
              placeholder="输入消息，回车发送…"
              maxlength="500"
              @keyup.enter="send"
            />
            <button class="send-btn" :disabled="!input.trim() || sending" @click="send">
              {{ sending ? '发送中…' : '发送' }}
            </button>
          </div>
        </template>

        <p v-else class="chat-empty">
          {{ convs.length === 0
              ? '还没有私信～ 去别人的主页点「私信」开始聊天'
              : '选择一个会话开始聊天' }}
        </p>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getConversations, getMessages, sendMessage, getUserProfile, markConversationRead, wsUrl as buildWsUrl } from '../services/authApi.js'
import { goLogin } from '../utils/auth.js'

const route = useRoute()
const router = useRouter()

const convs = ref([])
const messages = ref([])
const otherUser = ref(null)       // {id, username, avatar}
const input = ref('')
const sending = ref(false)
const sendErr = ref('')
const loadingConvs = ref(true)
const chatBox = ref(null)

// 网址 /messages/5 → 5; /messages → null
const currentId = computed(() =>
  route.params.id ? Number(route.params.id) : null
)

// 网址 /messages/with/14 → 14 (还没建会话时，用对方 id 进入)
const peerId = computed(() =>
  route.params.uid ? Number(route.params.uid) : null
)

const token = () => localStorage.getItem('token')

// ---------- 时间显示 ----------
const fmtTime = (s) => {
  if (!s) return ''
  const d = new Date(s.replace(' ', 'T'))
  const diff = (Date.now() - d.getTime()) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)} 天前`
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

const scrollBottom = () => {
  const el = chatBox.value
  if (el) el.scrollTop = el.scrollHeight
}

// 用户是不是贴着底部看 (如果他在往上翻历史, 就别强行把他拉回底部)
const isNearBottom = () => {
  const el = chatBox.value
  if (!el) return true
  return el.scrollHeight - el.scrollTop - el.clientHeight < 120
}

// ---------- WebSocket: 实时收新消息 ----------
// ★ 发送仍然走 REST（POST /conversations/{user_id}/messages）
//   这条 WebSocket 只负责"收到别人发给我的消息"。
let ws = null
let wsRetry = null
let wsPing = null
let alive = true              // 组件还在不在（离开页面后不再重连）

const wsUrl = () => buildWsUrl('/ws/chat', localStorage.getItem('token'))

const connectWs = () => {
  if (!alive || !token()) return
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return

  ws = new WebSocket(wsUrl())

  ws.onopen = () => {
    // 心跳: 后端收到 "ping" 会回 "pong"
    wsPing = setInterval(() => { try { ws.send('ping') } catch (e) {} }, 25000)
  }

  ws.onmessage = (e) => {
    let data
    try { data = JSON.parse(e.data) } catch { return }   // pong 之类的非 JSON 直接忽略
    if (data.type !== 'message') return

    const item = data.item
    // 自己刚发的消息已经上屏了，别重复加
    if (item && !messages.value.some(m => m.id === item.id)) {
      if (data.conversation_id === currentId.value) {
        const atBottom = isNearBottom()
        messages.value.push(item)
        if (atBottom) nextTick().then(scrollBottom)
        // ★ 这是"回执", 不是"取消息":
        //     内容已经在推送里到了(item), 这里只是告诉服务器"这个会话我读了"
        //     请求: PUT /conversations/{id}/read
        //   不发的话: 人明明看着, 左侧还显示未读, 对方也以为你没看
        markConversationRead(token(), data.conversation_id).catch(() => {})
      }
    }

    loadConversations()          // 左侧最后一句 / 未读跟着更新
    window.dispatchEvent(new Event('unread-changed'))
  }

  ws.onclose = () => {
    if (wsPing) { clearInterval(wsPing); wsPing = null }
    ws = null
    if (alive) wsRetry = setTimeout(connectWs, 3000)   // 3 秒后重连
  }

  ws.onerror = () => { try { ws.close() } catch (e) {} }
}

const closeWs = () => {
  alive = false
  if (wsRetry) { clearTimeout(wsRetry); wsRetry = null }
  if (wsPing) { clearInterval(wsPing); wsPing = null }
  if (ws) { try { ws.close() } catch (e) {} ; ws = null }
}

// ---------- 会话列表 ----------
const loadConversations = async () => {
  try {
    const res = await getConversations(token())
    convs.value = res.data.items || []
  } catch (e) {
    console.error('加载会话失败:', e)
    convs.value = []
  } finally {
    loadingConvs.value = false
  }
}

// ---------- 聊天记录 ----------
const loadMessages = async (id) => {
  try {
    const res = await getMessages(token(), id)
    if (res.data.error) {
      messages.value = []
      otherUser.value = null
      return
    }
    messages.value = res.data.messages || []
    otherUser.value = res.data.user
    await nextTick()
    scrollBottom()
    // 打开会话后端会自动标已读 → 刷新左侧的未读红点
    loadConversations()
    // 导航栏的红点也得跟着变 (否则要切页面才更新)
    window.dispatchEvent(new Event('unread-changed'))
  } catch (e) {
    console.error('加载聊天记录失败:', e)
    messages.value = []
  }
}

// ---------- 新会话: 按"对方 user_id"进入 ----------
// 数据库里可能还没有会话，这里只查对方资料，消息列表留空
const loadPeer = async (uid) => {
  try {
    const res = await getUserProfile(uid)
    if (res.data && !res.data.error) {
      otherUser.value = {
        id: res.data.id,
        username: res.data.username,
        avatar: res.data.avatar,
      }
    }
  } catch (e) {
    console.error('加载对方资料失败:', e)
  }
  messages.value = []
}

// 根据网址决定显示什么: /messages/with/:uid 或 /messages/:id
const loadRoute = async () => {
  if (peerId.value) {
    await loadPeer(peerId.value)
    return
  }
  if (currentId.value) {
    messages.value = []
    otherUser.value = null
    await loadMessages(currentId.value)
  }
}

// ---------- 点会话 ----------
const openConversation = (id) => {
  if (id === currentId.value) return
  router.push(`/messages/${id}`)     // 路由变化 → watch 去加载
}

const goUser = (id) => {
  if (id) router.push(`/user/${id}`)
}

// ---------- 发消息 ----------
const send = async () => {
  const text = input.value.trim()
  if (!text || sending.value || !otherUser.value) return

  sending.value = true
  sendErr.value = ''
  try {
    // ★ 这里传的是【对方的 user_id】
    const res = await sendMessage(token(), otherUser.value.id, text)
    if (res.data.error) {
      sendErr.value = res.data.error
      return
    }
    const wasNew = !!peerId.value
    input.value = ''

    if (wasNew) {
      // ★ 第一句发出去 → 后端已经建好会话 → 换成正式地址
      //   换地址会触发 watch → loadRoute → 拉一次完整的聊天记录
      await router.replace(`/messages/${res.data.conversation_id}`)
    } else {
      // ★ 后端直接返回了整条消息, 不用再拉一次列表
      messages.value.push(res.data.item)
      await nextTick()
      scrollBottom()
    }
    loadConversations()          // 左侧"最后一条消息"跟着更新
  } catch (e) {
    sendErr.value = '发送失败：' + e.message
  } finally {
    sending.value = false
  }
}

// ---------- 生命周期 ----------
onMounted(async () => {
  if (!token()) { goLogin(router); return }
  await loadConversations()

  if (peerId.value || currentId.value) {
    await loadRoute()
  } else if (convs.value.length) {
    // 没指定会话 → 自动打开最近的一个 (replace: 不留下一条空历史)
    router.replace(`/messages/${convs.value[0].id}`)
  }

  connectWs()             // ★ 建立 WebSocket，实时收新消息
})

// ★ 离开页面必须停掉计时器, 不然会一直发请求
onUnmounted(closeWs)

// 网址变了（切会话 / 新会话变正式会话）→ 重新决定显示什么
watch(() => route.fullPath, (val, old) => {
  if (val === old) return
  loadRoute()
})
</script>

<style scoped>
.msg-page { max-width: 1080px; }

.layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
  align-items: stretch;
  height: calc(100vh - 190px);
  min-height: 480px;
}

/* ================= 左栏 ================= */
.side {
  padding: 14px 10px;
  overflow-y: auto;
}

.side-title {
  font-size: 15px; font-weight: 700; color: #1f2937;
  padding: 4px 10px 12px;
}
.side-tip {
  font-size: 13px; color: #9aa5b1;
  text-align: center; padding: 30px 0;
}

.conv-item {
  display: flex; gap: 10px; align-items: center;
  padding: 10px; border-radius: 10px;
  cursor: pointer; transition: background 0.15s;
}
.conv-item:hover { background: #f7fffd; }
.conv-item.on { background: #f0fdfa; }

.conv-avatar {
  width: 38px; height: 38px; flex-shrink: 0;
  border-radius: 50%; background: #eef7f5;
  color: rgba(15, 118, 110, 0.55);
  display: flex; align-items: center; justify-content: center;
}
.conv-body { flex: 1; min-width: 0; }

.conv-top {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
}
.conv-name {
  font-size: 13px; font-weight: 600; color: #1f2937;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.conv-time { font-size: 10px; color: #b6c0cc; flex-shrink: 0; }

.conv-bottom {
  display: flex; align-items: center; justify-content: space-between; gap: 8px;
  margin-top: 3px;
}
.conv-last {
  font-size: 12px; color: #9aa5b1;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.conv-badge {
  min-width: 16px; height: 16px; padding: 0 4px;
  border-radius: 8px; background: #e74c3c; color: #fff;
  font-size: 10px; line-height: 16px; text-align: center; flex-shrink: 0;
}

/* ================= 右栏 ================= */
.main {
  display: flex; flex-direction: column;
  min-height: 0;                 /* ★ 让内部的滚动区能正常工作 */
  overflow: hidden;
}

.chat-head {
  padding: 14px 20px;
  border-bottom: 1px solid #eef1f6;
}
.chat-name {
  font-size: 15px; font-weight: 600; color: #1f2937;
  cursor: pointer;
}
.chat-name:hover { color: #0f766e; }

.chat-body {
  flex: 1;
  overflow-y: auto;
  padding: 18px 20px;
  display: flex; flex-direction: column; gap: 12px;
  background: #fbfdfd;
}

.chat-tip, .chat-empty {
  margin: auto;
  font-size: 13px; color: #9aa5b1; text-align: center;
  line-height: 1.9; padding: 40px 20px;
}

.bubble-row {
  display: flex; flex-direction: column;
  align-items: flex-start;
  max-width: 72%;
}
.bubble-row.mine {
  align-self: flex-end;
  align-items: flex-end;
}

.bubble {
  padding: 9px 13px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #eef1f6;
  color: #1f2937;
  font-size: 14px;
  line-height: 1.6;
  overflow-wrap: anywhere;
  white-space: pre-wrap;
}
.bubble-row.mine .bubble {
  background: #14b8a6;
  border-color: #14b8a6;
  color: #fff;
  border-bottom-right-radius: 4px;
}
.bubble-row:not(.mine) .bubble {
  border-bottom-left-radius: 4px;
}

.bubble-time {
  font-size: 10px; color: #b6c0cc;
  margin-top: 4px;
}

.send-err {
  padding: 0 20px 6px;
  font-size: 12px; color: #c0392b;
}

.chat-input {
  display: flex; gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid #eef1f6;
  background: #fff;
}
.chat-input input {
  flex: 1;
  border: 1px solid #e6ebf2; border-radius: 10px;
  padding: 10px 12px; font-size: 14px; outline: none;
  font-family: inherit;
}
.chat-input input:focus { border-color: #14b8a6; }
.send-btn {
  padding: 0 20px; border: none; border-radius: 10px;
  background: #14b8a6; color: #fff; font-size: 14px;
  font-family: inherit; cursor: pointer; transition: background 0.15s;
}
.send-btn:hover:not(:disabled) { background: #0d9488; }
.send-btn:disabled { opacity: 0.45; cursor: default; }

/* ================= 手机 ================= */
@media (max-width: 760px) {
  .layout {
    grid-template-columns: 1fr;
    height: auto;
  }
  .side { max-height: 220px; }
  .main { height: 65vh; }
}
</style>
