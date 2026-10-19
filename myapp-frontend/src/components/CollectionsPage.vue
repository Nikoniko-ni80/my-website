<template>
  <div class="page">
    <p v-if="loading" class="tip">加载中...</p>

    <div v-else class="layout">
      <!-- ================= 左栏: 收藏夹列表 ================= -->
      <aside class="side card">
        <div class="side-head">
          <span>我创建的收藏夹</span>
          <span class="side-cnt">{{ collections.length }}</span>
        </div>

        <div class="new-line" @click="openNew">
          <span class="plus">＋</span><span>新建收藏夹</span>
        </div>

        <div class="folder-list">
          <div
            v-for="c in collections"
            :key="c.id"
            class="folder-row"
            :class="{ on: c.id === currentId }"
            @click="selectFolder(c.id)"
          >
            <span class="f-ico">📁</span>
            <span class="f-name">{{ c.name }}</span>
            <span class="f-cnt">{{ c.count }}</span>
          </div>
        </div>
      </aside>

      <!-- ================= 右栏: 内容 ================= -->
      <section class="main">
        <template v-if="current">
          <!-- 收藏夹信息头 -->
          <div class="hero card">
            <div class="hero-ico">📁</div>
            <div class="hero-info">
              <h2>{{ current.name }}</h2>
              <p class="hero-meta">公开 · 收藏 {{ current.count }} 篇</p>
            </div>
            <div class="hero-btns">
              <button class="ghost-btn" @click="openRename(current)">✎ 改名</button>
              <button class="ghost-btn danger" @click="askDelete(current)">🗑 删除</button>
            </div>
          </div>

          <!-- 工具条: 排序 + 搜索 -->
          <div class="toolbar">
            <div class="tabs">
              <span
                v-for="t in tabs"
                :key="t.key"
                class="tab"
                :class="{ on: sortBy === t.key }"
                @click="sortBy = t.key"
              >{{ t.label }}</span>
            </div>
            <input class="search" v-model="keyword" placeholder="搜索标题或作者" />
          </div>

          <!-- 文章卡片网格 -->
          <p v-if="articlesLoading" class="tip">加载中...</p>

          <div v-else class="grid">
            <div
              v-for="(a, i) in shownArticles"
              :key="a.id"
              class="art-card card hoverable"
              @click="goDetail(a.id)"
            >
              <!-- 没有真封面图, 就用渐变色块 + emoji 顶替 (跟首页一个套路) -->
              <div class="cover" :class="coverOf(i)">
                <span class="cover-emoji"><IconDoc /></span>
                <span class="cover-tag">{{ a.author }}</span>
              </div>

              <div class="art-info">
                <p class="art-title">{{ a.title }}</p>
                <div class="art-meta">
                  <span class="avatar" :class="coverOf(i)"><IconUser /></span>
                  <!-- ★ 作者名可点 → 个人主页。.stop 防止顺带触发卡片的"进文章详情" -->
                  <span class="author-link" @click.stop="goUser(a.user_id)">{{ a.author }}</span>
                  <span>· 收藏于 {{ fmtDate(a.favorited_at) }}</span>
                  <!-- ★ 点赞量: margin-left:auto 推到最右边 -->
                  <span class="art-like">👍 {{ a.like_count || 0 }}</span>
                </div>
              </div>
            </div>
          </div>

          <p v-if="!articlesLoading && shownArticles.length === 0" class="empty">
            {{ keyword ? '没搜到匹配的文章～' : '这个收藏夹还是空的～ 去首页看看有什么想收藏的' }}
          </p>
        </template>

        <p v-else class="empty">还没有收藏夹，点左边「＋ 新建收藏夹」建一个</p>
      </section>
    </div>

    <p class="msg" v-if="msg">{{ msg }}</p>

    <!-- 新建 / 改名 共用这一个弹窗 (靠 formMode 区分是哪种) -->
    <Modal v-model="showForm" :title="formMode === 'new' ? '新建收藏夹' : '给收藏夹改名'">
      <input
        class="m-input"
        v-model="formName"
        placeholder="收藏夹名字"
        @keyup.enter="submitForm"
      />
      <div class="m-btns">
        <button class="cancel" @click="showForm = false">取消</button>
        <button class="ok" @click="submitForm">确定</button>
      </div>
    </Modal>

    <!-- 删除的二次确认: 把"会连带删掉几篇"写清楚 -->
    <Modal v-model="showConfirm" title="删除收藏夹">
      <p class="m-text">
        确定删除「{{ deleteTarget && deleteTarget.name }}」吗？<br />
        里面的 <b>{{ deleteTarget && deleteTarget.count }}</b> 篇收藏会一起被删掉，删了就找不回来了。
      </p>
      <div class="m-btns">
        <button class="cancel" @click="showConfirm = false">再想想</button>
        <button class="danger" @click="confirmDelete">确定删除</button>
      </div>
    </Modal>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getCollections, createCollection, renameCollection, deleteCollection,
  getCollectionArticles
} from '../services/authApi.js'
import Modal from './Modal.vue'
import { goLogin } from '../utils/auth.js'

const route = useRoute()
const router = useRouter()

// ---- 收藏夹 (左栏) ----
const collections = ref([])       // [{id, name, count}]
const loading = ref(false)

// ---- 文章 (右栏) ----
const articles = ref([])          // [{id, title, content, author, favorited_at}]
const articlesLoading = ref(false)
const keyword = ref('')
const sortBy = ref('recent')

const tabs = [
  { key: 'recent', label: '最近收藏' },
  { key: 'oldest', label: '最早收藏' },
  { key: 'title',  label: '按标题' },
]

const msg = ref('')

// ---- 弹窗 ----
const showForm = ref(false)
const formMode = ref('new')       // 'new' = 新建 | 'rename' = 改名
const formName = ref('')
const editingId = ref(null)
const showConfirm = ref(false)
const deleteTarget = ref(null)

// ★ 当前选中的是哪一本 —— 直接从网址里读, 不另存一份状态
//   (好处: 只有一个"真相来源", 不会出现"网址说是3、界面显示5"这种对不上的情况)
//   网址里没写 id (比如 /my-collections) → 就默认选第一本
const currentId = computed(() => {
  const id = Number(route.params.id)
  if (id && collections.value.some((c) => c.id === id)) return id
  return collections.value.length ? collections.value[0].id : null
})

const current = computed(() => collections.value.find((c) => c.id === currentId.value) || null)

// 点左边的收藏夹 → 改网址 → 上面的 currentId 自动跟着变 → 触发下面的 watch
const selectFolder = (id) => router.push(`/my-collections/${id}`)
const goDetail = (id) => router.push(`/article/${id}`)
const goUser = (id) => { if (id) router.push(`/user/${id}`) }   // 点作者名 → 个人主页

// ---- 封面装饰 (跟首页 HomePage 一个套路) ----
const covers = ['cover-1', 'cover-2', 'cover-3', 'cover-4', 'cover-5', 'cover-6']
const coverOf = (i) => covers[i % covers.length]

// "2026-09-14 10:30:00" → "9月14日"
const fmtDate = (s) => {
  if (!s) return ''
  const d = new Date(s.replace(' ', 'T'))
  if (isNaN(d)) return ''
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

// 排序 + 搜索都在前端做, 因为数据已经一次全拿回来了
const shownArticles = computed(() => {
  let list = [...articles.value]

  const k = keyword.value.trim()
  if (k) list = list.filter((a) => a.title.includes(k) || a.author.includes(k))

  if (sortBy.value === 'oldest') list.reverse()          // 后端给的是"最近在前", 反过来就是最早在前
  else if (sortBy.value === 'title') list.sort((a, b) => a.title.localeCompare(b.title, 'zh'))

  return list
})

// ---- 统一处理"请求异常" ----
const handleErr = (err) => {
  if (err.response && err.response.status === 401) {
    localStorage.removeItem('token')
    goLogin(router)
  } else {
    msg.value = '操作失败：' + err.message
  }
}

const getToken = () => {
  const token = localStorage.getItem('token')
  if (!token) { goLogin(router); return null }
  return token
}

// ---------- 拉左边: 收藏夹列表 ----------
const loadCollections = async () => {
  const token = getToken()
  if (!token) return
  loading.value = true
  try {
    const res = await getCollections(token)
    if (res.data.error) msg.value = res.data.error     // 后端错误是 200 + {error}, 得自己查
    else collections.value = res.data
  } catch (err) {
    handleErr(err)
  }
  loading.value = false
}

// ---------- 拉右边: 某个收藏夹里的文章 ----------
const loadArticles = async (id) => {
  const token = getToken()
  if (!token) return
  articlesLoading.value = true
  try {
    const res = await getCollectionArticles(token, id)
    if (res.data.error) { msg.value = res.data.error; articles.value = [] }
    else articles.value = res.data
  } catch (err) {
    handleErr(err)
    articles.value = []
  }
  articlesLoading.value = false
}

// ★ 只盯着 currentId 一个东西:
//   它一变 (点左边 / 网址变了 / 删掉了当前这本), 右边就自动重新拉数据
//   不用在"点收藏夹"那个函数里手动调 loadArticles —— 少一处会忘记同步的地方
watch(currentId, (id) => {
  keyword.value = ''        // 换收藏夹时把搜索框清掉
  if (id) loadArticles(id)
  else articles.value = []
})

// ---------- 新建 ----------
const openNew = () => {
  formMode.value = 'new'
  formName.value = ''
  msg.value = ''
  showForm.value = true
}

// ---------- 改名 ----------
const openRename = (c) => {
  formMode.value = 'rename'
  editingId.value = c.id
  formName.value = c.name          // 先把旧名字填进去, 用户改起来方便
  msg.value = ''
  showForm.value = true
}

// 新建和改名的提交逻辑几乎一样, 只是调的接口不同, 所以合成一个函数
const submitForm = async () => {
  const name = formName.value.trim()
  if (!name) { msg.value = '收藏夹名字不能为空'; return }
  const token = getToken()
  if (!token) return
  try {
    const res = formMode.value === 'new'
      ? await createCollection(token, name)
      : await renameCollection(token, editingId.value, name)
    if (res.data.error) { msg.value = res.data.error; return }
    showForm.value = false
    msg.value = ''
    await loadCollections()      // 重新拉一遍, 保证跟后端一致 (改名后右边标题也会跟着变)
  } catch (err) {
    handleErr(err)
  }
}

// ---------- 删除 ----------
const askDelete = (c) => {
  // 先拦住"删最后一个": 后端下次拉列表时会自动重建"默认收藏夹",
  // 用户删完一刷新发现又冒出来一个, 会以为"删除失败了"
  if (collections.value.length <= 1) {
    msg.value = '至少要留一个收藏夹哦'
    return
  }
  deleteTarget.value = c
  showConfirm.value = true
}

const confirmDelete = async () => {
  const token = getToken()
  if (!token) return
  const deletedId = deleteTarget.value.id          // 先记下来, 等下要判断删的是不是当前这本
  try {
    const res = await deleteCollection(token, deletedId)
    if (res.data.error) { msg.value = res.data.error; return }
    showConfirm.value = false
    msg.value = ''
    await loadCollections()
    // 删掉的正好是当前打开的这本 → 网址里那个 id 已经不存在了, 清掉它
    if (deletedId === Number(route.params.id)) router.push('/my-collections')
  } catch (err) {
    handleErr(err)
  }
}

onMounted(loadCollections)
</script>

<style scoped>
.page { max-width: 1200px; padding-top: 20px; }

/* ============ 两栏布局 ============ */
.layout { display: flex; gap: 18px; align-items: flex-start; }

/* ---------- 左栏 ---------- */
.side {
  width: 240px; flex-shrink: 0;
  padding: 14px 10px;
  position: sticky; top: 84px;      /* 页面往下滚时左栏跟着"粘"住 */
}
.side-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 4px 12px 12px;
  font-size: 14px; font-weight: 600; color: #1f2937;
}
.side-cnt { font-size: 12px; color: #9aa5b1; font-weight: 400; }

.new-line {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px; margin-bottom: 6px;
  border-radius: 10px; font-size: 14px; font-weight: 600;
  color: #14b8a6; cursor: pointer; transition: background 0.15s;
}
.new-line:hover { background: #f0fdfa; }
.plus { font-size: 15px; }

.folder-list { border-top: 1px solid #f2f5f9; padding-top: 6px; }

.folder-row {
  display: flex; align-items: center; gap: 10px;
  padding: 11px 12px; border-radius: 10px; cursor: pointer;
  font-size: 14px; color: #4b5563; transition: all 0.15s;
}
.folder-row:hover { background: #f5f8fa; }
/* ★ 选中态: 青绿实心 + 白字 (B站是蓝底白字, 这里换成你项目的主色) */
.folder-row.on { background: #14b8a6; color: #fff; font-weight: 600; }
.folder-row.on .f-cnt { color: rgba(255, 255, 255, 0.85); }
.folder-row.on .f-ico { filter: brightness(1.15); }

.f-ico { font-size: 15px; }
.f-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.f-cnt { font-size: 12px; color: #9aa5b1; }

/* ---------- 右栏 ---------- */
.main { flex: 1; min-width: 0; }

.hero {
  display: flex; align-items: center; gap: 16px;
  padding: 20px 24px; margin-bottom: 16px;
}
.hero-ico {
  width: 56px; height: 56px; border-radius: 14px; font-size: 26px; flex-shrink: 0;
  background: linear-gradient(135deg, #ccfbf1 0%, #a5b4fc 100%);
  display: flex; align-items: center; justify-content: center;
}
.hero-info h2 { font-size: 20px; color: #1f2937; }
.hero-meta { font-size: 13px; color: #9aa5b1; margin-top: 5px; }

.hero-btns { margin-left: auto; display: flex; gap: 8px; }
.ghost-btn {
  padding: 7px 14px; border: 1px solid #e6ebf2; border-radius: 8px;
  background: #fff; color: #4b5563; font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.ghost-btn:hover { border-color: #14b8a6; color: #14b8a6; }
.ghost-btn.danger:hover { border-color: #e74c3c; color: #e74c3c; }

/* ---------- 工具条 ---------- */
.toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
.tabs { display: flex; gap: 6px; }
.tab {
  padding: 7px 16px; border-radius: 18px; font-size: 13px;
  color: #4b5563; background: #fff; cursor: pointer; transition: all 0.15s;
}
.tab:hover { color: #14b8a6; }
.tab.on { background: #14b8a6; color: #fff; font-weight: 600; }

.search {
  margin-left: auto; width: 200px;
  padding: 8px 14px; border: 1px solid #e6ebf2; border-radius: 18px;
  font-size: 13px; outline: none; background: #fff;
}
.search:focus { border-color: #14b8a6; }

/* ---------- 卡片网格 ---------- */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 16px;
}

.art-card { overflow: hidden; }

.cover {
  height: 118px; position: relative;
  display: flex; align-items: center; justify-content: center;
}
.cover-emoji {
  width: 52px;
  height: 52px;
  color: rgba(15, 118, 110, 0.42);
}
.cover-tag {
  position: absolute; left: 10px; bottom: 9px;
  padding: 2px 8px; border-radius: 6px;
  font-size: 11px; color: #fff; background: rgba(15, 23, 42, 0.38);
}

.art-info { padding: 12px 14px 14px; }
.art-title {
  font-size: 14px; font-weight: 600; color: #1f2937; line-height: 1.5;
  height: 42px;                              /* 固定两行高, 卡片才会一样齐 */
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden;
}
.art-meta {
  display: flex; align-items: center; gap: 6px;
  margin-top: 10px; font-size: 12px; color: #9aa5b1;
}
.avatar {
  width: 20px; height: 20px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 11px;
}
.author-link { cursor: pointer; }
.author-link:hover { color: #14b8a6; text-decoration: underline; }
.art-like { margin-left: auto; flex-shrink: 0; }

/* ---------- 其他 ---------- */
.tip { color: #a8b2c1; font-size: 14px; padding: 30px 0; text-align: center; }
.empty { text-align: center; color: #a8b2c1; padding: 50px 0; font-size: 14px; }
.msg { color: #e74c3c; text-align: center; margin-top: 14px; font-size: 13px; }

/* ---- 弹窗里的内容 ---- */
.m-input {
  width: 100%; padding: 11px 14px; font-size: 14px;
  border: 1px solid #e6ebf2; border-radius: 10px; outline: none;
}
.m-input:focus { border-color: #14b8a6; }

.m-text { font-size: 14px; color: #4b5563; line-height: 1.9; }
.m-text b { color: #e74c3c; }

.m-btns { display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px; }
.m-btns button {
  padding: 9px 20px; border: none; border-radius: 10px;
  font-size: 14px; cursor: pointer;
}
.ok { background: #14b8a6; color: #fff; font-weight: 600; }
.ok:hover { background: #0d9488; }
.cancel { background: #f1f5f9; color: #64748b; }
.cancel:hover { background: #e2e8f0; }
.danger { background: #e74c3c; color: #fff; font-weight: 600; }
.danger:hover { background: #c0392b; }
</style>
