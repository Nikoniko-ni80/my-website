import { API_BASE } from '../services/authApi.js'

// 数据库里存的是相对路径（/uploads/xxx.png），显示时补上后端地址。
// 老的绝对地址（http://...）原样返回。
export const mediaUrl = (path) => {
  if (!path) return ''
  if (/^https?:\/\//i.test(path) || path.startsWith('data:')) return path
  return API_BASE + path
}
