<template>
  <div class="page ai-page">
    <!-- 顶部标题 -->
    <div class="ai-head">
      <div class="ai-avatar cover-6">✨</div>
      <div>
        <h2>AI 小助手</h2>
        <p>文章问答 · 陪你聊技术</p>
      </div>
    </div>

    <!-- 对话区 -->
    <div ref="chatArea" class="chat-area">
      <!-- 一条消息都没有时，显示欢迎语 -->
      <div v-if="messages.length === 0" class="bubble bubble-ai">
        你好呀～ 我是本站的 AI 小助手。<br />
        可以问我技术问题，也可以让我帮你理清一个概念。
      </div>

      <!-- 所有消息 -->
      <div
        v-for="(m, i) in messages"
        :key="i"
        class="bubble"
        :class="m.role === 'user' ? 'bubble-user' : 'bubble-ai'"
      >
        <span class="bubble-text">{{ m.content }}</span>
        <!-- 刚发出、还没收到第一个字时，显示"思考中" -->
        <span
          v-if="sending && i === messages.length - 1 && m.role === 'assistant' && !m.content"
          class="typing"
        >思考中…</span>
      </div>

      <div v-if="error" class="ai-error">{{ error }}</div>
    </div>

    <!-- 底部输入 -->
    <div class="chat-input">
      <textarea
        v-model="input"
        rows="1"
        placeholder="问我点什么…（Enter 发送，Shift+Enter 换行）"
        :disabled="sending"
        @keydown="onKeydown"
      ></textarea>
      <button v-if="!sending" :disabled="!input.trim()" @click="send">发送</button>
      <button v-else class="stop-btn" @click="stop">停止</button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { streamChat } from '../services/aiApi.js'
import { goLogin } from '../utils/auth.js'

const router = useRouter()

const messages = ref([])   // 这次会话的所有消息（刷新会丢，存库是下一步）
const input = ref('')
const sending = ref(false) // 正在等模型回答
const error = ref('')
const chatArea = ref(null)

let controller = null      // AbortController，用来"停止生成"

// 等页面把新消息渲染出来，再滚到底部
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

const send = async () => {
  const text = input.value.trim()
  if (!text || sending.value) return

  const token = localStorage.getItem('token')
  if (!token) {
    goLogin(router)
    return
  }

  error.value = ''
  input.value = ''

  // 先把用户消息和一条空的 AI 消息放进列表
  messages.value.push({ role: 'user', content: text })
  const aiIndex = messages.value.length
  messages.value.push({ role: 'assistant', content: '' })

  sending.value = true
  await scrollToBottom()

  // 发给后端的对话历史：不含刚插入的空 AI 消息
  const history = messages.value
    .slice(0, aiIndex)
    .filter((m) => m.content && (m.role === 'user' || m.role === 'assistant'))
    .map((m) => ({ role: m.role, content: m.content }))

  controller = new AbortController()

  await streamChat(token, history, {
    signal: controller.signal,

    onDelta: (delta) => {
      messages.value[aiIndex].content += delta
      scrollToBottom()
    },

    onDone: () => {
      sending.value = false
      controller = null
      scrollToBottom()
    },

    onError: (msg) => {
      sending.value = false
      controller = null

      // AI 一个字都没回时，把空气泡删掉，只显示错误提示
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

// Enter 发送，Shift+Enter 换行
const onKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

onUnmounted(() => {
  if (controller) controller.abort()
})
</script>

<style scoped>
.ai-page {
  max-width: 900px;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px);
  padding-bottom: 24px;
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
  .ai-page { height: calc(100vh - 56px); padding-bottom: 14px; }
  .bubble { max-width: 88%; }
}
</style>
