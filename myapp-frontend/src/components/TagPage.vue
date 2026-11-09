<template>
  <div class="page tag-page">
    <!-- 头部 -->
    <div class="tag-header">
      <div>
        <h2># {{ tagName }}</h2>
        <p class="tag-sub" v-if="tag">共 {{ total }} 篇公开文章</p>
        <p class="tag-sub" v-else-if="!loading">这个标签下还没有文章</p>
      </div>
      <button class="refresh" :disabled="refreshing" @click="load(true)">
        {{ refreshing ? '刷新中…' : '🔄 刷新' }}
      </button>
    </div>

    <p v-if="loading" class="tag-tip">加载中...</p>
    <p v-else-if="items.length === 0" class="tag-tip">
      还没有公开文章用过这个标签～
      <br />
      <router-link to="/home" class="back-link">回首页看看</router-link>
    </p>

    <!-- 文章列表 -->
    <div v-else class="art-list">
      <div
        v-for="a in items" :key="a.id"
        class="art-row card hoverable"
        @click="$router.push(`/article/${a.id}`)"
      >
        <div class="art-cover" :class="coverOf(a.id)">
          <img v-if="a.cover" :src="mediaUrl(a.cover)" alt="" class="cover-img" />
          <IconDoc v-else />
        </div>
        <div class="art-body">
          <p class="art-title">
            <span v-if="a.category" class="art-cat">{{ a.category }}</span>
            {{ a.title }}
          </p>
          <p class="art-sum">{{ stripMarkdown(a.content) || '（无内容）' }}</p>
          <div class="art-meta">
            <span
              class="author"
              @click.stop="$router.push(`/user/${a.user_id}`)"
            >{{ a.author }}</span>
            <span class="sep">·</span>
            <span>👍 {{ a.like_count || 0 }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div v-if="pages > 1" class="pager">
      <button class="pg-btn" :disabled="page === 1" @click="goPage(page - 1)">‹ 上一页</button>
      <button
        v-for="p in pageList" :key="p"
        class="pg-num" :class="{ on: p === page }"
        @click="goPage(p)"
      >{{ p }}</button>
      <button class="pg-btn" :disabled="page === pages" @click="goPage(page + 1)">下一页 ›</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getArticlesByTag } from '../services/authApi.js'
import { mediaUrl } from '../utils/media.js'
import { stripMarkdown } from '../utils/markdown.js'

const route = useRoute()

// 路由参数永远是字符串; 中文和空格已经在跳转时 encode 过了
const tagName = computed(() => route.params.name || '')

const items = ref([])
const tag = ref(null)          // 后端返回的标签信息, null = 这个标签不存在
const total = ref(0)
const pages = ref(0)
const page = ref(1)
const loading = ref(true)
const refreshing = ref(false)

const covers = ['cover-1', 'cover-2', 'cover-3', 'cover-4', 'cover-5', 'cover-6']
const coverOf = (id) => covers[id % covers.length]

const pageList = computed(() => Array.from({ length: pages.value }, (_, i) => i + 1))

const load = async (isRefresh = false) => {
  if (isRefresh) refreshing.value = true
  else loading.value = true
  try {
    const res = await getArticlesByTag(tagName.value, page.value, 10)
    items.value = res.data.items || []
    tag.value = res.data.tag || null
    total.value = res.data.total || 0
    pages.value = res.data.pages || 0
  } catch (e) {
    console.error('标签页加载失败:', e)
    items.value = []
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

const goPage = (p) => {
  if (p < 1 || p > pages.value) return
  page.value = p
  load()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onMounted(load)

// 从 /tag/A 点到 /tag/B 时组件不会重建, 所以要看参数变化
watch(() => route.params.name, () => {
  page.value = 1
  load()
})
</script>

<style scoped>
.tag-page { max-width: 1080px; }

.tag-header {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: 12px; margin: 6px 0 18px;
}
.tag-header h2 {
  font-size: 24px; font-weight: 800; color: #1f2937;
  letter-spacing: 0.5px;
}
.tag-sub { font-size: 12px; color: #9aa5b1; margin-top: 6px; }

.refresh {
  flex-shrink: 0;
  padding: 7px 14px; border: 1px solid #e6ebf2; border-radius: 9px;
  background: #fff; color: #64748b; font-size: 13px;
  font-family: inherit; cursor: pointer; transition: all 0.15s;
}
.refresh:hover:not(:disabled) { border-color: #14b8a6; color: #0f766e; }
.refresh:disabled { opacity: 0.6; cursor: default; }

.tag-tip {
  text-align: center; color: #9aa5b1; font-size: 13px;
  padding: 50px 0; line-height: 1.9;
}
.back-link { color: #14b8a6; text-decoration: none; }
.back-link:hover { text-decoration: underline; }

/* 列表 */
.art-list { display: flex; flex-direction: column; gap: 12px; }

.art-row {
  display: flex; align-items: stretch; gap: 16px;
  padding: 14px; cursor: pointer;
}

.art-cover {
  width: 96px; height: 72px; flex-shrink: 0;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: rgba(15, 118, 110, 0.42);
}
.art-cover :deep(svg) { width: 100%; height: 100%; padding: 22%; }

.art-body { flex: 1; min-width: 0; }

.art-title {
  font-size: 15px; font-weight: 600; color: #1f2937;
  line-height: 1.5; margin-bottom: 5px;
  overflow-wrap: anywhere;
}
.art-cat {
  display: inline-block; font-size: 11px; font-weight: 500;
  color: #0f766e; background: #ccfbf1;
  border-radius: 5px; padding: 1px 6px; margin-right: 6px;
  vertical-align: 1px;
}
.art-sum {
  font-size: 12px; color: #9aa5b1; line-height: 1.6;
  overflow: hidden; text-overflow: ellipsis;
  display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical;
  overflow-wrap: anywhere;
}
.art-meta {
  margin-top: 8px; font-size: 12px; color: #9aa5b1;
  display: flex; align-items: center; gap: 6px;
}
.author { color: #14b8a6; cursor: pointer; }
.author:hover { text-decoration: underline; }
.sep { color: #d1d8e0; }

/* 分页 */
.pager {
  display: flex; justify-content: center; align-items: center;
  gap: 6px; margin-top: 28px; flex-wrap: wrap;
}
.pg-btn, .pg-num {
  border: 1px solid #e6ebf2; background: #fff; color: #4b5563;
  border-radius: 9px; padding: 7px 12px; font-size: 13px;
  cursor: pointer; transition: all 0.15s;
}
.pg-btn:disabled { opacity: 0.45; cursor: default; }
.pg-num.on { background: #14b8a6; border-color: #14b8a6; color: #fff; }
.pg-num:hover:not(.on) { border-color: #14b8a6; color: #0f766e; }

.cover-img { width: 100%; height: 100%; object-fit: cover; display: block; }
</style>
