import { createApp } from 'vue'
import './style.css'
// 代码高亮的配色 (highlight.js 自带的主题之一, 深色)
//   html 里那些 class="hljs-keyword" 之类, 就是靠这个文件上色的
import 'highlight.js/styles/atom-one-dark.css'
import App from './App.vue'
import router from './router/index.js'
import IconUser from './components/IconUser.vue'
import IconDoc from './components/IconDoc.vue'

const app = createApp(App)
app.use(router)

// 两个中性图标在 7 个组件里都要用, 注册成【全局组件】省得每个文件都 import
app.component('IconUser', IconUser)
app.component('IconDoc', IconDoc)

app.mount('#app')
