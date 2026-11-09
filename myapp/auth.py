# ============================================================
# auth.py - 安全相关: 密码加密 + JWT Token
# ============================================================
import os

import bcrypt
from datetime import datetime, timedelta, timezone
from jose import jwt

# ---------- Token 配置 (这三个各是啥) ----------
# SECRET_KEY = 一串保密的字符串, 是"签名用的密钥"(相当于服务器自己的公章)
#   签 Token 用它盖戳、验 Token 用它验戳; 谁拿到它就能伪造 Token → 必须保密。
#   注意: 它不是"方法", 也不是"用户密码", 是"服务器盖章用的钥匙"。
#   (真项目要放环境变量, 不写死在代码里; 这里的 change-me 就是提醒你换)
# ALGORITHM = 一个字符串, 是"签名算法的名字"(HS256 = 一种标准盖章方式)。
#   库读到这个名字, 就用对应的算法来算签名。
# EXPIRE_MINUTES = Token 多久过期(分钟); 60 表示 60 分钟后失效。
# ★ 上线时一定要用环境变量 SECRET_KEY 换掉这串默认值。
#   换完之后, 原来签发的 Token 全部失效 —— 所有人都得重新登录, 这是正常的。
SECRET_KEY = os.getenv("SECRET_KEY", "qi-secret-key-change-me-in-real-project")
ALGORITHM = "HS256"
# ★ 默认 60 分钟; 线上用环境变量调长 (比如 7 天), 免得写文章写到一半过期
EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "60"))


def hash_password(password: str) -> str:
    """把明文密码 → 哈希值 (存库时用)"""
    pwd_bytes = password.encode("utf-8")        # 密码转成字节
    #把字符串转成字节(1/0)，因为bcrypt只能把字节作为参数输入
    salt = bcrypt.gensalt()                      # 生成随机"盐"
    # 盐 = 加密前撒的随机"佐料", 每个用户不同
    # 作用: 让同样密码("123456")加密出来的结果也不同 → 防"一次算好破所有人"(彩虹表)
    # 盐不是秘密(就明文存在哈希里), 价值在"每人不同", 不在"藏起来"
    hashed = bcrypt.hashpw(pwd_bytes, salt)      # 加密
    # 把 [密码+盐] 算成一串乱码(哈希) —— 单向: 密码→乱码能算, 乱码→密码反推不出
    # 这一步故意"慢"(约0.1秒): 正常用户只算1次(无感), 黑客爆破要试几百万次(每次0.1秒 → 拖垮)
    return hashed.decode("utf-8")                # 转回字符串(存库用)
    # 哈希格式是固定的: $2b$12$盐(22位)+结果(31位)  —— 盐永远在固定位置, 验证时按格式切出来复用


def verify_password(plain: str, hashed: str) -> bool:
    #plain是这一次输入的密码(字符串), hashed是数据库里面存的那一串乱码
    """验证: 输入的明文密码 跟 库里存的哈希 对不对 (登录时用)"""
    return bcrypt.checkpw(
        plain.encode("utf-8"),                   # 输入的密码(转字节)
        hashed.encode("utf-8"),                  # 库里存的哈希(转字节)
    )
    # checkpw(两个参数, 都要字节类) 内部干了啥:
    #   ① 把第二个参数(hashed)解读识别, 找出其中的"盐"部分
    #   ② 用这个盐作用于第一个参数(plain), 做一次 hashpw 操作(重算一遍)
    #   ③ 把算出来的结果, 跟第二个参数(hashed)比较 → 一样 True / 不一样 False
    # 所以: 不用"解开"原密码, 而是"取盐 → 重算 → 对比"


def create_token(user_id: int) -> str:
    """生成 Token: 把 user_id 装进去 + 过期时间, 签名后返回字符串"""
    # payload = 载荷, 装要携带的信息 + 过期时间
    payload = {
        "user_id": user_id,                                              # 你是谁
        "exp": datetime.now(timezone.utc) + timedelta(minutes=EXPIRE_MINUTES),  # 过期时间
    }
    # jwt.encode = 用 SECRET_KEY 签名, 生成 "头部.载荷.签名" 三段字符串
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    # jwt.encode 三个参数的角色:
    #   ① payload   = 要装进去的信息 (user_id + exp 那个字典)
    #   ② SECRET_KEY= 盖章的工具 (用它生成签名)
    #   ③ algorithm = 按哪个算法的规则签
    # 一句话: a 是要打包装进去的内容, b 是工具, c 是规则


def decode_token(token: str) -> dict:
    """验证并解析 Token: 签名对就返回内容(user_id等); 签名不对或过期会抛异常"""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    # jwt.decode 三个参数的角色:
    #   ① token      = 要拆的票 (待验证的 Token)
    #   ② SECRET_KEY = 验章的工具 (用它重算签名, 跟 Token 里的签名比对不对)
    #   ③ algorithms = 按哪个算法的规则验 (["HS256"] 是列表)
    # 一句话: a 是要验的东西, b 是工具, c 是规则
