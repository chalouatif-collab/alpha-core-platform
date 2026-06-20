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

# قاعدة بيانات مؤقتة في ذاكرة السيرفر لحفظ التذاكر
db_bets = []

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

# 🔐 مسار تسجيل الدخول النظيف
@app.post("/api/login")
async def login_user(req: LoginRequest):
    if req.username.lower() == "fethi" and req.password == "123456":
        return {
            "username": "fethi",
            "balance": 999999999999999,
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
    
    random_id = f"ST-{random.randint(100000, 900000)}"
    
    # تجهيز التذكرة بالكامل مع الوقت والتاريخ وحالة الرهان الافتراضية
    new_bet = {
        "betId": random_id,
        "username": req.username,
        "slipType": req.slipType,
        "amount": req.amount,
        "totalOdds": req.totalOdds,
        "potentialWin": req.potentialWin,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "En cours", # الحالات الممكنة: En cours, Gagné, Perdu
        "selections": [item.dict() for item in req.selections]
    }
    
    # حفظ التذكرة في قائمة السيرفر
    db_bets.append(new_bet)
    return {"status": "success", "message": "Ticket enregistré", "betId": random_id}

# 📑 مسار جلب سجل التذاكر الخاص بكل لاعب
@app.get("/api/bets/history/{username}")
async def get_bet_history(username: str):
    # فلترة التذاكر لتعود فقط بالتذاكر الخاصة باللاعب المطلوب
    user_bets = [bet for bet in db_bets if bet["username"].lower() == username.lower()]
    return user_bets[::-1] # إرجاع التذاكر من الأحدث إلى الأقدم

@app.get("/")
async def root():
    return {"status": "Alpha Core API is running perfectly!"}
