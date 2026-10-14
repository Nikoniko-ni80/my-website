-- MySQL dump 10.13  Distrib 8.4.9, for Win64 (x86_64)
--
-- Host: localhost    Database: myapp_db
-- ------------------------------------------------------
-- Server version	8.4.9

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `articles`
--

DROP TABLE IF EXISTS `articles`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `articles` (
  `id` int NOT NULL AUTO_INCREMENT,
  `title` varchar(100) NOT NULL,
  `content` text,
  `user_id` int NOT NULL,
  `created_at` datetime DEFAULT (now()),
  `is_public` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `articles_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=24 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `articles`
--

LOCK TABLES `articles` WRITE;
/*!40000 ALTER TABLE `articles` DISABLE KEYS */;
INSERT INTO `articles` VALUES (1,'updated title','updated content',4,'2026-09-16 09:39:59',1),(4,'前端','1111',5,'2026-09-16 11:50:43',0),(5,'public article','everyone can see',4,'2026-09-18 08:37:57',1),(6,'private article','only me',4,'2026-09-18 08:37:58',0),(7,'public one','大家好',4,'2026-09-18 08:44:37',1),(8,'private one','me only',4,'2026-09-18 08:44:37',0),(10,'我的第一篇博客','大家好，这是我第一次写博客，请多关照。',1,'2026-09-23 11:42:47',1),(11,'周末去了趟成都','吃了火锅、串串、兔头，太好吃了。',1,'2026-09-23 11:42:47',1),(12,'私人日记','今天心情不太好，不想让别人看到。',1,'2026-09-23 11:42:47',0),(13,'前端学习路线分享','从 HTML 到 Vue，我走过的弯路都写在这了。',9,'2026-09-23 11:42:47',1),(14,'CSS 布局踩坑记录','flex 和 grid 到底该用哪个？',9,'2026-09-23 11:42:47',1),(15,'我的简历草稿','这里是我的个人信息，先不公开。',9,'2026-09-23 11:42:47',0),(16,'Python 爬虫入门','requests + BeautifulSoup 抓一个小说网站。',10,'2026-09-23 11:42:48',1),(17,'数据库索引到底是啥','用大白话讲讲 B+ 树。',10,'2026-09-23 11:42:48',1),(18,'MySQL 事务隔离级别','脏读、不可重复读、幻读，一次讲清。',10,'2026-09-23 11:42:48',1),(19,'我用 FastAPI 写了个博客','前后端分离，踩了不少坑。',6,'2026-09-23 11:42:48',1),(20,'收藏功能的实现思路','为什么要用中间表。',6,'2026-09-23 11:42:48',1),(21,'还没写完的草稿','先存着，别让人看见。',6,'2026-09-23 11:42:48',0),(23,'aaa','？？？？',11,'2026-10-05 23:21:12',1);
/*!40000 ALTER TABLE `articles` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `collections`
--

DROP TABLE IF EXISTS `collections`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `collections` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `user_id` int NOT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `collections_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `collections`
--

LOCK TABLES `collections` WRITE;
/*!40000 ALTER TABLE `collections` DISABLE KEYS */;
INSERT INTO `collections` VALUES (1,'默认收藏夹',6,'2026-09-21 10:56:19'),(2,'english-test',6,'2026-09-21 10:56:32'),(3,'前端好文',6,'2026-09-21 10:56:36'),(4,'默认收藏夹',4,'2026-09-21 10:56:59'),(5,'akak',4,'2026-09-21 10:57:10'),(6,'默认收藏夹',7,'2026-09-21 14:46:09'),(10,'默认收藏夹',11,'2026-09-23 18:04:57');
/*!40000 ALTER TABLE `collections` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `comments`
--

DROP TABLE IF EXISTS `comments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `comments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `content` text NOT NULL,
  `user_id` int NOT NULL,
  `article_id` int NOT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `article_id` (`article_id`),
  CONSTRAINT `comments_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `comments_ibfk_2` FOREIGN KEY (`article_id`) REFERENCES `articles` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `comments`
--

LOCK TABLES `comments` WRITE;
/*!40000 ALTER TABLE `comments` DISABLE KEYS */;
INSERT INTO `comments` VALUES (1,'nice article!',4,5,'2026-09-20 20:13:34'),(2,'second comment',4,5,'2026-09-20 20:13:34'),(3,'我的第一篇文章',4,7,'2026-09-20 20:16:36'),(4,'写的很好',5,7,'2026-09-20 20:16:54'),(5,'？',4,7,'2026-09-20 20:33:53'),(6,'my own private note',4,6,'2026-09-20 20:35:23'),(7,'ok',4,5,'2026-09-20 20:35:23'),(12,'111',11,20,'2026-09-29 19:32:27'),(13,'111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111',11,20,'2026-09-29 19:32:43');
/*!40000 ALTER TABLE `comments` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `favorites`
--

DROP TABLE IF EXISTS `favorites`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `favorites` (
  `id` int NOT NULL AUTO_INCREMENT,
  `collection_id` int NOT NULL,
  `article_id` int NOT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_collection_article` (`collection_id`,`article_id`),
  KEY `article_id` (`article_id`),
  CONSTRAINT `favorites_ibfk_1` FOREIGN KEY (`collection_id`) REFERENCES `collections` (`id`),
  CONSTRAINT `favorites_ibfk_2` FOREIGN KEY (`article_id`) REFERENCES `articles` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=20 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `favorites`
--

LOCK TABLES `favorites` WRITE;
/*!40000 ALTER TABLE `favorites` DISABLE KEYS */;
INSERT INTO `favorites` VALUES (2,5,1,'2026-09-21 10:57:15'),(3,1,1,'2026-09-21 15:06:19'),(4,1,4,'2026-09-21 15:06:19'),(5,3,1,'2026-09-21 15:06:19'),(6,3,5,'2026-09-21 15:06:19'),(8,5,7,'2026-09-23 11:36:36'),(15,4,5,'2026-09-23 17:49:01'),(19,10,20,'2026-09-29 19:32:01');
/*!40000 ALTER TABLE `favorites` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `feedbacks`
--

DROP TABLE IF EXISTS `feedbacks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `feedbacks` (
  `id` int NOT NULL AUTO_INCREMENT,
  `content` text NOT NULL,
  `contact` varchar(100) DEFAULT NULL,
  `user_id` int NOT NULL,
  `created_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `feedbacks_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `feedbacks`
--

LOCK TABLES `feedbacks` WRITE;
/*!40000 ALTER TABLE `feedbacks` DISABLE KEYS */;
INSERT INTO `feedbacks` VALUES (1,'这个网站做得不错！','me@qq.com',6,'2026-09-29 19:14:06'),(2,'希望加个深色模式','',6,'2026-09-29 19:14:06');
/*!40000 ALTER TABLE `feedbacks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `histories`
--

DROP TABLE IF EXISTS `histories`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `histories` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `article_id` int NOT NULL,
  `viewed_at` datetime DEFAULT (now()),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_user_article_history` (`user_id`,`article_id`),
  KEY `article_id` (`article_id`),
  CONSTRAINT `histories_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `histories_ibfk_2` FOREIGN KEY (`article_id`) REFERENCES `articles` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `histories`
--

LOCK TABLES `histories` WRITE;
/*!40000 ALTER TABLE `histories` DISABLE KEYS */;
INSERT INTO `histories` VALUES (5,11,20,'2026-09-30 14:12:39'),(6,11,18,'2026-09-29 19:24:32'),(7,11,19,'2026-09-29 19:30:04'),(8,4,23,'2026-10-08 15:36:29'),(9,4,20,'2026-10-08 15:36:51'),(10,4,19,'2026-10-08 15:36:32'),(11,6,10,'2026-10-08 14:27:06'),(12,6,11,'2026-10-08 14:20:06'),(13,6,12,'2026-10-08 14:13:06'),(14,6,1,'2026-10-08 15:30:06'),(15,6,5,'2026-10-08 15:02:06'),(16,6,6,'2026-10-08 14:55:06'),(17,6,7,'2026-10-08 14:48:06'),(18,6,8,'2026-10-08 14:41:06'),(19,6,4,'2026-10-08 15:09:06'),(20,6,19,'2026-10-08 13:24:06'),(21,6,20,'2026-10-08 13:17:06'),(22,6,21,'2026-10-08 13:10:06'),(23,6,13,'2026-10-08 14:06:06'),(24,6,14,'2026-10-08 13:59:06'),(25,6,15,'2026-10-08 13:52:06'),(26,6,16,'2026-10-08 13:45:06'),(27,6,17,'2026-10-08 13:38:06'),(28,6,18,'2026-10-08 13:31:06'),(29,6,23,'2026-10-08 12:56:06');
/*!40000 ALTER TABLE `histories` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(200) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `users`
--

LOCK TABLES `users` WRITE;
/*!40000 ALTER TABLE `users` DISABLE KEYS */;
INSERT INTO `users` VALUES (1,'xiaoming','$2b$12$8r3xosA.Et8KkTHEaYIyP.fmwGQR7r04L/kmfIhQXIbR0NJOAvFPW'),(2,'testuser','$2b$12$5DIXLAU367T/Uf5CbLTn5us.XD6ZNe0THZ4xbFSIF2NELxRdseK9y'),(3,'frontend_test','$2b$12$TyVkHZBmQ1i0eeytCGKsJ.SsOhwR2lO3NTEP1XuI05kOunv3HyGyO'),(4,'xiaoli','$2b$12$Vu6XAfhtkQ3PB5om9BbfKOw8MzSpvSzKlWXLB5UFwUADVIXEL7N3K'),(5,'like','$2b$12$B3KQLNzhrCarMVC.wZ7o0Odat/aU.gNGq3YWi6lDE88y1sh5waKci'),(6,'favtest','$2b$12$OXFRLqAdCYsMi.g0ZEfXrOhAepkneHnY1pdVaAFXS9r/t95FAJU3S'),(7,'brandnew','$2b$12$097WnEduVyK.iR.4LqSqk.oIXWmxbTrKV/PXg326/ko9vCWg4HpT6'),(9,'xiaohong','$2b$12$22us8dCGSRpYZXCBbSxkou4ocOpVNmto9heaoeNGMjfINzUn61cpy'),(10,'xiaogang','$2b$12$3VE61Sb3RygDM34qzJV7oOpDAtAhGGwEnSyxIFxE1RSng.wxoKaxm'),(11,'k\'k','$2b$12$92Zl5P9kjFLPBesfynPkIuRkReCfl82RU6mhF3f/QhErvsWFdAUVK');
/*!40000 ALTER TABLE `users` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-10-09 18:59:40
