# ============================================================
# 前端镜像 (Vue 构建 → nginx 托管)
# ============================================================
# 【两段式构建】
#   第一段: 用 node 把 Vue 源码编译成 dist/ (一堆静态文件)
#   第二段: 只把 dist/ 拷进 nginx 镜像
#   最后镜像里没有 node_modules、没有源码, 只有最终文件 —— 小很多
# ============================================================

# ---------- 第一段: 构建 ----------
FROM node:22-alpine AS build

WORKDIR /app

# 依赖清单单独拷 → 装依赖 → 再拷源码, 同样是为了利用缓存
COPY package.json package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com

COPY . .

# ★ 这个参数决定了前端请求打到哪:
#   /api → 请求当前域名的 /api/xxx, 再由 nginx 转给后端容器
#   不传的话就是本地开发地址 (127.0.0.1:8000), 线上会连不上
ARG VITE_API_BASE=/api
ENV VITE_API_BASE=$VITE_API_BASE

RUN npm run build

# ---------- 第二段: 托管 ----------
FROM nginx:1.27-alpine

# 用我们自己的配置替换掉 nginx 自带的那份
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY site-locations.conf /etc/nginx/site-locations.conf

# 把编译产物拷进 nginx 的网站根目录
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
