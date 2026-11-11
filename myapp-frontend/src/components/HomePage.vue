<template>
  <div class="page">
    <!-- 顶部: 搜索 + 分类 -->
    <div class="topbar">
      <div class="search-wrap">
        <div class="search">
          <span class="s-ico">🔍</span>
          <input
            v-model="keyword"
            placeholder="搜标题…（回车搜索）"
            @focus="onFocus"
            @keydown.enter.prevent="doSearch"
            @blur="onBlur"
          />
          <span v-if="keyword" class="s-clear" @click="clearSearch">✕</span>
        </div>

        <!-- ★ 输入时的匹配建议：点一条就用它的标题去搜（B 站那种） -->
        <div v-if="showSuggest && suggestions.length" class="suggest">
          <div
            v-for="s in suggestions" :key="s.id"
            class="sug-item"
            @mousedown.prevent="pickSuggest(s)"
          >
            <span class="sug-title">{{ s.title }}</span>
            <span class="sug-author">{{ s.author }}</span>
          </div>
        </div>
      </div>
      <div class="cats">
        <!-- ★ 点一下 → 换分类 → 重新拉第一页 -->
        <span
          v-for="c in cats" :key="c.label"
          class="cat" :class="{ active: c.label === activeCat }"
          @click="switchCat(c.label)"
        >{{ c.label }}</span>
      </div>
    </div>

    <!-- 本站介绍: 第一次来的人先知道这里是干什么的 -->
    <section class="intro card">
      <div class="intro-text">
        <h1>技术笔记</h1>
        <p>记录后端开发、数据库、消息队列和 AI 的学习与实践。可以读文章、收藏、关注作者，也可以直接问站内 AI 助手。</p>
        <div class="intro-feats">
          <span>📚 技术文章</span>
          <span>🔥 热榜</span>
          <span>✨ AI 助手</span>
        </div>
      </div>
      <div class="intro-mark">✍️</div>
    </section>

    <!-- 轮播 banner -->
    <div class="banner" @mouseenter="stopAuto" @mouseleave="startAuto">
      <!-- 三张幻灯片叠在一起, 靠 opacity 切换 (不是靠 v-if 增删) -->
      <div
        v-for="(b, i) in banners" :key="i"
        class="slide"
        :class="[b.cover, { on: i === current, linkable: !!b.link }]"
        @click="openBanner(b)"
      >
        <!-- 背景图 (加载失败就藏起来, 露出底下的兜底渐变) -->
        <img class="slide-img" :src="b.img" alt="" @error="onImgError" />

        <!-- 压一层【左深右浅】的暗色遮罩:
             文字在左边, 所以左边压暗一点保证看得清; 右边留亮, 免得图全糊了 -->
        <div class="slide-mask"></div>

        <div class="banner-text">
          <h2>{{ b.title }}</h2>
          <p>{{ b.sub }}</p>
        </div>
      </div>

      <!-- 小圆点 (点的时候 .stop 一下, 别触发幻灯片的跳转) -->
      <div class="dots">
        <span
          v-for="(b, i) in banners" :key="i"
          class="dot" :class="{ active: i === current }"
          @click.stop="goSlide(i)"
        ></span>
      </div>
    </div>

    <!-- 主内容 + 侧栏 -->
    <div class="layout">
      <main class="main">
        <!-- 文章卡片 -->
        <h3 class="section-title">
          最新文章
          <span v-if="total" class="s-count">共 {{ total }} 篇</span>
        </h3>

        <p v-if="loading" class="loading">加载中...</p>

        <template v-else>
          <div class="grid">
            <div
              v-for="(a, i) in articles" :key="a.id"
              class="art-card card hoverable"
              @click="goDetail(a.id)"
            >
              <div class="art-cover" :class="coverOf(i)">
                <img v-if="a.cover" :src="mediaUrl(a.cover)" alt="" class="cover-img" />
                <span v-else class="art-emoji"><IconDoc /></span>
              </div>
              <div class="art-info">
                <p class="art-title">
                  <!-- ★ 分类小徽章 (没分类的不显示) -->
                  <span v-if="a.category" class="art-cat">{{ a.category }}</span>
                  {{ a.title }}
                </p>
                <!-- 摘要要把 Markdown 符号去掉, 不然卡片上会显示 "## **标题**" 这种源码 -->
                <p class="art-sum">{{ stripMarkdown(a.content) || '（无内容）' }}</p>
                <div class="art-meta">
                  <span class="avatar" :class="coverOf(i)"><IconUser /></span>
                  <!-- ★ 作者名可点 → 跳个人主页。.stop 防止同时触发外面卡片的"进文章详情" -->
                  <span class="author clickable" @click.stop="$router.push(`/user/${a.user_id}`)">
                    {{ a.author }}
                  </span>
                  <!-- ★ 点赞量: margin-left:auto 推到这一行最右边 -->
                  <span class="art-like">👍 {{ a.like_count || 0 }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 一篇都没有时: 分两种说法, 别混 -->
          <p v-if="articles.length === 0" class="empty">
            {{ keyword
                ? `没有找到标题含「${keyword}」的文章`
                : '还没有公开文章～ 去「我的」→「我的文章」写一篇并「上架」吧' }}
          </p>

          <!-- 分页条 (只有一页时就不显示了) -->
          <div v-if="pages > 1" class="pager">
            <button class="pg-btn" :disabled="page === 1" @click="goPage(page - 1)">‹ 上一页</button>

            <button
              v-for="p in pageList" :key="p"
              class="pg-num" :class="{ on: p === page }"
              @click="goPage(p)"
            >{{ p }}</button>

            <button class="pg-btn" :disabled="page === pages" @click="goPage(page + 1)">下一页 ›</button>
          </div>
        </template>
      </main>

      <!-- ================= 右侧栏 ================= -->
      <aside class="side">
        <!-- 热门文章 -->
        <section class="side-card">
          <header class="side-head">
            <span class="side-title"><span class="side-ico">🔥</span>热门文章</span>
            <router-link to="/hot" class="side-more">全部 ›</router-link>
          </header>
          <ol v-if="hotArticles.length" class="hot-list">
            <li
              v-for="(h, i) in hotArticles" :key="h.id"
              class="hot-item" @click="goDetail(h.id)"
            >
              <span class="rank" :class="`r${i + 1}`">{{ i + 1 }}</span>
              <div class="hot-body">
                <p class="hot-title">{{ h.title }}</p>
                <p class="hot-meta">
                  <span class="hot-author">{{ h.author }}</span>
                  <span v-if="h.heat" class="hot-heat">🔥 {{ h.heat }}</span>
                </p>
              </div>
            </li>
          </ol>
          <p v-else class="side-empty">暂无热门文章</p>
        </section>

        <!-- 热门标签 -->
        <section class="side-card">
          <header class="side-head">
            <span class="side-title"><span class="side-ico">🏷️</span>热门标签</span>
          </header>
          <div v-if="hotTags.length" class="tag-cloud">
            <router-link
              v-for="t in hotTags" :key="t.id"
              :to="`/tag/${encodeURIComponent(t.name)}`"
              class="tag-chip"
            >
              {{ t.name }}<em v-if="t.count">{{ t.count }}</em>
            </router-link>
          </div>
          <p v-else class="side-empty">还没有标签</p>
        </section>

        <!-- 创作入口 -->
        <section class="side-card about">
          <h4>✍️ 开始你的创作</h4>
          <p>记录技术成长，分享所思所得。支持 Markdown、代码高亮、图片上传。</p>
          <router-link to="/write" class="about-btn">写文章 →</router-link>
          <div class="about-stats">
            <div><b>{{ total }}</b><span>公开文章</span></div>
            <div><b>{{ hotTags.length }}</b><span>热门标签</span></div>
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { getPublicArticles, getSuggestions, getHotArticles, getTags } from '../services/authApi.js'
import { mediaUrl } from '../utils/media.js'
import { stripMarkdown } from '../utils/markdown.js'

const router = useRouter()

// ---- 搜索 + 分类 ----
const keyword = ref('')
const suggestions = ref([])     // 输入时的匹配建议（文章列表）
const showSuggest = ref(false)  // 建议下拉开不开
let skipSuggest = false         // 点了建议后，别再弹一次建议
// ★ 分类 tab
//    label = 显示的字的
//    value = 发给后端的值 (空字符串 = 不筛, 显示全部)
//    "全部"那个 tab 的 value 是空 —— 后端看到空就不加过滤条件
//
// ⚠️ 这个列表要跟后端的 schemas.py 里的 CATEGORIES 一致。加了分类两边都要改!
const cats = [
  { label: '全部', value: '' },
  { label: '前端', value: '前端' },
  { label: '后端', value: '后端' },
  { label: 'AI', value: 'AI' },
  { label: '其他', value: '其他' },
]
const activeCat = ref('全部')

// ---- 轮播图 ----
// 每张有两样东西:
//   img   = 背景图 (放在 public/banners/ 里, 用 /banners/xxx.jpg 引用)
//   cover = 兜底渐变 (图加载失败时露出来, 不至于是一片白)
//
// ★ public 文件夹的特殊之处: 里面的东西会被【原样】搬到网站根目录。
//   所以 public/banners/code.jpg → 访问地址就是 /banners/code.jpg (路径里没有 public)
const banners = [
  {
    title: '欢迎来到我的文章站', sub: '记录 · 分享 · 交流',
    img: '/banners/welcome.jpg', cover: 'bn-1', link: '',
  },
  {
    title: '小林coding', sub: '图解计算机基础 · 面试八股',
    img: '/banners/ai.jpg', cover: 'bn-2', link: 'https://xiaolincoding.com/',
  },
  {
    title: 'LeetCode', sub: '刷题 · 算法 · 面试',
    img: '/banners/code.jpg', cover: 'bn-3', link: 'https://leetcode.cn/',
  },
]

// 图片加载失败时, 把 <img> 藏起来 → 底下的兜底渐变就露出来了
const onImgError = (e) => { e.target.style.display = 'none' }

const current = ref(0)            // 现在是第几张
let slideTimer = null             // 自动轮播的计时器

const nextSlide = () => {
  current.value = (current.value + 1) % banners.length    // 到最后一张就绕回第 0 张
}

const startAuto = () => {
  stopAuto()                      // 先清掉旧的, 免得开两个计时器 (越开越快)
  slideTimer = setInterval(nextSlide, 4000)               // 每 4 秒翻一张
}

const stopAuto = () => {
  if (slideTimer) { clearInterval(slideTimer); slideTimer = null }
}

const goSlide = (i) => {
  current.value = i
  startAuto()                     // 手动点了之后重新计时 (不然可能刚点完就自动翻走)
}

// 点幻灯片本体: 有链接才跳, 没有就啥也不做
const openBanner = (b) => {
  if (b.link) window.open(b.link, '_blank')
}

// ---- 列表 + 分页 ----
// ★ 注意: articles 现在存的是【当前这一页】, 不是全部了
const articles = ref([])
const page = ref(1)          // 当前第几页
const pages = ref(0)         // 一共几页 (后端算好告诉我们的)
const total = ref(0)         // 一共几篇
const size = 12              // 每页几篇 (4 列 × 3 行)
const loading = ref(false)

// 页码按钮列表: 有几页就显示几个
// (页数特别多时要改成"只显示当前页附近几个 + 省略号", 这项目暂时用不上)
const pageList = computed(() => Array.from({ length: pages.value }, (_, i) => i + 1))

// ---- 侧栏: 热门文章 + 热门标签 ----
// 这两个数据跟"最新文章列表"互不影响, 各拉各的;
// 用 Promise.all 并行发, 不用一个等一个。
const hotArticles = ref([])
const hotTags = ref([])

const loadSidebar = async () => {
  try {
    const [hotRes, tagRes] = await Promise.all([
      getHotArticles(8),
      getTags('', 12),
    ])
    hotArticles.value = hotRes.data.items || []
    hotTags.value = tagRes.data.items || []
  } catch (e) {
    console.error('侧栏数据加载失败', e)
  }
}

// ---- 封面装饰 (纯样式, 没有真封面图) ----
const covers = ['cover-1', 'cover-2', 'cover-3', 'cover-4', 'cover-5', 'cover-6']
const coverOf = (i) => covers[i % covers.length]

const goDetail = (id) => router.push(`/article/${id}`)

// ---------- 拉数据: 只拉当前这一页 ----------
const load = async () => {
  loading.value = true
  try {
    // ★ 把当前分类也传过去 (空字符串 = 不筛)
    const cat = cats.find((c) => c.label === activeCat.value)?.value ?? ''
    const res = await getPublicArticles(page.value, size, keyword.value, cat)
    // ⚠️ 后端现在返回的是一个【对象】, 不是数组了:
    //      {items: [...], total: 12, page: 1, size: 8, pages: 2}
    articles.value = res.data.items        // ← 拿的是 .items
    total.value = res.data.total
    pages.value = res.data.pages
  } catch (e) {
    console.error('获取公开文章失败', e)
  }
  loading.value = false
}

// ---------- 点分类 tab ----------
const switchCat = (label) => {
  if (activeCat.value === label) return
  activeCat.value = label
  page.value = 1        // ★ 换分类要回到第 1 页 (不然可能停在空的第 3 页)
  load()
}

// ---------- 搜索 ----------
// 输入时只拉"建议列表"（防抖 250ms），不直接换结果；
// 回车 / 点建议 / 点 ✕ 才真正搜索。
let searchTimer = null
watch(keyword, () => {
  clearTimeout(searchTimer)

  if (skipSuggest) { skipSuggest = false; return }

  const kw = keyword.value.trim()
  if (!kw) {
    suggestions.value = []
    showSuggest.value = false
    return
  }

  searchTimer = setTimeout(async () => {
    try {
      // ★ 只读 Redis 的标题索引，不查 MySQL
      const res = await getSuggestions(kw, 6)
      suggestions.value = res.data.items || []
      showSuggest.value = suggestions.value.length > 0
    } catch (e) {
      suggestions.value = []
    }
  }, 250)
})

// 回车搜索
const doSearch = () => {
  showSuggest.value = false
  page.value = 1
  load()
}

// 点一条建议：直接用它的标题去搜
const pickSuggest = (s) => {
  skipSuggest = true            // 避免 keyword 变化又弹一次建议
  keyword.value = s.title
  showSuggest.value = false
  page.value = 1
  load()
}

// 点 ✕：清空并恢复全部
const clearSearch = () => {
  keyword.value = ''
  suggestions.value = []
  showSuggest.value = false
  page.value = 1
  load()
}

const onFocus = () => {
  if (keyword.value.trim() && suggestions.value.length) showSuggest.value = true
}
const onBlur = () => {
  // 延迟关，不然点建议时下拉先消失，点不到
  setTimeout(() => { showSuggest.value = false }, 150)
}

// ---------- 翻页 ----------
const goPage = (p) => {
  if (p < 1 || p > pages.value || p === page.value) return   // 越界或没变, 不管
  page.value = p
  load()
  window.scrollTo({ top: 0, behavior: 'smooth' })   // 翻页后回到顶部, 不然还停在页脚
}

onMounted(() => {
  load()
  loadSidebar()      // 侧栏: 热门文章 + 标签
  startAuto()        // 开始自动轮播
})

// ★ 离开这个页面时, 【必须】把计时器清掉
//   不清的话: 计时器会一直在后台跑 (切走了还在翻), 而且你切回来又会新开一个,
//   来回几次就有好几个计时器同时跑 —— 轮播会变得飞快。这是个很常见的坑。
onUnmounted(stopAuto)
</script>

<style scoped>
/* 顶部: 搜索 + 分类 */
.topbar {
  display: flex; align-items: center; gap: 30px;
  background: #fff; border-radius: 14px; padding: 14px 20px;
  box-shadow: 0 2px 10px rgba(20, 184, 166, 0.06);
  margin-bottom: 20px;
}
/* 本站介绍 */
.intro {
  display: flex; align-items: center; justify-content: space-between; gap: 20px;
  padding: 22px 26px; margin-bottom: 18px;
  background: linear-gradient(135deg, #f0fdfa 0%, #ffffff 65%);
  border: 1px solid rgba(20, 184, 166, 0.12);
}
.intro h1 { font-size: 22px; color: #0f766e; margin-bottom: 8px; }
.intro p { font-size: 13.5px; color: #4b5563; line-height: 1.7; max-width: 760px; }
.intro-feats { display: flex; gap: 10px; margin-top: 12px; flex-wrap: wrap; }
.intro-feats span {
  font-size: 12px; color: #0f766e; background: #ccfbf1;
  padding: 4px 10px; border-radius: 12px;
}
.intro-mark { font-size: 44px; opacity: 0.35; flex-shrink: 0; }

.search {
  flex: 1; max-width: 460px;
  display: flex; align-items: center; gap: 8px;
  background: #f2fbf9; border-radius: 20px; padding: 10px 16px;
}
.search .s-ico { font-size: 15px; opacity: 0.5; }
.search input { flex: 1; border: none; outline: none; font-size: 14px; background: transparent; }
.search .s-clear {
  font-size: 12px; color: #9aa5b1; cursor: pointer;
  padding: 2px 6px; border-radius: 50%;
}
.search .s-clear:hover { background: #e6ebf2; color: #4b5563; }

/* 搜索框 + 下拉建议 */
.search-wrap {
  position: relative;
  flex: 1; max-width: 460px;
}
.search-wrap .search { width: 100%; box-sizing: border-box; }

.suggest {
  position: absolute; left: 0; right: 0; top: calc(100% + 6px);
  background: #fff; border: 1px solid #eef1f6; border-radius: 12px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
  overflow: hidden; z-index: 20;
}
.sug-item {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 10px 14px; cursor: pointer; font-size: 13px;
}
.sug-item:hover { background: #f7fffd; }
.sug-title {
  color: #1f2937; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.sug-author { color: #9aa5b1; font-size: 11px; flex-shrink: 0; }

/* 分类: 药丸 */
.cats { display: flex; gap: 10px; }
.cat {
  font-size: 14px; color: #4b5563; cursor: pointer;
  padding: 7px 18px; border-radius: 20px;
  background: #fff; border: 1px solid #e6ebf2;
  transition: all 0.18s;
}
.cat:hover { border-color: #14b8a6; color: #14b8a6; }
.cat.active {
  background: #14b8a6; color: #fff; border-color: #14b8a6;
  font-weight: 600; box-shadow: 0 4px 12px rgba(20, 184, 166, 0.30);
}

/* 轮播 banner */
.banner {
  position: relative; height: 240px; border-radius: 18px;
  margin-bottom: 22px; overflow: hidden;
  box-shadow: 0 10px 30px rgba(15, 118, 110, 0.12);
}

/* 三张幻灯片【都铺满整个 banner, 叠在一起】, 靠 opacity 切换 */
/* 为什么不 v-if 一张张换? 因为那样没法做淡入淡出过渡 */
.slide {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  display: flex; align-items: flex-end; padding: 24px;
  opacity: 0;                          /* 默认全透明 (看不见) */
  transition: opacity 0.6s ease;       /* 变透明度的时候慢慢来 → 淡入淡出 */
  z-index: 1;
}
.slide.on { opacity: 1; z-index: 2; }  /* 当前这张不透明 */
.slide.linkable { cursor: pointer; }

/* 背景图: 铺满整张幻灯片
   object-fit: cover = "按比例放大到铺满, 多出来的裁掉" (不会把图拉变形) */
.slide-img {
  position: absolute;
  top: 0; left: 0; width: 100%; height: 100%;
  object-fit: cover;
  z-index: 0;
}

/* 遮罩: 左边深、右边浅的黑色渐变
   作用: 文字在左边, 压暗一点才看得清; 右边留亮, 免得整张图糊成一片 */
.slide-mask {
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(
    90deg,
    rgba(8, 20, 24, 0.72) 0%,
    rgba(8, 20, 24, 0.42) 45%,
    rgba(8, 20, 24, 0.08) 100%
  );
  z-index: 1;
}

/* 文字要盖在遮罩上面 (z-index 比遮罩大) */
.banner-text { position: relative; z-index: 2; }

/* ---------- 三张幻灯片的背景 ---------- */
/* 套路: 底下一个深色斜向渐变 + 上面两层【径向光晕】
   (radial-gradient 从中心往外淡出到 transparent, 叠起来就是柔和的"弥散色晕",
    比单纯一个 linear-gradient 有层次, 不会显得是一块死板的纯色) */
.bn-1 {
  background:
    radial-gradient(circle at 82% 18%, rgba(45, 212, 191, 0.60), transparent 52%),
    radial-gradient(circle at 10% 92%, rgba(129, 140, 248, 0.45), transparent 48%),
    linear-gradient(135deg, #0f766e 0%, #115e59 60%, #134e4a 100%);
}
.bn-2 {
  background:
    radial-gradient(circle at 80% 22%, rgba(96, 165, 250, 0.60), transparent 52%),
    radial-gradient(circle at 14% 88%, rgba(167, 139, 250, 0.50), transparent 48%),
    linear-gradient(135deg, #1e3a8a 0%, #1e40af 55%, #312e81 100%);
}
.bn-3 {
  background:
    radial-gradient(circle at 80% 20%, rgba(251, 146, 60, 0.58), transparent 52%),
    radial-gradient(circle at 16% 90%, rgba(244, 114, 182, 0.40), transparent 48%),
    linear-gradient(135deg, #7c2d12 0%, #9a3412 55%, #7c2d12 100%);
}

.banner-text h2 {
  font-size: 27px; color: #fff; letter-spacing: 0.5px;
  text-shadow: 0 2px 14px rgba(0, 0, 0, 0.35);   /* 深色背景上阴影要重一点才清楚 */
}
.banner-text p {
  font-size: 14px; color: rgba(255, 255, 255, 0.88); margin-top: 8px;
  text-shadow: 0 1px 8px rgba(0, 0, 0, 0.30);
}

/* 小圆点 (z-index 要大于幻灯片, 不然点不到) */
.dots {
  position: absolute; right: 20px; bottom: 20px;
  display: flex; gap: 6px; z-index: 10;
}
.dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: rgba(255,255,255,0.5); cursor: pointer;
  transition: all 0.25s;
}
.dot:hover { background: rgba(255,255,255,0.85); }
.dot.active { background: #fff; width: 18px; border-radius: 4px; }

/* ================= 主内容 + 侧栏 ================= */
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 22px;
  align-items: start;
}
.main { min-width: 0; }

/* 侧栏整体: 跟着页面滚, 但滚到顶就"粘"住 (sticky) */
.side {
  position: sticky;
  top: 84px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.side-card {
  background: #fff;
  border: 1px solid rgba(20, 184, 166, 0.10);
  border-radius: 16px;
  padding: 16px;
  box-shadow: 0 2px 12px rgba(20, 184, 166, 0.06);
}
.side-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 12px;
}
.side-title {
  display: flex; align-items: center; gap: 6px;
  font-size: 15px; font-weight: 700; color: #1f2937;
}
.side-ico { font-size: 15px; }
.side-more {
  font-size: 12px; color: #9aa5b1; text-decoration: none;
}
.side-more:hover { color: #14b8a6; }
.side-empty { font-size: 12px; color: #a8b2c1; padding: 14px 0; text-align: center; }

/* ---- 热门文章排行 ---- */
.hot-list { list-style: none; display: flex; flex-direction: column; gap: 2px; }
.hot-item {
  display: flex; gap: 10px; align-items: flex-start;
  padding: 9px 8px; border-radius: 10px; cursor: pointer;
  transition: background 0.16s;
}
.hot-item:hover { background: #f7fffd; }

/* 名次: 前三名给不同的强调色, 后面的低调一点 */
.rank {
  flex-shrink: 0; width: 22px; height: 22px; border-radius: 7px;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: #9aa5b1;
  background: #f4f7fa; margin-top: 1px;
}
.rank.r1 { background: #fff1f2; color: #e11d48; }
.rank.r2 { background: #fff7ed; color: #ea580c; }
.rank.r3 { background: #fefce8; color: #ca8a04; }

.hot-body { min-width: 0; flex: 1; }
.hot-title {
  font-size: 13px; line-height: 1.45; color: #374151;
  overflow: hidden; display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.hot-item:hover .hot-title { color: #0f766e; }
.hot-meta {
  display: flex; align-items: center; justify-content: space-between;
  margin-top: 5px; font-size: 11px; color: #a8b2c1;
}
.hot-author {
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  max-width: 110px;
}
.hot-heat { flex-shrink: 0; color: #f59e0b; }

/* ---- 标签云 ---- */
.tag-cloud { display: flex; flex-wrap: wrap; gap: 8px; }
.tag-chip {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 5px 11px; border-radius: 20px;
  font-size: 12px; color: #0f766e; text-decoration: none;
  background: #f0fdfa; border: 1px solid #ccfbf1;
  transition: all 0.16s;
}
.tag-chip:hover {
  background: #14b8a6; border-color: #14b8a6; color: #fff;
  transform: translateY(-1px);
}
.tag-chip em {
  font-style: normal; font-size: 10px;
  color: #5eead4; background: rgba(15, 118, 110, 0.12);
  padding: 0 5px; border-radius: 8px; line-height: 15px;
}
.tag-chip:hover em { color: #fff; background: rgba(255, 255, 255, 0.22); }

/* ---- 创作入口卡片 ---- */
.about {
  background:
    radial-gradient(circle at 88% 10%, rgba(45, 212, 191, 0.55), transparent 55%),
    linear-gradient(135deg, #0f766e 0%, #115e59 100%);
  border: none;
  color: #fff;
}
.about h4 { font-size: 16px; margin-bottom: 8px; }
.about p { font-size: 12px; line-height: 1.7; color: rgba(255, 255, 255, 0.75); }
.about-btn {
  display: inline-block; margin-top: 14px; padding: 9px 18px;
  border-radius: 20px; background: #fff; color: #0f766e;
  font-size: 13px; font-weight: 700; text-decoration: none;
  transition: transform 0.16s, box-shadow 0.16s;
}
.about-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.18);
}
.about-stats {
  display: flex; gap: 26px; margin-top: 18px;
  padding-top: 14px; border-top: 1px solid rgba(255, 255, 255, 0.18);
}
.about-stats div { display: flex; flex-direction: column; }
.about-stats b { font-size: 19px; line-height: 1.2; }
.about-stats span { font-size: 11px; color: rgba(255, 255, 255, 0.65); margin-top: 2px; }

/* 区块标题 */
.section-title { font-size: 18px; margin-bottom: 16px; }
.section-title::before {
  content: ''; display: inline-block; width: 4px; height: 16px;
  background: #14b8a6; border-radius: 2px; margin-right: 10px; vertical-align: -2px;
}
.s-count { font-size: 13px; color: #9aa5b1; font-weight: 400; margin-left: 8px; }

/* 文章卡片网格: 一排 3 个, 卡片小一点, 一屏能看更多 */
.grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.art-card {
  overflow: hidden;
  border: 1px solid rgba(20, 184, 166, 0.10);
  border-radius: 14px;
}
.art-cover {
  position: relative; height: 118px; overflow: hidden;
  display: flex; align-items: center; justify-content: center;
}
/* 封面上那个文档线框图标
   (渐变底色很浅, 所以用半透明墨绿, 别用白色 —— 白字在白底上看不见) */
.art-emoji {
  width: 44px;
  height: 44px;
  color: rgba(15, 118, 110, 0.42);
}
.art-info { padding: 12px; }
.art-title {
  font-size: 14px; line-height: 1.45; height: 41px; overflow: hidden;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
/* 分类小徽章 */
.art-cat {
  display: inline-block; vertical-align: 1px;
  font-size: 11px; line-height: 16px;
  padding: 0 7px; border-radius: 5px; margin-right: 5px;
  background: #f0fdfa; color: #0f766e; border: 1px solid #ccfbf1;
  font-weight: 500;
}
.art-sum {
  font-size: 11.5px; color: #9aa5b1; margin-top: 5px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.art-meta { display: flex; align-items: center; gap: 7px; margin-top: 8px; }
.avatar {
  width: 22px; height: 22px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center; font-size: 12px;
}
.author { font-size: 12px; color: #7b8794; flex: 1; overflow: hidden; white-space: nowrap; }
/* 点赞量: 推到卡片这一行的最右边 */
.art-like { font-size: 12px; color: #9aa5b1; flex-shrink: 0; }
.clickable { cursor: pointer; }
.clickable:hover { color: #14b8a6; text-decoration: underline; }

.loading { text-align: center; color: #a8b2c1; padding: 50px 0; }
.empty { text-align: center; color: #a8b2c1; padding: 50px 0; }

/* 分页条 */
.pager {
  display: flex; align-items: center; justify-content: center;
  gap: 8px; margin-top: 30px;
}
.pager button {
  border: 1px solid #e6ebf2; background: #fff; color: #4b5563;
  font-size: 14px; cursor: pointer; transition: all 0.15s;
}
.pg-btn { padding: 8px 16px; border-radius: 10px; }
.pg-num { width: 38px; height: 38px; border-radius: 10px; }
.pager button:hover:not(:disabled) { border-color: #14b8a6; color: #14b8a6; }
.pg-num.on {
  background: #14b8a6; border-color: #14b8a6; color: #fff; font-weight: 600;
}
.pager button:disabled { opacity: 0.45; cursor: not-allowed; }

.cover-img {
  width: 100%; height: 100%; object-fit: cover; display: block;
  transition: transform 0.45s cubic-bezier(0.2, 0.8, 0.3, 1);
}
/* 鼠标放到卡片上, 封面图轻轻放大 (overflow:hidden 把它裁在框里) */
.art-card:hover .cover-img { transform: scale(1.06); }

/* ---- 响应式: 窄屏时侧栏掉到下面, 卡片改单列 ---- */
@media (max-width: 1080px) {
  /* ★ 用 minmax(0, 1fr) 而不是 1fr:
     1fr 的最小宽度是"内容最小宽度", 卡片里的单行摘要(min-content 很宽)
     会把整个页面撑出屏幕; minmax(0, ...) 允许它缩到 0 */
  .layout { grid-template-columns: minmax(0, 1fr); }
  .side {
    position: static;
    display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .about { grid-column: span 2; }
}
@media (max-width: 720px) {
  .intro { padding: 16px; }
  .intro h1 { font-size: 18px; }
  .intro-mark { display: none; }
  .topbar { flex-direction: column; align-items: stretch; gap: 14px; }
  .search-wrap { max-width: none; }
  .cats { flex-wrap: wrap; }
  .cat { flex-shrink: 0; }
  .banner { height: 190px; }
  .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
  .side { grid-template-columns: minmax(0, 1fr); }
  .about { grid-column: auto; }
}
@media (max-width: 480px) {
  .grid { grid-template-columns: minmax(0, 1fr); }
}
</style>
