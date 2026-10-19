<template>
  <div class="page">
    <!-- 顶部: 头像 + 登录状态 (点一下 → 看我自己的个人主页) -->
    <div class="user-head" @click="go(user ? `/user/${user.id}` : '/login')">
      <div class="head-avatar cover-3">
        <img v-if="user && user.avatar" :src="user.avatar" alt="" />
        <span v-else><IconUser /></span>
      </div>
      <div class="head-info">
        <template v-if="user">
          <h2>{{ user.username }}</h2>
          <p>{{ user.bio || '欢迎回来～ 点这里看你的主页' }}</p>
        </template>
        <template v-else>
          <h2>登录 / 注册</h2>
          <p>不可以哦，主人还没有登录呢～</p>
        </template>
      </div>
      <span class="arrow">›</span>
    </div>

    <!-- 四宫格 -->
    <div class="quad card">
      <div class="q-item" @click="go('/my-articles')">
        <span class="q-ico">📝</span><span>我的文章</span>
      </div>
      <div class="q-item" @click="go('/my-collections')">
        <span class="q-ico">⭐</span><span>我的收藏</span>
      </div>
      <div class="q-item" @click="go('/history')">
        <span class="q-ico">🕐</span><span>浏览历史</span>
      </div>
      <div class="q-item">
        <span class="q-ico">💬</span><span>我的消息</span>
      </div>
    </div>

    <!-- 继续阅读 (样式, 以后接后端) -->
    <div class="continue card">
      <span class="c-ico">📖</span>
      <div class="c-text">
        <p class="c-title">上次看到还没读完的文章</p>
        <p class="c-sub">继续阅读 ›</p>
      </div>
    </div>

    <!-- 列表 -->
    <div class="list card">
      <div class="l-item" @click="logout" v-if="user">
        <span>退出登录</span><span class="arrow">›</span>
      </div>
      <div class="l-item" @click="go('/login')" v-else>
        <span>去登录</span><span class="arrow">›</span>
      </div>
      <div class="l-item"><span>主题设置</span><span class="arrow">›</span></div>
      <div class="l-item" @click="openFeedback">
        <span>建议反馈</span><span class="arrow">›</span>
      </div>
      <div class="l-item" @click="showAbout = true">
        <span>关于</span><span class="arrow">›</span>
      </div>
    </div>

    <!-- ===== 最近浏览 (把页面下半部分填满, 也是真能用上的入口) ===== -->
    <div v-if="recent.length" class="recent card">
      <div class="recent-head">
        <span class="r-title">🕐 最近浏览</span>
        <span class="r-more" @click="go('/history')">查看全部 ›</span>
      </div>
      <div
        v-for="a in recent" :key="a.id"
        class="r-item"
        @click="go(`/article/${a.id}`)"
      >
        <span class="r-name">{{ a.title }}</span>
        <span class="r-author">{{ a.author }}</span>
      </div>
    </div>

    <p class="msg" v-if="msg">{{ msg }}</p>

    <!-- ============ 建议反馈弹窗 ============ -->
    <Modal v-model="showFeedback" title="建议反馈">
      <!-- 还没提交: 显示输入框 -->
      <template v-if="!fbDone">
        <textarea
          class="m-textarea"
          v-model="fbContent"
          rows="5"
          placeholder="用得哪里不顺手？想加点什么功能？都可以说～"
        ></textarea>

        <input
          class="m-input"
          v-model="fbContact"
          placeholder="联系方式（选填，方便我回你）"
        />

        <p v-if="fbMsg" class="m-err">{{ fbMsg }}</p>

        <div class="m-btns">
          <button class="cancel" @click="showFeedback = false">取消</button>
          <button class="ok" :disabled="fbSending" @click="submitFeedback">
            {{ fbSending ? '提交中…' : '提交' }}
          </button>
        </div>
      </template>

      <!-- 提交成功: 换成"谢谢"那一屏 -->
      <div v-else class="m-done">
        <div class="done-ico">🎉</div>
        <p class="done-text">收到啦，感谢你的反馈！</p>
        <div class="m-btns center">
          <button class="ok" @click="showFeedback = false">好的</button>
        </div>
      </div>
    </Modal>

    <!-- ============ 关于弹窗 ============ -->
    <Modal v-model="showAbout" title="关于">
      <div class="about">
        <div class="a-logo">✨</div>
        <h3 class="a-name">我的文章站</h3>
        <p class="a-ver">v1.0.0</p>

        <div class="a-rows">
          <div class="a-row"><span>前端</span><b>Vue 3 · Vite · Vue Router · Axios</b></div>
          <div class="a-row"><span>后端</span><b>FastAPI · SQLAlchemy</b></div>
          <div class="a-row"><span>数据</span><b>MySQL · Redis</b></div>
          <div class="a-row"><span>作者</span><b>qi</b></div>
        </div>

        <p class="a-note">一个边学边写的全栈练手项目</p>
      </div>
    </Modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getMe, sendFeedback, getHistory } from '../services/authApi.js'
import Modal from './Modal.vue'


const user = ref(null)
const msg = ref('')
const recent = ref([])          // 最近浏览的 5 篇
const router = useRouter()

// ---- 建议反馈 ----
const showFeedback = ref(false)   // 弹窗开不开
const fbContent = ref('')         // 反馈内容
const fbContact = ref('')         // 联系方式
const fbMsg = ref('')             // 错误提示
const fbDone = ref(false)         // 提交成功了吗 (成功后换成"谢谢"那一屏)
const fbSending = ref(false)      // 正在提交中 (防连点)

// ---- 关于 ----
const showAbout = ref(false)

const go = (path) => router.push(path)

onMounted(async () => {
  const token = localStorage.getItem('token')
  if (!token) return                      // 没登录 → 显示"未登录"状态 (不跳转)
  try {
    const res = await getMe(token)
    user.value = res.data
  } catch (err) {
    if (err.response && err.response.status === 401) {
      localStorage.removeItem('token')    // token 失效 → 清掉, 回到未登录态
    }
  }

  // 最近浏览: 拿 5 条。
  // ★ 单独一个 try —— 历史拿不到不能让整页变"未登录"
  try {
    const h = await getHistory(token)
    recent.value = (h.data || []).slice(0, 5)
  } catch (e) {
    recent.value = []
  }
})

const logout = () => {
  localStorage.removeItem('token')
  user.value = null
  msg.value = '已退出登录'
  setTimeout(() => (msg.value = ''), 1500)
}

// ---------- 打开反馈弹窗 ----------
const openFeedback = () => {
  if (!user.value) {                       // 没登录 → 提示一下, 不开弹窗
    msg.value = '登录后才能反馈哦'
    setTimeout(() => (msg.value = ''), 1500)
    return
  }
  // 每次打开都清空上次的残留
  fbContent.value = ''
  fbContact.value = ''
  fbMsg.value = ''
  fbDone.value = false
  showFeedback.value = true
}

// ---------- 提交反馈 ----------
const submitFeedback = async () => {
  const content = fbContent.value.trim()
  if (!content) { fbMsg.value = '内容不能为空'; return }
  if (fbSending.value) return              // 正在提交, 忽略重复点击

  fbSending.value = true
  fbMsg.value = ''
  const token = localStorage.getItem('token')
  try {
    const res = await sendFeedback(token, content, fbContact.value.trim())
    // ⚠️ 后端业务错误是 200 + {error}, 得自己查
    if (res.data.error) { fbMsg.value = res.data.error; return }
    fbDone.value = true                    // 成功 → 切成"谢谢"那一屏
  } catch (err) {
    fbMsg.value = '提交失败：' + err.message
  }
  fbSending.value = false
}
</script>

<style scoped>
/* PC: "我的"页内容居中收窄 (单栏; 稍微放宽一点, 免得两边太空) */
.page { max-width: 880px; }

/* 顶部用户区 */
.user-head {
  display: flex; align-items: center; gap: 12px;
  padding: 18px 16px; background: #fff; border-radius: 16px;
  box-shadow: 0 2px 10px rgba(20, 184, 166, 0.06); margin-bottom: 14px;
}
.head-avatar {
  width: 60px; height: 60px; border-radius: 50%; flex-shrink: 0; overflow: hidden;
  display: flex; align-items: center; justify-content: center; font-size: 24px;
  color: rgba(15, 118, 110, 0.55);
}
.head-avatar img { width: 100%; height: 100%; object-fit: cover; }
/* 整块可点 → 手感更像"卡片可点" */
.user-head { cursor: pointer; }
/* min-width: 0 不能省 —— 里面装的是用户名和简介(用户输入的),
   不写的话长用户名会把右边那个箭头挤出容器 (见 style.css 顶部那段说明) */
.head-info { flex: 1; min-width: 0; }
.head-info h2 { font-size: 18px; }
.head-info p { font-size: 12px; color: #7b8794; margin-top: 3px; }
.arrow { color: #c3ccd8; font-size: 20px; text-decoration: none; }

/* 四宫格 */
.quad { display: flex; padding: 16px 0; margin-bottom: 14px; }
.q-item {
  flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px;
  font-size: 12px; color: #4b5563; cursor: pointer;
}
.q-ico { font-size: 25px; }

/* 继续阅读 */
.continue { display: flex; align-items: center; gap: 12px; padding: 14px 16px; margin-bottom: 14px; }
.c-ico { font-size: 22px; }
.c-title { font-size: 13px; }
.c-sub { font-size: 11px; color: #14b8a6; margin-top: 3px; }

/* 列表 */
.list { overflow: hidden; }
.l-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 18px; font-size: 14px; cursor: pointer;
  border-bottom: 1px solid #f2f5f9;
}
.l-item:last-child { border-bottom: none; }

/* ---- 最近浏览 ---- */
.recent { padding: 16px 18px; margin-top: 14px; }
.recent-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px;
}
.r-title { font-size: 13px; font-weight: 600; color: #374151; }
.r-more { font-size: 12px; color: #14b8a6; cursor: pointer; }
.r-more:hover { text-decoration: underline; }

.r-item {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 10px 0; border-bottom: 1px dashed #eef1f6;
  cursor: pointer;
}
.r-item:last-child { border-bottom: none; }
.r-name {
  font-size: 13px; color: #4b5563; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
  transition: color 0.15s;
}
.r-item:hover .r-name { color: #0f766e; }
.r-author { flex-shrink: 0; font-size: 11px; color: #9aa5b1; }

.msg { text-align: center; color: #14b8a6; font-size: 13px; margin-top: 14px; }

/* ============ 建议反馈弹窗里的东西 ============ */
.m-textarea {
  width: 100%; padding: 12px 14px; font-size: 14px;
  font-family: inherit; line-height: 1.6; resize: vertical;
  border: 1px solid #e6ebf2; border-radius: 10px; outline: none;
}
.m-textarea:focus { border-color: #14b8a6; }

.m-input {
  width: 100%; padding: 11px 14px; margin-top: 10px; font-size: 14px;
  border: 1px solid #e6ebf2; border-radius: 10px; outline: none;
}
.m-input:focus { border-color: #14b8a6; }

.m-err { color: #e74c3c; font-size: 13px; margin-top: 10px; }

.m-btns { display: flex; gap: 10px; justify-content: flex-end; margin-top: 18px; }
.m-btns.center { justify-content: center; }
.m-btns button {
  padding: 9px 22px; border: none; border-radius: 10px;
  font-size: 14px; cursor: pointer; transition: all 0.15s;
}
.ok { background: #14b8a6; color: #fff; font-weight: 600; }
.ok:hover:not(:disabled) { background: #0d9488; }
.ok:disabled { opacity: 0.55; cursor: not-allowed; }
.cancel { background: #f1f5f9; color: #64748b; }
.cancel:hover { background: #e2e8f0; }

/* 提交成功那一屏 */
.m-done { text-align: center; padding: 10px 0 6px; }
.done-ico { font-size: 42px; }
.done-text { font-size: 14px; color: #4b5563; margin-top: 10px; }

/* ============ 关于弹窗里的东西 ============ */
.about { text-align: center; }
.a-logo {
  width: 62px; height: 62px; margin: 6px auto 12px;
  border-radius: 18px; font-size: 30px;
  background: linear-gradient(135deg, #ccfbf1 0%, #a5b4fc 100%);
  display: flex; align-items: center; justify-content: center;
}
.a-name { font-size: 17px; color: #1f2937; }
.a-ver { font-size: 12px; color: #9aa5b1; margin-top: 4px; }

.a-rows {
  margin-top: 18px; border-top: 1px solid #f2f5f9;
  padding-top: 14px; text-align: left;
}
.a-row {
  display: flex; align-items: baseline; gap: 12px;
  padding: 7px 0; font-size: 13px;
}
.a-row > span { color: #9aa5b1; width: 42px; flex-shrink: 0; }
.a-row > b { color: #4b5563; font-weight: 500; }

.a-note { font-size: 12px; color: #a8b2c1; margin-top: 16px; }
</style>
