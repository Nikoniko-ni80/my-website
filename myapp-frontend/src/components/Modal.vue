<template>
  <!-- Teleport (传送门): 把弹窗的 DOM "传送"到 <body> 下面, 不留在当前页面组件里。
       为什么要这么做? 三个坑, 都是这个项目里真实存在的:
         ① 祖先有 transform 时, position:fixed 不再相对屏幕定位 (style.css 的 .hoverable:hover 就用了 transform)
         ② 祖先有 overflow:hidden 时, 弹窗会被裁掉 (.art-card 就是这样)
         ③ z-index 层叠: 顶栏 App.vue 是 z-index:100, 弹窗留在页面里会被顶栏盖住
       传送到 body 之后, 这三个问题一次性全没了。
       放心: <style scoped> 不会失效 —— scoped 是给元素自己加 data-v-xxx 属性, 跟它被放到哪没关系 -->
  <Teleport to="body">
    <!-- v-if 控制整个弹窗的显示/隐藏 -->
    <div v-if="modelValue" class="mask" @click.self="close">
      <!-- @click.self: 只有"点击的目标就是遮罩本身"时才触发关闭。
           点中间那个白卡片时, 事件目标是卡片不是遮罩, 所以不会误关 -->
      <div class="box">
        <div class="head">
          <h3>{{ title }}</h3>
          <button class="x" @click="close">✕</button>
        </div>
        <div class="body">
          <!-- 插槽: 父组件写在 <Modal> 标签中间的内容, 会塞到这里来 -->
          <slot />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { watch, onUnmounted } from 'vue'

// props: 父组件传进来的数据 (子组件里只读, 不能直接改)
const props = defineProps({
  modelValue: { type: Boolean, default: false },   // 开 / 关
  title:      { type: String,  default: '' },      // 弹窗标题
})

// emits: 子组件要"通知父组件"的事件
const emit = defineEmits(['update:modelValue'])

const close = () => emit('update:modelValue', false)
// ↑ 父组件写 <Modal v-model="show">, 这里 emit 之后父组件的 show 自动变 false。
//   v-model 其实就是 "传 modelValue + 监听 update:modelValue" 的语法糖。
//   好处: 开关状态只有一个来源(父组件), 不会出现"子组件关了、父组件以为还开着"

// 弹窗打开时锁住背景滚动, 关闭时还回去
// 为什么需要: 遮罩只是盖住了"视觉", 滚轮照样能滚背后的文章
watch(() => props.modelValue, (open) => {
  document.body.style.overflow = open ? 'hidden' : ''
})

// ⚠️ 兜底: 弹窗还开着的时候如果切了路由 (组件被销毁), 上面那个 watch 不会再执行,
//   body 的 overflow:hidden 就永远留在那了 —— 整个网站会滚不动。这个坑很隐蔽。
onUnmounted(() => { document.body.style.overflow = '' })
</script>

<style scoped>
/* 遮罩: 铺满整个屏幕的半透明黑 */
.mask {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(17, 24, 39, 0.45);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;                     /* 要比顶栏的 100 大 */
}

/* 中间的白卡片 */
.box {
  background: #fff;
  border-radius: 16px;
  width: 420px;
  max-width: calc(100vw - 40px);      /* 手机屏幕上别超出屏幕 */
  max-height: 72vh;                   /* 内容太高就内部滚动 */
  display: flex; flex-direction: column;
  box-shadow: 0 20px 60px rgba(17, 24, 39, 0.22);
}

.head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 22px 12px;
}
.head h3 { font-size: 17px; color: #1f2937; }

.x {
  border: none; background: transparent; cursor: pointer;
  font-size: 15px; color: #9aa5b1; padding: 4px 8px; border-radius: 8px;
}
.x:hover { background: #f0fdfa; color: #14b8a6; }

.body { padding: 0 22px 22px; overflow-y: auto; }
</style>
