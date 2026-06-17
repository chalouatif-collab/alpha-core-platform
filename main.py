import sqlite3
import random
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

app = FastAPI(title="Alpha Core - Ultimate Casino Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "alpha_platform.db"

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

# نموذج استقبال بيانات الرهان من اللاعب
class CasinoBetModel(BaseModel):
    username: str
    game_type: str  # 'slots', 'roulette', 'crash'
    bet_amount: float
    choice: Optional[str] = None  # لون الرهان في الرويت أو نقطة السحب في الكراش

@app.post("/api/register")
async def register_user(user: AuthModel):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password, role, balance, rtp, is_blocked, created_by, timestamp) VALUES (?, ?, ?, ?, 50, 0, ?, ?)",
                       (user.username.lower(), user.password, user.role, 0.0, user.created_by, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return {"message": "Success"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà pris!")
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
            raise HTTPException(status_code=403, detail="Compte bloqué!")
        return {"username": row[0], "role": row[1], "balance": row[2], "rtp": row[4]}
    raise HTTPException(status_code=401, detail="Identifiants incorrects!")

@app.post("/api/admin/update-balance")
async def update_balance(data: BalanceUpdateModel):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if data.action == "charge":
        cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (data.amount, data.target_username.lower()))
    elif data.action == "withdraw":
        cursor.execute("UPDATE users SET balance = balance - ? WHERE username = ?", (data.amount, data.target_username.lower()))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (data.amount, data.admin_username.lower()))
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

@app.post("/api/admin/configure-account")
async def configure_account(data: ControlModel):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET rtp = ?, is_blocked = ? WHERE username = ?", (data.rtp, data.is_blocked, data.target_username.lower()))
    conn.commit()
    conn.close()
    return {"message": "Success"}

# --- 🎰 محرك الكازينو الخارق والمربح المرتبط بالـ RTP لكل مستخدم على حدة ---
@app.post("/api/casino/play")
async def play_casino(bet: CasinoBetModel):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance, rtp, is_blocked FROM users WHERE username = ?", (bet.username.lower(),))
    user_data = cursor.fetchone()
    
    if not user_data:
        conn.close()
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
    if user_data[2] == 1:
        conn.close()
        raise HTTPException(status_code=403, detail="Compte bloqué!")
    if user_data[0] < bet.bet_amount:
        conn.close()
        raise HTTPException(status_code=400, detail="Solde insuffisant!")

    player_balance = user_data[0]
    player_rtp = user_data[1] # نسبة الربح المخزنة والتي حددتها أنت في لوحة التحكم (مثلاً 30%)

    # خوارزمية تحديد النتيجة الحتمية بناءً على نسبة الـ RTP الخاصة باللاعب
    dice = random.randint(1, 100)
    is_win = dice <= player_rtp

    win_amount = 0.0
    result_details = {}

    if bet.game_type == "slots":
        symbols_pool = ["🍒", "🍋", "🍊", "🍇", "🔔", "💎", "7️⃣"]
        if is_win:
            win_sym = random.choice(symbols_pool)
            slots_result = [win_sym, win_sym, win_sym]
            win_amount = bet.bet_amount * 3.0
        else:
            slots_result = [random.choice(symbols_pool), random.choice(symbols_pool), random.choice(symbols_pool)]
            if slots_result[0] == slots_result[1] == slots_result[2]:
                slots_result[2] = "🍏" if slots_result[0] != "🍏" else "🍒"
        result_details = {"combination": slots_result}

    elif bet.game_type == "roulette":
        colors = ["red", "black"]
        if is_win:
            winning_color = bet.choice if bet.choice in colors else "red"
            win_amount = bet.bet_amount * 2.0
        else:
            winning_color = "black" if bet.choice == "red" else "red"
        result_details = {"number": random.randint(1, 36), "color": winning_color}

    elif bet.game_type == "crash":
        if is_win:
            multiplier = round(random.uniform(1.5, 4.5), 2)
            win_amount = bet.bet_amount * multiplier
        else:
            multiplier = round(random.uniform(1.0, 1.3), 2)
        result_details = {"multiplier": multiplier}

    # تحديث الحساب المالي المباشر في قاعدة البيانات
    new_balance = player_balance - bet.bet_amount + win_amount
    cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, bet.username.lower()))
    
    # حفظ المعاملة في سجل الكازينو
    cursor.execute("INSERT INTO casino_history (username, game_type, bet_amount, win_amount, timestamp) VALUES (?, ?, ?, ?, ?)",
                   (bet.username, bet.game_type, bet.bet_amount, win_amount, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()

    return {
        "is_win": is_win and win_amount > 0,
        "win_amount": win_amount,
        "new_balance": new_balance,
        "details": result_details
    }

@app.delete("/api/admin/delete-account")
async def delete_account(admin_username: str, target_username: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = ?", (target_username.lower(),))
    conn.commit()
    conn.close()
    return {"message": "Success"}
