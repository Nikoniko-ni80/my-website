// ============================================================
// services/aiApi.js —— AI 聊天的前端请求层
// ============================================================
// 为什么不放在 authApi.js?
//   authApi 里全是 axios 的普通请求 (发一次、收一次)。
//   AI 要用 fetch 读流, 是另一种用法, 单独放一个文件更好找。
//
// ============================================================
// 【三种请求方式的区别 —— 为什么这里必须用 fetch】
// ============================================================
//
// ① axios 普通请求 (authApi.js 里的 getMe)
//    写法: api.get('/me', { headers: { Authorization } })
//    发送: GET/POST 都行, 能带请求头、请求体
//    接收: 浏览器里会等响应【全部收完】才返回, 拿不到中间的流
//    适合: 登录、文章列表、增删改查
//
// ② EventSource (App.vue 里的通知)
//    写法: new EventSource(url); es.onmessage = fn
//    发送: 【只能 GET】, 不能带请求体和自定义请求头, token 只能拼在网址里
//    接收: 浏览器自动解析 data:, 每来一条就调一次 onmessage
//          —— 它是【边收边给】的, 不是收完再给
//    适合: 服务器单向推送 (通知、新闻流)
//
// ③ fetch (本文件)
//    写法: fetch(url, { method, headers, body })
//    发送: 能 POST, 能带自定义请求头和请求体 (请求体是普通 JSON, 不是流)
//    接收: res.body 是【可读的流】, 可以一段段读
//          但浏览器不会帮你解析 SSE, 要自己:
//            reader.read() 取字节 → TextDecoder 转文字
//            → 按 \n\n 切事件 → JSON.parse
//    适合: AI 流式回答 —— 既要 POST 交消息, 又要边收边显示
//
// 【为什么 AI 不能用前两个】
//   EventSource: 发送端不行 —— 只能 GET, 带不了 messages 和 Authorization 头
//   axios:       接收端不行 —— 浏览器里收完整段响应才返回, 做不到边收边显示
//   所以只能 fetch: 它发送端和接收端都满足, 代价是解析要自己写
//
// 【一个关键点: 发送和接收是同一次请求的两半】
//   不能"用 axios 发请求, 再用 fetch 收响应"。
//   响应是跟着这次请求回来的: 谁发的请求, 谁收响应。
//
//   我们这里:
//     发送 → POST /ai/chat, body 是普通 JSON (messages), 一次性发完
//     接收 → 同一个请求的响应体是流, 一段一段到达
//
// ============================================================
// 【它对外只暴露一个函数】
//   streamChat(token, messages, { onDelta, onDone, onError, signal })
//
//   onDelta(text)  每收到一小段文字调用一次
//   onDone()       回答结束调用一次
//   onError(msg)   出错时调用, 参数是给用户看的话
//   signal         AbortController 的 signal, 用来"停止生成"
// ============================================================
import { API_BASE } from './authApi.js'

//下面这个东西同时执行发送和接收请求，就是站在前端的角度，先发送请求然后接收响应
export async function streamChat(token, messages, { onDelta, onDone, onError, signal } = {}) {
//export就是可以被前端vue import的函数  token登录凭证， message对话记录  后面的{}是对象啥的
//比如后面我前端调用这个函数
//streamChat(token, messages, {
//  onDelta: (text) => { 显示文字 },
//  onDone: () => { 停止转圈 },
//  onError: (msg) => { 显示错误 },
//})
//就会给这一崔函数，这种函数比如onDelta，里面有我加的参数text和他内部的方法函数“显示文字”
  let finished = false

  const finish = () => {    //一个变量名叫finish，下面{}是变量内部装的函数
    if (finished) return//如果finished是true就立刻退出，不执行后面
    finished = true
    onDone && onDone()
  }

  const fail = (msg) => {
    if (finished) return
    finished = true
    onError && onError(msg)
  }

  //上面这两个东西就是结束是执行的对应操作，通过finished这个参数来保证只执行一次

  let res
  try {
    res = await fetch(`${API_BASE}/ai/chat`, {//发请求，res是后端响应返回的东西
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ messages }),
      signal,
    })
  } catch (err) {
    if (err.name === 'AbortError') return
    //这个AbortError是请求中断的错误，就是说用户点击停止生成是会触发这个，此时直接return即可
    fail('网络错误，请检查网络后重试')
    return
  }
  //注意上面的网络请求错误检测搞了用户自行中断，没有识别网络方面的问题，下面还要单独搞（401，429.。。。）

  // 401 Unauthorized: 没登录 / token 过期 / token 无效
  // (后端的 get_current_user 验不过时返回)
  if (res.status === 401) {
    fail('登录已过期，请重新登录')
    return
  }

  // 429 Too Many Requests: 请求太频繁 / 今日额度用完
  // (后端的每日额度、nginx 的登录限流都会返回它)
  if (res.status === 429) {
    let msg = '今天的 AI 额度用完了，明天再来'
    try {
      const data = await res.json()
      if (data.error) msg = data.error
    } catch (e) { /* 忽略解析失败 */ }
    fail(msg)
    return
  }

  // 兜底: 剩下的非 2xx, 或者没有响应体
  // 常见状态码:
  //   200 OK          成功 (200~299 都算 ok)
  //   401 Unauthorized 未认证 (上面已处理)
  //   403 Forbidden    已登录但没权限
  //   404 Not Found    接口地址不存在 (路由没挂上时会看到)
  //   422 Unprocessable 请求格式不对 (FastAPI 校验失败)
  //   429 Too Many     请求太多 / 额度用完 (上面已处理)
  //   500 Internal     后端代码报错
  if (!res.ok || !res.body) {
    fail('AI 服务暂时不可用，请稍后再试')
    return
  }

  // ---------- 读流 ----------
  const reader = res.body.getReader()
  //res.body现在是流，现在从流里面通过getReader获取一个读取器reader后面通过reader.read()读取
  const decoder = new TextDecoder('utf-8')//解码器
  let buffer = ''//有时候网络返回的不一定是完整请求比如返回ta","content":"RAG"}\n\n
                 //要一个一个在buffer拼起来

  try {
    while (true) {
      const { value, done } = await reader.read()
      if (done) break

      // 网络给的是字节, 先转成字符串; stream:true 保证多字节汉字不会被切坏
      buffer += decoder.decode(value, { stream: true })

      // SSE 用空行分隔事件; 一次可能收到多个, 也可能只有半个

      let sep//现在要把上面的那个buffer切割成正常的事件响应，sep是分隔符\的位置
      while ((sep = buffer.indexOf('\n\n')) !== -1) { 
        //找到了\进入循环
        const rawEvent = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)

        for (const line of rawEvent.split('\n')) {
          if (!line.startsWith('data:')) continue
          const data = line.slice(5).trim()

          if (data === '[DONE]') { //后端流结束时回发[DONE]
            finish()
            return
          }

          try {
            const event = JSON.parse(data)//把data字符串转化以后再来成内容
            if (event.type === 'delta') {
              onDelta && onDelta(event.content)//正常就把数据给前端页面
            } else if (event.type === 'error') {
              fail(event.message || 'AI 暂时不可用')
              return
            }
          } catch (e) {
            // 非 JSON 行, 跳过
          }
        }
      }
    }

    // 流正常结束, 但没收到 [DONE]（少数情况）也当作完成
    finish()
  } catch (err) {
    if (err.name === 'AbortError') return
    fail('接收回答时出错，请重试')
  } finally {
    try { reader.releaseLock() } catch (e) { /* 忽略 */ }
  }
}
