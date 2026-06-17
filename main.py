import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

app = FastAPI(title="Alpha Core - Advanced Control Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "alpha_platform.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # تحديث جدول المستخدمين ليدعم الـ RTP والحظر
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        balance REAL DEFAULT 0.0,
        rtp INTEGER DEFAULT 50,
        is_blocked INTEGER DEFAULT 0,
        created_by TEXT,
        timestamp TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS casino_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        game_type TEXT NOT NULL,
        bet_amount REAL,
        win_amount REAL,
        timestamp TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT NOT NULL,
        receiver TEXT NOT NULL,
        type TEXT NOT NULL,
        amount REAL,
        timestamp TEXT
    )
    """)
    
    # التأكد من وجود حساب fethi الرئيسي
    cursor.execute("SELECT * FROM users WHERE username = 'fethi'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password, role, balance, rtp, is_blocked, created_by, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ('fethi', 'fethi2026', 'super_owner', 1000000.0, 50, 0, 'SYSTEM', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        
    conn.commit()
    conn.close()

init_db()

class AuthModel(BaseModel):
    username: str
    password: str
    role: Optional[str] = "player"
    created_by: Optional[str] = "SYSTEM"

class BalanceUpdateModel(BaseModel):
    admin_username: str
    target_username: str
    action: str
    amount: float

class ControlModel(BaseModel):
    admin_username: str
    target_username: str
    rtp: Optional[int] = 50
    is_blocked: Optional[int] = 0

@app.post("/api/register")
async def register_user(user: AuthModel):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password, role, balance, rtp, is_blocked, created_by, timestamp) VALUES (?, ?, ?, ?, 50, 0, ?, ?)",
                       (user.username.lower(), user.password, user.role, 0.0, user.created_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return {"message": "User created successfully"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="اسم المستخدم محجوز مسبقاً!")
    finally:
        conn.close()

@app.post("/api/login")
async def login_user(user: AuthModel):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username, role, balance, is_blocked, rtp FROM users WHERE username = ? AND password = ?", 
                   (user.username.lower(), user.password))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        if row[3] == 1:
            raise HTTPException(status_code=403, detail="هذا الحساب محظور حالياً من الإدارة!")
        return {"username": row[0], "role": row[1], "balance": row[2], "rtp": row[4]}
    raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة!")

@app.post("/api/admin/update-balance")
async def update_balance(data: BalanceUpdateModel):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE username = ?", (data.admin_username.lower(),))
    admin_bal = cursor.fetchone()[0]
    
    if data.action == "charge":
        cursor.execute("UPDATE users SET balance = balance - ? WHERE username = ? AND username != 'fethi'", (data.amount, data.admin_username.lower()))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (data.amount, data.target_username.lower()))
    elif data.action == "reset":
        cursor.execute("SELECT balance FROM users WHERE username = ?", (data.target_username.lower(),))
        target_bal = cursor.fetchone()[0]
        cursor.execute("UPDATE users SET balance = 0.0 WHERE username = ?", (data.target_username.lower(),))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ? AND username != 'fethi'", (target_bal, data.admin_username.lower()))

    cursor.execute("INSERT INTO transactions (sender, receiver, type, amount, timestamp) VALUES (?, ?, ?, ?, ?)",
                   (data.admin_username, data.target_username, data.action, data.amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    return {"message": "Success"}

@app.get("/api/admin/users")
async def get_controlled_users(admin_username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, role, balance, created_by, rtp, is_blocked FROM users WHERE username != 'fethi'")
    users = cursor.fetchall()
    conn.close()
    return [{"id": u[0], "username": u[1], "role": u[2], "balance": u[3], "created_by": u[4], "rtp": u[5], "is_blocked": u[6]} for u in users]

# --- المسارات الجديدة للتحكم المطلق في الـ RTP وبلوك الحساب وحذفه ---

@app.post("/api/admin/configure-account")
async def configure_account(data: ControlModel):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET rtp = ?, is_blocked = ? WHERE username = ?", 
                   (data.rtp, data.is_blocked, data.target_username.lower()))
    conn.commit()
    conn.close()
    return {"message": "تم تحديث الإعدادات بنجاح"}

@app.delete("/api/admin/delete-account")
async def delete_account(admin_username: str, target_username: str):
    if target_username.lower() == "fethi":
        raise HTTPException(status_code=400, detail="لا يمكن حذف الحساب الرئيسي")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = ?", (target_username.lower(),))
    conn.commit()
    conn.close()
    return {"message": "تم حذف الحساب نهائياً من السيستم"}

@app.get("/api/admin/reports")
async def get_platform_reports():
    return {"ggr": 0.0, "total_deposits": 0.0}

@app.get("/api/admin/transactions")
async def get_transactions_history():
    return []
