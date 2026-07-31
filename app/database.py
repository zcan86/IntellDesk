# -*- coding: utf-8 -*-
"""SQLite 数据库 — 用户 + 订单

零依赖，零配置，文件存储 data/orders.db
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from loguru import logger

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "orders.db"

# ── 用户表（轻量，无密码）─────────────────────────────────────

_USERS = [
    ("u001", "张三", "13800000001"),
    ("u002", "李四", "13800000002"),
    ("u003", "王五", "13800000003"),
]

# ── 订单表 ────────────────────────────────────────────────────

_ORDERS = [
    ("DD20240701001", "u001", "Nike Air Force 1 '07 白色", 899, 1, "已签收",
     "2025-07-01 10:30:00", "北京市朝阳区xxx路1号", "SF1234567890", 42),
    ("DD20240715001", "u001", "Nike Dunk Low Retro 熊猫", 799, 1, "运输中",
     "2025-07-15 14:20:00", "北京市朝阳区xxx路1号", "YT9876543210", 40),
    ("DD20240720001", "u002", "Nike Air Max 97 银色子弹", 1199, 1, "已签收",
     "2025-07-20 09:15:00", "上海市浦东新区xxx路2号", "SF1122334455", 42),
    ("DD20240725001", "u002", "Nike ZoomX Vaporfly 3 竞速", 2599, 1, "待发货",
     "2025-07-25 16:45:00", "上海市浦东新区xxx路2号", None, 44),
    ("DD20240728001", "u003", "Nike Air Jordan 1 Retro High OG", 1499, 1, "运输中",
     "2025-07-28 11:00:00", "广州市天河区xxx路3号", "ZT5566778899", 43),
    ("DD20240730001", "u003", "Nike React Infinity Run 4", 1099, 1, "已签收",
     "2025-07-30 08:30:00", "广州市天河区xxx路3号", "SF9988776655", 41),
    ("DD20240731001", "u001", "Nike Blazer Mid '77 Vintage", 749, 1, "待付款",
     "2025-07-31 10:00:00", "北京市朝阳区xxx路1号", None, 39),
]


def init_db():
    """创建表 + 写入初始数据（幂等）"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            phone TEXT
        );
        CREATE TABLE IF NOT EXISTS return_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            return_id TEXT UNIQUE NOT NULL,
            order_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            reason TEXT,
            request_type TEXT DEFAULT '退货退款',
            status TEXT DEFAULT '待审核',
            created_at TEXT NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER DEFAULT 1,
            status TEXT DEFAULT '待付款',
            created_at TEXT NOT NULL,
            shipping_address TEXT,
            tracking_number TEXT,
            shoe_size INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)

    # 幂等写入
    for u in _USERS:
        conn.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", u)
    for o in _ORDERS:
        conn.execute(
            "INSERT OR IGNORE INTO orders(order_id, user_id, product_name, price, quantity, status, created_at, shipping_address, tracking_number, shoe_size) VALUES (?,?,?,?,?,?,?,?,?,?)",
            o,
        )

    conn.commit()
    conn.close()
    logger.info(f"数据库就绪: {DB_PATH}")


# ── 查询接口 ──────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_order(order_id: str) -> dict | None:
    """查询单个订单"""
    conn = get_connection()
    row = conn.execute(
        "SELECT o.*, u.name as user_name FROM orders o JOIN users u ON o.user_id = u.user_id WHERE o.order_id = ?",
        (order_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_orders(user_id: str) -> list[dict]:
    """查询用户的所有订单"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user(user_id: str) -> dict | None:
    """查询用户信息"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_return_request(order_id: str, reason: str, request_type: str = "退货退款") -> dict:
    """创建退换货申请，返回结果"""
    conn = get_connection()

    # 查订单
    order = conn.execute(
        "SELECT o.*, u.name FROM orders o JOIN users u ON o.user_id = u.user_id WHERE o.order_id = ?",
        (order_id,),
    ).fetchone()
    if not order:
        conn.close()
        return {"success": False, "reason": f"订单 {order_id} 不存在"}

    order = dict(order)

    # 条件 1: 必须已签收
    if order["status"] != "已签收":
        conn.close()
        return {
            "success": False,
            "reason": f"订单状态为「{order['status']}」, 无法申请退换货。只有已签收的订单才能退换。",
        }

    # 条件 2: 签收后 7 天内
    from datetime import datetime, timedelta
    try:
        sign_date = datetime.strptime(order["created_at"][:10], "%Y-%m-%d")
        days_since = (datetime.now() - sign_date).days
    except Exception:
        days_since = 0

    if request_type in ("退货退款", "退货"):
        if days_since > 7:
            conn.close()
            return {
                "success": False,
                "reason": f"已签收 {days_since} 天，超过 7 天无理由退货期限。可申请换货（15 天内质量问题）。",
            }
    elif request_type == "换货":
        if days_since > 15:
            conn.close()
            return {
                "success": False,
                "reason": f"已签收 {days_since} 天，超过 15 天换货期限。",
            }

    # 条件 3: 创建退换货申请
    return_id = f"RT{datetime.now().strftime('%Y%m%d%H%M%S')}"
    conn.execute(
        "INSERT OR IGNORE INTO return_requests(return_id, order_id, user_id, reason, request_type, status, created_at) VALUES (?,?,?,?,?,?,?)",
        (return_id, order_id, order["user_id"], reason, request_type, "待审核", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()

    shipping = {
        "退货退款": "退回运费由买家承担（非质量问题）",
        "退货": "退回运费由买家承担",
        "换货": "退回运费由商家承担",
    }

    next_steps = [
        f"✅ {request_type}申请已创建（编号：{return_id}）",
        f"📦 请将商品寄回至：浙江省杭州市余杭区耐克退货中心（{shipping.get(request_type, '')}）",
        "📋 审核预计 1-2 个工作日",
    ]
    if request_type in ("退货退款", "退货"):
        next_steps.append("💵 审核通过后，仓库签收 1-3 工作日退款")
    else:
        next_steps.append("📦 审核通过后，2-3 工作日寄出新商品")

    return {
        "success": True,
        "return_id": return_id,
        "order": f"{order['product_name']} ¥{order['price']}",
        "days_since_sign": days_since,
        "reason": reason,
        "type": request_type,
        "steps": "\n".join(next_steps),
    }
