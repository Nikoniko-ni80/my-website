<template>
  <!-- 中性用户剪影: 线条风格, 颜色跟着父元素的 color 走 -->
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <circle cx="12" cy="8.2" r="3.6" />
    <path d="M4.6 20.2c0-3.6 3.3-5.8 7.4-5.8s7.4 2.2 7.4 5.8" />
  </svg>
</template>

<style scoped>
svg {
  display: block;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  padding: 16%;       /* 留白, 别贴边 */
}
</style>
