from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import random

app = FastAPI(
    title="Alpha Core - Auth & Database Edition",
    version="6.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_NAME = "alpha_platform.db"

# 🗄️ دالة لتهيئة قاعدة البيانات وإنشاء الجداول إذا لم تكن موجودة
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # جدول المستخدمين والمحافظ المالية
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            balance REAL DEFAULT 1000.0
        )
    """)
    conn.commit()
    conn.close()

init_db()

# الإعدادات الديناميكية للمنصة والإحصائيات
ADMIN_SETTINGS = {"sports_margin": 1.05, "casino_difficulty": "medium"}
PLATFORM_STATS = {"total_sports_bets": 0, "total_casino_bets": 0, "total_money_wagered": 0.0, "total_money_paid_out": 0.0, "platform_net_profit": 0.0}

# نماذج البيانات (Pydantic Models)
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class BetRequest(BaseModel):
    user_external_id: str
    fixture_id: str
    predicted_outcome: str
    stake_amount: float

class CasinoPlayRequest(BaseModel):
    user_external_id: str
    bet_amount: float

class UpdateSettingsRequest(BaseModel):
    sports_margin: float
    casino_difficulty: str

# 🔐 روابط نظام الحسابات (Auth APIs)

@app.post("/api/auth/register")
def register_user(req: RegisterRequest):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        # إنشاء المستخدم الجديد ومنحه رصيد افتراضي 1000 دولار
        cursor.execute("INSERT INTO users (username, password, balance) VALUES (?, ?, 1000.0)", (req.username, req.password))
        conn.commit()
        return {"success": True, "message": "تم إنشاء الحساب بنجاح! يمكنك تسجيل الدخول الآن."}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="اسم المستخدم موجود بالفعل، اختر اسماً آخر.")
    finally:
        conn.close()

@app.post("/api/auth/login")
def login_user(req: LoginRequest):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance FROM users WHERE username = ? AND password = ?", (req.username, req.password))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=401, detail="اسم المستخدم أو كلمة المرور غير صحيحة.")
    
    return {
        "success": True,
        "username": user[0],
        "balance": user[1],
        "message": "تم تسجيل الدخول بنجاح!"
    }

@app.get("/api/v1/wallet/{user_id}")
def get_wallet_balance(user_id: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE username = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"user_id": user_id, "balance": row[0]}
    return {"user_id": user_id, "balance": 0.0}

# ⚽ محرك الرياضة المربوط بالهامش والـ DB
@app.get("/api/v1/fixtures")
def get_live_fixtures():
    margin = ADMIN_SETTINGS["sports_margin"]
    return {"fixtures": [
        {"id": "m1", "sport": "🏆 UEFA Champions League", "home_team": "ريال مدريد 🇪🇸", "away_team": "مانشستر سيتي 🏴󠁧󠁢󠁥󠁮󠁧󠁿", "odds": {"home_win": round(2.25/margin, 2), "draw": round(3.50/margin, 2), "away_win": round(2.90/margin, 2)}},
        {"id": "m2", "sport": "🏆 UEFA Champions League", "home_team": "برشلونة 🇪🇸", "away_team": "بايرن ميونخ 🇩🇪", "odds": {"home_win": round(2.50/margin, 2), "draw": round(3.70/margin, 2), "away_win": round(2.40/margin, 2)}}
    ]}

@app.post("/api/v1/place-bet")
def place_bet(bet: BetRequest):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE username = ?", (bet.user_external_id,))
    row = cursor.fetchone()
    
    if outfits := not row or row[0] < bet.stake_amount:
        conn.close()
        raise HTTPException(status_code=400, detail="الرصيد غير كافٍ أو الحساب غير موجود")
    
    current_balance = row[0]
    new_balance = round(current_balance - bet.stake_amount, 2)
    
    # تحديث الإحصائيات العامة
    PLATFORM_STATS["total_sports_bets"] += 1
    PLATFORM_STATS["total_money_wagered"] += bet.stake_amount

    is_win = random.choice([True, False])
    win_amount = 0.0
    message = "خسرت الرهان الرياضي ❌"
    
    if is_win:
        win_amount = round(bet.stake_amount * round(2.20 / ADMIN_SETTINGS["sports_margin"], 2), 2)
        new_balance = round(new_balance + win_amount, 2)
        PLATFORM_STATS["total_money_paid_out"] += win_amount
        message = "مبروك الفوز بالرهان! 🎉"

    # حفظ الرصيد الجديد في قاعدة البيانات فوراً
    cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, bet.user_external_id))
    conn.commit()
    conn.close()

    PLATFORM_STATS["platform_net_profit"] = round(PLATFORM_STATS["total_money_wagered"] - PLATFORM_STATS["total_money_paid_out"], 2)
    return {"success": True, "message": message, "new_balance": new_balance}

# 🎰 محرك الكازينو المربوط بقاعدة البيانات
@app.post("/api/v1/casino/spin")
def casino_spin(request: CasinoPlayRequest):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE username = ?", (request.user_external_id,))
    row = cursor.fetchone()
    
    if not row or row[0] < request.bet_amount:
        conn.close()
        raise HTTPException(status_code=400, detail="الرصيد غير كافٍ")
    
    current_balance = row[0]
    new_balance = round(current_balance - request.bet_amount, 2)
    
    PLATFORM_STATS["total_casino_bets"] += 1
    PLATFORM_STATS["total_money_wagered"] += request.bet_amount

    difficulty = ADMIN_SETTINGS["casino_difficulty"]
    if difficulty == "easy":
        multipliers = [1, 1.5, 2, 5]
    elif difficulty == "medium":
        multipliers = [0, 0, 1.5, 2]
    else:
        multipliers = [0, 0, 0, 0.5, 1.5]

    result_multiplier = random.choice(multipliers)
    win_amount = round(request.bet_amount * result_multiplier, 2)
    new_balance = round(new_balance + win_amount, 2)
    
    # حفظ النتيجة والرصيد الجديد في الـ DB بالثانية
    cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, request.user_external_id))
    conn.commit()
    conn.close()

    PLATFORM_STATS["total_money_paid_out"] += win_amount
    PLATFORM_STATS["platform_net_profit"] = round(PLATFORM_STATS["total_money_wagered"] - PLATFORM_STATS["total_money_paid_out"], 2)

    return {
        "success": True,
        "multiplier": result_multiplier,
        "win_amount": win_amount,
        "new_balance": new_balance,
        "status": "WIN" if result_multiplier > 1 else "LOSE"
    }

# 🎛️ روابط لوحة التحكم الإدارية
@app.get("/api/admin/stats")
def get_platform_stats():
    return {"stats": PLATFORM_STATS, "settings": ADMIN_SETTINGS}

@app.post("/api/admin/settings")
def update_platform_settings(settings: UpdateSettingsRequest):
    ADMIN_SETTINGS["sports_margin"] = settings.sports_margin
    ADMIN_SETTINGS["casino_difficulty"] = settings.casino_difficulty
    return {"success": True, "message": "تم تحديث إعدادات الإدارة!"}