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
          <router-link to="/me">我的</router-link>
        </nav>

        <div class="nav-right">
          <!-- 登录了 → 显示头像 + 名字 (点一下进自己主页) -->
          <router-link v-if="me" :to="`/user/${me.id}`" class="me-link">
            <span class="nav-avatar">
              <img v-if="me.avatar" :src="me.avatar" alt="" />
              <span v-else>🐦</span>
            </span>
            {{ me.username }}
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
import { ref, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getMe } from './services/authApi.js'

const route = useRoute()
const me = ref(null)          // null = 没登录

const refresh = async () => {
  const token = localStorage.getItem('token')
  if (!token) { me.value = null; return }
  try {
    const res = await getMe(token)
    me.value = res.data.error ? null : res.data
  } catch (e) {
    me.value = null           // token 过期/无效 → 当没登录
  }
}

onMounted(refresh)
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

.menu { display: flex; gap: 28px; flex: 1; }
.menu a {
  font-size: 15px;
  color: #4b5563;
  text-decoration: none;
  padding: 4px 0;
  transition: color 0.15s;
}
.menu a:hover { color: #14b8a6; }
.menu a.router-link-active { color: #14b8a6; font-weight: 600; }

.nav-right { display: flex; align-items: center; }

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
</style>
