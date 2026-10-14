<template>
  <div class="page auth-page">
    <div class="brand">
      <div class="brand-ico cover-1">✨</div>
      <h2>欢迎回来</h2>
      <p>登录后可以发布文章、收藏、评论</p>
    </div>

    <div class="form card">
      <input v-model="username" placeholder="用户名" />
      <input v-model="password" type="password" placeholder="密码" @keyup.enter="handleLogin" />
      <button class="primary" @click="handleLogin">登录</button>
    </div>

    <p class="msg">{{ msg }}</p>

    <p class="switch">
      还没有账号？<router-link to="/register">去注册</router-link>
    </p>
    <p class="switch"><router-link to="/home">← 先逛逛首页</router-link></p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../services/authApi.js'

const username = ref('')
const password = ref('')
const msg = ref('')
const router = useRouter()

const handleLogin = async () => {
  if (!username.value || !password.value) {
    msg.value = '请填用户名和密码'
    return
  }
  try {
    const res = await login(username.value, password.value)
    if (res.data.token) {
      localStorage.setItem('token', res.data.token)   // 存 token
      router.push('/me')                              // 回"我的"
    } else {
      msg.value = res.data.error
    }
  } catch (err) {
    msg.value = '登录失败：' + err.message
  }
}
</script>

<style scoped>
.auth-page { max-width: 420px; padding-top: 60px; }
.brand { text-align: center; margin-bottom: 24px; }
.brand-ico {
  width: 60px; height: 60px; border-radius: 18px; margin: 0 auto 12px;
  display: flex; align-items: center; justify-content: center; font-size: 28px;
}
.brand h2 { font-size: 20px; }
.brand p { font-size: 12px; color: #7b8794; margin-top: 6px; }

.form { padding: 20px; display: flex; flex-direction: column; gap: 12px; }
.form input {
  padding: 12px 14px; border: 1px solid #e6ebf2; border-radius: 10px;
  font-size: 14px; outline: none;
}
.form input:focus { border-color: #14b8a6; }
.primary {
  padding: 12px; border: none; border-radius: 10px; cursor: pointer;
  background: #14b8a6; color: #fff; font-size: 15px; font-weight: 600;
}
.primary:active { opacity: 0.85; }

.msg { text-align: center; color: #e74c3c; font-size: 13px; margin-top: 14px; min-height: 18px; }
.switch { text-align: center; font-size: 13px; color: #7b8794; margin-top: 12px; }
.switch a { color: #14b8a6; text-decoration: none; }
</style>
