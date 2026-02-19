import requests
import re
import os
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image  # Додали бібліотеку для роботи з фотографіями

# Завантажуємо API ключ з .env
load_dotenv()
OCR_API_KEY = os.getenv("OCR_API_KEY", "ТВІЙ_КЛЮЧ_ТУТ")


def compress_image_if_needed(image_path, max_size_kb=950):
    """
    Перевіряє розмір файлу. Якщо він більший за max_size_kb,
    стискає зображення, щоб воно пройшло ліміти API.
    """
    file_size_kb = os.path.getsize(image_path) / 1024
    if file_size_kb <= max_size_kb:
        return image_path  # Розмір нормальний, нічого не робимо

    print(f"Файл завеликий ({file_size_kb:.2f} KB). Починаємо стиснення...")
    try:
        with Image.open(image_path) as img:
            # Переводимо в RGB (якщо фото раптом має прозорість/альфа-канал)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Зменшуємо роздільну здатність до макс 1600х1600 (зберігаючи пропорції)
            img.thumbnail((1600, 1600))

            # Перезберігаємо поверх старого файлу з оптимізацією
            img.save(image_path, "JPEG", quality=75, optimize=True)

        new_size = os.path.getsize(image_path) / 1024
        print(f"Стиснення успішне! Новий розмір: {new_size:.2f} KB")
    except Exception as e:
        print(f"Помилка під час стиснення: {e}")

    return image_path


def extract_date_from_image(image_path: str):
    """
    Стискає фото, відправляє на OCR.space API та витягує дату Regex-ом.
    """
    # 1. СТИСКАЄМО ФОТО ПЕРЕД ВІДПРАВКОЮ
    compress_image_if_needed(image_path)

    url = 'https://api.ocr.space/parse/image'
    print(f"Відправляємо фото {image_path} на розпізнавання...")

    try:
        with open(image_path, 'rb') as f:
            payload = {
                'apikey': OCR_API_KEY,
                'language': 'auto',
                'OCREngine': '2',
                'scale': 'true'
            }
            files = {'file': f}

            response = requests.post(url, data=payload, files=files)
            result = response.json()
    except Exception as e:
        print(f"Помилка з'єднання з API: {e}")
        return None

    if result.get('IsErroredOnProcessing'):
        print(f"Помилка обробки на стороні API: {result.get('ErrorMessage')}")
        return None

    parsed_results = result.get('ParsedResults', [])
    if not parsed_results:
        print("API не повернуло жодного тексту.")
        return None

    full_text = parsed_results[0].get('ParsedText', '')
    print(f"Знайдений текст: \n{full_text}\n")

    # --- РОЗУМНА ЛОГІКА REGEX ---
    pattern_full = r'(?<!\d)(\d{2})\s*[./,-]\s*(\d{2})\s*[./,-]\s*(\d{2,4})(?!\d)'
    pattern_short = r'(?<!\d)(\d{2})\s*[./,-]\s*(\d{2})(?!\d)'

    found_dates = []

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

    if found_dates:
        final_date = max(found_dates)
        print(f"Витягнута дата: {final_date}")
        return final_date

    return None