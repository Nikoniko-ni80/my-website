<template>
  <div class="page">
    <!-- 顶部: 标题 + 新建 -->
    <div class="head">
      <h2>我的文章</h2>
      <button class="new-btn" @click="goWrite">＋ 新建</button>
    </div>

    <p v-if="loading">加载中...</p>

    <div v-else class="list">
      <div v-for="a in articles" :key="a.id" class="item card">
        <div class="art-text">
          <p class="t">
            <strong class="clickable" @click="goDetail(a.id)">{{ a.title }}</strong>
            <span class="badge" :class="a.is_public ? 'pub-badge' : 'priv-badge'">
              {{ a.is_public ? '公开' : '私有' }}
            </span>
          </p>
          <p class="c">{{ a.content || '（无内容）' }}</p>
          <p class="meta">👍 {{ a.like_count || 0 }}</p>
        </div>

        <div class="btns">
          <button class="edit-btn" @click="goEdit(a.id)">编辑</button>
          <!-- 私有 → 显示"上架"; 公开 → 显示"下架" -->
          <button
            :class="a.is_public ? 'down-btn' : 'up-btn'"
            @click="togglePublish(a)"
          >{{ a.is_public ? '下架' : '上架' }}</button>
          <button class="del-btn" @click="handleDelete(a.id)">删除</button>
        </div>
      </div>
      <p v-if="articles.length === 0" class="empty">还没有文章，点右上角「＋ 新建」写一篇</p>
    </div>

    <p class="msg">{{ msg }}</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getMyArticles, deleteArticle, updateArticle } from '../services/authApi.js'

const articles = ref([])
const loading = ref(false)
const msg = ref('')
const router = useRouter()

const goWrite = () => router.push('/write')
const goEdit = (id) => router.push(`/write/${id}`)
const goDetail = (id) => router.push(`/article/${id}`)   // 点标题 → 像读者一样"看"

const loadArticles = async () => {
  const token = localStorage.getItem('token')
  if (!token) { router.push('/login'); return }
  loading.value = true
  try {
    const res = await getMyArticles(token)
    articles.value = res.data
  } catch (err) {
    if (err.response && err.response.status === 401) {
      localStorage.removeItem('token')
      router.push('/login')
    } else {
      msg.value = '获取失败：' + err.message
    }
  }
  loading.value = false
}

// 上架 / 下架 (切换 公开/私有)
const togglePublish = async (a) => {
  const token = localStorage.getItem('token')
  const newVal = !a.is_public                      // 现在私有 → 变公开; 现在公开 → 变私有
  try {
    await updateArticle(token, a.id, a.title, a.content, newVal)
    a.is_public = newVal                           // 本地更新, 页面立刻变
  } catch (err) {
    msg.value = '操作失败：' + err.message
  }
}

const handleDelete = async (id) => {
  const token = localStorage.getItem('token')
  try {
    await deleteArticle(token, id)
    articles.value = articles.value.filter(x => x.id !== id)
  } catch (err) {
    msg.value = '删除失败：' + err.message
  }
}

onMounted(loadArticles)
</script>

<style scoped>
.page { max-width: 820px; padding-top: 24px; }

.head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 18px; }
.head h2 { font-size: 20px; }
.new-btn {
  padding: 9px 20px; border: none; border-radius: 10px; cursor: pointer;
  background: #14b8a6; color: #fff; font-size: 14px; font-weight: 600;
  box-shadow: 0 4px 12px rgba(20, 184, 166, 0.28);
}
.new-btn:hover { background: #0d9488; }

.item { display: flex; justify-content: space-between; align-items: center; padding: 16px 18px; margin-bottom: 10px; }
.art-text { flex: 1; min-width: 0; margin-right: 14px; }
.t { display: flex; align-items: center; gap: 8px; font-size: 15px; }
.clickable { cursor: pointer; }
.clickable:hover { color: #14b8a6; }
.c { color: #6b7280; margin-top: 6px; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.meta { color: #9aa5b1; font-size: 12px; margin-top: 6px; }

.badge { font-size: 11px; padding: 2px 8px; border-radius: 6px; font-weight: 400; }
.pub-badge { background: #ccfbf1; color: #0f766e; }
.priv-badge { background: #f1f5f9; color: #64748b; }

.btns { display: flex; gap: 8px; flex-shrink: 0; }
.btns button { padding: 7px 14px; border: none; border-radius: 8px; cursor: pointer; font-size: 13px; }

.edit-btn { background: #0ea5e9; color: #fff; }
.edit-btn:hover { background: #0284c7; }

/* 上架 = 青绿 (往公开走) */
.up-btn { background: #14b8a6; color: #fff; }
.up-btn:hover { background: #0d9488; }
/* 下架 = 橙 (往私有走) */
.down-btn { background: #f59e0b; color: #fff; }
.down-btn:hover { background: #d97706; }

.del-btn { background: #e74c3c; color: #fff; }
.del-btn:hover { background: #c0392b; }

.empty { text-align: center; color: #a8b2c1; padding: 40px 0; }
.msg { color: #e74c3c; text-align: center; margin-top: 12px; }
</style>
