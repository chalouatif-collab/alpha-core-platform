from fastapi import FastAPI, HTTPException, Header
import requests
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import random
from datetime import datetime
import sqlite3

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

API_KEY = "f9afe7e1bc006f79f75bafe764b0f117"
DB_FILE = "alpha_casino.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            balance REAL DEFAULT 0.0,
            role TEXT DEFAULT 'user'
        )
    ''')
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
    cursor.execute("SELECT * FROM users WHERE username = 'fethi'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, balance, role) VALUES ('fethi', '123456', 999999999999999, 'admin')")
    conn.commit()
    conn.close()

init_db()

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

# 🎰 Hub88 الموديلات المتوافقة مع تسميات صورة التوثيق 
class Hub88UserInfoRequest(BaseModel):
    user: str
    request_uuid: str

class Hub88BalanceRequest(BaseModel):
    user: str
    request_uuid: str

class Hub88TransactionRequest(BaseModel):
    user: str
    amount: float
    transaction_id: str
    game_id: Optional[str] = None
    request_uuid: str

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
    
    # 🛠️ إصلاح الاستعلام السليم هنا وحذف الكلمة المكررة الزائدة ليعمل الخصم فورا
    cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, uname))
    
    cursor.execute("INSERT INTO bets (bet_id, username, slip_type, amount, total_odds, potential_win, date, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'En cours')",
                   (random_id, uname, req.slipType, req.amount, req.totalOdds, req.potentialWin, date_str))
    
    for item in req.selections:
        cursor.execute("INSERT INTO bet_selections (bet_id, match_id, match_name, prediction, odds, league_name) VALUES (?, ?, ?, ?, ?, ?)",
                       (random_id, item.matchId, item.matchName, item.prediction, item.odds, item.leagueName))
    
    conn.commit()
    conn.close()
    return {"status": "success", "betId": random_id, "newBalance": new_balance}

# 🛠️ دمج مسار جلب السجل ليتوافق مع الـ Query Param والـ Path Param في نفس الوقت لمنع الـ 404
@app.get("/api/bets/history")
async def get_bet_history_query(username: str):
    return await execute_history_fetch(username)

@app.get("/api/bets/history/{username}")
async def get_bet_history_path(username: str):
    return await execute_history_fetch(username)

async def execute_history_fetch(username: str):
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
    admin_uname = req.adminUsername.strip().lower()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if req.betId == "RECHARGE":
        try:
            target_player, amount_to_charge = req.newStatus.split(":")
            amount_to_charge = float(amount_to_charge)
            target_player = target_player.strip().lower()
            
            # نظام الوكلاء الحقيقي: إذا كان الآدمين fethi هو من ينفذ العملية
            if admin_uname == "fethi":
                if target_player == "fethi":
                    # السوبر أونر يشحن للآدمين مباشرة (توليد رصيد للآدمين)
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE username = 'fethi'", (amount_to_charge,))
                else:
                    # الآدمين يشحن للبقية: يتم التأكد من رصيد الآدمين أولاً
                    cursor.execute("SELECT balance FROM users WHERE username = 'fethi'")
                    admin_row = cursor.fetchone()
                    
                    if not admin_row or admin_row[0] < amount_to_charge:
                        conn.close()
                        raise HTTPException(status_code=400, detail="Votre solde admin est insuffisant")
                    
                    # الخصم من رصيد الآدمين الإداري والإضافة للمستلم الفعلي
                    cursor.execute("UPDATE users SET balance = balance - ? WHERE username = 'fethi'", (amount_to_charge,))
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (amount_to_charge, target_player))
            
            conn.commit()
            conn.close()
            return {"status": "success", "message": "Transaction effectuée"}
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=400, detail=str(e) if "insuffisant" in str(e) else "Format invalide")
            
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
# 🎰 🎰 مـسارات الـ WEBHOOKS الـرسـمية الـمـتطـابـقة مـع Hub88 حرفياً
# =========================================================================

@app.post("/user/info")
async def hub88_user_info(req: Hub88UserInfoRequest):
    uname = req.user.strip().lower()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE username = ?", (uname,))
    user = cursor.fetchone()
    conn.close()
    if not user:
        return {"status": "RS_ERROR_USER_NOT_FOUND", "request_uuid": req.request_uuid}
    
    return {
        "user": uname,
        "status": "RS_OK",
        "request_uuid": req.request_uuid,
        "country": "TN",
        "currency": "USDT"
    }

@app.post("/user/balance")
async def hub88_get_balance(req: Hub88BalanceRequest):
    uname = req.user.strip().lower()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE username = ?", (uname,))
    user = cursor.fetchone()
    conn.close()
    if not user:
        return {"status": "RS_ERROR_USER_NOT_FOUND", "request_uuid": req.request_uuid}
    return {
        "user": uname,
        "status": "RS_OK",
        "balance": user[0],
        "request_uuid": req.request_uuid
    }

@app.post("/transaction/bet")
async def hub88_process_bet(req: Hub88TransactionRequest):
    uname = req.user.strip().lower()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE username = ?", (uname,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return {"status": "RS_ERROR_USER_NOT_FOUND", "request_uuid": req.request_uuid}
    
    current_balance = user[0]
    if current_balance < req.amount:
        conn.close()
        return {"status": "RS_ERROR_NOT_ENOUGH_MONEY", "balance": current_balance, "request_uuid": req.request_uuid}
        
    new_balance = current_balance - req.amount
    cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, uname))
    conn.commit()
    conn.close()
    return {
        "status": "RS_OK",
        "user": uname,
        "balance": new_balance,
        "request_uuid": req.request_uuid
    }

@app.post("/transaction/win")
async def hub88_process_win(req: Hub88TransactionRequest):
    uname = req.user.strip().lower()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE username = ?", (uname,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return {"status": "RS_ERROR_USER_NOT_FOUND", "request_uuid": req.request_uuid}
        
    new_balance = user[0] + req.amount
    cursor.execute("UPDATE users SET balance = ? WHERE username = ?", (new_balance, uname))
    conn.commit()
    conn.close()
    return {
        "status": "RS_OK",
        "user": uname,
        "balance": new_balance,
        "request_uuid": req.request_uuid
    }

@app.get("/")
async def root():
    return {"status": "Hub88 Native Webhook Engine is active!"}
