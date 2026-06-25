from fastapi import FastAPI, HTTPException
import requests
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import random
from datetime import datetime

app = FastAPI()

# تفعيل الـ CORS بشكل كامل ومفتوح لضمان الاتصال الآمن مع الواجهات المعزولة
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# مفتاح الـ API الخاص بك لجلب المباريات
API_KEY = "f9afe7e1bc006f79f75bafe764b0f117"

# --- محاكاة قاعدة البيانات الشاملة للشبكة والمحافظ (Database Simulation) ---
# حساب fethi كـ Super Owner، وحساب samir وحسابات الإدارة والمحلات
users_db = [
    {"username": "fethi", "role": "owner", "balance": 999999.00, "rtp": 50, "is_blocked": 0, "created_by": "System"},
    {"username": "samir", "role": "super_admin", "balance": 5000.00, "rtp": 50, "is_blocked": 0, "created_by": "fethi"}
]

db_bets = []

# --- النماذج وهياكل البيانات المدخلة (Pydantic Models) ---
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str
    created_by: str

class ConfigureAccountRequest(BaseModel):
    admin_username: str
    target_username: str
    rtp: int
    is_blocked: int

class UpdateBalanceRequest(BaseModel):
    admin_username: str
    target_username: str
    action: str  # "charge" أو "withdraw"
    amount: float

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

# --- 🔐 مسارات الحماية والتحقق من الهوية (Authentication APIs) ---

@app.post("/api/login")
async def login_user(req: LoginRequest):
    uname = req.username.lower().strip()
    
    # فحص حساب السوبر أونر fethi مباشرة
    if uname == "fethi" and req.password == "123456":
        return {"username": "fethi", "role": "owner", "balance": 999999.00}
        
    # فحص بقية حسابات الشبكة (مثل samir والمحلات)
    for u in users_db:
        if u["username"] == uname and req.password == "123456": # يمكنك تعديل كلمة المرور للشبكة هنا
            if u["is_blocked"] == 1:
                raise HTTPException(status_code=403, detail="Ce compte est bloqué par l'administration")
            return {"username": u["username"], "role": u["role"], "balance": u["balance"]}
            
    raise HTTPException(status_code=401, detail="Identifiants incorrects")

@app.post("/api/register")
async def register_user(req: RegisterRequest):
    uname = req.username.lower().strip()
    
    # التحقق من عدم تكرار الاسم
    for u in users_db:
        if u["username"] == uname:
            raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà pris")
            
    new_user = {
        "username": uname,
        "role": req.role,
        "balance": 0.00,
        "rtp": 50,
        "is_blocked": 0,
        "created_by": req.created_by
    }
    users_db.append(new_user)
    return {"status": "success", "message": "Compte créé avec succès"}

# --- 📊 مسارات الإدارة العامة والتحكم المالي (Management APIs) ---

@app.get("/api/admin/users")
async def get_all_network_users(admin_username: Optional[str] = None):
    # مسار حاسم: يعود بكافة المستخدمين لضمان ملء الجداول الإدارية فوراً
    return users_db

@app.post("/api/admin/configure-account")
async def configure_account(req: ConfigureAccountRequest):
    for u in users_db:
        if u["username"] == req.target_username.lower().strip():
            u["rtp"] = req.rtp
            u["is_blocked"] = req.is_blocked
            return {"status": "success", "message": "Compte configuré"}
    raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

@app.post("/api/admin/update-balance")
async def update_balance(req: UpdateBalanceRequest):
    target = req.target_username.lower().strip()
    amount = float(req.amount)
    
    for u in users_db:
        if u["username"] == target:
            if req.action == "charge":
                u["balance"] += amount
            elif req.action == "withdraw":
                if u["balance"] < amount:
                    raise HTTPException(status_code=400, detail="Solde insuffisant pour le retrait")
                u["balance"] -= amount
            return {"status": "success", "balance": u["balance"]}
            
    raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

@app.delete("/api/admin/delete-account")
async def delete_account(admin_username: str, target_username: str):
    global users_db
    target = target_username.lower().strip()
    if target == "fethi":
        raise HTTPException(status_code=400, detail="Impossible de supprimer le Super Owner")
        
    for i, u in enumerate(users_db):
        if u["username"] == target:
            users_db.pop(i)
            return {"status": "success", "message": "Compte supprimé"}
    raise HTTPException(status_code=404, detail="Compte non trouvé")

# --- ⚽ مسارات الرهان الرياضي (Sports Betting APIs) ---

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
        except Exception:
            pass
    return all_matches

@app.post("/api/bets/sports")
async def confirm_sports_bet(req: BetRequest):
    if req.amount <= 0 or len(req.selections) == 0:
        raise HTTPException(status_code=400, detail="Données incomplètes")
    
    uname = req.username.lower().strip()
    player_found = None
    for u in users_db:
        if u["username"] == uname:
            player_found = u
            break
            
    if not player_found:
        raise HTTPException(status_code=404, detail="Joueur non trouvé")
        
    if player_found["balance"] < req.amount:
        raise HTTPException(status_code=400, detail="Solde insuffisant")
        
    player_found["balance"] -= req.amount
    random_id = f"ST-{random.randint(100000, 900000)}"
    
    new_bet = {
        "betId": random_id,
        "username": req.username,
        "slipType": req.slipType,
        "amount": req.amount,
        "totalOdds": req.totalOdds,
        "potentialWin": req.potentialWin,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "En cours",
        "selections": [item.dict() for item in req.selections]
    }
    db_bets.append(new_bet)
    return {"status": "success", "betId": random_id, "newBalance": player_found["balance"]}

@app.get("/api/bets/history/{username}")
async def get_bet_history(username: str):
    return [bet for bet in db_bets if bet["username"].lower() == username.lower()][::-1]

@app.get("/api/admin/bets")
async def admin_get_all_bets():
    return db_bets[::-1]

@app.post("/api/admin/bets/settle")
async def admin_settle_bet(req: UpdateBetStatusRequest):
    for bet in db_bets:
        if bet["betId"] == req.betId:
            if bet["status"] != "En cours":
                raise HTTPException(status_code=400, detail="Ticket déjà traité")
            bet["status"] = req.newStatus
            if req.newStatus == "Gagné":
                for u in users_db:
                    if u["username"] == bet["username"].lower().strip():
                        u["balance"] += bet["potentialWin"]
            return {"status": "success", "updatedBet": bet}
    raise HTTPException(status_code=404, detail="Ticket non trouvé")

@app.get("/")
async def root():
    return {"status": "Alpha Core API Architecture deployed and running perfectly!"}
