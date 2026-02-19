import requests
import re
import os
from datetime import datetime
from dotenv import load_dotenv

# Завантажуємо API ключ з .env
load_dotenv()
OCR_API_KEY = os.getenv("OCR_API_KEY", "K83107144588957")


def extract_date_from_image(image_path: str):
    """
    Відправляє фото на OCR.space API та витягує дату за допомогою Regex.
    """
    url = 'https://api.ocr.space/parse/image'

    print(f"Відправляємо фото {image_path} на розпізнавання...")

    # Відкриваємо файл і готуємо запит
    try:
        with open(image_path, 'rb') as f:
            payload = {
                'apikey': OCR_API_KEY,
                'language': 'ukr',  # Підтримка української
                'OCREngine': '2',  # Engine 2 зазвичай краще читає цифри та чеки
                'scale': 'true'  # Автоматичний апскейл для кращого розпізнавання
            }
            files = {'file': f}

            response = requests.post(url, data=payload, files=files)
            result = response.json()
    except Exception as e:
        print(f"Помилка з'єднання з API: {e}")
        return None

    # Перевіряємо, чи немає помилок від самого API
    if result.get('IsErroredOnProcessing'):
        print(f"Помилка обробки на стороні API: {result.get('ErrorMessage')}")
        return None

    # Витягуємо весь розпізнаний текст
    parsed_results = result.get('ParsedResults', [])
    if not parsed_results:
        print("API не повернуло жодного тексту.")
        return None

    full_text = parsed_results[0].get('ParsedText', '')
    print(f"Знайдений текст: \n{full_text}\n")

    # --- ЛОГІКА REGEX ЗАЛИШАЄТЬСЯ НАШОЮ ---
    pattern_full = r'\b(\d{2})[./-](\d{2})[./-](\d{2,4})\b'
    pattern_short = r'\b(\d{2})[./-](\d{2})\b'

    found_dates = []

    # 1. Шукаємо повні дати
    matches_full = re.findall(pattern_full, full_text)
    for match in matches_full:
        day, month, year = match
        if len(year) == 2:
            year = f"20{year}"
        try:
            date_obj = datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d").date()
            found_dates.append(date_obj)
        except ValueError:
            pass

    # 2. Якщо повних немає, шукаємо короткі
    if not found_dates:
        matches_short = re.findall(pattern_short, full_text)
        current_year = datetime.now().year
        for match in matches_short:
            day, month = match
            try:
                date_obj = datetime.strptime(f"{current_year}-{month}-{day}", "%Y-%m-%d").date()
                found_dates.append(date_obj)
            except ValueError:
                pass

    # 3. Повертаємо найпізнішу дату
    if found_dates:
        final_date = max(found_dates)
        print(f"Витягнута дата: {final_date}")
        return final_date

    return None