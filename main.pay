import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

app = FastAPI(title="Alpha Core - Multi-Level Hierarchy Platform")

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
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        balance REAL DEFAULT 0.0,
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
    CREATE TABLE IF NOT EXISTS sports_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        match_name TEXT NOT NULL,
        bet_on TEXT NOT NULL,
        amount REAL,
        status TEXT DEFAULT 'pending',
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
    
    cursor.execute("SELECT * FROM users WHERE username = 'fethi'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password, role, balance, created_by, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            ('fethi', 'fethi2026', 'super_owner', 1000000.0, 'SYSTEM', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
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

@app.post("/api/register")
async def register_user(user: AuthModel):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password, role, balance, created_by, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                       (user.username.lower(), user.password, user.role, 0.0, user.created_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return {"message": "User created successfully", "username": user.username, "role": user.role}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="اسم المستخدم محجوز مسبقاً!")
    finally:
        conn.close()

@app.post("/api/login")
async def login_user(user: AuthModel):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username, role, balance, created_by FROM users WHERE username = ? AND password = ?", 
                   (user.username.lower(), user.password))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "username": row[0],
            "role": row[1],
            "balance": row[2],
            "created_by": row[3]
        }
    raise HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة!")

@app.post("/api/admin/update-balance")
async def update_balance(data: BalanceUpdateModel):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT role, balance FROM users WHERE username = ?", (data.admin_username.lower(),))
    admin = cursor.fetchone()
    cursor.execute("SELECT role, balance FROM users WHERE username = ?", (data.target_username.lower(),))
    target = cursor.fetchone()
    
    if not admin or not target:
        conn.close()
        raise HTTPException(status_code=404, detail="الحسابات غير موجودة!")
        
    admin_role, admin_balance = admin[0], admin[1]
    target_role, target_balance = target[0], target[1]
    
    role_weights = {'super_owner': 6, 'owner': 5, 'super_admin': 4, 'admin': 3, 'shop': 2, 'player': 1}
    
    if role_weights[admin_role] <= role_weights[target_role] and admin_role != 'super_owner':
        conn.close()
        raise HTTPException(status_code=403, detail="لا تملك الصلاحية لهذه الرتبة!")

    if data.action == "charge":
        if admin_role != 'super_owner' and admin_balance < data.amount:
            conn.close()
            raise HTTPException(status_code=400, detail="رصيدك الإداري غير كافٍ!")
            
        if admin_role != 'super_owner':
            cursor.execute("UPDATE users SET balance = balance - ? WHERE username = ?", (data.amount, data.admin_username.lower()))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (data.amount, data.target_username.lower()))
        new_target_bal = target_balance + data.amount

    elif data.action == "reset":
        cursor.execute("UPDATE users SET balance = 0.0 WHERE username = ?", (data.target_username.lower(),))
        if admin_role != 'super_owner':
            cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (target_balance, data.admin_username.lower()))
        new_target_bal = 0.0

    cursor.execute("INSERT INTO transactions (sender, receiver, type, amount, timestamp) VALUES (?, ?, ?, ?, ?)",
                   (data.admin_username, data.target_username, data.action, data.amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()
    return {"message": "تم التحديث بنجاح", "new_balance": new_target_bal}

@app.get("/api/admin/users")
async def get_controlled_users(admin_username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT role FROM users WHERE username = ?", (admin_username.lower(),))
    admin_row = cursor.fetchone()
    if not admin_row:
        conn.close()
        return []
    admin_role = admin_row[0]
    
    if admin_role == 'super_owner':
        cursor.execute("SELECT id, username, role, balance, created_by FROM users WHERE username != 'fethi'")
    else:
        cursor.execute("SELECT id, username, role, balance, created_by FROM users WHERE created_by = ? OR (role = 'player' AND created_by = ?)", 
                       (admin_username, admin_username))
    users = cursor.fetchall()
    conn.close()
    return [{"id": u[0], "username": u[1], "role": u[2], "balance": u[3], "created_by": u[4]} for u in users]

@app.get("/api/admin/reports")
async def get_platform_reports():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(bet_amount), SUM(win_amount) FROM casino_history")
    casino = cursor.fetchone()
    total_bets = casino[0] if casino[0] else 0.0
    total_wins = casino[1] if casino[1] else 0.0
    conn.close()
    return {"ggr": (total_bets - total_wins), "total_deposits": total_bets}

# --- المسارات الجديدة لخدمة أزرار قائمة الأونر ولغات التقارير ---

@app.get("/api/admin/transactions")
async def get_transactions_history():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT sender, receiver, type, amount, timestamp FROM transactions ORDER BY id DESC")
    txs = cursor.fetchall()
    conn.close()
    return [{"sender": t[0], "receiver": t[1], "type": t[2], "amount": t[3], "timestamp": t[4]} for t in txs]

@app.post("/api/user/change-password")
async def change_user_password(data: dict):
    username = data.get("username")
    new_password = data.get("new_password")
    if not username or not new_password:
        raise HTTPException(status_code=400, detail="البيانات غير كاملة")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password = ? WHERE username = ?", (new_password, username.lower()))
    conn.commit()
    conn.close()
    return {"message": "تم تغيير كلمة المرور بنجاح"}
