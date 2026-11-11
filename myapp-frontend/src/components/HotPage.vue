<template>
  <div class="page hot-page">
    <div class="hot-header">
      <div>
        <h2>🔥 全站热榜</h2>
        <p class="hot-sub">按「热度 ÷ 时间衰减」排序 · 新文章也有机会上榜</p>
      </div>
      <!-- 刷新按钮: 进页面只拉一次, 想更新就点它 -->
      <button class="refresh" :disabled="refreshing" @click="load(true)">
        {{ refreshing ? '刷新中…' : '🔄 刷新' }}
      </button>
    </div>

    <p v-if="loading" class="hot-tip">加载中...</p>
    <p v-else-if="items.length === 0" class="hot-tip">
      还没有数据～ 去首页逛逛文章，或者发一篇吧
    </p>

    <div v-else class="hot-list">
      <div
        v-for="(a, i) in items"
        :key="a.id"
        class="hot-row card hoverable"
        @click="$router.push(`/article/${a.id}`)"
      >
        <!-- 名次徽章: 前三名有颜色 -->
        <span class="rank" :class="`r${i + 1}`">{{ i + 1 }}</span>

        <div class="hot-body">
          <p class="hot-title">
            <span v-if="a.category" class="hot-cat">{{ a.category }}</span>
            {{ a.title }}
          </p>
          <p class="hot-sum">{{ stripMarkdown(a.content) || '（无内容）' }}</p>
          <div class="hot-meta">
            <!-- 作者名可点, .stop 防止触发外层的"进文章详情" -->
            <span class="author" @click.stop="$router.push(`/user/${a.user_id}`)">
              {{ a.author }}
            </span>
            <span class="sep">·</span>
            <span>👍 {{ a.like_count }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getHotArticles } from '../services/authApi.js'
import { stripMarkdown } from '../utils/markdown.js'

const items = ref([])
const loading = ref(true)        // 首次加载 (整页显示"加载中")
const refreshing = ref(false)    // 手动刷新 (只把按钮变灰)

// ★ 抽成函数, 这样"进页面"和"点刷新"共用同一段逻辑
//   为什么用参数区分?
//     首次加载 → 整页显示"加载中..."
//     点刷新   → 列表不动, 只把按钮变成"刷新中…" (体验更顺)
const load = async (isRefresh = false) => {
  if (isRefresh) refreshing.value = true
  try {
    // 拿前 20 名 (后端最多给 50)
    const res = await getHotArticles(20)
    items.value = res.data.items || []
  } catch (e) {
    // 热榜挂了不能白屏, 控制台留个记录就行
    console.error('热榜加载失败:', e)
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

onMounted(() => load())
</script>

<style scoped>
.hot-page {
  max-width: 1080px;
}

.hot-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin: 6px 0 18px;
}
.hot-header h2 {
  font-size: 22px;
  color: #1f2937;
  margin-bottom: 6px;
}
.hot-sub {
  font-size: 12px;
  color: #9aa5b1;
}

/* 刷新按钮 */
.refresh {
  flex-shrink: 0;
  padding: 7px 14px;
  border: 1px solid #e6ebf2;
  border-radius: 9px;
  background: #fff;
  color: #64748b;
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: all .15s;
}
.refresh:hover:not(:disabled) {
  border-color: #14b8a6;
  color: #0f766e;
}
.refresh:disabled {
  opacity: .6;
  cursor: default;
}

.hot-tip {
  text-align: center;
  color: #9aa5b1;
  font-size: 13px;
  padding: 40px 0;
}

.hot-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hot-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  cursor: pointer;
}

/* ---- 名次徽章 ---- */
.rank {
  width: 30px;
  height: 30px;
  flex-shrink: 0;
  border-radius: 9px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  background: #f1f5f9;
  color: #64748b;
}
/* 前三名 */
.rank.r1 { background: linear-gradient(135deg, #fbbf24, #f59e0b); color: #fff; }
.rank.r2 { background: linear-gradient(135deg, #cbd5e1, #94a3b8); color: #fff; }
.rank.r3 { background: linear-gradient(135deg, #fdba74, #ea580c); color: #fff; }

/* ---- 中间正文 ---- */
.hot-body {
  flex: 1;
  min-width: 0;              /* ★ 没有它, flex 里的长文字会把布局撑破 */
}

.hot-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 4px;
  overflow-wrap: anywhere;
}

.hot-cat {
  display: inline-block;
  font-size: 11px;
  font-weight: 500;
  color: #0f766e;
  background: #ccfbf1;
  border-radius: 5px;
  padding: 1px 6px;
  margin-right: 6px;
  vertical-align: 1px;
}

.hot-sum {
  font-size: 12px;
  color: #9aa5b1;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow-wrap: anywhere;
}

.hot-meta {
  margin-top: 6px;
  font-size: 12px;
  color: #9aa5b1;
  display: flex;
  align-items: center;
  gap: 6px;
}
.hot-meta .author {
  color: #14b8a6;
  cursor: pointer;
}
.hot-meta .author:hover {
  text-decoration: underline;
}
</style>
