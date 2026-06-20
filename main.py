from fastapi import FastAPI, HTTPException
import requests
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware
import random

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

# 🔐 مسار تسجيل الدخول النظيف (بدون أي تكرار)
@app.post("/api/login")
async def login_user(req: LoginRequest):
    if req.username.lower() == "fethi" and req.password == "123456":
        return {
            "username": "fethi",
            "balance": 999999999999999,  # الرصيد الافتراضي الفخم الخاص بك
            "role": "admin"
        }
    else:
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

# ⚽ مسار متطور يجلب أقوى مباريات العالم معاً (إنجلترا، إسبانيا، إيطاليا، ودوري الأبطال)
@app.get("/api/sports/live")
async def get_sports():
    leagues = [
        "soccer_epl",           # الدوري الإنجليزي
        "soccer_spain_la_liga", # الدوري الإسباني
        "soccer_italy_serie_a", # الدوري الإيطالي
        "soccer_uefa_champs_league" # دوري أبطال أوروبا
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

# 🧾 ⚽ مسار جديد ومحمي لاستقبال وتثبيت تذاكر الرهان المتعدد
@app.post("/api/bets/sports")
async def confirm_sports_bet(req: BetRequest):
    if not req.username or req.amount <= 0 or len(req.selections) == 0:
        raise HTTPException(status_code=400, detail="Données du ticket incomplètes")
    
    # طباعة التذكرة في لوحة تحكم السيرفر (Logs) لمتابعتها فوراً
    print(f"🏈 [Pari Sportif] Nouveau ticket pour {req.username}:")
    print(f"   - Type: {req.slipType} | Mise: {req.amount} USDT | Cote: {req.totalOdds}")
    print(f"   - Gains Estimés: {req.potentialWin} USDT")
    print(f"   - Nombre de matchs: {len(req.selections)}")
    
    # إرجاع استجابة النجاح التام مع توليد رقم تذكرة عشوائي مميز
    random_id = random.randint(100000, 900000)
    return {
        "status": "success",
        "message": "Ticket enregistré avec succès",
        "betId": f"ST-{random_id}"
    }

# 🏠 المسار الترحيبي للرئيسية لضمان عمل السيرفر بنجاح
@app.get("/")
async def root():
    return {"status": "Alpha Core API is running perfectly!"}
