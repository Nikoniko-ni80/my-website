import { createRouter, createWebHashHistory } from 'vue-router'
import HomePage from '../components/HomePage.vue'
import ArticleDetailPage from '../components/ArticleDetailPage.vue'
import AiPage from '../components/AiPage.vue'
import MePage from '../components/MePage.vue'
import MyArticlesPage from '../components/MyArticlesPage.vue'
import WriteArticlePage from '../components/WriteArticlePage.vue'
import LoginPage from '../components/LoginPage.vue'
import RegisterPage from '../components/RegisterPage.vue'
import CollectionsPage from '../components/CollectionsPage.vue'
import HistoryPage from '../components/HistoryPage.vue'
import UserPage from '../components/UserPage.vue'
import FeedPage from '../components/FeedPage.vue'
import HotPage from '../components/HotPage.vue'
import TagPage from '../components/TagPage.vue'

const routes = [
  { path: '/home', component: HomePage },                    // 首页 (公开文章流)
  { path: '/article/:id', component: ArticleDetailPage },    // 文章详情
  { path: '/ai', component: AiPage },                        // AI 助手
  { path: '/me', component: MePage },                        // 我的
  { path: '/my-articles', component: MyArticlesPage },       // 我的文章
  { path: '/my-collections', component: CollectionsPage },        // 我的收藏 (默认选第一本)
  { path: '/my-collections/:id', component: CollectionsPage },    // 我的收藏 (指定看哪一本)
  { path: '/history', component: HistoryPage },              // 浏览历史
  { path: '/user/:id', component: UserPage },                // 个人主页 (看别人的)
  { path: '/feed', component: FeedPage },                    // 关注 (我关注的人发的文章)
  { path: '/hot', component: HotPage },                      // 🔥 全站热榜
  { path: '/tag/:name', component: TagPage },                // # 标签页
  // ↑ 两条路由共用同一个组件: 左边夹子列表 + 右边内容, 靠网址里的 id 决定右边显示谁
  { path: '/write', component: WriteArticlePage },           // 写文章
  { path: '/write/:id', component: WriteArticlePage },       // 编辑文章
  { path: '/login', component: LoginPage },                  // 登录
  { path: '/register', component: RegisterPage },            // 注册
  { path: '/', redirect: '/home' }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
