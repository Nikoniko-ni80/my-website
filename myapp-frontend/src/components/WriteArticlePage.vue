<template>
  <div class="write-page">
    <!-- 顶部栏 -->
    <header class="wbar">
      <button class="back" @click="goBack">‹ 返回</button>
      <span class="wtitle">{{ isEdit ? '编辑文章' : '写文章' }}</span>

      <div class="right">
        <!-- ★ 分类下拉: 一篇文章只能选一个 -->
        <select class="cat-sel" v-model="category">
          <option value="">未分类</option>
          <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
        </select>
        <label class="pub">
          <input type="checkbox" v-model="isPublic" />
          <span>公开</span>
        </label>
        <!-- ★ 付费: 勾上后填价格 (单位元, 提交时转成分) -->
        <label class="pub">
          <input type="checkbox" v-model="isPaid" />
          <span>付费</span>
        </label>
        <label v-if="isPaid" class="price-wrap">
          ¥
          <input
            class="price-input"
            v-model="priceYuan"
            type="number"
            min="0"
            step="0.01"
            placeholder="0.00"
          />
        </label>
        <button class="done" @click="handleDone">完成</button>
      </div>
    </header>

    <!-- 标题 -->
    <input class="title-input" v-model="title" placeholder="请输入标题…" />

    <!-- ===== 封面 ===== -->
    <div class="cover-row">
      <div class="cover-box">
        <img v-if="coverUrl" :src="mediaUrl(coverUrl)" alt="" />
        <span v-else class="cover-tip">封面（可不填）</span>
      </div>
      <div class="cover-actions">
        <label class="cover-pick">
          {{ coverBusy ? '上传中…' : (coverUrl ? '换一张' : '上传封面') }}
          <input
            type="file"
            accept="image/png,image/jpeg,image/gif,image/webp"
            hidden
            @change="onPickCover"
          />
        </label>
        <button v-if="coverUrl" class="cover-rm" type="button" @click="coverUrl = ''">移除</button>
        <span class="cover-hint">不传就用默认渐变</span>
      </div>
    </div>

    <!-- ===== 标签 ===== -->
    <div class="tag-row">
      <span class="tag-label">标签</span>
      <div class="tag-box">
        <span v-for="t in tags" :key="t" class="tag-chip">
          {{ t }}
          <button class="tag-x" @click="removeTag(t)">×</button>
        </span>
        <input
          v-model="tagInput"
          class="tag-input"
          :disabled="tags.length >= MAX_TAGS"
          :placeholder="tags.length >= MAX_TAGS ? '最多 5 个标签' : '输入后按回车添加…'"
          @keydown.enter.prevent="addTagFromInput"
          @input="searchTags"
          @focus="searchTags"
          @blur="closeSuggest"
        />
      </div>

      <!-- 联想下拉: 用 mousedown.prevent 抢在 blur 之前触发 -->
      <div v-if="showSuggest && suggestions.length" class="tag-suggest">
        <div
          v-for="s in suggestions" :key="s.id"
          class="sug-item"
          @mousedown.prevent="pickTag(s.name)"
        >
          <span>{{ s.name }}</span>
          <span class="sug-count">{{ s.count }} 篇</span>
        </div>
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <button v-for="t in tools" :key="t.label" :title="t.tip" @click="applyTool(t)">
        {{ t.label }}
      </button>

      <!-- ★ 插入图片: 上传后自动插入 Markdown -->
      <button type="button" title="插入图片" :disabled="imgBusy" @click="pickImage">
        {{ imgBusy ? '…' : '🖼' }}
      </button>
      <input
        ref="imgInput"
        type="file"
        accept="image/png,image/jpeg,image/gif,image/webp"
        hidden
        @change="onPickImage"
      />

      <!-- ★ 导入 Markdown：md + 图片一起选 -->
      <button type="button" title="导入 Markdown（连同图片一起选）" :disabled="mdImporting" @click="pickMd">
        {{ mdImporting ? '…' : '📥' }}
      </button>
      <input
        ref="mdInput"
        type="file"
        multiple
        accept=".md,.markdown,image/png,image/jpeg,image/gif,image/webp"
        hidden
        @change="onImportMd"
      />

      <span class="tip">支持 Markdown · 右边实时预览</span>
    </div>

    <!-- 左右分栏: 编辑 | 预览 -->
    <div class="panes">
      <textarea
        ref="editorRef"
        class="pane editor"
        v-model="content"
        @paste="handlePaste"
        @drop="handleDrop"
        @dragover="handleDragOver"
        placeholder="开始写吧…

试试这些:
# 一级标题
**粗体**  *斜体*
- 列表项

```python
print('代码块')
```"
      ></textarea>

      <!-- 预览: v-html 插入渲染好的 HTML
           (内容已经过 DOMPurify 清洗, 见 utils/markdown.js) -->
      <div class="pane preview">
        <div v-if="!content.trim()" class="preview-empty">这里会实时显示效果</div>
        <div v-else class="md-body" v-html="rendered"></div>
      </div>
    </div>

    <!-- 图片墙: 一次传多张, 点缩略图插入正文 (朋友圈那种感觉) -->
    <div class="img-wall">
      <div class="wall-head">
        <span class="wall-title">🖼 正文图片</span>
        <button type="button" class="wall-pick" :disabled="wallBusy" @click="pickWallImages">
          {{ wallBusy ? '上传中…' : '上传图片' }}
        </button>
        <input
          ref="wallInput"
          type="file"
          multiple
          accept="image/png,image/jpeg,image/gif,image/webp"
          hidden
          @change="onPickWallImages"
        />
        <span class="wall-hint">上传后点缩略图，插入到光标位置</span>
      </div>

      <div v-if="wallImages.length" class="wall-grid">
        <div v-for="(img, i) in wallImages" :key="img.url" class="wall-item">
          <img :src="mediaUrl(img.url)" alt="" @click="insertWallImage(img.url)" />
          <button type="button" class="wall-rm" title="移除" @click="removeWallImage(i)">✕</button>
        </div>
      </div>
      <p v-else class="wall-empty">还没有图片，可以一次选多张上传</p>
    </div>

    <p class="msg" v-if="msg">{{ msg }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getMyArticle, addArticle, updateArticle, getTags, uploadFile } from '../services/authApi.js'
import { renderMarkdown } from '../utils/markdown.js'
import { mediaUrl } from '../utils/media.js'
import { goLogin } from '../utils/auth.js'

const route = useRoute()
const router = useRouter()

const editId = route.params.id ? Number(route.params.id) : null  // 有 id = 编辑, 没 id = 新建
const isEdit = !!editId

const title = ref('')
const content = ref('')
const isPublic = ref(false)
// ★ 付费: priceYuan 是输入框里的"元", 提交时 ×100 转成"分"
const isPaid = ref(false)
const priceYuan = ref('')

// 封面
const coverUrl = ref('')
const coverBusy = ref(false)
const onPickCover = async (e) => {
  const file = e.target.files && e.target.files[0]
  e.target.value = ''
  if (!file) return
  coverBusy.value = true
  try {
    const res = await uploadFile(localStorage.getItem('token'), file)
    if (res.data.error) { msg.value = res.data.error; return }
    coverUrl.value = res.data.url
  } catch (err) {
    msg.value = '封面上传失败：' + err.message
  } finally {
    coverBusy.value = false
  }
}
// ★ 分类: 空字符串 = 未分类
// ⚠️ 这个列表要跟后端 schemas.py 里的 CATEGORIES 一致!
const CATEGORIES = ['前端', '后端', 'AI', '其他']
const category = ref('')
const msg = ref('')
const editorRef = ref(null)

// 预览: 内容一变就重新算 (computed 会自己缓存, 不用手动更新)
const rendered = computed(() => renderMarkdown(content.value))

// ============================================================
// 标签
// ============================================================
const MAX_TAGS = 5                 // 跟后端 MAX_TAGS_PER_ARTICLE 对齐
const tags = ref([])               // 已选的标签名, 如 ["Redis", "缓存"]
const tagInput = ref('')           // 输入框里正在打的字
const suggestions = ref([])        // 联想出来的"已有标签"
const showSuggest = ref(false)
let suggestTimer = null            // 防抖计时器

// 加一个标签 (回车 / 点联想项都会走这里)
const addTag = (raw) => {
  // 前端也做一次规范化: 去首尾空格 + 合并连续空格
  // (后端还会再做一次 —— 前端传的一律不可信)
  const name = String(raw || '').trim().replace(/\s+/g, ' ')
  if (!name) return
  if (tags.value.length >= MAX_TAGS) return
  // 大小写不敏感地判重: 已经有 Redis 了, 就不要再加 redis
  if (tags.value.some(t => t.toLowerCase() === name.toLowerCase())) return
  tags.value.push(name)
}

const addTagFromInput = () => {
  addTag(tagInput.value)
  tagInput.value = ''
  suggestions.value = []
  showSuggest.value = false
}

const pickTag = (name) => {
  addTag(name)
  tagInput.value = ''
  suggestions.value = []
  showSuggest.value = false
}

const removeTag = (name) => {
  tags.value = tags.value.filter(t => t !== name)
}

// 输入时调接口拿"已有标签"做联想
// ★ 防抖: 每打一个字就请求一次太浪费, 停 250ms 才发
const searchTags = () => {
  clearTimeout(suggestTimer)
  suggestTimer = setTimeout(async () => {
    try {
      const res = await getTags(tagInput.value, 8)
      // 已经选过的不再显示
      suggestions.value = (res.data.items || []).filter(
        s => !tags.value.some(t => t.toLowerCase() === s.name.toLowerCase())
      )
      showSuggest.value = suggestions.value.length > 0
    } catch (e) {
      // 联想失败不能打扰用户, 控制台留个记录就行
      console.error('标签联想失败:', e)
    }
  }, 250)
}

// 输入框失焦时收起下拉。
// 延迟 120ms: 给联想项的 mousedown 一点时间先触发
const closeSuggest = () => {
  setTimeout(() => { showSuggest.value = false }, 120)
}

// ============================================================
// 工具栏: 点一下按钮, 帮你在光标处插入 Markdown 语法
// ============================================================
const tools = [
  { label: 'B',    tip: '加粗',   before: '**', after: '**',       ph: '粗体' },
  { label: 'I',    tip: '斜体',   before: '*',  after: '*',        ph: '斜体' },
  { label: 'H2',   tip: '二级标题', before: '## ', after: '',      ph: '标题' },
  { label: 'H3',   tip: '三级标题', before: '### ', after: '',     ph: '标题' },
  { label: '‹›',   tip: '行内代码', before: '`',  after: '`',      ph: 'code' },
  { label: '```',  tip: '代码块', before: '```\n', after: '\n```', ph: '代码' },
  { label: '🔗',   tip: '链接',   before: '[',  after: '](https://)', ph: '链接文字' },
  { label: '≡',    tip: '列表',   before: '- ', after: '',         ph: '列表项' },
  { label: '❝',    tip: '引用',   before: '> ', after: '',         ph: '引用内容' },
]

// 在【光标位置】插入一段文字
//   选中了东西 → 把选中的包起来   (比如选中"你好" 点 B → **你好**)
//   没选中     → 插入占位符, 并把占位符选中 (方便你直接打字替换)
// ---------- 导入 Markdown（md + 本地图片） ----------
const mdInput = ref(null)
const mdImporting = ref(false)
const pickMd = () => { if (mdInput.value) mdInput.value.click() }

const onImportMd = async (e) => {
  const files = Array.from(e.target.files || [])
  e.target.value = ''

  const md = files.find(f => /\.(md|markdown)$/i.test(f.name))
  if (!md) { msg.value = '请选择一个 .md 文件'; return }
  const imgs = files.filter(f => f.type && f.type.startsWith('image/'))

  if (content.value.trim() && !confirm('导入会替换当前正文，继续？')) return

  mdImporting.value = true
  try {
    // ① 图片逐个上传，记下 "文件名 → /uploads/xxx.png"
    const map = {}
    for (const f of imgs) {
      const res = await uploadFile(localStorage.getItem('token'), f)
      if (res.data.error) { msg.value = res.data.error; continue }
      map[f.name] = res.data.url
    }

    // ② 读 md，替换图片路径
    let text = await md.text()
    const missing = []
    text = text.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (all, alt, raw) => {
      const src = raw.trim().replace(/^<|>$/g, '')
      // 网络地址、base64、已经上传过的，原样保留
      if (/^(https?:|data:|\/uploads\/)/i.test(src)) return all
      const name = src.split(/[\\/]/).pop().split(/[?#]/)[0]
      const url = map[name]
      if (!url) { missing.push(name); return all }
      return `![${alt}](${url})`
    })

    content.value = text

    // ③ 标题：没填就用第一行 # 标题，再不行用文件名
    if (!title.value.trim()) {
      const h = text.match(/^#\s+(.+)$/m)
      title.value = h ? h[1].trim() : md.name.replace(/\.(md|markdown)$/i, '')
    }

    msg.value = missing.length
      ? `已导入，但有 ${missing.length} 张图没匹配到：${missing.slice(0, 3).join('、')}…`
      : '已导入'
    setTimeout(() => { msg.value = '' }, 4000)
  } catch (err) {
    msg.value = '导入失败：' + err.message
  } finally {
    mdImporting.value = false
  }
}

// ---------- 文章内插图 ----------
const imgInput = ref(null)
const imgBusy = ref(false)

const pickImage = () => { if (imgInput.value) imgInput.value.click() }

// ---------- 图片墙: 批量上传 + 缩略图 ----------
const wallInput = ref(null)
const wallImages = ref([])      // [{ url: '/uploads/xxx.png' }]
const wallBusy = ref(false)

const pickWallImages = () => { if (wallInput.value) wallInput.value.click() }

const onPickWallImages = async (e) => {
  const files = [...(e.target.files || [])].filter(f => f.type.startsWith('image/'))
  e.target.value = ''
  if (!files.length) return

  const token = localStorage.getItem('token')
  if (!token) { goLogin(router); return }

  wallBusy.value = true
  try {
    for (const f of files) {
      const res = await uploadFile(token, f)
      if (res.data.error) { msg.value = res.data.error; continue }
      wallImages.value.push({ url: res.data.url })
    }
  } catch (err) {
    msg.value = '图片上传失败：' + err.message
  }
  wallBusy.value = false
}

const insertWallImage = (url) => {
  insertAtCursor(`\n![图片](${url})\n`)
}

const removeWallImage = (i) => {
  wallImages.value.splice(i, 1)
}

// ★ 粘贴 / 拖入图片：直接上传并插入 Markdown（CSDN 那种体验）
const uploadAndInsert = async (files) => {
  imgBusy.value = true
  try {
    for (const f of files) {
      const res = await uploadFile(localStorage.getItem('token'), f)
      if (res.data.error) { msg.value = res.data.error; continue }
      insertAtCursor(`
![图片](${res.data.url})
`)
    }
  } catch (err) {
    msg.value = '图片上传失败：' + err.message
  } finally {
    imgBusy.value = false
  }
}

const handlePaste = async (e) => {
  const items = Array.from(e.clipboardData?.items || [])
  const files = items
    .filter(i => i.kind === 'file' && i.type.startsWith('image/'))
    .map(i => i.getAsFile())
    .filter(Boolean)
  if (!files.length) return
  e.preventDefault()
  await uploadAndInsert(files)
}

const handleDragOver = (e) => {
  if (e.dataTransfer && Array.from(e.dataTransfer.items || []).some(i => i.kind === 'file')) {
    e.preventDefault()
  }
}

const handleDrop = async (e) => {
  const files = Array.from(e.dataTransfer?.files || []).filter(f => f.type.startsWith('image/'))
  if (!files.length) return
  e.preventDefault()
  await uploadAndInsert(files)
}

const onPickImage = async (e) => {
  const file = e.target.files && e.target.files[0]
  e.target.value = ''
  if (!file) return

  imgBusy.value = true
  try {
    const res = await uploadFile(localStorage.getItem('token'), file)
    if (res.data.error) { msg.value = res.data.error; return }
    insertAtCursor(`
![图片](${res.data.url})
`)
  } catch (err) {
    msg.value = '图片上传失败：' + err.message
  } finally {
    imgBusy.value = false
  }
}

function insertAtCursor(text) {
  const el = editorRef.value
  if (!el) { content.value += text; return }
  const start = el.selectionStart
  const end = el.selectionEnd
  content.value = content.value.slice(0, start) + text + content.value.slice(end)
  nextTick(() => {
    el.focus()
    el.setSelectionRange(start + text.length, start + text.length)
  })
}

function applyTool(t) {
  const el = editorRef.value
  if (!el) return

  const start = el.selectionStart
  const end = el.selectionEnd
  const selected = content.value.slice(start, end)
  const inner = selected || t.ph        // 没选中就用占位符

  const before = content.value.slice(0, start)
  const after = content.value.slice(end)
  content.value = before + t.before + inner + t.after + after

  // 改完要等 DOM 更新完再动光标 (跟新建收藏夹那里用 nextTick 是一个道理)
  nextTick(() => {
    el.focus()
    // 把刚插入的那段选中 —— 如果是占位符, 你直接打字就替换掉了
    el.setSelectionRange(start + t.before.length, start + t.before.length + inner.length)
  })
}

// ---------- 编辑模式: 先把原文章读进来 ----------
onMounted(async () => {
  const token = localStorage.getItem('token')
  if (!token) { goLogin(router); return }
  if (!editId) return
  try {
    // ★ 用 getMyArticle 而不是 getMyArticles:
    //   前者是单篇详情, 返回里带 tags; 后者是列表, 不带标签
    const res = await getMyArticle(token, editId)
    const a = res.data
    if (!a.error) {
      title.value = a.title
      content.value = a.content
      isPublic.value = a.is_public
      category.value = a.category || ''          // ★ 回填分类
      isPaid.value = !!a.is_paid                 // ★ 回填付费设置
      coverUrl.value = a.cover || ''
      priceYuan.value = a.price ? (a.price / 100).toFixed(2) : ''
      tags.value = (a.tags || []).map(t => t.name)   // ★ 回填标签
    }
  } catch (e) {
    msg.value = '加载失败：' + e.message
  }
})

const goBack = () => router.push('/my-articles')

const handleDone = async () => {
  if (!title.value.trim()) {
    msg.value = '标题不能为空'
    return
  }
  const token = localStorage.getItem('token')
  if (!token) { goLogin(router); return }

  // ★ 付费校验: 勾了付费必须填 > 0 的价格; 前端用"元", 提交时转成"分"
  let priceFen = 0
  if (isPaid.value) {
    const yuan = Number(priceYuan.value)
    if (!yuan || yuan <= 0) {
      msg.value = '付费文章请填写价格'
      return
    }
    priceFen = Math.round(yuan * 100)
  }

  try {
    if (isEdit) {
      await updateArticle(token, editId, title.value.trim(), content.value.trim(), isPublic.value, category.value, tags.value, isPaid.value, priceFen, coverUrl.value)
    } else {
      await addArticle(token, title.value.trim(), content.value.trim(), isPublic.value, category.value, tags.value, isPaid.value, priceFen, coverUrl.value)
    }
    router.push('/my-articles')
  } catch (err) {
    // 401 = token 过期或无效。直接提示"保存失败"会让人以为是代码问题,
    // 这里单独说清楚, 并把人送回登录页。
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      msg.value = '登录已过期，请重新登录'
      setTimeout(() => goLogin(router), 800)
      return
    }
    msg.value = '保存失败：' + (err.response?.data?.error || err.message)
  }
}
</script>

<style scoped>
.write-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px 24px 40px;
  min-height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
}

/* 顶部栏 */
.wbar {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 16px;
}
.back {
  border: none; background: transparent; cursor: pointer;
  font-size: 15px; color: #4b5563; padding: 6px 12px; border-radius: 8px;
}
.back:hover { background: #f0fdfa; color: #14b8a6; }
.wtitle { font-size: 15px; font-weight: 600; color: #1f2937; }
.right { display: flex; align-items: center; gap: 16px; }

.pub {
  display: flex; align-items: center; gap: 6px;
  font-size: 14px; color: #4b5563; cursor: pointer; user-select: none;
}
.pub input { cursor: pointer; accent-color: #14b8a6; }

/* 付费价格输入 */
.price-wrap {
  display: flex; align-items: center; gap: 4px;
  font-size: 14px; color: #0f766e;
}
.price-input {
  width: 76px; padding: 5px 8px;
  border: 1px solid #e6ebf2; border-radius: 8px;
  font-size: 13px; font-family: inherit; outline: none;
}
.price-input:focus { border-color: #14b8a6; }

/* 分类下拉 */
.cat-sel {
  padding: 6px 10px; border: 1px solid #e6ebf2; border-radius: 8px;
  background: #fff; color: #4b5563; font-size: 13px; cursor: pointer;
  outline: none; font-family: inherit;
}
.cat-sel:focus { border-color: #14b8a6; }

.done {
  padding: 8px 24px; border: none; border-radius: 8px; cursor: pointer;
  background: #14b8a6; color: #fff; font-size: 14px; font-weight: 600;
}
.done:hover { background: #0d9488; }

/* 标题输入 */
.title-input {
  width: 100%; border: none; outline: none; background: transparent;
  font-size: 26px; font-weight: 700; color: #1f2937;
  padding: 8px 4px 16px; border-bottom: 1px solid #eef1f6;
}
.title-input::placeholder { color: #c3ccd8; }

/* ===== 标签 ===== */
.tag-row {
  position: relative;              /* 联想下拉要绝对定位在它下面 */
  display: flex; align-items: center; gap: 10px;
  padding: 12px 4px 10px;
}
.tag-label {
  flex-shrink: 0; font-size: 13px; color: #6b7280;
}
.tag-box {
  flex: 1; display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
  min-height: 34px; padding: 4px 6px;
  border: 1px solid #e6ebf2; border-radius: 10px;
  background: #fff; transition: border-color 0.15s;
}
.tag-box:focus-within { border-color: #14b8a6; }

.tag-chip {
  display: inline-flex; align-items: center; gap: 4px;
  padding: 3px 8px; border-radius: 7px;
  background: #ccfbf1; color: #0f766e;
  font-size: 12px; line-height: 1.5;
}
.tag-x {
  border: none; background: transparent; cursor: pointer;
  color: #0f766e; font-size: 14px; line-height: 1;
  padding: 0 1px; opacity: 0.6;
}
.tag-x:hover { opacity: 1; }

.tag-input {
  flex: 1; min-width: 140px;
  border: none; outline: none; background: transparent;
  font-size: 13px; color: #1f2937; padding: 4px 2px;
}
.tag-input::placeholder { color: #b6c0cc; }
.tag-input:disabled { cursor: not-allowed; }

/* 联想下拉 */
.tag-suggest {
  position: absolute; left: 52px; right: 4px; top: 100%;
  z-index: 30;
  background: #fff; border: 1px solid #e6ebf2; border-radius: 10px;
  box-shadow: 0 10px 28px rgba(20, 184, 166, 0.14);
  overflow: hidden;
}
.sug-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; font-size: 13px; color: #374151;
  cursor: pointer;
}
.sug-item:hover { background: #f0fdfa; color: #0f766e; }
.sug-count { font-size: 11px; color: #9aa5b1; }

/* 工具栏 */
.toolbar {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 0 12px;
}
.toolbar button {
  min-width: 34px; height: 30px; padding: 0 9px;
  border: 1px solid #eef1f6; border-radius: 7px;
  background: #fff; color: #4b5563;
  font-size: 13px; cursor: pointer; transition: all 0.15s;
}
.toolbar button:hover { border-color: #14b8a6; color: #14b8a6; background: #f0fdfa; }
.toolbar .tip { margin-left: auto; font-size: 12px; color: #a8b2c1; }

/* 左右分栏 */
.panes {
  flex: 1; display: flex; gap: 16px;
  min-height: 460px;
}
.pane {
  flex: 1; min-width: 0;
  border: 1px solid #eef1f6; border-radius: 14px;
  background: #fff; box-shadow: 0 2px 12px rgba(20, 184, 166, 0.06);
  padding: 18px 20px;
  overflow-y: auto;
}

.editor {
  font-size: 15px; line-height: 1.85; color: #1f2937;
  resize: none; outline: none; font-family: inherit;
}
.editor:focus { border-color: #99f6e4; }

.preview { background: #fcfefe; }
.preview-empty {
  color: #c3ccd8; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
  height: 100%;
}

.msg { text-align: center; color: #e74c3c; margin-top: 12px; }

/* ===== 正文图片墙 ===== */
.img-wall {
  margin-top: 16px;
  padding: 14px 16px;
  border: 1px solid #eef1f6; border-radius: 14px;
  background: #fff;
}
.wall-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.wall-title { font-size: 13px; font-weight: 600; color: #374151; }
.wall-pick {
  padding: 5px 12px; border-radius: 14px;
  border: 1px solid #14b8a6; background: #fff; color: #0f766e;
  font-size: 12px; cursor: pointer;
}
.wall-pick:hover { background: #f0fdfa; }
.wall-pick:disabled { opacity: 0.6; cursor: not-allowed; }
.wall-hint { font-size: 11px; color: #9aa5b1; }
.wall-grid {
  display: grid; grid-template-columns: repeat(auto-fill, 86px);
  gap: 10px; margin-top: 12px;
}
.wall-item { position: relative; width: 86px; height: 86px; }
.wall-item img {
  width: 100%; height: 100%; object-fit: cover;
  border-radius: 10px; border: 1px solid #eef1f6;
  cursor: pointer; transition: transform 0.15s;
}
.wall-item img:hover { transform: scale(1.04); border-color: #14b8a6; }
.wall-rm {
  position: absolute; top: -6px; right: -6px;
  width: 20px; height: 20px; border-radius: 50%;
  border: none; background: #e74c3c; color: #fff;
  font-size: 11px; line-height: 20px; cursor: pointer; padding: 0;
}
.wall-empty { font-size: 12px; color: #b6c0cc; margin-top: 10px; }

/* ===== 封面 ===== */
.cover-row { display: flex; align-items: center; gap: 16px; margin: 14px 0 4px; }
.cover-box {
  width: 180px; height: 100px; border-radius: 10px; overflow: hidden;
  background: #f2fbf9; border: 1px dashed #99f6e4;
  display: flex; align-items: center; justify-content: center;
}
.cover-box img { width: 100%; height: 100%; object-fit: cover; }
.cover-tip { font-size: 12px; color: #9aa5b1; }
.cover-actions { display: flex; flex-direction: column; gap: 6px; }
.cover-pick {
  display: inline-block; padding: 7px 14px;
  border: 1px solid #14b8a6; border-radius: 9px;
  color: #0f766e; font-size: 13px; cursor: pointer; text-align: center;
}
.cover-pick:hover { background: #f0fdfa; }
.cover-rm {
  border: none; background: none; color: #9aa5b1;
  font-size: 12px; cursor: pointer; text-align: left; padding: 0;
}
.cover-rm:hover { color: #e74c3c; }
.cover-hint { font-size: 11px; color: #b6c0cc; }

/* ---- 手机: 编辑/预览上下排, 工具栏换行 ---- */
@media (max-width: 720px) {
  .panes { flex-direction: column; min-height: 0; gap: 12px; }
  .pane { min-height: 260px; }
  .toolbar { flex-wrap: wrap; }
  .toolbar .tip { display: none; }
  .cover-row { flex-wrap: wrap; }
  .cover-box { width: 140px; height: 80px; }
  .wall-grid { grid-template-columns: repeat(auto-fill, 72px); }
  .wall-item { width: 72px; height: 72px; }
}
</style>
