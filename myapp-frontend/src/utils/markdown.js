// ============================================================
// utils/markdown.js —— Markdown 渲染 (全站共用这一个)
// ============================================================
// 为什么要单独一个文件?
//   因为"渲染 Markdown"这件事在两个地方要用:
//     ① 写文章页 —— 右边那个实时预览
//     ② 文章详情页 —— 显示正文
//   如果各写各的, 以后想改(比如换个高亮主题)就要改两处。
//   —— 这就是"能复用就抽出来"的例子
// ============================================================
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'

// ---------- 配置 marked ----------
marked.use({
  gfm: true,      // 支持 GitHub 风格: 表格 / 删除线 / 任务列表
  breaks: true,   // 单个换行也当成换行 (不然写一行换行会被并成一句)

  renderer: {
    // 自定义"代码块"怎么渲染 —— 顺便用 highlight.js 上色
    // (marked v5 之后删掉了旧的 highlight 选项, 现在只能这样写)
    code({ text, lang }) {
      // 语言写了而且认识就用它, 不认识就按纯文本处理
      const language = (lang && hljs.getLanguage(lang)) ? lang : 'plaintext'
      const colored = hljs.highlight(text, { language }).value
      return `<pre><code class="hljs language-${language}">${colored}</code></pre>`
    },
  },
})


// ---------- 把 Markdown 变成能插进页面的 HTML ----------
export function renderMarkdown(text) {
  if (!text) return ''

  const html = marked.parse(text)

  // ★★★ 这一行【绝对不能省】★★★
  // marked 只是"翻译", 不管安全。如果文章里写了:
  //     <img src=x onerror="偷走你的token并发送到黑客服务器">
  // 直接插进页面, 浏览器就会执行它 —— 这叫 XSS 攻击。
  //
  // 你的文章是【所有人能看】的, 所以在别人浏览器上执行 = 真的能偷东西。
  // DOMPurify 会把危险的标签/属性洗掉, 只留下安全的那些。
  //
  // 一句话: 【永远不要 v-html 一段没洗过的用户输入】
  return DOMPurify.sanitize(html)
}


// ---------- 把 Markdown 变成纯文本 (给列表页的摘要用) ----------
// 卡片上那行小字不能显示 "## 标题 **粗体**" 这种源码, 得去掉符号
export function stripMarkdown(text) {
  if (!text) return ''
  return text
    .replace(/```[\s\S]*?```/g, ' [代码] ')     // 代码块 → 一句话带过
    .replace(/`([^`]+)`/g, '$1')                 // 行内代码去掉反引号
    .replace(/!\[[^\]]*\]\([^)]*\)/g, '')        // 图片整个删掉
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')     // 链接 → 只留文字
    .replace(/^#{1,6}\s+/gm, '')                 // 标题的 #
    .replace(/(\*\*|__)(.*?)\1/g, '$2')          // 粗体
    .replace(/(\*|_)(.*?)\1/g, '$2')             // 斜体
    .replace(/^\s*[-*+]\s+/gm, '')               // 列表的 -
    .replace(/^\s*>\s?/gm, '')                   // 引用的 >
    .replace(/\s+/g, ' ')                        // 一堆空白合成一个
    .trim()
}
