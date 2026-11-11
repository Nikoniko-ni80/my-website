<template>
  <div class="page">
    <!-- 返回 -->
    <button class="back" @click="$router.back()">‹ 返回</button>

    <p v-if="loading" class="tip">加载中...</p>

    <!-- 后端业务错误也是 200 + {error} -->
    <p v-else-if="error" class="tip">{{ error }}</p>

    <template v-else-if="user">
      <!-- ========== 顶部名片 ========== -->
      <div class="profile card">
        <!-- 头像: 有 URL 就显示图片, 没有就用默认 emoji 占位 -->
        <div class="avatar">
          <img v-if="user.avatar" :src="mediaUrl(user.avatar)" alt="头像" />
          <span v-else><IconUser /></span>
        </div>

        <div class="info">
          <h2 class="name">{{ user.username }}</h2>
          <p class="counts">
            <span class="clickable" @click="openList('following')">
              <b>{{ user.following_count }}</b> 关注
            </span>
            <span class="clickable" @click="openList('followers')">
              <b>{{ user.follower_count }}</b> 粉丝
            </span>
            <span><b>{{ user.article_count }}</b> 公开文章</span>
            <span class="joined">加入于 {{ fmtDate(user.created_at) }}</span>
          </p>
          <p class="bio">{{ user.bio || '这个人很懒，什么都没写～' }}</p>
        </div>

        <div class="actions">
          <!-- 看自己的主页 → 编辑资料; 看别人的 → 关注 + 私信 -->
          <button v-if="isMe" class="btn-edit" @click="openEdit">编辑资料</button>
          <template v-else>
            <button
              class="btn-follow"
              :class="{ on: following }"
              :disabled="followBusy"
              @click="toggleFollow"
            >
              {{ following ? '✓ 已关注' : '+ 关注' }}
            </button>
            <button class="btn-msg" @click="startChat">✉️ 私信</button>
          </template>
        </div>
      </div>

      <!-- 对方设置了关注欢迎语时, 后端会顺手发一条私信, 这里提示一下 -->
      <p v-if="followTip" class="follow-tip">✉️ {{ user.username }} 给你发了一条私信</p>

      <!-- ========== 他的文章 ========== -->
      <h3 class="sec-title">
        {{ isMe ? '我的公开文章' : `他的公开文章` }}
      </h3>

      <div class="list">
        <div
          v-for="(a, i) in user.articles"
          :key="a.id"
          class="item card hoverable"
          @click="$router.push(`/article/${a.id}`)"
        >
          <div class="cover" :class="coverOf(i)">
                <img v-if="a.cover" :src="mediaUrl(a.cover)" alt="" class="cover-img" />
                <IconDoc v-else />
              </div>
          <div class="art-text">
            <p class="t"><strong>{{ a.title }}</strong></p>
            <p class="c">{{ stripMarkdown(a.content) || '（无内容）' }}</p>
            <p class="meta">{{ fmtTime(a.created_at) }}</p>
          </div>
        </div>

        <p v-if="user.articles.length === 0" class="empty">
          {{ isMe ? '你还没有公开的文章，去写一篇吧～' : '他还没有公开的文章' }}
        </p>
      </div>
    </template>

    <!-- ========== 关注/粉丝 列表弹窗 ========== -->
    <Modal v-model="showList" :title="listTab === 'following' ? '他关注的人' : '他的粉丝'">
      <div class="tabs">
        <button :class="{ on: listTab === 'following' }" @click="openList('following')">
          关注 {{ user ? user.following_count : 0 }}
        </button>
        <button :class="{ on: listTab === 'followers' }" @click="openList('followers')">
          粉丝 {{ user ? user.follower_count : 0 }}
        </button>
      </div>

      <p v-if="listLoading" class="l-tip">加载中...</p>

      <div v-else-if="listData.length" class="u-list">
        <div
          v-for="u in listData"
          :key="u.id"
          class="u-item"
          @click="goUser(u.id)"
        >
          <div class="u-avatar">
            <img v-if="u.avatar" :src="mediaUrl(u.avatar)" alt="" />
            <span v-else><IconUser /></span>
          </div>
          <div class="u-text">
            <p class="u-name">{{ u.username }}</p>
            <p class="u-bio">{{ u.bio || '这个人很懒～' }}</p>
          </div>
          <!-- 看自己的关注列表时，可以直接取关 -->
          <button
            v-if="isMe && listTab === 'following'"
            class="u-unfollow"
            @click.stop="unfollowFromList(u)"
          >取关</button>
        </div>
      </div>

      <p v-else class="l-tip">
        {{ listTab === 'following' ? '他还没有关注任何人' : '他还没有粉丝' }}
      </p>
    </Modal>

    <!-- ========== 编辑资料的弹窗 ========== -->
    <Modal v-model="showEdit" title="编辑资料">
      <div class="form">
        <label class="lbl">用户名</label>
        <input v-model="editUsername" placeholder="改一个新名字" />
        <p class="hint">改了之后要用新用户名登录哦</p>

        <label class="lbl">头像</label>
        <div class="avatar-edit">
          <div class="avatar small">
            <img v-if="editAvatar" :src="mediaUrl(editAvatar)" alt="" @error="imgBad = true" />
            <span v-else><IconUser /></span>
          </div>
          <div class="av-actions">
            <label class="pick-btn">
              {{ uploading ? '上传中…' : '选择图片' }}
              <input
                type="file"
                accept="image/png,image/jpeg,image/gif,image/webp"
                hidden
                @change="onPickAvatar"
              />
            </label>
            <button v-if="editAvatar" class="rm-btn" type="button" @click="clearAvatar">移除</button>
            <span class="av-hint">jpg / png / gif / webp，2MB 以内</span>
          </div>
        </div>
        <p v-if="imgBad" class="hint">⚠️ 这张图加载不出来</p>

        <label class="lbl">个人简介</label>
        <textarea v-model="editBio" rows="3" placeholder="介绍一下自己～"></textarea>
      </div>

      <!-- ★ 保存失败的提示 (比如"用户名已经有人用了") -->
      <p v-if="editMsg" class="err-msg">{{ editMsg }}</p>

      <div class="m-btns">
        <button class="cancel" @click="showEdit = false">取消</button>
        <button class="ok" :disabled="saving" @click="save">
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>
    </Modal>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getUserProfile, getMe, updateMe, followUser, unfollowUser, getFollowStatus,
  getFollowers, getFollowing, uploadFile
} from '../services/authApi.js'
import { mediaUrl } from '../utils/media.js'
import { stripMarkdown } from '../utils/markdown.js'
import Modal from './Modal.vue'
import { goLogin } from '../utils/auth.js'

const route = useRoute()
const router = useRouter()

// ★ 路由参数永远是字符串, 得转成数字再比较
const userId = Number(route.params.id)

const user = ref(null)
const loading = ref(false)
const error = ref('')

// ---- 是不是我自己的主页 ----
const myId = ref(null)
const myName = ref('')
const isMe = computed(() => myId.value !== null && myId.value === userId)

// ---- 关注 ----
const following = ref(false)
const followBusy = ref(false)
const followTip = ref(false)   // 对方设置了欢迎语 → 提示"他给你发了条私信"

const toggleFollow = async () => {
  const token = localStorage.getItem('token')
  if (!token) { goLogin(router); return }
  if (followBusy.value) return

  followBusy.value = true
  try {
    const res = following.value
      ? await unfollowUser(token, userId)
      : await followUser(token, userId)

    if (res.data.error) { error.value = res.data.error; return }

    // ★ 重复关注时后端返回 {message: "已经关注过了"} —— 那是成功, 不是错误
    following.value = !following.value
    // 粉丝数本地跟着动一下, 不用重新请求
    user.value.follower_count += following.value ? 1 : -1

    // 对方设了欢迎语 → 后端以他的身份发了一条私信, 告诉我一声
    if (following.value && res.data.sent_greeting) {
      followTip.value = true
      setTimeout(() => { followTip.value = false }, 4000)
    }
  } catch (e) {
    console.error('关注操作失败', e)
    error.value = '操作失败：' + e.message
  }
  followBusy.value = false
}

// 在自己的关注列表里直接取关
const unfollowFromList = async (u) => {
  const token = localStorage.getItem('token')
  if (!token) { goLogin(router); return }
  try {
    const res = await unfollowUser(token, u.id)
    if (res.data.error) { error.value = res.data.error; return }
    listData.value = listData.value.filter((x) => x.id !== u.id)
    if (user.value) {
      user.value.following_count = Math.max(0, user.value.following_count - 1)
    }
  } catch (e) {
    error.value = '取关失败：' + e.message
  }
}

// ---- 私信 ----
// 点「私信」直接进聊天页（用对方 id 进），第一句话发出去才真正建会话
const startChat = () => {
  if (!localStorage.getItem('token')) { goLogin(router); return }
  if (isMe.value) return
  router.push(`/messages/with/${userId}`)
}

// ---- 关注 / 粉丝 列表弹窗 ----
const showList = ref(false)
const listTab = ref('following')      // 'following' 或 'followers'
const listData = ref([])
const listLoading = ref(false)

const goUser = (id) => {
  showList.value = false
  if (id !== userId) router.push(`/user/${id}`)   // 点自己就不跳了
}

const openList = async (tab) => {
  listTab.value = tab
  showList.value = true
  listLoading.value = true
  listData.value = []
  try {
    // 两个都是【不用登录】的公开接口
    const res = tab === 'following'
      ? await getFollowing(userId)
      : await getFollowers(userId)
    if (!res.data.error) listData.value = res.data
  } catch (e) {
    console.error('获取列表失败', e)
  }
  listLoading.value = false
}

// ---- 编辑资料 ----
const showEdit = ref(false)
const editUsername = ref('')
const editAvatar = ref('')
const uploading = ref(false)

// 选图 → 立刻上传 → 拿到 /uploads/xxx.png 存进表单
const onPickAvatar = async (e) => {
  const file = e.target.files && e.target.files[0]
  e.target.value = ''            // 允许第二次选同一个文件
  if (!file) return

  uploading.value = true
  imgBad.value = false
  try {
    const res = await uploadFile(localStorage.getItem('token'), file)
    if (res.data.error) { editMsg.value = res.data.error; return }
    editAvatar.value = res.data.url
  } catch (err) {
    editMsg.value = '上传失败：' + err.message
  } finally {
    uploading.value = false
  }
}

const clearAvatar = () => {
  editAvatar.value = ''
  imgBad.value = false
}
const editBio = ref('')
const saving = ref(false)
const imgBad = ref(false)          // 预览图加载失败
const editMsg = ref('')

// 打开弹窗时, 把当前值填进去 (不然是空的)
const openEdit = () => {
  editUsername.value = user.value.username || ''
  editAvatar.value = user.value.avatar || ''
  editBio.value = user.value.bio || ''
  imgBad.value = false
  editMsg.value = ''
  showEdit.value = true
}
// 换了地址就把"图片挂了"的标记清掉
watch(editAvatar, () => { imgBad.value = false })

const save = async () => {
  const token = localStorage.getItem('token')
  if (!token) { goLogin(router); return }
  saving.value = true
  editMsg.value = ''
  try {
    const res = await updateMe(
      token,
      editAvatar.value.trim(),
      editBio.value.trim(),
      editUsername.value.trim(),       // ★ 用户名也一起传 (没改的话后端会自己跳过)
    )
    // ⚠️ 后端业务错误是 200 + {error}, 不是异常! 要自己查
    if (res.data.error) { editMsg.value = res.data.error; return }

    // 本地也更新, 不用重新请求
    user.value.username = res.data.username
    user.value.avatar = res.data.avatar
    user.value.bio = res.data.bio
    showEdit.value = false
  } catch (err) {
    if (err.response && err.response.status === 401) {
      localStorage.removeItem('token')
      goLogin(router)
    } else {
      error.value = '保存失败：' + err.message
      showEdit.value = false
    }
  }
  saving.value = false
}

// ---- 封面装饰 (跟首页/收藏页/历史页一个套路, 纯样式) ----
const covers = ['cover-1', 'cover-2', 'cover-3', 'cover-4', 'cover-5', 'cover-6']
const coverOf = (i) => covers[i % covers.length]

// 时间 → 人话 (跟 HistoryPage 一样的写法)
const fmtTime = (s) => {
  if (!s) return ''
  const d = new Date(s.replace(' ', 'T'))
  if (isNaN(d)) return ''
  const min = Math.floor((Date.now() - d.getTime()) / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  const day = Math.floor(hr / 24)
  if (day < 7) return `${day} 天前`
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

// 加入时间只显示日期
const fmtDate = (s) => {
  if (!s) return '很久以前'
  const d = new Date(s.replace(' ', 'T'))
  if (isNaN(d)) return '很久以前'
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

// ---- 加载 ----
const load = async () => {
  loading.value = true
  error.value = ''
  try {
    // ① 先看这个人是谁 (不用登录)
    const res = await getUserProfile(userId)
    if (res.data.error) {
      error.value = res.data.error
    } else {
      user.value = res.data
    }

    // ② 顺便确认"我是不是他" —— 登录了才问
    //    【静默失败】: 这只是决定显不显示"编辑资料"按钮, 失败了不影响看主页
    const token = localStorage.getItem('token')
    if (token) {
      try {
        const me = await getMe(token)
        if (!me.data.error) {
          myId.value = me.data.id
          myName.value = me.data.username
        }
      } catch (e) {
        console.error('获取我的信息失败', e)
      }

      // ② 顺便问一次"我关注他了吗" —— 自己的主页不用问(关注自己没意义)
      if (myId.value !== userId) {
        try {
          const st = await getFollowStatus(token, userId)
          if (!st.data.error) following.value = st.data.following
        } catch (e) {
          console.error('获取关注状态失败', e)
        }
      }
    }
  } catch (e) {
    error.value = '加载失败：' + e.message
  }
  loading.value = false
}

onMounted(load)
</script>

<style scoped>
.page { max-width: 1080px; padding-top: 24px; }

.back {
  border: none; background: transparent; cursor: pointer;
  font-size: 14px; color: #4b5563; padding: 6px 12px; border-radius: 8px;
  margin-bottom: 16px;
}
.back:hover { background: #f0fdfa; color: #14b8a6; }

/* ---------- 顶部名片 ---------- */
.profile {
  display: flex; align-items: flex-start; gap: 20px;
  padding: 26px 28px; margin-bottom: 26px;
}

.avatar {
  width: 72px; height: 72px; border-radius: 50%; flex-shrink: 0; overflow: hidden;
  background: linear-gradient(135deg, #ccfbf1 0%, #a5b4fc 100%);
  display: flex; align-items: center; justify-content: center; font-size: 32px;
}
.avatar img { width: 100%; height: 100%; object-fit: cover; }
.avatar.small { width: 44px; height: 44px; font-size: 20px; }

.info { flex: 1; min-width: 0; }
.name { font-size: 22px; color: #1f2937; margin-bottom: 8px; }

/* 关注 / 粉丝 / 文章 三个数字 */
.counts {
  display: flex; align-items: center; gap: 16px;
  font-size: 13px; color: #9aa5b1; margin-bottom: 10px; flex-wrap: wrap;
}
.counts b { color: #0f766e; font-size: 15px; font-weight: 600; }
.counts .clickable { cursor: pointer; transition: opacity 0.15s; }
.counts .clickable:hover { opacity: 0.7; }
.counts .clickable:hover b { text-decoration: underline; }
.joined { margin-left: auto; }

/* ---------- 关注/粉丝列表弹窗 ---------- */
.tabs { display: flex; gap: 8px; margin-bottom: 16px; }
.tabs button {
  flex: 1; padding: 8px 0; border: none; border-radius: 10px;
  background: #f1f5f9; color: #64748b; font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.tabs button.on { background: #14b8a6; color: #fff; font-weight: 600; }

.u-list { max-height: 340px; overflow-y: auto; }
.u-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 8px; border-radius: 10px; cursor: pointer;
  transition: background 0.15s;
}
.u-item:hover { background: #f0fdfa; }
.u-avatar {
  width: 38px; height: 38px; border-radius: 50%; flex-shrink: 0; overflow: hidden;
  background: linear-gradient(135deg, #ccfbf1 0%, #a5b4fc 100%);
  display: flex; align-items: center; justify-content: center; font-size: 18px;
}
.u-avatar img { width: 100%; height: 100%; object-fit: cover; }
.u-text { flex: 1; min-width: 0; }
.u-name { font-size: 14px; color: #374151; font-weight: 500; }
.u-unfollow {
  flex-shrink: 0; margin-left: auto;
  padding: 5px 12px; border-radius: 14px;
  border: 1px solid #e6ebf2; background: #fff;
  color: #6b7280; font-size: 12px; cursor: pointer;
}
.u-unfollow:hover { color: #e74c3c; border-color: #fca5a5; background: #fef2f2; }
.u-bio {
  font-size: 12px; color: #9aa5b1; margin-top: 3px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.l-tip { font-size: 13px; color: #b6c0cc; text-align: center; padding: 30px 0; }

.bio { font-size: 14px; color: #4b5563; line-height: 1.7; word-break: break-word; }

.actions {
  flex-shrink: 0;
  display: flex; align-items: center; gap: 10px;
}

/* 关注后的小提示: 告诉用户私信是他关注的人发的, 不是系统广告 */
.follow-tip {
  margin: 10px 0 0;
  padding: 9px 14px;
  border-radius: 10px;
  background: #f0fdfa;
  border: 1px solid #ccfbf1;
  color: #0f766e;
  font-size: 13px;
}
.btn-edit {
  padding: 8px 18px; border: 1px solid #e6ebf2; border-radius: 10px;
  background: #fff; color: #64748b; font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.btn-edit:hover { border-color: #14b8a6; color: #14b8a6; }

/* 关注按钮: 没关注 = 实心; 已关注 = 白底描边 */
.btn-follow {
  padding: 8px 22px; border: none; border-radius: 10px;
  background: #14b8a6; color: #fff; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: all 0.15s;
}
.btn-follow:hover { background: #0d9488; }
.btn-follow:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-follow.on {
  background: #fff; color: #14b8a6; border: 1px solid #14b8a6;
}
.btn-follow.on:hover { background: #f0fdfa; }

/* 私信按钮 */
.btn-msg {
  padding: 8px 18px; border: 1px solid #e6ebf2; border-radius: 10px;
  background: #fff; color: #4b5563; font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.btn-msg:hover { border-color: #14b8a6; color: #0f766e; background: #f0fdfa; }

/* 第一次私信的输入框 */
.chat-textarea {
  width: 100%; min-height: 80px; padding: 10px 12px;
  border: 1px solid #e6ebf2; border-radius: 10px; outline: none;
  font-family: inherit; font-size: 14px; line-height: 1.6; resize: vertical;
}
.chat-textarea:focus { border-color: #14b8a6; }

/* ---------- 文章列表 ---------- */
.sec-title { font-size: 16px; color: #374151; margin-bottom: 14px; }

.item {
  display: flex; align-items: center; gap: 14px;
  padding: 14px 18px; margin-bottom: 10px; cursor: pointer;
}
.cover {
  width: 54px; height: 54px; border-radius: 12px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  color: rgba(15, 118, 110, 0.45);
}
.art-text { flex: 1; min-width: 0; }
.t { font-size: 15px; }
.c {
  color: #6b7280; margin-top: 5px; font-size: 13px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.item .meta { font-size: 12px; color: #9aa5b1; margin-top: 6px; margin-bottom: 0; }

.tip { text-align: center; color: #a8b2c1; padding: 60px 0; }
.empty { text-align: center; color: #a8b2c1; padding: 40px 0; font-size: 14px; }

/* ---------- 弹窗表单 ---------- */
.form { display: flex; flex-direction: column; }
.lbl { font-size: 13px; color: #64748b; margin-bottom: 6px; }
.form input, .form textarea {
  padding: 10px 14px; border: 1px solid #e6ebf2; border-radius: 10px;
  font-size: 14px; outline: none; background: #f9fcfb;
  font-family: inherit; resize: vertical; margin-bottom: 16px;
}
.form input:focus, .form textarea:focus { border-color: #14b8a6; background: #fff; }

.preview { display: flex; align-items: center; gap: 12px; }
.pv-tip { font-size: 12px; color: #9aa5b1; }
.hint { font-size: 12px; color: #9aa5b1; margin: -10px 0 16px; }
.err-msg { color: #e74c3c; font-size: 13px; margin-top: 4px; }

.m-btns { display: flex; gap: 10px; justify-content: flex-end; margin-top: 8px; }
.m-btns button {
  padding: 9px 20px; border: none; border-radius: 10px;
  font-size: 14px; cursor: pointer;
}
.cancel { background: #f1f5f9; color: #64748b; }
.cancel:hover { background: #e2e8f0; }
.ok { background: #14b8a6; color: #fff; font-weight: 600; }
.ok:hover { background: #0d9488; }
.ok:disabled { opacity: 0.6; cursor: not-allowed; }

/* ===== 头像上传 ===== */
.avatar-edit { display: flex; align-items: center; gap: 14px; margin-bottom: 6px; }
.av-actions { display: flex; flex-direction: column; gap: 6px; }
.pick-btn {
  display: inline-block; padding: 7px 14px;
  border: 1px solid #14b8a6; border-radius: 9px;
  color: #0f766e; font-size: 13px; cursor: pointer; text-align: center;
}
.pick-btn:hover { background: #f0fdfa; }
.rm-btn {
  border: none; background: none; color: #9aa5b1;
  font-size: 12px; cursor: pointer; text-align: left; padding: 0;
}
.rm-btn:hover { color: #e74c3c; }
.av-hint { font-size: 11px; color: #b6c0cc; }

.cover-img { width: 100%; height: 100%; object-fit: cover; display: block; }

/* ---- 手机: 名片改成上下排, 按钮占满一行 ---- */
@media (max-width: 640px) {
  .page { padding: 14px 12px 40px; }
  .back { margin-bottom: 10px; }

  .profile {
    flex-wrap: wrap;
    padding: 18px 16px;
    gap: 14px;
    margin-bottom: 18px;
  }
  .avatar { width: 56px; height: 56px; font-size: 26px; }
  .info { flex: 1 1 calc(100% - 70px); }
  .name { font-size: 18px; margin-bottom: 6px; }
  .counts { gap: 10px 14px; font-size: 12px; }
  .joined { margin-left: 0; flex-basis: 100%; }

  .actions { width: 100%; }
  .actions button { flex: 1; }

  .item { padding: 12px 12px; gap: 10px; }
  .cover { width: 46px; height: 46px; }
  .t { font-size: 14px; }
  .c { font-size: 12px; }
}
</style>
