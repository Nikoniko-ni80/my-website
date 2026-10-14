# ============================================================
# database.py - 数据库连接相关 (跟数据库打交道的东西都在这)
# ============================================================
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 连接串: 连到项目的库 myapp_db
DATABASE_URL = "mysql+pymysql://root:123456@localhost/myapp_db?charset=utf8mb4"

engine = create_engine(DATABASE_URL)      # 引擎
Base = declarative_base()                 # 所有 Model 的父类
SessionLocal = sessionmaker(bind=engine)  # 会话工厂


# ---------- get_db: 给 FastAPI 用的"会话依赖" ----------
# 作用: 每个请求来 → 开一个会话 → 用完自动关
# (这是 FastAPI 的标准写法, 后面接口函数里我们会用到它)
def get_db():
    db = SessionLocal()      # 开一个会话
    try:
        yield db             # 把会话"交给"接口函数用
        #有了这一步才有隔壁的db: Session = Depends(get_db)
    finally:
        db.close()           # 请求结束, 自动关闭
