# ============================================================
# mq.py —— 消息队列 (RabbitMQ)
# ============================================================
# 【它在这个项目里干什么】
#   两件事, 都是"晚一点做也没关系"的:
#     ① 延迟关单: 订单创建 30 分钟后, 如果还没付钱, 自动取消
#     ② 支付成功后扇出: 作者收益入账 / 给作者发通知
#
# 【一句话理解 RabbitMQ】
#   生产者把消息交给 Exchange(交换机), 交换机按规则丢进 Queue(队列),
#   消费者从队列里拿。消息默认"至少一次", 所以消费端必须能扛重复。
#
# 【我们的拓扑】
#   order.exchange (direct)
#       └─ order.delay.queue   ← 故意没有消费者! 消息躺在这里等 TTL 到期
#              (TTL = 30 分钟, 到期 → 死信 → 转去 order.expire.queue)
#       └─ order.expire.queue  ← 消费者: 还是 pending 就取消
#
#   payment.exchange (fanout 广播)
#       ├─ earning.queue   ← 消费者A: 记作者收益
#       └─ notify.queue    ← 消费者B: 通知作者
#
# 【为什么延迟用"TTL + 死信"而不是定时器】
#   定时器只活在当前进程里, 进程一重启就没了。
#   消息躺在 Broker 上, 重启后还在, 到点自动转出去 —— 这是 MQ 该干的活。
#   (RabbitMQ 官方插件也能做延迟, 但 TTL+DLX 是内置能力, 不用装东西)
# ============================================================
import json
import os
import threading
import time
import uuid
##先引入一些python自己的库工具

import pika
##只有pika是第三方的库,RabbitMQ 的 Python 客户端

AMQP_URL = os.getenv("AMQP_URL", "amqp://blog:123456@127.0.0.1:5672/%2F")


# amqp://      协议名 (RabbitMQ 用的协议, 不是 HTTP)
# blog:123456  用户名:密码
# 127.0.0.1    地址
# 5672         端口 (15672 是网页管理界面, 5672 才是收发消息的)
# %2F          vhost = "/" 的 URL 编码
##这里用的"AMQP_URL"是环境变量的意思，意思是优先读取环境地址，没有再看后面的那一串串作为默认


ORDER_EXCHANGE = "order.exchange"
DELAY_QUEUE = "order.delay.queue"
EXPIRE_QUEUE = "order.expire.queue"

PAYMENT_EXCHANGE = "payment.exchange"
EARNING_QUEUE = "earning.queue"
NOTIFY_QUEUE = "notify.queue"

# 订单多久没付就关。默认 30 分钟; 测试时可以设成 5000 毫秒
ORDER_TTL_MS = int(os.getenv("ORDER_TTL_MS", str(30 * 60 * 1000)))

# 消费失败最多重试几次, 超过就放弃 (真实项目会扔进死信队列等人处理)
MAX_RETRY = 3


# ------------------------------------------------------------
# 连接: 每个线程一条, 不共用
# ------------------------------------------------------------
# 【先分清两个进程, 别混】
#   你的后端 = python 进程 (Windows), 里面开了几条线程:
#       主线程            → 处理 HTTP 请求
#       order-expire      → 盯 order.expire.queue
#       payment-earning   → 盯 earning.queue
#       payment-notify    → 盯 notify.queue
#   RabbitMQ = 另一个进程 (WSL), 队列和交换机都住在它里面。
#   两边只通过 127.0.0.1:5672 说话, 不共享内存。
#
# 【线程 = 同一个进程里的多条执行流】
#   它们共享这块内存 —— 所以连接不能共用, 必须每线程一条。
#
# ★ pika 的 BlockingConnection 【不是线程安全的】。
#   两个线程共用一条连接 → 消息会串、ack 会错位, 报错还特别难懂。
#   所以用 threading.local: 每个线程自己拿一份, 互不干扰。
_local = threading.local()

##建立一条新连接同时带两个超时参数
def _new_connection() -> pika.BlockingConnection:
    params = pika.URLParameters(AMQP_URL)

    # 两个 30 防的是两件不同的事:
    #   heartbeat: 对面"悄悄死了"(断网/进程没了/机器休眠)。
    #              每 15 秒互发心跳, 60 秒什么都没收到 → 判定连接已死。
    #              ★ 这个值是双方协商的, Broker 也知道。
    #   blocked_connection_timeout: 对面"活着但罢工"(磁盘满/内存告警, 主动不收消息)。
    #              此时心跳照常正常, 只能靠这个参数发现; 等 30 秒还不恢复就抛异常。
    #              ★ 只有客户端自己知道, Broker 不管这个值。
    #   (一句话: 活着 != 能干活, 所以要两个)
    params.heartbeat = 30
    params.blocked_connection_timeout = 30
    return pika.BlockingConnection(params)


def _get_channel():
    conn = getattr(_local, "conn", None)##(从谁身上取，取哪个，默认返回值)
    ##getattr就是查找结构体属性的方法,现在就是在_local这个结构体上取他的coon属性值
    ##这个coon就是一条和mq的链接，就是上面那个函数干的
    if conn is None or conn.is_closed:
        conn = _new_connection()
        _local.conn = conn
        _local.channel = conn.channel()
        ##connection是一条tcp路通道，可以同时承载好几个后端和别的进程的链接
        ##一个链接就相当于一条路就是一个channel,多路复用
        _declare_topology(_local.channel)
    return _local.channel


def _drop_connection():
    conn = getattr(_local, "conn", None)
    try:
        if conn and conn.is_open:
            conn.close()
    except Exception:
        pass
    _local.conn = None
    _local.channel = None


# ------------------------------------------------------------
# 声明拓扑: 交换机 / 队列 / 绑定关系
# ------------------------------------------------------------
# ★ 这个操作是【幂等】的: 已经存在且参数一致就什么都不做。
#   所以每次连接建立时都跑一遍, 不怕重复。
def _declare_topology(ch):
    # ① 订单相关
    ch.exchange_declare(exchange=ORDER_EXCHANGE, exchange_type="direct", durable=True)
    ##建立交换机 (建立谁，匹配规则严格匹配，持久化(broker重启交换机也在))

    ch.queue_declare(queue=DELAY_QUEUE, durable=True, arguments={
        "x-message-ttl": ORDER_TTL_MS,          # 消息在这躺多久算过期
        "x-dead-letter-exchange": ORDER_EXCHANGE,   # 过期后转给谁
        "x-dead-letter-routing-key": "order.expire",
    })
    ##延时队列

    ch.queue_declare(queue=EXPIRE_QUEUE, durable=True)
    ch.queue_bind(queue=EXPIRE_QUEUE, exchange=ORDER_EXCHANGE, routing_key="order.expire")

    # ② 支付成功扇出
    ch.exchange_declare(exchange=PAYMENT_EXCHANGE, exchange_type="fanout", durable=True)

    ch.queue_declare(queue=EARNING_QUEUE, durable=True)
    ch.queue_bind(queue=EARNING_QUEUE, exchange=PAYMENT_EXCHANGE)
    #bind就是挂队列，看后面有个exchange就是把这个队列挂到某某交换机上面

    ch.queue_declare(queue=NOTIFY_QUEUE, durable=True)
    ch.queue_bind(queue=NOTIFY_QUEUE, exchange=PAYMENT_EXCHANGE)


# ------------------------------------------------------------
# 发消息
# ------------------------------------------------------------
def _publish(exchange: str, routing_key: str, payload: dict):
    ##(投哪个交换机，贴什么标签(让交换机知道给哪些队列)，发送内容)
    try:
        ch = _get_channel()
        ch.basic_publish(
            exchange=exchange,
            routing_key=routing_key,##放到哪个队列
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            ##把作为字典的payload数据转换成json字符串再搞成字节
            properties=pika.BasicProperties(
                delivery_mode=2,        # 2 = 持久化, Broker 重启后消息还在
                content_type="application/json",
                message_id=str(uuid.uuid4()),
            ),
        )
        return True
    except Exception as e:
        # ★ 连不上 Broker 不该把用户的请求搞挂:
        #   下单失败 → 用户莫名其妙; 关单消息丢了 → 最多订单多挂一会儿
        print(f"[MQ] 发送失败 {exchange}/{routing_key}: {e}")
        _drop_connection()
        return False


def publish_order_delay(order_id: int):
    """下单时调: 把订单扔进"30 分钟后再看"的箱子。"""
    # ★ 路由键随便写, 因为这个队列【没有绑定任何交换机】——
    #   我们直接发到默认交换机("")并用队列名当路由键, 消息就直接进队列。
    #   (默认交换机: 路由键 == 队列名 就投给那个队列)
    return _publish("", DELAY_QUEUE, {"order_id": order_id})  
    #这里第一个参数是指定交换机没有指定说明是默认交换机，就是说谁符合后面的目标标签就找谁
    ##注意这里调用了publish,执行了publish函数方法，已经写到mq里面了


def publish_payment_success(order_id: int, user_id: int, article_id: int, amount: int):
    """支付成功后调: 广播给"收益"和"通知"两个消费者。"""
    return _publish(PAYMENT_EXCHANGE, "", {
        "order_id": order_id,
        "user_id": user_id,        # 买家
        "article_id": article_id,
        "amount": amount,
    })


# ------------------------------------------------------------
# 消费: 一个队列一个线程
# ------------------------------------------------------------
def start_consumer(queue: str, handler, name: str):#哪个队列，交给谁，日志里叫什么
    """常驻通道: 后端一直连着 MQ 并订阅这个队列。

    消息一到 → 调 handler(payload) 去操作数据库。
    ★ 不是 MQ 来操作后端: MQ 只负责把消息递过来, 干活的是这条线程。
    一个队列一条线程; 断了 5 秒后自动重连。
    """
    def run():
        while True:
            try:
                conn = _new_connection()#建立进程链接
                ch = conn.channel()##连接上开通道
                _declare_topology(ch)##检查或者再定义一次对应表
                ch.basic_qos(prefetch_count=1)   # 设置通道参数，一次只拿一条消息, 做完再拿
                ##！！！！这里注意很重要，我的机制是mq那边推，就是说通道从一开始的一次http建立好(这里是mq做权限，只能后端pika自己来)之后
                ##mq就可以主动向我推东西了,这个就叫推(拉是pika请求一条他发一条)
                ##但是防止推速度过快，这里设定一个参数1，就是他发现我有一条没有ask回复就停下来，不会多发把我撑爆
                ##这种就是我的性能有多少他就推多块

                ch.basic_consume(queue=queue, on_message_callback=_make_callback(ch, handler, name))
                #这一行是去broker登记，我这个queue一旦有东西加进来就去调用后面这个函数makecallback函数
                print(f"[MQ] {name} 已启动, 监听 {queue}")
                ch.start_consuming()             # 阻塞, 直到连接断开
            except Exception as e:
                print(f"[MQ] {name} 断开, 5 秒后重连: {e}")
                time.sleep(5)

    t = threading.Thread(target=run, name=f"mq-{name}", daemon=True)
    t.start()
    return t

##makecallback返回一个"收到一条消息后怎么处理"的函数：
##解析内容 → 交给你的业务函数干活 → 成功就告诉 MQ"处理完了"；失败就重试，最多 3 次，还不行就放弃。

# handler = 后端的业务函数 (consumers.py 里的 handle_xxx)。
# 叫醒它的不是前端请求, 是队列里的消息:
#   API 函数 : 前端点名才执行一次
#   handler  : 线程一直等, 消息到了才执行一次
# 这个函数把它包进一层"ack + 重试"的壳, 返回壳 (on_message)。
def _make_callback(ch, handler, name):
    def on_message(channel, method, properties, body):
        #(当前通道，投递消息，消息属性，内容)
        try:
            payload = json.loads(body)
            handler(payload)##调用后端代码！！，这里修改数据库！！
            channel.basic_ack(method.delivery_tag) 
            ##basicack是一个方法，就是可以通知另一个mq进程broker一些信息，
            #然后后面这个tag就是告诉应该通知mq哪一条channel的东西可以告诉那边要删了
        except Exception as e:
            retry = (properties.headers or {}).get("x-retry", 0)
            print(f"[MQ] {name} 处理失败 (第 {retry + 1} 次): {e}")

            if retry + 1 >= MAX_RETRY:
                # 重试够了: 确认掉, 别无限循环把队列堵死
                # (真实项目这里是"扔进死信队列 + 告警", 我们先用日志代替)
                print(f"[MQ] {name} 放弃这条消息: {body[:200]}")
                channel.basic_ack(method.delivery_tag)
                return

            # 放回去重试: 重新发一条带 x-retry+1 的, 然后把原来的确认掉
            try:
                channel.basic_publish(
                    exchange="",
                    routing_key=method.routing_key,
                    body=body,
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                        content_type="application/json",
                        headers={"x-retry": retry + 1},
                    ),
                )
                channel.basic_ack(method.delivery_tag)
            except Exception as e2:
                print(f"[MQ] {name} 重投失败: {e2}")
                channel.basic_nack(method.delivery_tag, requeue=True)

    return on_message
