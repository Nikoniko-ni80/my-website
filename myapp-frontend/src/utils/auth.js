// ============================================================
// auth.js —— 登录跳转的小工具
// ============================================================
// 【解决什么问题】
//   以前各页面写的是 router.push('/login')，登录页写死跳 /me。
//   结果: 在文章页点"关注" → 跳登录 → 登录完回到"我的"，
//         而不是回到刚才那篇文章。用户得自己再找回去。
//
// 【怎么解决】
//   跳登录时把"我现在在哪"带上:  /login?redirect=/article/23
//   登录成功后: 有 redirect 就回去, 没有才去 /me。
// ============================================================

export const goLogin = (router) => {
  // router.currentRoute.value.fullPath = 当前地址 (含查询参数), 如 /article/23?x=1
  const back = router.currentRoute.value.fullPath
  router.push({ path: '/login', query: { redirect: back } })
}

// 只接受站内路径, 防止有人构造 /login?redirect=https://evil.com
export const safeRedirect = (raw, fallback = '/me') => {
  if (typeof raw !== 'string') return fallback
  if (!raw.startsWith('/')) return fallback      // 必须是站内绝对路径
  if (raw.startsWith('//')) return fallback      // 排除 //evil.com 这种协议相对地址
  return raw
}
