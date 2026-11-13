<template>
  <div class="app">
    <!-- 顶部导航栏 -->
    <header class="topnav">
      <div class="nav-inner">
        <router-link to="/home" class="logo">
          <img class="logo-mascot" src="/mascot-avatar.png" alt="" />
          <span class="logo-text">文章站</span>
        </router-link>

        <nav class="menu">
          <router-link to="/home">首页</router-link>
          <router-link to="/hot">🔥 热榜</router-link>
          <router-link to="/feed">关注</router-link>
          <router-link to="/ai">AI 助手</router-link>
          <router-link to="/notifications" class="msg-link">
            消息
            <span v-if="unread > 0" class="badge">{{ unread > 99 ? '99+' : unread }}</span>
          </router-link>
          <router-link to="/me">我的</router-link>
        </nav>

        <div class="nav-right">
          <!-- 创作入口: 没登录点进去, 写文章页会自己跳到登录页 -->
          <router-link to="/write" class="write-btn">✍️ 写文章</router-link>
          <!-- 登录了 → 显示头像 + 名字 (点一下进自己主页) -->
          <router-link v-if="me" :to="`/user/${me.id}`" class="me-link">
            <span class="nav-avatar">
              <img v-if="me.avatar" :src="mediaUrl(me.avatar)" alt="" />
              <span v-else>🐦</span>
            </span>
            <span class="me-name">{{ me.username }}</span>
          </router-link>
          <!-- 没登录 → 显示登录按钮 -->
          <router-link v-else to="/login" class="login-link">登录</router-link>
        </div>
      </div>
    </header>

    <!-- 页面内容 -->
    <router-view />

    <!-- 页脚: 短页面底下不会空着, 也让它更像一个"站" -->
    <footer class="footer">
      <div class="footer-inner">
        <span>© 2026 我的文章站</span>
        <span class="dot">·</span>
        <span>FastAPI + Vue 3 + MySQL + Redis</span>
        <span class="dot">·</span>
        <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">接口文档</a>
        <span class="dot">·</span>
        <a href="http://127.0.0.1:8000/articles/hot" target="_blank" rel="noreferrer">热榜 API</a>
      </div>
    </footer>
  </div>
</template>

<script setup>
// ============================================================
// 导航栏右边: 显示"登录"还是"我的头像+名字"
// ============================================================
// ⚠️ 难点: token 存在 localStorage 里, 它【不是响应式的】——
//    你在登录页写进 localStorage, App.vue 这边不会自动"感知到"。
//    所以这里用两个笨办法凑合:
//      ① onMounted 时查一次
//      ② 每次【切路由】再查一次 (登录/退出登录都会切页面, 所以能刷新过来)
//    真实项目会用 Pinia 之类的状态管理, 这个项目暂时不上。
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getMe, getUnreadCount, eventStreamUrl } from './services/authApi.js'
import { mediaUrl } from './utils/media.js'

const route = useRoute()
const me = ref(null)          // null = 没登录
const unread = ref(0)         // 未读消息数 (导航栏红点)

// ---------- SSE: 通知实时推送 ----------
let es = null

const stopStream = () => {
  if (es) { es.close(); es = null }
}

const startStream = () => {
  const token = localStorage.getItem('token')
  if (!token) { stopStream(); return }
  if (es) return                       // 已经连着了
  es = new EventSource(eventStreamUrl(token)) 
  es.onmessage = () => {
    refresh()                                          // 红点立刻更新
    window.dispatchEvent(new Event('notify-push'))     // 消息页收到后刷新列表
  }
  //es就是一个这样的EventSorce这样一个类，然后这样一个类就是可以接收SSE的结构体，
  //然后他内部有一个onmessage属性，这个属性就是里面就可以写一些操作就是收到数据后执行onmessage这一部分的代码是这样子的吗
  //断线时浏览器会自动重连, 不用自己写
}

const refresh = async () => {
  const token = localStorage.getItem('token')
  if (!token) { me.value = null; unread.value = 0; stopStream(); return }
  startStream()
  try {
    const res = await getMe(token)
    me.value = res.data.error ? null : res.data
  } catch (e) {
    me.value = null           // token 过期/无效 → 当没登录
  }

  // 未读数: 单独 try, 拿不到不影响登录状态显示
  try {
    const r = await getUnreadCount(token)
    // ★ total = 通知未读 + 私信未读 (老接口只有 unread, 这里兼容一下)
    unread.value = r.data.total ?? r.data.unread ?? 0
  } catch (e) {
    unread.value = 0
  }
}

// ★ 别的地方(读了私信、清了通知)改完数, 喊一嗓子, 这里再拉一次。
//   不引状态管理库, 一个自定义事件就够。
const onUnreadChanged = () => refresh()

onMounted(() => {
  refresh()
  window.addEventListener('unread-changed', onUnreadChanged)
})
onUnmounted(() => {
  window.removeEventListener('unread-changed', onUnreadChanged)
  stopStream()
})

watch(() => route.fullPath, refresh)
</script>

<style scoped>
.topnav {
  position: sticky;
  top: 0;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid #eef1f6;
  z-index: 100;
}
.nav-inner {
  max-width: 1200px;
  margin: 0 auto;
  height: 64px;
  padding: 0 24px;
  display: flex;
  align-items: center;
  gap: 40px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 9px;
  color: #0f766e;
  text-decoration: none;
  white-space: nowrap;
}

/* LOGO: 二次元头像, 圆形裁切 */
.logo-mascot {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  object-fit: cover;
  background: #fff;
  box-shadow: 0 2px 8px rgba(20, 184, 166, 0.22);
}

/* 纯文字字标: 不放图标, 靠字重和字距撑起来 */
.logo-text {
  font-size: 19px;
  font-weight: 800;
  letter-spacing: 1.5px;
  color: #0f766e;
}

.menu { display: flex; gap: 28px; flex: 1; min-width: 0; }
.menu a {
  position: relative;
  white-space: nowrap;   /* 窄屏时别把"首页"拆成两行 */
  font-size: 15px;
  color: #4b5563;
  text-decoration: none;
  padding: 4px 0;
  transition: color 0.15s;
}
.menu a:hover { color: #14b8a6; }
.menu a.router-link-active { color: #14b8a6; font-weight: 600; }

/* 悬停 / 当前页: 底下划出一条小横线 */
.menu a::after {
  content: '';
  position: absolute; left: 0; right: 0; bottom: -3px; height: 2px;
  border-radius: 2px; background: #14b8a6;
  transform: scaleX(0);
  transition: transform 0.2s ease;
}
.menu a:hover::after,
.menu a.router-link-active::after { transform: scaleX(1); }

/* 「消息」+ 未读红点 */
.msg-link {
  position: relative;
  display: inline-flex !important;
  align-items: center;
  gap: 4px;
}
.badge {
  min-width: 17px;
  height: 17px;
  padding: 0 5px;
  border-radius: 9px;
  background: #e74c3c;
  color: #fff;
  font-size: 10px;
  font-weight: 600;
  line-height: 17px;
  text-align: center;
}

.nav-right { display: flex; align-items: center; flex-shrink: 0; }

/* 写文章: 导航栏里唯一的实心按钮, 用来突出"创作"这个动作 */
.write-btn {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 8px 18px; margin-right: 12px;
  border-radius: 20px;
  font-size: 13px; font-weight: 600;
  color: #fff; text-decoration: none; white-space: nowrap;
  background: linear-gradient(135deg, #2dd4bf 0%, #0d9488 100%);
  box-shadow: 0 4px 14px rgba(20, 184, 166, 0.30);
  transition: transform 0.16s, box-shadow 0.16s;
}
.write-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 20px rgba(20, 184, 166, 0.38);
}

/* 登录后: 头像 + 名字 */
.me-link {
  display: flex; align-items: center; gap: 8px;
  font-size: 14px; color: #374151; text-decoration: none;
  padding: 5px 12px 5px 5px; border-radius: 20px;
  transition: background 0.15s;
}
.me-link:hover { background: #f0fdfa; color: #14b8a6; }
.nav-avatar {
  width: 30px; height: 30px; border-radius: 50%; flex-shrink: 0; overflow: hidden;
  background: linear-gradient(135deg, #ccfbf1 0%, #a5b4fc 100%);
  display: flex; align-items: center; justify-content: center; font-size: 15px;
}
.nav-avatar img { width: 100%; height: 100%; object-fit: cover; }

.login-link {
  font-size: 14px;
  color: #14b8a6;
  text-decoration: none;
  padding: 7px 18px;
  border: 1px solid #14b8a6;
  border-radius: 18px;
  transition: all 0.15s;
}
.login-link:hover { background: #14b8a6; color: #fff; }

/* ---- 页脚 ---- */
.footer {
  margin-top: 48px;
  padding: 28px 24px 36px;
  border-top: 1px solid rgba(20, 184, 166, 0.14);
  text-align: center;
  font-size: 12px;
  color: #9aa5b1;
}
.footer-inner {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  max-width: var(--maxw);
  margin: 0 auto;
}
.footer a {
  color: #14b8a6;
  text-decoration: none;
}
.footer a:hover { text-decoration: underline; }
.footer .dot { color: #d1d8e0; }

/* ---- 窄屏: 导航栏放不下这么多东西, 让菜单可以横向滑, 别挤成两行 ---- */
@media (max-width: 900px) {
  .nav-inner { gap: 14px; padding: 0 14px; }
  .logo-text { display: none; }        /* 只留头像, 省地方 */
  .menu {
    gap: 16px;
    overflow-x: auto;
    -ms-overflow-style: none;          /* 隐藏滚动条 (Firefox/IE) */
    scrollbar-width: none;
  }
  .menu::-webkit-scrollbar { display: none; }
  .me-link { max-width: 110px; overflow: hidden; }
  .me-name { display: none; }  /* 窄屏只显示头像, 名字省掉 */
}
@media (max-width: 560px) {
  .nav-inner { height: 56px; }
  .write-btn { display: none; }        /* 首页侧栏还有创作入口, 这里省掉 */
}
</style>
