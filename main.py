from fastapi import FastAPI, HTTPException
import requests
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

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
    # قائمة بأقوى البطولات العالمية المتاحة في الـ API
    leagues = [
        "soccer_epl",           # الدوري الإنجليزي
        "soccer_spain_la_liga", # الدوري الإسباني
        "soccer_italy_serie_a", # الدوري الإيطالي
        "soccer_uefa_champs_league" # دوري أبطال أوروبا
    ]
    
    all_matches = []
    
    # جلب البيانات من كل دوري ودمجها في قائمة واحدة
    for league in leagues:
        url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={API_KEY}&regions=eu&markets=h2h"
        try:
            response = requests.get(url)
            if response.status_code == 200:
                all_matches.extend(response.json())
        except Exception as e:
            print(f"Error fetching {league}: {str(e)}")
            
    return all_matches

# 🏠 المسار الترحيبي للرئيسية لضمان عمل السيرفر بنجاح
@app.get("/")
async def root():
    return {"status": "Alpha Core API is running perfectly!"}
