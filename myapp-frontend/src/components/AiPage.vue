<template>
  <div class="page ai-page">
    <!-- 左边：会话列表 -->
    <aside class="conv-side">
      <button class="new-btn" :disabled="creating" @click="newConversation">+ 新对话</button>

      <div class="conv-list">
        <div
          v-for="c in conversations"
          :key="c.id"
          class="conv-item"
          :class="{ active: c.id === conversationId }"
          @click="openConversation(c.id)"
        >
          <span class="conv-title">{{ c.title }}</span>
          <span class="conv-ops">
            <button title="改名" @click.stop="renameConv(c)">✎</button>
            <button title="删除" @click.stop="removeConv(c)">✕</button>
          </span>
        </div>
        <p v-if="!conversations.length" class="conv-empty">还没有对话</p>
      </div>
    </aside>

    <!-- 右边：聊天区 -->
    <section class="chat-main">
      <div class="ai-head">
        <div class="ai-avatar cover-6">✨</div>
        <div>
          <h2>AI 小助手</h2>
          <p>文章问答 · 陪你聊技术</p>
        </div>
      </div>

      <div ref="chatArea" class="chat-area">
        <div v-if="loadingHistory" class="conv-empty">加载中…</div>

        <div v-else-if="messages.length === 0" class="bubble bubble-ai">
          你好呀～ 我是本站的 AI 小助手。<br />
          可以问我技术问题，也可以让我帮你理清一个概念。
        </div>

        <div
          v-for="(m, i) in messages"
          :key="i"
          class="bubble"
          :class="m.role === 'user' ? 'bubble-user' : 'bubble-ai'"
        >
          <span class="bubble-text">{{ m.content }}</span>
          <span
            v-if="sending && i === messages.length - 1 && m.role === 'assistant' && !m.content"
            class="typing"
          >思考中…</span>
        </div>

        <div v-if="error" class="ai-error">{{ error }}</div>
      </div>

      <div class="chat-input">
        <textarea
          v-model="input"
          rows="1"
          placeholder="问我点什么…（Enter 发送，Shift+Enter 换行）"
          :disabled="sending || !conversationId"
          @keydown="onKeydown"
        ></textarea>
        <button v-if="!sending" :disabled="!input.trim() || !conversationId" @click="send">发送</button>
        <button v-else class="stop-btn" @click="stop">停止</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  streamChatInConversation,
  listConversations,
  createConversation,
  renameConversation,
  deleteConversation,
  getMessages,
} from '../services/aiApi.js'
import { goLogin } from '../utils/auth.js'

const router = useRouter()

const conversations = ref([])   // 左侧列表
const conversationId = ref(null) // 当前打开的是哪个会话
const messages = ref([])        // 当前会话的消息
const input = ref('')
const sending = ref(false)
const loadingHistory = ref(false)
const creating = ref(false)
const error = ref('')
const chatArea = ref(null)

let controller = null

const token = () => localStorage.getItem('token')

const scrollToBottom = async () => {
  await nextTick()
  const el = chatArea.value
  if (el) el.scrollTop = el.scrollHeight
}

const stop = () => {
  if (controller) {
    controller.abort()
    controller = null
  }
  sending.value = false
}

// ---------- 会话列表 ----------
const loadConversations = async () => {
  const list = await listConversations(token())
  conversations.value = Array.isArray(list) ? list : []
  return conversations.value
}

const openConversation = async (id) => {
  if (sending.value) stop()
  conversationId.value = id
  messages.value = []
  error.value = ''
  loadingHistory.value = true
  try {
    const rows = await getMessages(token(), id, 50)
    messages.value = (rows || []).map((m) => ({ role: m.role, content: m.content }))
    await scrollToBottom()
  } catch (e) {
    error.value = e.message
  } finally {
    loadingHistory.value = false
  }
}

const newConversation = async () => {
  creating.value = true
  error.value = ''
  try {
    const conv = await createConversation(token())
    await loadConversations()
    await openConversation(conv.id)
  } catch (e) {
    error.value = e.message
  } finally {
    creating.value = false
  }
}

const renameConv = async (c) => {
  const title = window.prompt('新的标题', c.title)
  if (!title || !title.trim()) return
  try {
    await renameConversation(token(), c.id, title.trim())
    await loadConversations()
  } catch (e) {
    error.value = e.message
  }
}

const removeConv = async (c) => {
  if (!window.confirm(`删除「${c.title}」？聊天记录会一起删掉`)) return
  try {
    await deleteConversation(token(), c.id)
    const wasActive = conversationId.value === c.id
    await loadConversations()
    if (wasActive) {
      if (conversations.value.length) await openConversation(conversations.value[0].id)
      else await newConversation()
    }
  } catch (e) {
    error.value = e.message
  }
}

// ---------- 发送 ----------
const send = async () => {
  const text = input.value.trim()
  if (!text || sending.value || !conversationId.value) return

  if (!token()) {
    goLogin(router)
    return
  }

  error.value = ''
  input.value = ''

  messages.value.push({ role: 'user', content: text })
  const aiIndex = messages.value.length
  messages.value.push({ role: 'assistant', content: '' })

  sending.value = true
  await scrollToBottom()

  controller = new AbortController()

  await streamChatInConversation(token(), conversationId.value, text, {
    signal: controller.signal,

    onDelta: (delta) => {
      messages.value[aiIndex].content += delta
      scrollToBottom()
    },

    onDone: async () => {
      sending.value = false
      controller = null
      scrollToBottom()
      // 第一句会自动变成标题, 刷新一下左侧列表
      try { await loadConversations() } catch (e) { /* 忽略 */ }
    },

    onError: (msg) => {
      sending.value = false
      controller = null

      if (!messages.value[aiIndex].content) {
        messages.value.splice(aiIndex, 1)
      }

      error.value = msg
      scrollToBottom()

      if (msg.includes('登录已过期')) {
        localStorage.removeItem('token')
        setTimeout(() => goLogin(router), 800)
      }
    },
  })
}

const onKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

// ---------- 进页面 ----------
onMounted(async () => {
  if (!token()) {
    goLogin(router)
    return
  }
  try {
    const list = await loadConversations()
    if (list.length) await openConversation(list[0].id)
    else await newConversation()
  } catch (e) {
    error.value = e.message
  }
})

onUnmounted(() => {
  if (controller) controller.abort()
})
</script>

<style scoped>
.ai-page {
  max-width: 1040px;
  display: flex;
  gap: 16px;
  height: calc(100vh - 64px);
  padding-bottom: 24px;
}

/* ---------- 左侧会话列表 ---------- */
.conv-side {
  width: 210px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.new-btn {
  height: 40px;
  border: 1px dashed #ccd8e3;
  border-radius: 12px;
  background: #fff;
  color: #14b8a6;
  font-size: 14px;
  cursor: pointer;
}
.new-btn:hover { border-color: #14b8a6; background: #f0fdfa; }
.new-btn:disabled { color: #9aa5b1; cursor: default; }

.conv-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.conv-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 9px 10px;
  border-radius: 10px;
  font-size: 13px;
  color: #4a5765;
  cursor: pointer;
}
.conv-item:hover { background: #f4f8fb; }
.conv-item.active { background: #e6fffa; color: #0f766e; font-weight: 600; }
.conv-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.conv-ops { display: none; gap: 2px; }
.conv-item:hover .conv-ops { display: flex; }
.conv-ops button {
  border: none;
  background: transparent;
  color: #9aa5b1;
  font-size: 12px;
  cursor: pointer;
  padding: 2px 4px;
}
.conv-ops button:hover { color: #0f766e; }
.conv-empty { font-size: 12px; color: #9aa5b1; padding: 8px 10px; }

/* ---------- 右侧聊天 ---------- */
.chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.ai-head { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.ai-avatar {
  width: 46px; height: 46px; border-radius: 14px;
  display: flex; align-items: center; justify-content: center; font-size: 22px;
}
.ai-head h2 { font-size: 17px; }
.ai-head p { font-size: 12px; color: #7b8794; margin-top: 2px; }

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding: 4px 4px 10px;
}

.bubble {
  max-width: 78%;
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.65;
}
.bubble-text { white-space: pre-wrap; overflow-wrap: anywhere; }
.bubble-ai {
  align-self: flex-start; background: #fff; color: #2c3e50;
  box-shadow: 0 2px 10px rgba(20, 184, 166, 0.07);
  border-bottom-left-radius: 4px;
}
.bubble-user {
  align-self: flex-end; background: #14b8a6; color: #fff;
  border-bottom-right-radius: 4px;
}

.typing { color: #9aa5b1; font-size: 12px; }
.ai-error {
  align-self: center;
  font-size: 13px;
  color: #b91c1c;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 10px;
  padding: 8px 14px;
}

.chat-input {
  display: flex;
  gap: 10px;
  padding-top: 10px;
  border-top: 1px solid #eef1f6;
}
.chat-input textarea {
  flex: 1;
  min-height: 44px;
  max-height: 120px;
  padding: 11px 14px;
  border: 1px solid #e6ebf2;
  border-radius: 14px;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.5;
  outline: none;
  resize: none;
  background: #fff;
}
.chat-input textarea:focus { border-color: #14b8a6; }
.chat-input button {
  align-self: flex-end;
  height: 44px;
  min-width: 76px;
  padding: 0 18px;
  border: none;
  border-radius: 14px;
  background: #14b8a6;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
}
.chat-input button:disabled { background: #c9d6e5; cursor: not-allowed; }
.chat-input .stop-btn { background: #e74c3c; }

@media (max-width: 720px) {
  .ai-page {
    height: calc(100vh - 56px);
    padding-bottom: 14px;
    flex-direction: column;
    gap: 10px;
  }
  .conv-side {
    width: 100%;
    max-height: 132px;
    flex-direction: row;
    align-items: flex-start;
  }
  .new-btn { width: 96px; flex-shrink: 0; height: 34px; font-size: 13px; }
  .conv-list { flex-direction: row; overflow-x: auto; overflow-y: hidden; }
  .conv-item { white-space: nowrap; max-width: 150px; }
  .bubble { max-width: 88%; }
}
</style>
