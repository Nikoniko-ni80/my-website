# ============================================================
# routers/upload.py —— 文件上传
# ============================================================
# 【一句话】
#   收一个文件 → 检查 → 用随机名字存到磁盘 → 返回一个路径。
#   它【不碰数据库】, 只负责"把文件落地 + 告诉我地址"。
#
# 【为什么数据库只存路径】
#   MySQL 能存二进制 (BLOB), 但一般不这么干:
#     ① 一行几 MB, 查询 / 备份 / 主从复制都被拖慢
#     ② 读图要经过 Python: 查库 → 吐字节, 比直接读磁盘慢一个数量级
#     ③ 用不上浏览器缓存 / CDN / 断点续传
#   所以: 文件落磁盘 (以后可以换成 OSS / 七牛), 数据库只存一个字符串。
#
# 【存相对路径, 不存完整网址】
#   ✅ /uploads/8f3a.png
#   ❌ http://127.0.0.1:8000/uploads/8f3a.png
#   换域名 / 换端口 / 上 Docker / 加 CDN 时, 数据库一行都不用改。
#
# 【四个安全检查】  ← 面试可以讲
#   ① 必须登录          → 匿名的人不能往你服务器上写文件
#   ② 后缀白名单        → 只收图片, 不收 .php / .exe
#   ③ 核对文件头        → 改个后缀就能骗过 ②, 所以再看前几个字节
#   ④ 大小上限          → 不限的话一个人就能把磁盘塞满
#
# ★ 为什么文件名不能用用户传来的?
#   重名会互相覆盖; 更严重的是 "../../../etc/passwd" 这种名字能写到项目外面去
#   (这叫 路径穿越)。自己生成 uuid 名字, 只保留后缀, 用户传什么都进不来。
# ============================================================
import os
import uuid

from fastapi import APIRouter, Depends, File, UploadFile

from dependencies import get_current_user
from models import User

router = APIRouter()

# 上传目录 = myapp/uploads (跟 routers/ 同级)
# __file__ 是 routers/upload.py → 往上一级是 routers/ → 再往上一级是 myapp/
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)     # 不存在就建, 启动时执行一次

MAX_SIZE = 2 * 1024 * 1024                  # 2MB

# 后缀白名单 → 这个后缀的文件, 开头几个字节应该长什么样
ALLOWED = {
    ".png":  [b"\x89PNG\r\n\x1a\n"],
    ".jpg":  [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".gif":  [b"GIF87a", b"GIF89a"],
    ".webp": [b"RIFF"],                     # 真正的 webp 还要再查第 8~12 字节
}


def looks_like_image(ext: str, data: bytes) -> bool:
    """看文件头对不对得上这个后缀。

    ★ 只看后缀是不够的: 把一个 .exe 改名成 .png, 后缀检查就过了。
      文件头是文件内容自带的, 改后缀改不掉它。
    """
    if ext == ".webp":
        return len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return any(data.startswith(sig) for sig in ALLOWED.get(ext, []))


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),                 # 表单里的文件字段, 名字叫 file
    current_user: User = Depends(get_current_user),
):
    # ① 后缀: 取最后一段, 转小写 (A.PNG 和 a.png 一样)
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED:
        return {"error": "只支持 png / jpg / jpeg / gif / webp"}

    # ② 大小: 最多读 MAX_SIZE + 1 字节
    #    多读 1 个字节就能判断"是不是超了", 不用把整个大文件读进内存
    content = await file.read(MAX_SIZE + 1)
    if not content:
        return {"error": "文件是空的"}
    if len(content) > MAX_SIZE:
        return {"error": "图片不能超过 2MB"}

    # ③ 内容: 文件头得对得上后缀
    if not looks_like_image(ext, content):
        return {"error": "这个文件不是真正的图片"}

    # ④ 存盘: 随机名字 + 原后缀
    name = uuid.uuid4().hex + ext
    path = os.path.join(UPLOAD_DIR, name)
    with open(path, "wb") as f:
        f.write(content)

    return {
        "url": f"/uploads/{name}",     # ★ 前端拿这个存进数据库
        "size": len(content),
    }
