# ============================================================
# cache.py - Redis 缓存连接 (跟 database.py 连 MySQL 一个套路)
# ============================================================
import redis

# 连接 Redis (数据在内存里, 比 MySQL 快得多)
redis_client = redis.Redis(  #这个redif.Redis相当于sql的engine,在后面{}设置地址和端口
    host="localhost",
    port=6379,
    decode_responses=True,   # 让取出来的是字符串, 不是字节
    #加密部分的两种编码  "abc".encode()   字符串编码为字节
    #                   b"abc".decode()   字节解码为字符串
)
