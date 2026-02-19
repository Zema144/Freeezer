import os
import shutil
import asyncio
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, Depends
from fastapi.middleware.cors import CORSMiddleware

from database import SessionLocal, Product
from ocr import extract_date_from_image

# --- ІМПОРТИ ДЛЯ БОТА ---
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()

# Налаштування бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://твоє-посилання.netlify.app")  # Заміни на своє Netlify посилання

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def cmd_start(message: Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Відкрити холодильник 🧊", web_app=WebAppInfo(url=WEB_APP_URL))]
    ])
    await message.answer("Привіт! Я слідкую за нашим холодильником. Натисни кнопку нижче.", reply_markup=markup)


# --- ІНТЕГРАЦІЯ БОТА І FASTAPI ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Цей код виконується при старті сервера
    print("Запускаємо Телеграм-бота...")
    asyncio.create_task(dp.start_polling(bot))
    yield
    # Цей код виконується при вимкненні сервера
    print("Зупиняємо бота...")


# Ініціалізуємо FastAPI з lifespan
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- ЕНДПОІНТ ДЛЯ ДОДАВАННЯ ПРОДУКТУ ---
@app.post("/api/upload/")
async def upload_product(
        product_name: str = Form(...),
        user_id: str = Form(...),
        manual_date: Optional[str] = Form(None),
        photo: Optional[UploadFile] = File(None),
        db: SessionLocal = Depends(get_db)
):
    final_date_obj = None
    date_status_msg = "Очікує обробки"

    if manual_date:
        try:
            final_date_obj = datetime.strptime(manual_date, "%Y-%m-%d").date()
            date_status_msg = f"Вказана вручну: {final_date_obj.strftime('%d.%m.%Y')}"
        except ValueError:
            return {"status": "error", "message": "Неправильний формат ручної дати."}

    elif photo and photo.filename:
        file_path = os.path.join(UPLOAD_DIR, photo.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)

        extracted_date = extract_date_from_image(file_path)

        if extracted_date:
            final_date_obj = extracted_date
            date_status_msg = f"Розпізнано з фото: {final_date_obj.strftime('%d.%m.%Y')}"
        else:
            date_status_msg = "Не вдалося знайти дату на фото"
    else:
        return {"status": "error", "message": "Потрібно надати фото або вказати дату."}

    new_product = Product(name=product_name, user_id=user_id, expiry_date=final_date_obj)
    db.add(new_product)
    db.commit()

    return {"status": "success", "message": "Продукт успішно оброблено!", "date_status": date_status_msg}


# --- НОВІ ЕНДПОІНТИ ДЛЯ СПИСКУ ТА ВИДАЛЕННЯ ---

@app.get("/api/products/")
def get_active_products(db: SessionLocal = Depends(get_db)):
    """Повертає всі продукти, які ще є в холодильнику (статус active)"""
    products = db.query(Product).filter(Product.status == "active").all()
    return products


@app.post("/api/products/{product_id}/consume")
def consume_product(product_id: int, db: SessionLocal = Depends(get_db)):
    """Позначає продукт як з'їдений (змінює статус на consumed)"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        product.status = "consumed"
        db.commit()
        return {"status": "success", "message": "Продукт видалено з холодильника"}
    return {"status": "error", "message": "Продукт не знайдено"}