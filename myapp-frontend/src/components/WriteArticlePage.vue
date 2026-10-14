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
        <button class="done" @click="handleDone">完成</button>
      </div>
    </header>

    <!-- 标题 -->
    <input class="title-input" v-model="title" placeholder="请输入标题…" />

    <!-- 工具栏 -->
    <div class="toolbar">
      <button v-for="t in tools" :key="t.label" :title="t.tip" @click="applyTool(t)">
        {{ t.label }}
      </button>
      <span class="tip">支持 Markdown · 右边实时预览</span>
    </div>

    <!-- 左右分栏: 编辑 | 预览 -->
    <div class="panes">
      <textarea
        ref="editorRef"
        class="pane editor"
        v-model="content"
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

    <p class="msg" v-if="msg">{{ msg }}</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getMyArticles, addArticle, updateArticle } from '../services/authApi.js'
import { renderMarkdown } from '../utils/markdown.js'

const route = useRoute()
const router = useRouter()

const editId = route.params.id ? Number(route.params.id) : null  // 有 id = 编辑, 没 id = 新建
const isEdit = !!editId

const title = ref('')
const content = ref('')
const isPublic = ref(false)
// ★ 分类: 空字符串 = 未分类
// ⚠️ 这个列表要跟后端 schemas.py 里的 CATEGORIES 一致!
const CATEGORIES = ['前端', '后端', 'AI', '其他']
const category = ref('')
const msg = ref('')
const editorRef = ref(null)

// 预览: 内容一变就重新算 (computed 会自己缓存, 不用手动更新)
const rendered = computed(() => renderMarkdown(content.value))

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
  if (!token) { router.push('/login'); return }
  if (!editId) return
  try {
    const res = await getMyArticles(token)
    const a = res.data.find(x => x.id === editId)
    if (a) {
      title.value = a.title
      content.value = a.content
      isPublic.value = a.is_public
      category.value = a.category || ''          // ★ 回填分类
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
  if (!token) { router.push('/login'); return }

  try {
    if (isEdit) {
      await updateArticle(token, editId, title.value.trim(), content.value.trim(), isPublic.value, category.value)
    } else {
      await addArticle(token, title.value.trim(), content.value.trim(), isPublic.value, category.value)
    }
    router.push('/my-articles')
  } catch (err) {
    msg.value = '保存失败：' + err.message
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
</style>
