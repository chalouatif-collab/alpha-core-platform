from fastapi import FastAPI, HTTPException
import requests
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware
import random
from datetime import datetime

app = FastAPI()

# تفعيل الـ CORS لحماية الاتصال مع الواجهة
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# مفتاح الـ API الخاص بك لجلب المباريات
API_KEY = "f9afe7e1bc006f79f75bafe764b0f117"

# قاعدة بيانات مؤقتة في ذاكرة السيرفر لحفظ التذاكر ورصيد المستخدم الافتراضي
db_bets = []
user_wallet = {"fethi": 999999999999999} # حفظ رصيدك الفخم في السيرفر ليتحدث مع الأرباح والخسائر

# نموذج استقبال بيانات تسجيل الدخول
class LoginRequest(BaseModel):
    username: str
    password: str

# نماذج استقبال بيانات الرهان الرياضي
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

# نموذج إدارة التذاكر من الأدمن
class UpdateBetStatusRequest(BaseModel):
    adminUsername: str
    betId: str
    newStatus: str # "Gagné" أو "Perdu"

# 🔐 مسار تسجيل الدخول النظيف
@app.post("/api/login")
async def login_user(req: LoginRequest):
    uname = req.username.lower()
    if uname == "fethi" and req.password == "123456":
        # إذا لم يكن المستخدم مسجلاً في المحفظة، نضع له رصيده الافتراضي الفخم
        if uname not in user_wallet:
            user_wallet[uname] = 999999999999999
        return {
            "username": "fethi",
            "balance": user_wallet[uname],
            "role": "admin"
        }
    else:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

# ⚽ مسار متطور يجلب أقوى مباريات العالم معاً
@app.get("/api/sports/live")
async def get_sports():
    leagues = [
        "soccer_epl",
        "soccer_spain_la_liga",
        "soccer_italy_serie_a",
        "soccer_uefa_champs_league"
    ]
    all_matches = []
    for league in leagues:
        url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                all_matches.extend(response.json())
        except Exception as e:
            print(f"Error fetching {league}: {str(e)}")
    return all_matches

# 🧾 مسار استقبال وتثبيت تذاكر الرهان وحفظها في السيرفر
@app.post("/api/bets/sports")
async def confirm_sports_bet(req: BetRequest):
    if not req.username or req.amount <= 0 or len(req.selections) == 0:
        raise HTTPException(status_code=400, detail="Données du ticket incomplètes")
    
    uname = req.username.lower()
    # التحقق من الرصيد وخصمه داخل السيرفر
    current_bal = user_wallet.get(uname, 0)
    if current_bal < req.amount:
        raise HTTPException(status_code=400, detail="Solde insuffisant dans le serveur")
    
    # خصم قيمة الرهان من محفظة السيرفر
    user_wallet[uname] = current_bal - req.amount
    
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
    return {"status": "success", "message": "Ticket enregistré", "betId": random_id, "newBalance": user_wallet[uname]}

# 📑 مسار جلب سجل التذاكر الخاص بكل لاعب
@app.get("/api/bets/history/{username}")
async def get_bet_history(username: str):
    user_bets = [bet for bet in db_bets if bet["username"].lower() == username.lower()]
    return user_bets[::-1]

# 👑 🛠️ مسار الأدمن السري: جلب كافة التذاكر الموجودة في السيرفر لإدارتها
@app.get("/api/admin/bets")
async def admin_get_all_bets():
    return db_bets[::-1]

# 👑 💰 مسار الأدمن السري: البت في التذكرة (تحديد الرابح والخاسر وتحديث الرصيد الفعلي تلقائياً)
@app.post("/api/admin/bets/settle")
async def admin_settle_bet(req: UpdateBetStatusRequest):
    if req.adminUsername.lower() != "fethi":
        raise HTTPException(status_code=403, detail="Action non autorisée")
        
    # البحث عن التذكرة المطلوبة في السيرفر
    target_bet = None
    for bet in db_bets:
        if bet["betId"] == req.betId:
            target_bet = bet
            break
            
    if not target_bet:
        raise HTTPException(status_code=404, detail="Ticket non trouvé")
        
    if target_bet["status"] != "En cours":
        raise HTTPException(status_code=400, detail="Ce ticket هو مصفى ومحسوم مسبقاً")
        
    # تحديث حالة التذكرة
    target_bet["status"] = req.newStatus
    player_name = target_bet["username"].lower()
    
    # إذا حدد الأدمن أن التذكرة رابحة (Gagné)، نقوم بإضافة الأرباح لمحفظة اللاعب الفخرية بالسيرفر
    if req.newStatus == "Gagné":
        win_amount = target_bet["potentialWin"]
        user_wallet[player_name] = user_wallet.get(player_name, 0) + win_amount
        
    return {
        "status": "success", 
        "message": f"Ticket {req.betId} marqué comme {req.newStatus}.",
        "updatedBet": target_bet
    }

@app.get("/")
async def root():
    return {"status": "Alpha Core API is running perfectly!"}
