<template>
  <p v-if="loading" class="tip">加载中...</p>

  <template v-else>
    <!-- 收藏夹列表: 点一整行 = 收藏 / 取消收藏 -->
    <div class="list">
      <div
        v-for="c in collections"
        :key="c.id"
        class="row"
        :class="{ on: c.favorited, busy: busyId === c.id }"
        @click="toggle(c)"
      >
        <span class="tick">{{ c.favorited ? '✓' : '' }}</span>
        <span class="name">{{ c.name }}</span>
        <span class="cnt">{{ c.count }} 篇</span>
      </div>
      <!-- ⚠️ 这里【必须】带上 !msg:
           因为 collections 为空有【两种】原因 ——
             ① 用户真的没有收藏夹   → 不可能发生 (后端 get_or_create 保证了至少有一个)
             ② 这次请求失败了       → 这才是唯一会发生的
           而②的时候下面会显示真正的错误原因 (msg), 这里再冒出一句
           "还没有收藏夹" 就是误导 —— 用户明明有夹子, 会跑去乱建一个。
           加上 !msg 之后: 出错了就只说错误原因, 不再叠这条假提示。 -->
      <p v-if="!msg && collections.length === 0" class="tip">还没有收藏夹, 点下面新建一个</p>
    </div>

    <!-- ＋新建: 就地展开一个输入框
         (不在这里再弹一个 Modal —— 弹窗套弹窗体验很差, 层级也乱) -->
    <div v-if="!showNew" class="new-line" @click="openNew">＋ 新建收藏夹</div>
    <div v-else class="new-line editing">
      <input
        ref="newInput"
        v-model="newName"
        placeholder="收藏夹名字"
        @keyup.enter="createNew"
      />
      <button class="ok" @click="createNew">确定</button>
      <button class="cancel" @click="cancelNew">取消</button>
    </div>

    <p v-if="msg" class="msg">{{ msg }}</p>
  </template>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  getCollectionsOfArticle, addFavorite, removeFavorite, createCollection
} from '../services/authApi.js'

// props: 父组件(文章详情页)传进来的文章 id, 已经 Number() 过了
const props = defineProps({
  articleId: { type: Number, required: true },
})

// emits: 转给父组件一件事 —— "现在这篇被收进几个夹子了"
// (父组件拿这个数字去更新按钮上的文案, 它自己就不用再发一次请求)
const emit = defineEmits(['changed'])

const router = useRouter()
const collections = ref([])     // [{id, name, count, favorited}]
const loading = ref(false)
const msg = ref('')
const showNew = ref(false)
const newName = ref('')
const newInput = ref(null)
const busyId = ref(null)        // 正在请求的那一行 (防止手快连点两次)

// 状态变了就顺手报个数给父组件
const emitChanged = () => {
  emit('changed', collections.value.filter((c) => c.favorited).length)
}

// 统一拿 token (照抄 MyArticlesPage.vue 的写法)
const getToken = () => {
  const token = localStorage.getItem('token')
  if (!token) { router.push('/login'); return null }
  return token
}

// 统一处理"请求异常" (网络断 / 后端没开 / 500 / 401)
const handleErr = (err) => {
  if (err.response && err.response.status === 401) {
    localStorage.removeItem('token')       // token 失效 → 清掉再跳登录
    router.push('/login')
  } else {
    msg.value = '操作失败：' + err.message
  }
}

// ---------- 拉收藏夹列表 ----------
const load = async () => {
  const token = getToken()
  if (!token) return
  loading.value = true
  try {
    const res = await getCollectionsOfArticle(token, props.articleId)
    // ⚠️ 后端业务错误是 HTTP 200 + body 里的 {error}, 不会抛异常!
    //    所以 await 没报错 ≠ 成功, 每次都得查一下 res.data.error
    if (res.data.error) {
      msg.value = res.data.error
    } else {
      collections.value = res.data //这里后端装返回的信息
      emitChanged()
    }
  } catch (err) {
    handleErr(err)
  }
  loading.value = false
}

// ---------- 点一行: 已收藏 → 取消; 没收藏 → 收藏 ----------
const toggle = async (c) => {
  if (busyId.value) return                  // 上一次请求还没回来, 先忽略这次点击
  const token = getToken()
  if (!token) return
  busyId.value = c.id
  msg.value = ''
  try {
    if (c.favorited) {
      // ---- 取消收藏 ----
      const res = await removeFavorite(token, c.id, props.articleId)
      if (res.data.error) {
        // 后端说"没有收藏过这篇" → 我们想要的结果就是"没收藏", 目标已达成, 当成成功
        if (res.data.error.includes('没有收藏过')) c.favorited = false
        else msg.value = res.data.error
      } else {
        c.favorited = false
        c.count--
      }
    } else {
      // ---- 收藏 ----
      const res = await addFavorite(token, c.id, props.articleId)
      if (res.data.error) {
        // ★ 重复收藏: 后端说"已经有这篇文章了" → 我们想要的就是"已经在里面", 目标已达成。
        //   最常见的原因是手快点了两次, 不该弹红字吓用户, 当成成功处理。
        if (res.data.error.includes('已经有')) {
          c.favorited = true                // 本地纠正成正确状态 (count 不动, 服务端的数本来就算它了)
        } else {
          msg.value = res.data.error        // 其他错误(夹子不是我的 / 文章不可见)正常报
        }
      } else {
        c.favorited = true
        c.count++
      }
    }
    emitChanged()
  } catch (err) {
    handleErr(err)
  }
  busyId.value = null
}

// ---------- 新建收藏夹 ----------
const openNew = async () => {
  showNew.value = true
  msg.value = ''
  await nextTick()          // 等输入框渲染出来再聚焦
  if (newInput.value) newInput.value.focus()
}

const cancelNew = () => {
  showNew.value = false
  newName.value = ''
  msg.value = ''
}

const createNew = async () => {
  const name = newName.value.trim()
  if (!name) { msg.value = '收藏夹名字不能为空'; return }
  const token = getToken()
  if (!token) return
  try {
    const res = await createCollection(token, name)
    if (res.data.error) { msg.value = res.data.error; return }
    // 新建成功 → 先塞进列表, 再顺手把当前这篇收进去 (省用户一次点击)
    const c = { id: res.data.id, name: res.data.name, count: 0, favorited: false }
    collections.value.push(c)
    cancelNew()
    await toggle(c)
  } catch (err) {
    handleErr(err)
  }
}

onMounted(load)
</script>

<style scoped>
.tip { font-size: 13px; color: #a8b2c1; padding: 16px 0; text-align: center; }

/* 夹子列表 */
.list { margin-bottom: 6px; }
.row {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 12px; border-radius: 10px; cursor: pointer;
  transition: background 0.15s;
}
.row:hover { background: #f0fdfa; }
.row.on { background: #f0fdfa; }
.row.busy { opacity: 0.5; cursor: default; }   /* 请求中变灰, 视觉上也告诉你点不动 */

/* 打勾的方框 */
.tick {
  width: 20px; height: 20px; flex-shrink: 0;
  border: 1.5px solid #d8e0ea; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; color: #fff;
}
.row.on .tick { background: #14b8a6; border-color: #14b8a6; }

/* min-width: 0 不能省 —— 收藏夹名字是用户输入的, 很长的话会把右边的
   "N 篇" 和打勾挤出去 (见 style.css 顶部那段说明) */
.name { flex: 1; min-width: 0; font-size: 14px; color: #374151; }
.row.on .name { color: #0f766e; font-weight: 600; }
.cnt { font-size: 12px; color: #9aa5b1; }

/* 新建那一行 */
.new-line {
  padding: 12px; border-top: 1px solid #f2f5f9;
  font-size: 14px; color: #14b8a6; cursor: pointer; font-weight: 600;
}
.new-line:hover { color: #0d9488; }
.new-line.editing {
  display: flex; gap: 8px; align-items: center; cursor: default;
}
.new-line.editing input {
  flex: 1; min-width: 0; padding: 8px 12px; font-size: 13px;
  border: 1px solid #e6ebf2; border-radius: 8px; outline: none;
}
.new-line.editing input:focus { border-color: #14b8a6; }
.new-line.editing button {
  padding: 8px 14px; border: none; border-radius: 8px;
  font-size: 13px; cursor: pointer; flex-shrink: 0;
}
.ok { background: #14b8a6; color: #fff; }
.ok:hover { background: #0d9488; }
.cancel { background: #f1f5f9; color: #64748b; }
.cancel:hover { background: #e2e8f0; }

.msg { color: #e74c3c; font-size: 13px; margin-top: 10px; }
</style>
