<template>
  <div class="page">
    <div class="head">
      <h2>浏览历史</h2>
      <button v-if="items.length" class="clear-btn" @click="showConfirm = true">
        清空历史
      </button>
    </div>

    <p v-if="loading" class="tip">加载中...</p>

    <div v-else class="list">
      <div v-for="(a, i) in items" :key="a.id" class="item card">
        <div class="cover" :class="coverOf(i)">
                <img v-if="a.cover" :src="mediaUrl(a.cover)" alt="" class="cover-img" />
                <IconDoc v-else />
              </div>

        <div class="art-text">
          <p class="t">
            <strong class="clickable" @click="goDetail(a.id)">{{ a.title }}</strong>
          </p>
          <p class="c">{{ a.content || '（无内容）' }}</p>
          <p class="meta">
            <!-- ★ 作者名可点 → 跳个人主页 -->
            <span class="author-link" @click.stop="goUser(a.user_id)">{{ a.author }}</span>
            · {{ fmtTime(a.viewed_at) }}
          </p>
        </div>
      </div>

      <p v-if="items.length === 0" class="empty">
        还没有浏览记录～ 去首页随便点几篇看看
      </p>
    </div>

    <p class="msg" v-if="msg">{{ msg }}</p>

    <!-- 清空的二次确认 (跟删收藏夹一个套路: 不可恢复的都要问一句) -->
    <Modal v-model="showConfirm" title="清空浏览历史">
      <p class="m-text">
        确定清空全部 <b>{{ items.length }}</b> 条浏览记录吗？<br />
        清空之后就找不回来了。
      </p>
      <div class="m-btns">
        <button class="cancel" @click="showConfirm = false">再想想</button>
        <button class="danger" @click="doClear">确定清空</button>
      </div>
    </Modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getHistory, clearHistory } from '../services/authApi.js'
import { mediaUrl } from '../utils/media.js'
import Modal from './Modal.vue'
import { goLogin } from '../utils/auth.js'

const router = useRouter()

const items = ref([])        // [{id, title, content, author, viewed_at}]
const loading = ref(false)
const msg = ref('')
const showConfirm = ref(false)

const goDetail = (id) => router.push(`/article/${id}`)
const goUser = (id) => { if (id) router.push(`/user/${id}`) }   // 点作者名 → 个人主页

// ---- 封面装饰 (跟首页/收藏页一个套路, 纯样式) ----
const covers = ['cover-1', 'cover-2', 'cover-3', 'cover-4', 'cover-5', 'cover-6']
const coverOf = (i) => covers[i % covers.length]

// 把时间变成"人话": 刚刚 / 5分钟前 / 3小时前 / 2天前 / 9月29日
const fmtTime = (s) => {
  if (!s) return ''
  const d = new Date(s.replace(' ', 'T'))     // "2026-09-29 19:17:40" → 能被 Date 认出来
  if (isNaN(d)) return ''

  const diffMs = Date.now() - d.getTime()
  const min = Math.floor(diffMs / 60000)      // 差了几分钟
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`

  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`

  const day = Math.floor(hr / 24)
  if (day < 7) return `${day} 天前`

  return `${d.getMonth() + 1}月${d.getDate()}日`
}

// ---- 统一处理请求异常 ----
const handleErr = (err) => {
  if (err.response && err.response.status === 401) {
    localStorage.removeItem('token')
    goLogin(router)
  } else {
    msg.value = '操作失败：' + err.message
  }
}

const load = async () => {
  const token = localStorage.getItem('token')
  if (!token) { goLogin(router); return }
  loading.value = true
  try {
    const res = await getHistory(token)
    if (res.data.error) msg.value = res.data.error      // 后端错误是 200 + {error}
    else items.value = res.data
  } catch (err) {
    handleErr(err)
  }
  loading.value = false
}

const doClear = async () => {
  const token = localStorage.getItem('token')
  if (!token) { goLogin(router); return }
  try {
    const res = await clearHistory(token)
    if (res.data.error) { msg.value = res.data.error; return }
    items.value = []                                     // 本地也清掉
    showConfirm.value = false
    msg.value = '已清空'
    setTimeout(() => (msg.value = ''), 1500)
  } catch (err) {
    handleErr(err)
  }
}

onMounted(load)
</script>

<style scoped>
.page { max-width: 1080px; padding-top: 24px; }

.head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 18px;
}
.head h2 { font-size: 20px; }
.clear-btn {
  padding: 8px 18px; border: 1px solid #e6ebf2; border-radius: 10px;
  background: #fff; color: #64748b; font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.clear-btn:hover { border-color: #e74c3c; color: #e74c3c; }

.item {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 18px; margin-bottom: 10px;
}
.cover {
  width: 54px; height: 54px; border-radius: 12px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  color: rgba(15, 118, 110, 0.45);
}

.art-text { flex: 1; min-width: 0; }
.t { font-size: 15px; }
.clickable { cursor: pointer; }
.clickable:hover { color: #14b8a6; }
.c {
  color: #6b7280; margin-top: 5px; font-size: 13px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.meta { color: #9aa5b1; font-size: 12px; margin-top: 6px; }
.author-link { cursor: pointer; }
.author-link:hover { color: #14b8a6; text-decoration: underline; }

.tip { text-align: center; color: #a8b2c1; padding: 40px 0; }
.empty { text-align: center; color: #a8b2c1; padding: 50px 0; font-size: 14px; }
.msg { color: #14b8a6; text-align: center; margin-top: 14px; font-size: 13px; }

/* 弹窗 */
.m-text { font-size: 14px; color: #4b5563; line-height: 1.9; }
.m-text b { color: #e74c3c; }
.m-btns { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
.m-btns button {
  padding: 9px 20px; border: none; border-radius: 10px;
  font-size: 14px; cursor: pointer;
}
.cancel { background: #f1f5f9; color: #64748b; }
.cancel:hover { background: #e2e8f0; }
.danger { background: #e74c3c; color: #fff; font-weight: 600; }
.danger:hover { background: #c0392b; }

.cover-img { width: 100%; height: 100%; object-fit: cover; display: block; }
</style>
