# ============================================================
# launcher.py —— 项目控制台 (一个小网页, 用来启停三个服务)
# ============================================================
# 运行: python launcher.py      (或者双击 控制台.bat)
# 打开: http://127.0.0.1:5001/
#
# 【它是怎么工作的】
#   这个文件自己就是一个 FastAPI 服务 (跑在 5001)。
#   它做的事:
#     ① 提供一个网页 (GET /)             —— 那个控制台界面
#     ② 提供"查状态"的接口 (GET /api/status) —— 挨个端口探一下通不通
#     ③ 提供"启停"的接口 (POST /api/...)     —— 用 subprocess 执行命令
#
#   ★ 核心难点是"怎么知道服务在不在跑":
#     看端口。用 socket 去连一下那个端口, 连得上 = 在跑, 连不上 = 没跑。
#     这比"看进程名"靠谱 —— 进程名可能是别的程序。
# ============================================================
import subprocess
import socket
import sys
import webbrowser
from threading import Timer

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

# ---------- 路径配置 (改项目位置就改这里) ----------
MYSQL_BIN = r"C:\Users\qi\mysql\bin\mysqld.exe"
MYSQL_BASEDIR = "C:/Users/qi/mysql"
MYSQL_DATADIR = "C:/Users/qi/mysql/data"

# ★ 这两个改成"跟着 launcher.py 自己走" —— 不写死绝对路径。
#   为什么? 写死路径的话, 哪天你把整个项目文件夹挪个地方(换电脑 / 换个盘 /
#   放进 git 仓库的子目录), 这里就失效了, 而且报的错是"找不到目录", 很难想到是这。
#   os.path.dirname(__file__) = "launcher.py 自己所在的文件夹"
#   所以 launcher.py 跟 myapp / myapp-frontend 放同一层就行。
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(_HERE, "myapp")
FRONTEND_DIR = os.path.join(_HERE, "myapp-frontend")

PORT = 5001          # 控制台自己占的端口

# ---------- 三个服务的定义 ----------
#   每个服务记两件事: 用哪个端口判断"活没活" + 用什么命令启动
SERVICES = [
    {
        "key": "mysql",
        "label": "MySQL",
        "port": 3306,
        "cwd": None,          # mysqld 不需要工作目录
        "cmd": f'"{MYSQL_BIN}" --basedir="{MYSQL_BASEDIR}" --datadir="{MYSQL_DATADIR}"',
    },
    {
        "key": "backend",
        "label": "后端 FastAPI",
        "port": 8000,
        "cwd": BACKEND_DIR,   # ★ 必须在这个目录跑, 不然 from routers import ... 会找不到
        "cmd": "python -m uvicorn main:app",
    },
    {
        "key": "frontend",
        "label": "前端 Vue",
        "port": 5173,
        "cwd": FRONTEND_DIR,
        "cmd": "npm run dev",
    },
]


# ---------- 判断端口是否有人在监听 ----------
def port_alive(port: int) -> bool:
    """连一下这个端口, 连得上就说明有服务在跑"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) == 0


# ---------- 启动一个服务 ----------
def start_service(svc: dict):
    if port_alive(svc["port"]):
        return False, "已经在跑了"
    try:
        # CREATE_NEW_CONSOLE = 开一个【新窗口】跑, 这样能看到日志
        #   (不这么做的话, 子进程的输出会跟控制台混在一起, 看不清)
        subprocess.Popen(
            svc["cmd"],
            cwd=svc["cwd"],
            shell=True,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
        )
        return True, "已启动（等几秒再刷新看状态）"
    except Exception as e:
        return False, f"启动失败: {e}"


# ---------- 停止一个服务 ----------
def stop_service(svc: dict) -> tuple:
    """停服务 = 把占用这个端口的进程杀掉"""
    port = svc["port"]
    if not port_alive(port):
        return False, "本来就没在跑"

    try:
        # netstat 找出占这个端口的进程号 (最后一列就是 PID)
        out = subprocess.run(
            f'netstat -ano | findstr ":{port} "',
            shell=True, capture_output=True, text=True,
        ).stdout

        pids = set()
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[3] == "LISTENING":
                pids.add(parts[4])

        if not pids:
            return False, "没找到占用这个端口的进程"

        for pid in pids:
            subprocess.run(["taskkill", "/F", "/PID", pid],
                           capture_output=True, shell=True)
        return True, f"已停止 (杀掉了 {len(pids)} 个进程)"
    except Exception as e:
        return False, f"停止失败: {e}"


# ---------- 查所有服务的状态 ----------
def all_status():
    return [
        {
            "key": s["key"],
            "label": s["label"],
            "port": s["port"],
            "running": port_alive(s["port"]),
        }
        for s in SERVICES
    ]


def find(key):
    return next((s for s in SERVICES if s["key"] == key), None)


# ============================================================
# FastAPI 应用
# ============================================================
app = FastAPI()


@app.get("/api/status")
def api_status():
    return all_status()


@app.post("/api/start/{key}")
def api_start(key: str):
    svc = find(key)
    if not svc:
        return {"ok": False, "msg": "没有这个服务"}
    ok, msg = start_service(svc)
    return {"ok": ok, "msg": msg}


@app.post("/api/stop/{key}")
def api_stop(key: str):
    svc = find(key)
    if not svc:
        return {"ok": False, "msg": "没有这个服务"}
    ok, msg = stop_service(svc)
    return {"ok": ok, "msg": msg}


@app.post("/api/start-all")
def api_start_all():
    msgs = []
    for s in SERVICES:
        ok, msg = start_service(s)
        msgs.append(f"{s['label']}: {msg}")
    return {"ok": True, "msg": " / ".join(msgs)}


@app.post("/api/stop-all")
def api_stop_all():
    msgs = []
    # 倒着停 (前端 → 后端 → MySQL), 跟手工关的顺序一致
    for s in reversed(SERVICES):
        ok, msg = stop_service(s)
        msgs.append(f"{s['label']}: {msg}")
    return {"ok": True, "msg": " / ".join(msgs)}


@app.get("/", response_class=HTMLResponse)
def page():
    return PAGE


# ============================================================
# 控制台页面 (就是一个 HTML 字符串, 直接返回给浏览器)
# ============================================================
PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>项目控制台</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, "Microsoft YaHei", sans-serif;
    background: linear-gradient(135deg, #f0fdfa 0%, #eff6ff 100%);
    min-height: 100vh; display: flex; align-items: center; justify-content: center;
  }
  .box {
    width: 520px; background: #fff; border-radius: 20px; padding: 30px 34px;
    box-shadow: 0 18px 50px rgba(20, 184, 166, 0.16);
  }
  h1 { font-size: 21px; color: #1f2937; margin-bottom: 4px; }
  .sub { font-size: 12px; color: #9aa5b1; margin-bottom: 22px; }

  .row {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 16px; border-radius: 12px;
    border: 1px solid #eef1f6; margin-bottom: 10px;
    transition: all .15s;
  }
  .row:hover { border-color: #ccfbf1; }
  .dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .on  { background: #14b8a6; box-shadow: 0 0 0 4px rgba(20,184,166,.16); }
  .off { background: #d1d8e0; }
  .label { flex: 1; font-size: 14px; color: #374151; }
  .label small { color: #9aa5b1; font-size: 11px; margin-left: 6px; }
  .state { font-size: 12px; color: #9aa5b1; width: 48px; text-align: right; }
  .on-text { color: #0f766e; font-weight: 600; }

  button {
    padding: 7px 16px; border: none; border-radius: 9px;
    font-size: 13px; cursor: pointer; font-family: inherit;
    transition: all .15s;
  }
  .btn-start { background: #14b8a6; color: #fff; }
  .btn-start:hover { background: #0d9488; }
  .btn-stop { background: #f1f5f9; color: #64748b; }
  .btn-stop:hover { background: #e74c3c; color: #fff; }

  .actions { display: flex; gap: 10px; margin-top: 22px; }
  .actions button { flex: 1; padding: 12px; font-size: 14px; font-weight: 600; }
  .all-on { background: #14b8a6; color: #fff; }
  .all-on:hover { background: #0d9488; }
  .all-off { background: #fff; color: #64748b; border: 1px solid #e6ebf2; }
  .all-off:hover { border-color: #e74c3c; color: #e74c3c; }

  .msg {
    margin-top: 16px; padding: 11px 14px; border-radius: 10px;
    background: #f0fdfa; color: #0f766e; font-size: 13px; line-height: 1.6;
  }
  .links { margin-top: 18px; font-size: 12px; color: #9aa5b1; text-align: center; }
  .links a { color: #14b8a6; text-decoration: none; }
  .links a:hover { text-decoration: underline; }
</style>
</head>
<body>
<div class="box">
  <h1>🎛️ 项目控制台</h1>
  <div class="sub">启停三个服务 · 状态每 2 秒自动刷新</div>

  <div id="list">加载中…</div>

  <div class="actions">
    <button class="all-on"  onclick="act('/api/start-all')">一键全启动</button>
    <button class="all-off" onclick="act('/api/stop-all')">一键全停止</button>
  </div>

  <div class="msg" id="msg" style="display:none"></div>

  <div class="links">
    <a href="http://localhost:5173/" target="_blank">前端页面</a> ·
    <a href="http://127.0.0.1:8000/docs" target="_blank">接口文档</a>
  </div>
</div>

<script>
const list = document.getElementById('list')
const msgBox = document.getElementById('msg')
let busy = false

// 拉状态, 重画列表
async function refresh() {
  if (busy) return
  const res = await fetch('/api/status')
  const data = await res.json()
  list.innerHTML = data.map(s => `
    <div class="row">
      <span class="dot ${s.running ? 'on' : 'off'}"></span>
      <span class="label">${s.label}<small>:${s.port}</small></span>
      <span class="state ${s.running ? 'on-text' : ''}">${s.running ? '运行中' : '已停止'}</span>
      ${s.running
        ? `<button class="btn-stop"  onclick="act('/api/stop/${s.key}')">停止</button>`
        : `<button class="btn-start" onclick="act('/api/start/${s.key}')">启动</button>`}
    </div>
  `).join('')
}

// 点按钮 → 调接口 → 显示结果
async function act(url) {
  busy = true
  show('处理中…')
  try {
    const res = await fetch(url, { method: 'POST' })
    const d = await res.json()
    show(d.msg)
  } catch (e) {
    show('出错了：' + e.message)
  }
  busy = false
  // 等一会儿再刷新 —— 服务启动需要时间, 立刻刷新会显示"还没起来"
  setTimeout(refresh, 1200)
}

function show(text) {
  msgBox.style.display = 'block'
  msgBox.textContent = text
}

refresh()
setInterval(refresh, 2000)     // 每 2 秒自动刷新一次
</script>
</body>
</html>
"""


# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    url = f"http://127.0.0.1:{PORT}/"
    print("=" * 50)
    print("  项目控制台")
    print(f"  {url}")
    print("  关掉这个窗口就是关掉控制台 (服务不受影响)")
    print("=" * 50)

    # 等服务器起来再开浏览器 (1.5 秒后)
    Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
