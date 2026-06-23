from fastapi import FastAPI, HTTPException
import requests
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware
import random
from datetime import datetime
import sqlite3
import os

app = FastAPI()

# تفعيل الـ CORS لضمان استقبال الطلبات من السيرفرات الخارجية والواجهة
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = "f9afe7e1bc006f79f75bafe764b0f117"
DB_FILE = "alpha_casino.db"

# دالة تأسيس قاعدة البيانات الحقيقية والجداول تلقائياً
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # 1. جدول المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            balance REAL DEFAULT 0.0,
            role TEXT DEFAULT 'user'
        )
    ''')
    # 2. جدول تذاكر الرهان الرياضي
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bets (
            bet_id TEXT PRIMARY KEY,
            username TEXT,
            slip_type TEXT,
            amount REAL,
            total_odds REAL,
            potential_win REAL,
            date TEXT,
            status TEXT DEFAULT 'En cours'
        )
    ''')
    # 3. جدول تفاصيل الرهانات الرياضية
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bet_selections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bet_id TEXT,
            match_id TEXT,
            match_name TEXT,
            prediction TEXT,
            odds REAL,
            league_name TEXT,
            FOREIGN KEY(bet_id) REFERENCES bets(bet_id)
        )
    ''')
    
    # إضافة حسابك كأدمن رئيسي تلقائياً برصيد ثابت
    cursor.execute("SELECT * FROM users WHERE username = 'fethi'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, balance, role) VALUES ('fethi', '123456', 999999999999999, 'admin')")
        
    conn.commit()
    conn.close()

init_db()

# نماذج استقبال البيانات لـ Pydantic
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str

class SelectionItem(BaseModel):
    matchId: str
    matchName: str
    prediction: str
    odds: float
    leagueName: str

class BetRequest(BaseModel):
    username: str
    slipType: str
    amount: float
    totalOdds: float
    potentialWin: float
    selections: List[SelectionItem]

class UpdateBetStatusRequest(BaseModel):
    adminUsername: str
    betId: str
    newStatus: str

# 🎰 نماذج استقبال طلبات مزودي الألعاب العالمية (API Aggregators Models)
class ProviderBalanceRequest(BaseModel):
    username: str

class ProviderTransactionRequest(BaseModel):
    username: str
    transaction_id: str
    game_id: str
    amount: float  # قيمة الرهان أو الربح
    type: str      # 'bet' للخصم أو 'win' للإضافة

# 📝 مسار إنشاء حساب جديد للاعبين (Inscription)
@app.post("/api/register")
async def register_user(req: RegisterRequest):
    uname = req.username.strip().lower()
    if not uname or len(req.password) < 4:
        raise HTTPException(status_code=400, detail="Données invalides")
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password, balance, role) VALUES (?, ?, 0.0, 'user')", (uname, req.password))
        conn.commit()
        return {"status": "success", "message": "Compte créé avec succès"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Ce nom d'utilisateur existe déjà")
    finally:
        conn.close()

# 🔐 مسار تسجيل الدخول المربوط بقاعدة البيانات الحقيقية
@app.post("/api/login")
async def login_user(req: LoginRequest):
    uname = req.username.strip().lower()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username, balance, role FROM users WHERE username = ? AND password = ?", (uname, req.password))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {"username": user[0], "balance": user[1], "role": user[2]}
    else:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

# ⚽ مسار جلب المباريات الحية
@app.get("/api/sports/live")
async def get_sports():
    leagues = ["soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a", "soccer_uefa_champs_league"]
    all_matches = []
    for league in leagues:
        url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                all_matches.extend(response.json())
        except:
            pass
    return all_matches

# 🧾 مسار تثبيت تذاكر الرهان الرياضي
@app.post("/api/bets/sports")
async def confirm_sports_bet(req: BetRequest):
    uname = req.username.strip().lower()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance FROM users WHERE username = ?", (uname,))
    user_row = cursor.fetchone()
    if not user_row or user_row[0] < req.amount:
        conn.close()
        raise HTTPException(status_code=400, detail="Solde insuffisant")
        
    new_balance = user_row[0] - req.amount
    random_id = f"ST-{random.randint(100000, 900000)}"
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, uname))
    cursor.execute("INSERT INTO bets (bet_id, username, slip_type, amount, total_odds, potential_win, date, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'En cours')",
                   (random_id, uname, req.slipType, req.amount, req.totalOdds, req.potentialWin, date_str))
    
    for item in req.selections:
        cursor.execute("INSERT INTO bet_selections (bet_id, match_id, match_name, prediction, odds, league_name) VALUES (?, ?, ?, ?, ?, ?)",
                       (random_id, item.matchId, item.matchName, item.prediction, item.odds, item.leagueName))
                       
    conn.commit()
    conn.close()
    return {"status": "success", "betId": random_id, "newBalance": new_balance}

# 📑 مسار جلب سجل التذاكر الخاص بكل لاعب
@app.get("/api/bets/history/{username}")
async def get_bet_history(username: str):
    uname = username.strip().lower()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bets WHERE username = ? ORDER BY date DESC", (uname,))
    bets_rows = cursor.fetchall()
    history = []
    for bet in bets_rows:
        cursor.execute("SELECT match_id as matchId, match_name as matchName, prediction, odds, league_name as leagueName FROM bet_selections WHERE bet_id = ?", (bet["bet_id"],))
        selections = [dict(row) for row in cursor.fetchall()]
        history.append({
            "betId": bet["bet_id"], "username": bet["username"], "slipType": bet["slip_type"],
            "amount": bet["amount"], "totalOdds": bet["total_odds"], "potentialWin": bet["potential_win"],
            "date": bet["date"], "status": bet["status"], "selections": selections
        })
    conn.close()
    return history

# 👑 مسار الإدارة لجلب التذاكر وحسمها وشحن الرصيد
@app.get("/api/admin/bets")
async def admin_get_all_bets():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bets ORDER BY date DESC")
    bets_rows = cursor.fetchall()
    all_bets = []
    for bet in bets_rows:
        cursor.execute("SELECT match_id as matchId, match_name as matchName, prediction, odds, league_name as leagueName FROM bet_selections WHERE bet_id = ?", (bet["bet_id"],))
        selections = [dict(row) for row in cursor.fetchall()]
        all_bets.append({
            "betId": bet["bet_id"], "username": bet["username"], "slipType": bet["slip_type"],
            "amount": bet["amount"], "totalOdds": bet["total_odds"], "potentialWin": bet["potential_win"],
            "date": bet["date"], "status": bet["status"], "selections": selections
        })
    conn.close()
    return all_bets

@app.post("/api/admin/bets/settle")
async def admin_settle_bet(req: UpdateBetStatusRequest):
    if req.adminUsername.strip().lower() != "fethi":
        raise HTTPException(status_code=403, detail="Non autorisé")
        
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if req.betId == "RECHARGE":
        try:
            target_player, amount_to_charge = req.newStatus.split(":")
            amount_to_charge = float(amount_to_charge)
            cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (amount_to_charge, target_player.strip().lower()))
            conn.commit()
            conn.close()
            return {"status": "success", "message": "Recharge effectuée"}
        except:
            conn.close()
            raise HTTPException(status_code=400, detail="Format de recharge invalide")

    cursor.execute("SELECT status, username, potential_win FROM bets WHERE bet_id = ?", (req.betId,))
    bet = cursor.fetchone()
    if not bet or bet[0] != "En cours":
        conn.close()
        raise HTTPException(status_code=400, detail="Ticket déjà traité")
        
    cursor.execute("UPDATE bets SET status = ? WHERE bet_id = ?", (req.newStatus, req.betId))
    if req.newStatus == "Gagné":
        cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (bet[2], bet[1]))
        
    conn.commit()
    conn.close()
    return {"status": "success", "updatedBet": {"username": bet[1], "potentialWin": bet[2]}}


# =========================================================================
# 🎰 🎰 مـسارات الـ WEBHOOKS الـدولـية لـربـط مـزودي الألـعـاب (Seamless Wallet API)
# =========================================================================

# 1. مسار تحقق شركة الألعاب من رصيد اللاعب الفعلي داخل موقعك
@app.post("/api/casino/balance")
async def casino_get_balance(req: ProviderBalanceRequest):
    uname = req.username.strip().lower()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE username = ?", (uname,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=404, detail="Joueur non trouvé")
    
    # نرد على السيرفر الدولي بالصيغة المعتمدة لـ Hub88 / Softswiss
    return {"username": uname, "balance": user[0], "currency": "USDT", "status": "OK"}

# 2. مسار معالجة حركات الرهان والربح التلقائية داخل اللعبة
@app.post("/api/casino/transaction")
async def casino_process_transaction(req: ProviderTransactionRequest):
    uname = req.username.strip().lower()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("SELECT balance FROM users WHERE username = ?", (uname,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Joueur non trouvé")
        
    current_balance = user[0]
    
    if req.type == "bet":
        # خصم الرهان (اللاعب يدور العجلة أو يلعب سحب)
        if current_balance < req.amount:
            conn.close()
            return {"status": "ERROR_INSUFFICIENT_FUNDS", "balance": current_balance, "error": "Solde insuffisant"}
        new_balance = current_balance - req.amount
    elif req.type == "win":
        # إضافة الربح (اللاعب حقق فوزاً داخل اللعبة)
        new_balance = current_balance + req.amount
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Type de transaction inconnu")
        
    # تحديث محفظة اللاعب فوراً في قاعدة البيانات الحقيقية
    cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, uname))
    conn.commit()
    conn.close()
    
    return {
        "status": "OK",
        "transaction_id": req.transaction_id,
        "username": uname,
        "balance": new_balance,
        "currency": "USDT"
    }

@app.get("/")
async def root():
    return {"status": "Alpha SQLite Database & Casino Webhook Engine is running perfectly!"}
