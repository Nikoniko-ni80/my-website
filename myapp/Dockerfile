# ============================================================
# 后端镜像 (FastAPI)
# ============================================================
# 基础镜像: python:3.12-slim —— 官方精简版 Python, 不带一堆用不上的系统工具
# (slim 大约 130MB; alpine 更小, 但 bcrypt/cryptography 这类库
#  在 alpine 上经常没有现成轮子, 要现场编译, 反而更慢更容易出错)
FROM python:3.12-slim

WORKDIR /app

# PYTHONDONTWRITEBYTECODE: 不生成 __pycache__ (容器里没必要)
# PYTHONUNBUFFERED: 日志直接吐出来, docker logs 能实时看到
# (不加的话 Python 会攒着缓冲, 容器里看起来像"日志卡住了")
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 先只拷依赖清单 → 装依赖 → 再拷代码
# ★ 顺序很重要: 代码改了以后重建镜像, 这一层还能用缓存,
#   不用每次重新 pip install (那是构建里最慢的一步)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
        -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

# 上传目录: 容器里先建好。真跑的时候会用 volume 挂进来,
# 这样图片存在宿主机上, 删了容器也不会丢。
RUN mkdir -p /app/uploads

EXPOSE 8000

# ★ 为什么先 create_tables?
#   全新数据库里一张表都没有, 直接启动会在第一个请求时报错。
#   create_all 是幂等的: 表已经存在就什么都不做, 所以每次启动跑一遍没坏处。
#
# ★ 为什么 --workers 1?
#   我们的 MQ 消费者、后台线程是在应用启动时拉起来的。
#   多开 worker 的话每个进程都会各起一套消费者, 同一条消息会被消费好几遍。
#   要扩多进程, 得先把消费者拆成单独的服务 —— 这个项目先不折腾。
# ★ 为什么要用 until 循环重试?
#   MySQL 第一次启动时要先初始化(导入 init.sql), 这中间它会把自己重启一次。
#   就在这个空档里, 后端可能连上一下又断掉。
#   不加循环的话后端会直接崩掉、等 Docker 重启它 —— 能恢复, 但日志很难看。
#   加了循环就是: 连不上就等 2 秒再试, 直到连上为止。
CMD ["sh", "-c", "until python create_tables.py; do echo '[wait] MySQL 还没准备好, 2 秒后重试...'; sleep 2; done; exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1"]
