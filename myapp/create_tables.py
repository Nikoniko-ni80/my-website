# ============================================================
# create_tables.py - 根据 models 里的类, 自动建表
# 运行: python create_tables.py
# ============================================================
from database import Base, engine
import models   # 导入 models, 让 User 类被 Base 知道 (不导入就不认)

# create_all = "把 Base 管的所有 Model 对应的表都建出来"(已存在的表不会动)
Base.metadata.create_all(engine)
print("表创建完成! 去 DBeaver 看 myapp_db 里的 users 表")
