<template>
  <div class="page ai-page">
    <!-- 顶部标题 -->
    <div class="ai-head">
      <div class="ai-avatar cover-6">✨</div>
      <div>
        <h2>AI 小助手</h2>
        <p>文章问答 · 陪你聊技术</p>
      </div>
    </div>

    <!-- 对话区 -->
    <div class="chat-area">
      <div class="bubble bubble-ai">
        你好呀～ 我是这个站的 AI 小助手。以后你可以问我文章相关的问题～
      </div>

      <div class="bubble bubble-ai">
        不过我现在还在"施工中" 🚧<br />
        等接入 AI 能力后，就能真正陪你聊天了。
      </div>

      <div class="bubble bubble-user">那什么时候能好呀？</div>

      <div class="bubble bubble-ai">
        快了！等后端把 <b>AI Agent</b> 做出来就上线～
      </div>
    </div>

    <!-- 底部输入 (占位, 暂不可用) -->
    <div class="chat-input">
      <input placeholder="AI 功能开发中，敬请期待…" disabled />
      <button disabled>发送</button>
    </div>
  </div>
</template>

<script setup></script>

<style scoped>
/* PC: AI 页居中收窄, 占满可视高度 */
.ai-page {
  max-width: 760px;
  display: flex;
  flex-direction: column;
  height: calc(100vh - 64px);
  padding-bottom: 24px;
}

.ai-head { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.ai-avatar {
  width: 46px; height: 46px; border-radius: 14px;
  display: flex; align-items: center; justify-content: center; font-size: 22px;
}
.ai-head h2 { font-size: 17px; }
.ai-head p { font-size: 12px; color: #7b8794; margin-top: 2px; }

.chat-area { flex: 1; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; padding-bottom: 10px; }
.bubble {
  max-width: 78%; padding: 10px 14px; border-radius: 14px;
  font-size: 14px; line-height: 1.5;
}
.bubble-ai {
  align-self: flex-start; background: #fff; color: #2c3e50;
  box-shadow: 0 2px 10px rgba(20, 184, 166, 0.07);
  border-bottom-left-radius: 4px;
}
.bubble-user {
  align-self: flex-end; background: #14b8a6; color: #fff;
  border-bottom-right-radius: 4px;
}

.chat-input {
  display: flex; gap: 10px; padding-top: 10px;
  border-top: 1px solid #eef1f6; background: #f6f8fb;
}
.chat-input input {
  flex: 1; padding: 11px 14px; border: 1px solid #e6ebf2; border-radius: 20px;
  font-size: 14px; outline: none; background: #fff;
}
.chat-input button {
  padding: 0 20px; border: none; border-radius: 20px;
  background: #c9d6e5; color: #fff; font-size: 14px;
}
</style>
