import { createApp } from 'vue'
import './style.css'
// 代码高亮的配色 (highlight.js 自带的主题之一, 深色)
//   html 里那些 class="hljs-keyword" 之类, 就是靠这个文件上色的
import 'highlight.js/styles/atom-one-dark.css'
import App from './App.vue'
import router from './router/index.js'

const app = createApp(App)
app.use(router)
app.mount('#app')
