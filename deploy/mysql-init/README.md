# 数据库初始化说明

这个文件夹里的 `.sql` **不进 git**（里面有用户数据），但服务器第一次启动时要用。

## 它是干什么的

`docker-compose.yml` 里把本文件夹挂到了 MySQL 容器的 `/docker-entrypoint-initdb.d`。
MySQL **第一次**启动（数据卷还是空的）会自动执行里面的 `.sql`，把表结构和数据导进去。

## 怎么重新生成

在本地数据库正常运行时：

```bash
mysqldump -uroot -p123456 \
  --default-character-set=utf8mb4 \
  --single-transaction --no-tablespaces \
  myapp_db > deploy/mysql-init/01-init.sql
```

## 注意

- 只在 MySQL **第一次初始化**时执行；数据卷已经有数据就不会再跑
- 想重新初始化，得先把数据卷删掉（会丢数据）：
  `docker compose down -v`
- 如果是全新的线上服务器、不需要旧数据，可以整个文件夹留空，让后端启动时自己建表
